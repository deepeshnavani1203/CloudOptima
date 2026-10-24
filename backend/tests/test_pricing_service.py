import asyncio
from collections import defaultdict
from datetime import datetime, timezone
from types import SimpleNamespace

from app.adapters.pricing_common import ProviderRequestError
from app.db import store
from app.services import pricing


def test_refresh_keeps_successful_provider_records_when_other_provider_fails(monkeypatch):
    now = datetime.now(timezone.utc)
    raw_record = {
        "provider": "GCP",
        "region": "us-east1",
        "instance_type": "Verified instance price",
        "vcpu": 2,
        "memory_gb": 8,
        "hourly_price": 0.1,
        "currency": "USD",
        "pricing_type": "OnDemand",
        "source": "catalog test fixture",
        "observed_at": now,
        "fetched_at": now,
        "freshness": "fresh",
        "availability_evidence": "test fixture",
        "interruption_risk": "unknown",
        "pricing_model_status": "verified",
        "specifications_complete": True,
    }

    async def gcp_success():
        return [raw_record], now

    async def azure_failure(region=None):
        raise ProviderRequestError("Azure catalog test failure.")

    monkeypatch.setattr(pricing, "fetch_gcp_prices", gcp_success)
    monkeypatch.setattr(pricing, "fetch_azure_prices", azure_failure)
    monkeypatch.setattr(pricing, "settings", SimpleNamespace(
        azure_pricing_enabled=True,
        gcp_billing_api_key="configured",
        demo_mode=True,
    ))
    monkeypatch.setattr(store, "mode", "memory")
    monkeypatch.setattr(store, "status", "unavailable")
    monkeypatch.setattr(store, "_memory", defaultdict(dict))
    service = pricing.PricingService()

    result = asyncio.run(service.refresh())

    assert result["providers"]["GCP"]["records_normalized"] == 1
    assert result["providers"]["GCP"]["verified_live_data"] is True
    assert result["providers"]["Azure"]["error"] == "Azure catalog test failure."
    assert result["items"][0]["provider"] == "GCP"
    assert result["records_persisted"] == 0
    assert result["persistence"] == {"status": "unavailable", "mode": "memory"}
    assert "GCP_BILLING_API_KEY" not in str(result)


def test_refresh_reports_partial_azure_query_failure(monkeypatch):
    now = datetime.now(timezone.utc)

    async def gcp_success():
        return [], now

    async def azure_partial(region=None):
        return [], now, ["Spot pricing query: request failed (HTTP 503)."]

    monkeypatch.setattr(pricing, "fetch_gcp_prices", gcp_success)
    monkeypatch.setattr(pricing, "fetch_azure_prices", azure_partial)
    monkeypatch.setattr(pricing, "settings", SimpleNamespace(
        azure_pricing_enabled=True,
        gcp_billing_api_key="configured",
        demo_mode=True,
    ))
    monkeypatch.setattr(store, "mode", "memory")
    monkeypatch.setattr(store, "status", "unavailable")
    monkeypatch.setattr(store, "_memory", defaultdict(dict))
    service = pricing.PricingService()

    result = asyncio.run(service.refresh())

    assert result["providers"]["Azure"]["warnings"] == [
        "Spot pricing query: request failed (HTTP 503)."
    ]
    assert result["providers"]["Azure"]["error"] is None
    assert result["providers"]["Azure"]["fetched_at"] == now
    assert any("Spot pricing query" in error for error in result["errors"])
