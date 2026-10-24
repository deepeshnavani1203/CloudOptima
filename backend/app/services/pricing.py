import asyncio
import hashlib
import logging
from datetime import datetime, timedelta, timezone

from pydantic import ValidationError

from app.adapters.azure_pricing import fetch_azure_prices
from app.adapters.gcp_pricing import fetch_gcp_prices
from app.adapters.pricing_common import ProviderRequestError
from app.config import settings
from app.db import store
from app.schemas import PriceRecord

FRESHNESS_LIMIT = timedelta(hours=24)
CACHE_TTL = timedelta(minutes=30)
MAX_STORED_RECORDS = 1000
logger = logging.getLogger(__name__)


def normalize_price(record: dict) -> PriceRecord:
    normalized = dict(record)
    normalized.pop("_id", None)
    normalized.pop("created_at", None)
    normalized.setdefault("currency", "USD")
    return PriceRecord.model_validate(normalized)


def is_fresh(observed_at: datetime, now: datetime | None = None) -> bool:
    now = now or datetime.now(timezone.utc)
    now = now.replace(tzinfo=timezone.utc) if now.tzinfo is None else now
    timestamp = observed_at.replace(tzinfo=timezone.utc) if observed_at.tzinfo is None else observed_at
    return now - timestamp <= FRESHNESS_LIMIT and timestamp <= now


def _parse_time(value) -> datetime | None:
    if isinstance(value, datetime):
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed
        except ValueError:
            return None
    return None


class PricingService:
    def __init__(self):
        self._cache: dict[str, tuple[datetime, list[dict]]] = {}
        self._last_success: dict[str, datetime | None] = {"GCP": None, "Azure": None}
        self._last_attempt: dict[str, datetime | None] = {"GCP": None, "Azure": None}
        self._provider_status: dict[str, dict] = {}
        self._lock = asyncio.Lock()

    def status(self) -> dict:
        now = datetime.now(timezone.utc)
        return {
            "providers": {
                "GCP": {
                    "configured": bool(settings.gcp_billing_api_key),
                    "enabled": bool(settings.gcp_billing_api_key),
                    "status": self._provider_status.get("GCP", {}).get(
                        "status", "configured" if settings.gcp_billing_api_key else "not_configured"
                    ),
                    "last_attempt_at": self._last_attempt["GCP"],
                    "last_successful_fetch_at": self._last_success["GCP"],
                    "cached": any(key.startswith("GCP:") and value[0] > now for key, value in self._cache.items()),
                    "error": self._provider_status.get("GCP", {}).get("error"),
                    "warnings": self._provider_status.get("GCP", {}).get("warnings", []),
                },
                "Azure": {
                    "configured": True,
                    "enabled": settings.azure_pricing_enabled,
                    "status": self._provider_status.get("Azure", {}).get(
                        "status", "configured" if settings.azure_pricing_enabled else "disabled"
                    ),
                    "last_attempt_at": self._last_attempt["Azure"],
                    "last_successful_fetch_at": self._last_success["Azure"],
                    "cached": any(key.startswith("Azure:") and value[0] > now for key, value in self._cache.items()),
                    "error": self._provider_status.get("Azure", {}).get("error"),
                    "warnings": self._provider_status.get("Azure", {}).get("warnings", []),
                },
            },
            "persistence": {"status": store.status, "mode": store.mode},
        }

    async def _fetch_provider(self, provider: str, region: str | None = None) -> dict:
        now = datetime.now(timezone.utc)
        if provider == "GCP" and not settings.gcp_billing_api_key:
            message = "GCP Billing Catalog API key is not configured."
            self._provider_status[provider] = {"status": "not_configured", "error": message}
            return {"provider": provider, "records": [], "cached": False, "error": message, "attempted": False}
        if provider == "Azure" and not settings.azure_pricing_enabled:
            message = "Azure Retail Prices integration is disabled."
            self._provider_status[provider] = {"status": "disabled", "error": message}
            return {"provider": provider, "records": [], "cached": False, "error": message, "attempted": False}
        self._last_attempt[provider] = now
        cache_key = f"{provider}:{region or '*'}"
        cache = self._cache.get(cache_key)
        if cache and cache[0] > now:
            warnings = self._provider_status.get(provider, {}).get("warnings", [])
            self._provider_status[provider] = {"status": "cached", "error": None, "warnings": warnings}
            return {
                "provider": provider,
                "records": cache[1],
                "cached": True,
                "error": None,
                "warnings": warnings,
                "attempted": True,
            }

        try:
            if provider == "GCP":
                records, fetched_at = await fetch_gcp_prices()
                warnings = []
            else:
                records, fetched_at, warnings = await fetch_azure_prices(region=region)
            self._cache[cache_key] = (fetched_at + CACHE_TTL, records)
            self._last_success[provider] = fetched_at
            self._provider_status[provider] = {
                "status": "partial" if warnings else "connected",
                "error": None,
                "warnings": warnings,
            }
            return {
                "provider": provider,
                "records": records,
                "cached": False,
                "error": None,
                "warnings": warnings,
                "attempted": True,
            }
        except ProviderRequestError as error:
            self._provider_status[provider] = {"status": "error", "error": str(error), "warnings": []}
            return {"provider": provider, "records": [], "cached": False, "error": str(error), "warnings": [], "attempted": True}
        except (AttributeError, KeyError, TypeError, ValueError, OverflowError) as error:
            logger.warning("Provider catalog parsing failed for %s (%s)", provider, type(error).__name__)
            message = f"{provider} returned an incomplete or invalid catalog response."
            self._provider_status[provider] = {"status": "error", "error": message, "warnings": []}
            return {"provider": provider, "records": [], "cached": False, "error": message, "warnings": [], "attempted": True}

    async def refresh(self, azure_region: str | None = None) -> dict:
        async with self._lock:
            outcomes = await asyncio.gather(
                self._fetch_provider("GCP"),
                self._fetch_provider("Azure", azure_region),
            )
        providers = {}
        all_records = []
        validation_errors = []
        attempted = []
        for result in outcomes:
            provider = result["provider"]
            if result.get("attempted"):
                attempted.append(provider)
            normalized_records = []
            for raw_record in result["records"]:
                try:
                    record = normalize_price(raw_record)
                except ValidationError:
                    validation_errors.append(f"{provider}: a catalog record failed schema validation.")
                    continue
                normalized_records.append(record.model_dump(mode="python"))
            persisted = 0
            for record in (normalized_records if not result["cached"] else []):
                fetched_at = record.get("fetched_at") or record["observed_at"]
                identity = "|".join(str(record.get(key) or "") for key in (
                    "provider", "sku_id", "arm_sku_name", "meter_id", "region", "pricing_type",
                    "native_price", "native_unit",
                ))
                snapshot_id = hashlib.sha256(f"{identity}|{fetched_at.isoformat()}".encode()).hexdigest()
                document = {**record, "snapshot_id": snapshot_id, "created_at": fetched_at}
                await store.insert("pricing_snapshots", snapshot_id, document)
                persisted += 1
            unsupported = sum(
                record.get("hourly_price") is None or record.get("pricing_model_status") != "verified"
                for record in normalized_records
            )
            providers[provider] = {
                "records_retrieved": len(result["records"]),
                "records_normalized": len(normalized_records),
                "records_persisted": persisted if store.mode == "mongodb" else 0,
                "records_unsupported": unsupported,
                "cached": result["cached"],
                "error": result["error"],
                "warnings": result.get("warnings", []),
                "fetched_at": self._last_success.get(provider),
                "verified_live_data": any(
                    record.get("hourly_price") is not None
                    and record.get("pricing_model_status") == "verified"
                    for record in normalized_records
                ) and not result["cached"] and not result["error"],
                "attempted": result.get("attempted", False),
            }
            all_records.extend(normalized_records)

        return {
            "items": all_records[:MAX_STORED_RECORDS],
            "providers_attempted": attempted,
            "providers": providers,
            "records_retrieved": sum(item["records_retrieved"] for item in providers.values()),
            "records_normalized": sum(item["records_normalized"] for item in providers.values()),
            "records_persisted": sum(item["records_persisted"] for item in providers.values()),
            "records_unsupported": sum(item["records_unsupported"] for item in providers.values()),
            "errors": validation_errors + [
                f"{provider}: {result['error']}" for provider, result in providers.items() if result["error"]
            ] + [
                f"{provider}: {warning}"
                for provider, result in providers.items()
                for warning in result["warnings"]
            ],
            "fetched_at": datetime.now(timezone.utc),
            "persistence": {"status": store.status, "mode": store.mode},
            "mode": "demo" if settings.demo_mode else "live",
            "data_mode": "live_catalog" if any(item["verified_live_data"] for item in providers.values()) else "unavailable",
            "message": "Catalog refresh completed with partial provider results where available.",
        }

    async def list_records(
        self,
        provider: str | None = None,
        region: str | None = None,
        pricing_model: str | None = None,
        search: str | None = None,
        freshness: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict:
        records = await store.list("pricing_snapshots", limit=MAX_STORED_RECORDS)
        now = datetime.now(timezone.utc)
        filtered = []
        for raw in records:
            record = dict(raw)
            observed_at = _parse_time(record.get("observed_at"))
            if not observed_at:
                continue
            record["freshness"] = "fresh" if is_fresh(observed_at, now) else "stale"
            if provider and record.get("provider") != provider:
                continue
            if region and region.lower() not in str(record.get("region", "")).lower():
                continue
            if pricing_model and record.get("pricing_type", "").lower() != pricing_model.lower():
                continue
            if freshness and record.get("freshness") != freshness:
                continue
            if search and search.lower() not in " ".join(str(record.get(key) or "") for key in (
                "instance_type", "sku_id", "arm_sku_name", "meter_id", "service_id",
                "product_id", "meter_name", "region"
            )).lower():
                continue
            filtered.append(record)
        return {
            "items": filtered[offset:offset + limit],
            "total": len(filtered),
            "limit": limit,
            "offset": offset,
            "mode": "demo" if settings.demo_mode else "live",
            "data_mode": "live_catalog" if filtered else "unavailable",
            "source": "Google Cloud Billing Catalog API and Azure Retail Prices API",
            "persistence": {"status": store.status, "mode": store.mode},
            "status": self.status(),
            "warnings": (["No pricing data is currently available."] if not filtered else []) + [
                provider_status["error"] or warning
                for provider_status in self.status()["providers"].values()
                for warning in ([None] if provider_status.get("error") else provider_status.get("warnings", []))
                if provider_status.get("error") or warning
            ],
        }

    async def get_status(self) -> dict:
        result = self.status()
        records = await store.list("pricing_snapshots", limit=MAX_STORED_RECORDS)
        for provider, state in result["providers"].items():
            timestamps = [
                _parse_time(record.get("fetched_at") or record.get("observed_at"))
                for record in records if record.get("provider") == provider
            ]
            timestamps = [timestamp for timestamp in timestamps if timestamp]
            if timestamps and state["last_successful_fetch_at"] is None:
                state["last_successful_fetch_at"] = max(timestamps)
        return result


pricing_service = PricingService()
