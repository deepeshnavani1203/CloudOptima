import asyncio
import math
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx

from app.adapters.pricing_common import ProviderRequestError
from app.config import settings

PRICES_URL = "https://prices.azure.com/api/retail/prices"
MAX_PAGES = 5


def _hourly_unit(unit: str) -> bool:
    normalized = " ".join(unit.strip().lower().split())
    return normalized in {"1 hour", "hour", "hours", "1 h", "h"}


def _parse_datetime(value) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed


def _pricing_type(item: dict) -> tuple[str, str]:
    price_type = str(item.get("type", "")).strip().lower()
    if price_type == "spot":
        return "Spot", "Azure Retail Prices API type is Spot."
    if price_type == "consumption":
        return "OnDemand", "Azure Retail Prices API type is Consumption; this is not Spot pricing."
    return "Unclassified", "Azure Retail Prices API did not identify a supported pricing type."


def _is_vm(item: dict) -> bool:
    service = str(item.get("serviceName", "")).lower()
    product = str(item.get("productName", "")).lower()
    meter = str(item.get("meterName", "")).lower()
    if not ("virtual machine" in service or "virtual machine" in product or "virtual machines" in product):
        return False
    sku = str(item.get("armSkuName") or item.get("skuName") or "").lower()
    sku_family = sku.removeprefix("standard_").removeprefix("basic_")[:1]
    return (
        any(token in meter for token in ("compute", "instance", "spot", "vcpu"))
        or bool(sku_family and meter.lstrip().startswith(sku_family))
    )


def _safe_next_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "prices.azure.com":
        raise ProviderRequestError("Azure returned an invalid pagination URL.")
    return url


async def fetch_azure_prices(region: str | None = None) -> tuple[list[dict], datetime, list[str]]:
    if not settings.azure_pricing_enabled:
        raise ProviderRequestError("Azure Retail Prices integration is disabled.")

    fetched_at = datetime.now(timezone.utc)
    records = []
    warnings = []
    completed_queries = 0
    async with httpx.AsyncClient(timeout=httpx.Timeout(15)) as client:
        for price_type in ("Consumption", "Spot"):
            try:
                filters = [
                    "serviceName eq 'Virtual Machines'",
                    f"priceType eq '{price_type}'",
                ]
                if region:
                    filters.append(f"armRegionName eq '{region}'")
                params = {"$filter": " and ".join(filters)}
                url = PRICES_URL
                for page in range(MAX_PAGES):
                    payload = await _get_json(client, url, params if page == 0 else None)
                    if not isinstance(payload, dict) or not isinstance(payload.get("Items", []), list):
                        raise ProviderRequestError("Azure returned an incomplete retail pricing response.")

                    for item in payload.get("Items", []):
                        if not isinstance(item, dict):
                            continue
                        if not _is_vm(item):
                            continue
                        classified_type, evidence = _pricing_type(item)
                        expected_type = "Spot" if price_type == "Spot" else "OnDemand"
                        unit = str(item.get("unitOfMeasure") or "")
                        currency = str(item.get("currencyCode") or "UNK").upper()
                        raw_price = item.get("retailPrice")
                        effective_raw = item.get("effectiveStartDate")
                        effective_at = _parse_datetime(effective_raw)
                        try:
                            native_price = float(raw_price) if raw_price is not None else None
                        except (TypeError, ValueError):
                            native_price = None
                        if native_price is not None and (not math.isfinite(native_price) or native_price < 0):
                            native_price = None
                        valid_price = (
                            native_price is not None
                            and _hourly_unit(unit)
                            and currency == "USD"
                            and classified_type == expected_type
                            and (effective_raw is None or (effective_at is not None and effective_at <= fetched_at))
                        )
                        if valid_price:
                            price_evidence = evidence
                        elif effective_raw is not None and (effective_at is None or effective_at > fetched_at):
                            price_evidence = "Provider price is not effective yet or its effective date is invalid."
                        elif currency == "UNK":
                            price_evidence = "Provider catalog did not return a currency for this price."
                        elif currency != "USD":
                            price_evidence = "Only USD catalog prices are currently comparable; no currency conversion is applied."
                        elif not _hourly_unit(unit):
                            price_evidence = "Meter unit is not a directly supported hourly unit."
                        else:
                            price_evidence = "No non-negative, verified hourly retail price is available for this meter."
                        records.append({
                            "provider": "Azure",
                            "region": str(item.get("armRegionName") or "unknown"),
                            "instance_type": str(item.get("armSkuName") or item.get("skuName") or item.get("meterName") or "Virtual Machine SKU"),
                            "vcpu": None,
                            "memory_gb": None,
                            "hourly_price": native_price if valid_price else None,
                            "currency": currency,
                            "pricing_type": classified_type,
                            "source": "Azure Retail Prices API",
                            "observed_at": fetched_at,
                            "freshness": "fresh",
                            "availability_evidence": "Public retail catalog listing; regional capacity is not verified.",
                            "interruption_risk": "high" if classified_type == "Spot" else "unknown",
                            "sku_id": item.get("skuId"),
                            "arm_sku_name": item.get("armSkuName"),
                            "meter_id": item.get("meterId"),
                            "service_id": item.get("serviceId"),
                            "product_id": item.get("productId"),
                            "meter_name": item.get("meterName"),
                            "pricing_model_status": "unclassified" if classified_type == "Unclassified" else "verified",
                            "pricing_evidence": price_evidence,
                            "native_price": native_price,
                            "native_unit": unit or None,
                            "effective_at": effective_at,
                            "fetched_at": fetched_at,
                            "source_url": PRICES_URL,
                            "specifications_complete": False,
                        })
                    next_url = payload.get("NextPageLink")
                    if not next_url:
                        break
                    url = _safe_next_url(str(next_url))
                completed_queries += 1
            except ProviderRequestError as error:
                warnings.append(f"{price_type} pricing query: {error}")
    if not completed_queries:
        raise ProviderRequestError("; ".join(warnings))
    return records, fetched_at, warnings


async def _get_json(client: httpx.AsyncClient, url: str, params: dict | None = None) -> dict:
    last_status = None
    for attempt in range(2):
        try:
            response = await client.get(url, params=params)
            last_status = response.status_code
            if (response.status_code == 429 or response.status_code >= 500) and attempt == 0:
                await asyncio.sleep(0.25)
                continue
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict):
                raise ProviderRequestError("Azure returned an invalid retail pricing response.")
            return data
        except httpx.TimeoutException as error:
            if attempt == 0:
                await asyncio.sleep(0.25)
                continue
            raise ProviderRequestError("Azure Retail Prices request timed out.") from error
        except httpx.HTTPStatusError as error:
            status = error.response.status_code
            if status == 429:
                raise ProviderRequestError("Azure Retail Prices rate limit was reached.", status) from error
            raise ProviderRequestError(f"Azure Retail Prices request failed (HTTP {status}).", status) from error
        except (ValueError, httpx.RequestError) as error:
            if attempt == 0 and isinstance(error, httpx.RequestError):
                await asyncio.sleep(0.25)
                continue
            raise ProviderRequestError("Azure Retail Prices response could not be processed.", last_status) from error
    raise ProviderRequestError("Azure Retail Prices request failed.", last_status)
