import asyncio
from collections import defaultdict
from datetime import datetime, timezone
from types import SimpleNamespace

from app.adapters.pricing_common import ProviderRequestError
from app.db import store
from app.services import pricing
from app.services.pricing import _interleave_providers


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


def test_azure_rate_limit_enters_cooldown_without_repeating_provider_request(monkeypatch):
    calls = 0

    async def azure_rate_limited(region=None):
        nonlocal calls
        calls += 1
        raise ProviderRequestError("Azure rate limit.", 429, 120)

    monkeypatch.setattr(pricing, "fetch_azure_prices", azure_rate_limited)
    monkeypatch.setattr(pricing, "settings", SimpleNamespace(
        azure_pricing_enabled=True,
        gcp_billing_api_key="configured",
        demo_mode=True,
    ))
    service = pricing.PricingService()

    first = asyncio.run(service._fetch_provider("Azure"))
    second = asyncio.run(service._fetch_provider("Azure"))

    assert first["error"] == "Azure rate limit."
    assert second["attempted"] is False
    assert "retry in about 119" in second["error"] or "retry in about 120" in second["error"]
    assert service.status()["providers"]["Azure"]["status"] == "rate_limited"
    assert calls == 1


def test_pricing_records_interleave_providers_before_pagination():
    records = [
        {"provider": "Azure", "sku_id": "azure-1"},
        {"provider": "Azure", "sku_id": "azure-2"},
        {"provider": "Azure", "sku_id": "azure-3"},
        {"provider": "GCP", "sku_id": "gcp-1"},
        {"provider": "GCP", "sku_id": "gcp-2"},
    ]

    result = _interleave_providers(records)

    assert [record["provider"] for record in result] == [
        "GCP", "Azure", "GCP", "Azure", "Azure"
    ]
