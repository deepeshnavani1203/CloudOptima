import math
from datetime import datetime, timezone

import httpx

from app.adapters.pricing_common import ProviderRequestError
from app.config import settings

SERVICES_URL = "https://cloudbilling.googleapis.com/v1/services"
SOURCE_URL = "https://cloudbilling.googleapis.com/v1/services/{service_id}/skus"
MAX_SERVICE_PAGES = 3
MAX_SKU_PAGES_PER_SERVICE = 4
PAGE_SIZE = 500
MAX_RECORDS = 2000


def _money(value: dict) -> float | None:
    if not isinstance(value, dict):
        return None
    units = value.get("units", "0")
    nanos = value.get("nanos", 0)
    try:
        amount = float(units) + float(nanos) / 1_000_000_000
    except (TypeError, ValueError):
        return None
    return amount if amount >= 0 and math.isfinite(amount) else None


def _parse_datetime(value) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed


def _hourly_rate(expression: dict) -> tuple[float | None, str | None]:
    if not isinstance(expression, dict):
        return None, None
    usage_unit = str(expression.get("usageUnit", "")).strip().lower()
    if usage_unit not in {"h", "hour", "hours", "1 hour", "instance-hour"}:
        return None, None
    tiers = [tier for tier in (expression.get("tieredRates") or []) if isinstance(tier, dict)]
    first_tier = None
    for tier in tiers:
        try:
            starts_at_zero = float(tier.get("startUsageAmount", 0) or 0) == 0
        except (TypeError, ValueError):
            starts_at_zero = False
        if starts_at_zero:
            first_tier = tier
            break
    if not first_tier:
        return None, usage_unit
    unit = str(first_tier.get("unit", "")).strip().lower()
    if unit not in {"h", "hour", "hours", "1 hour", "instance-hour"}:
        return None, unit or usage_unit
    return _money(first_tier.get("unitPrice") or {}), unit


def _pricing_type(sku: dict) -> tuple[str, str]:
    category = sku.get("category") or {}
    if not isinstance(category, dict):
        category = {}
    usage_type = str(category.get("usageType", "")).upper()
    description = str(sku.get("description", "")).lower()
    if usage_type == "PREEMPTIBLE" or "preemptible" in description or "spot" in description:
        return "Spot", "Catalog usage type or SKU description explicitly identifies Spot/preemptible pricing."
    if usage_type == "STANDARD":
        return "OnDemand", "Catalog usage type identifies standard pricing; not a Spot price."
    return "Unclassified", "Catalog fields do not reliably identify the pricing model."


def _is_compute_vm_sku(sku: dict) -> bool:
    description = str(sku.get("description", "")).lower()
    category = sku.get("category") or {}
    if not isinstance(category, dict):
        category = {}
    resource_family = str(category.get("resourceFamily", "")).lower()
    return (
        resource_family == "compute"
        and any(word in description for word in ("instance", "machine", "vm"))
        and not any(word in description for word in ("license", "commitment", "sole tenancy"))
    )


def _is_complete_instance_price(sku: dict, unit: str | None) -> bool:
    description = str(sku.get("description", "")).lower()
    return (
        unit in {"h", "hour", "hours", "1 hour", "instance-hour"}
        and "instance" in description
        and not any(word in description for word in ("core", "vcpu", "ram", "memory", "gpu"))
    )


async def _get_json(client: httpx.AsyncClient, url: str, params: dict | None = None) -> dict:
    last_status = None
    for attempt in range(2):
        try:
            response = await client.get(url, params=params)
            last_status = response.status_code
            if response.status_code == 429 or response.status_code >= 500:
                if attempt == 0:
                    await asyncio.sleep(0.25)
                    continue
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict):
                raise ProviderRequestError("GCP returned an invalid catalog response.")
            return data
        except httpx.TimeoutException as error:
            if attempt == 0:
                await asyncio.sleep(0.25)
                continue
            raise ProviderRequestError("GCP catalog request timed out.") from error
        except httpx.HTTPStatusError as error:
            status = error.response.status_code
            if status in {401, 403}:
                raise ProviderRequestError("GCP catalog authentication or access was rejected.", status) from error
            if status == 429:
                raise ProviderRequestError("GCP catalog rate limit was reached.", status) from error
            raise ProviderRequestError(f"GCP catalog request failed (HTTP {status}).", status) from error
        except (ValueError, httpx.RequestError) as error:
            if attempt == 0 and isinstance(error, httpx.RequestError):
                await asyncio.sleep(0.25)
                continue
            raise ProviderRequestError("GCP catalog response could not be processed.", last_status) from error
    raise ProviderRequestError("GCP catalog request failed.", last_status)


async def fetch_gcp_prices() -> tuple[list[dict], datetime]:
    if not settings.gcp_billing_api_key:
        raise ProviderRequestError("GCP Billing Catalog API key is not configured.")

    fetched_at = datetime.now(timezone.utc)
    records = []
    headers = {"X-Goog-Api-Key": settings.gcp_billing_api_key}
    async with httpx.AsyncClient(timeout=httpx.Timeout(15), headers=headers) as client:
        services = []
        page_token = None
        for _ in range(MAX_SERVICE_PAGES):
            payload = await _get_json(
                client,
                SERVICES_URL,
                {"pageSize": PAGE_SIZE, **({"pageToken": page_token} if page_token else {})},
            )
            if not isinstance(payload.get("services", []), list):
                raise ProviderRequestError("GCP returned an incomplete services response.")
            services.extend(
                service for service in payload.get("services", [])
                if isinstance(service, dict)
                and service.get("serviceId")
                and "compute engine" in str(service.get("displayName", "")).lower()
            )
            page_token = payload.get("nextPageToken")
            if not page_token:
                break

        for service in services:
            page_token = None
            for _ in range(MAX_SKU_PAGES_PER_SERVICE):
                payload = await _get_json(
                    client,
                    SOURCE_URL.format(service_id=service["serviceId"]),
                    {"pageSize": PAGE_SIZE, **({"pageToken": page_token} if page_token else {})},
                )
                if not isinstance(payload.get("skus", []), list):
                    raise ProviderRequestError("GCP returned an incomplete SKU response.")
                for sku in payload.get("skus", []):
                    if not isinstance(sku, dict):
                        continue
                    if not _is_compute_vm_sku(sku):
                        continue
                    pricing_type, evidence = _pricing_type(sku)
                    pricing_info = sku.get("pricingInfo") or []
                    if not isinstance(pricing_info, list):
                        pricing_info = []
                    pricing_info = [item for item in pricing_info if isinstance(item, dict)]
                    dated_info = [
                        (effective_at, item)
                        for item in pricing_info
                        if (effective_at := _parse_datetime(item.get("effectiveTime"))) is not None
                    ]
                    current_info = [pair for pair in dated_info if pair[0] <= fetched_at]
                    info = (
                        max(current_info, key=lambda pair: pair[0])[1]
                        if current_info
                        else {} if dated_info else next(iter(pricing_info), {})
                    )
                    expression = info.get("pricingExpression") or {}
                    if not isinstance(expression, dict):
                        expression = {}
                    rate, native_unit = _hourly_rate(expression)
                    tiers = [tier for tier in (expression.get("tieredRates") or []) if isinstance(tier, dict)]
                    price = (
                        rate
                        if len(tiers) == 1 and _is_complete_instance_price(sku, native_unit)
                        else None
                    )
                    currency = "UNK"
                    if tiers:
                        unit_price = tiers[0].get("unitPrice") or {}
                        currency = str(unit_price.get("currencyCode") or "UNK").upper()
                    if currency != "USD":
                        price = None
                    if price is not None:
                        price_evidence = evidence
                    elif currency == "UNK":
                        price_evidence = "Provider catalog did not return a currency for this price."
                    elif currency != "USD":
                        price_evidence = "Only USD catalog prices are currently comparable; no currency conversion is applied."
                    elif len(tiers) > 1:
                        price_evidence = "Multiple tiered rates cannot be represented as one instance-hour price."
                    elif not _is_complete_instance_price(sku, native_unit):
                        price_evidence = "This SKU does not provide a complete VM instance-hour price."
                    else:
                        price_evidence = "The catalog does not provide a directly comparable hourly price."
                    regions = sku.get("serviceRegions") or ["unknown"]
                    for region in regions:
                        records.append({
                            "provider": "GCP",
                            "region": region,
                            "instance_type": str(sku.get("description") or sku.get("skuId") or "Compute SKU"),
                            "vcpu": None,
                            "memory_gb": None,
                            "hourly_price": price,
                            "currency": currency,
                            "pricing_type": pricing_type,
                            "source": "Google Cloud Billing Catalog API",
                            "observed_at": fetched_at,
                            "freshness": "fresh",
                            "availability_evidence": "Public catalog listing; regional capacity is not verified.",
                            "interruption_risk": "high" if pricing_type == "Spot" else "unknown",
                            "sku_id": sku.get("skuId"),
                            "service_id": service.get("serviceId"),
                            "product_id": service.get("displayName"),
                            "pricing_model_status": "unclassified" if pricing_type == "Unclassified" else "verified",
                            "pricing_evidence": price_evidence,
                            "native_price": rate,
                            "native_unit": native_unit or expression.get("usageUnit"),
                            "effective_at": info.get("effectiveTime"),
                            "fetched_at": fetched_at,
                            "source_url": SOURCE_URL.format(service_id=service["serviceId"]),
                            "specifications_complete": False,
                        })
                        if len(records) >= MAX_RECORDS:
                            break
                    if len(records) >= MAX_RECORDS:
                        break
                page_token = payload.get("nextPageToken")
                if not page_token or len(records) >= MAX_RECORDS:
                    break
            if len(records) >= MAX_RECORDS:
                break
    return records, fetched_at
