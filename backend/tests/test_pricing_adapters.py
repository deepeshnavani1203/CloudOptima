import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.adapters import azure_pricing, gcp_pricing
from app.adapters.pricing_common import ProviderRequestError


class Response:
    def __init__(self, payload, status_code=200, headers=None):
        self.payload = payload
        self.status_code = status_code
        self.headers = headers or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            import httpx

            request = httpx.Request("GET", "https://provider.example")
            response = httpx.Response(self.status_code, request=request)
            raise httpx.HTTPStatusError("request failed", request=request, response=response)

    def json(self):
        return self.payload


class FakeAsyncClient:
    payloads = []
    calls = []

    def __init__(self, **_kwargs):
        self.pages = iter(self.payloads)
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def get(self, url, params=None):
        self.calls.append((url, params))
        FakeAsyncClient.calls.append((url, params))
        return next(self.pages)


def gcp_sku(sku_id, usage_type, description):
    return {
        "skuId": sku_id,
        "description": description,
        "category": {"resourceFamily": "Compute", "usageType": usage_type},
        "serviceRegions": ["us-east1"],
        "pricingInfo": [{
            "effectiveTime": "2026-10-01T00:00:00Z",
            "pricingExpression": {
                "usageUnit": "h",
                "tieredRates": [{
                    "startUsageAmount": 0,
                    "unitPrice": {"currencyCode": "USD", "units": "0", "nanos": 200000000},
                }],
            },
        }],
    }


def test_gcp_catalog_paginates_services_and_skus_and_classifies_prices(monkeypatch):
    monkeypatch.setattr(gcp_pricing, "settings", SimpleNamespace(gcp_billing_api_key="test-only-key"))
    FakeAsyncClient.calls = []
    FakeAsyncClient.payloads = [
        Response({"services": [{"serviceId": "svc-one", "displayName": "Compute Engine"}], "nextPageToken": "services-next"}),
        Response({"services": [{"serviceId": "svc-two", "displayName": "Compute Engine"}]}),
        Response({"skus": [gcp_sku("sku-standard", "STANDARD", "N2 VM instance hourly")], "nextPageToken": "skus-next"}),
        Response({"skus": [gcp_sku("sku-spot", "PREEMPTIBLE", "N2 Spot VM instance hourly")]}),
        Response({"skus": []}),
    ]
    monkeypatch.setattr(gcp_pricing.httpx, "AsyncClient", FakeAsyncClient)

    records, fetched_at = asyncio.run(gcp_pricing.fetch_gcp_prices())

    assert len(records) == 2
    assert {record["pricing_type"] for record in records} == {"OnDemand", "Spot"}
    assert all(record["hourly_price"] == pytest.approx(0.2) for record in records)
    assert all(record["currency"] == "USD" for record in records)
    assert all(record["sku_id"] for record in records)
    assert all(record["specifications_complete"] is False for record in records)
    assert all(record["native_price"] == pytest.approx(0.2) for record in records)
    assert datetime.fromisoformat(records[0]["effective_at"]).tzinfo == timezone.utc
    assert fetched_at.tzinfo == timezone.utc
    assert any(params and params.get("pageToken") == "services-next" for _, params in FakeAsyncClient.calls)
    assert any(params and params.get("pageToken") == "skus-next" for _, params in FakeAsyncClient.calls)


def test_gcp_hourly_parser_rejects_monthly_units_and_handles_money():
    assert gcp_pricing._money({"units": "1", "nanos": 250000000}) == pytest.approx(1.25)
    assert gcp_pricing._hourly_rate({
        "usageUnit": "mo",
        "tieredRates": [{"startUsageAmount": 0, "unit": "mo", "unitPrice": {"units": "5"}}],
    }) == (None, None)
    assert gcp_pricing._pricing_type({
        "description": "standard virtual machine",
        "category": {"usageType": "PREEMPTIBLE"},
    })[0] == "Spot"
    assert gcp_pricing._pricing_type({
        "description": "compute instance",
        "category": {"usageType": "UNKNOWN"},
    })[0] == "Unclassified"
    assert gcp_pricing._pricing_type({
        "description": "E2 Instance Core",
        "category": {"usageType": "OnDemand"},
    })[0] == "OnDemand"
    assert gcp_pricing._hourly_rate({
        "usageUnit": "h",
        "tieredRates": [
            {"startUsageAmount": 0, "unit": "h", "unitPrice": {"units": "1"}},
            {"startUsageAmount": 100, "unit": "h", "unitPrice": {"units": "0.5"}},
        ],
    })[0] == 1
    memory_rate, memory_unit = gcp_pricing._hourly_rate({
        "usageUnit": "GiBy.h",
        "tieredRates": [{
            "startUsageAmount": 0,
            "unitPrice": {"currencyCode": "USD", "units": "0", "nanos": 1398000},
        }],
    })
    assert memory_rate == pytest.approx(0.001398)
    assert memory_unit == "giby.h"


def test_gcp_does_not_flatten_multiple_hourly_tiers_into_one_price(monkeypatch):
    monkeypatch.setattr(gcp_pricing, "settings", SimpleNamespace(gcp_billing_api_key="test-only-key"))
    sku = gcp_sku("sku-tiered", "STANDARD", "N2 VM instance hourly")
    sku["pricingInfo"][0]["pricingExpression"]["tieredRates"].append({
        "startUsageAmount": 100,
        "unit": "h",
        "unitPrice": {"currencyCode": "USD", "units": "0", "nanos": 100000000},
    })
    FakeAsyncClient.payloads = [
        Response({"services": [{"serviceId": "svc-one", "displayName": "Compute Engine"}]}),
        Response({"skus": [sku]}),
    ]
    monkeypatch.setattr(gcp_pricing.httpx, "AsyncClient", FakeAsyncClient)

    records, _ = asyncio.run(gcp_pricing.fetch_gcp_prices())

    assert records[0]["native_price"] == pytest.approx(0.2)
    assert records[0]["hourly_price"] is None
    assert "Multiple tiered rates" in records[0]["pricing_evidence"]


def test_azure_catalog_follows_next_page_and_uses_returned_type_and_currency(monkeypatch):
    monkeypatch.setattr(azure_pricing, "settings", SimpleNamespace(azure_pricing_enabled=True))
    FakeAsyncClient.calls = []
    FakeAsyncClient.payloads = [
        Response({
            "Items": [{
                "serviceName": "Virtual Machines",
                "productName": "Virtual Machines D2 Series",
                "armSkuName": "Standard_D2s_v5",
                "skuId": "azure-sku-1",
                "meterId": "azure-meter-1",
                "meterName": "D2s v5/D2s v5",
                "armRegionName": "eastus",
                "type": "Consumption",
                "unitOfMeasure": "1 Hour",
                "currencyCode": "USD",
                "retailPrice": 0.096,
                "effectiveStartDate": "2026-01-01T00:00:00Z",
            }, {
                "serviceName": "Virtual Machines",
                "productName": "Virtual Machines D2 Series",
                "armSkuName": "Standard_D2s_v5",
                "skuId": "azure-spot-sku",
                "meterId": "azure-spot-meter",
                "meterName": "D2s v5 Spot",
                "armRegionName": "eastus",
                "type": "DevTestConsumption",
                "unitOfMeasure": "1 Hour",
                "currencyCode": "USD",
                "retailPrice": 0.03,
            }],
            "NextPageLink": "https://prices.azure.com/api/retail/prices?$skip=100",
        }),
        Response({
            "Items": [{
                "serviceName": "Virtual Machines",
                "productName": "Virtual Machines D2 Series",
                "armSkuName": "Standard_D2s_v5",
                "skuId": "azure-sku-3",
                "meterId": "azure-meter-3",
                "meterName": "D2s v5",
                "armRegionName": "eastus",
                "type": "Consumption",
                "unitOfMeasure": "1 Month",
                "currencyCode": "EUR",
                "retailPrice": 20,
            }],
            "NextPageLink": "https://prices.azure.com/api/retail/prices?$skip=200",
        }),
    ]
    monkeypatch.setattr(azure_pricing.httpx, "AsyncClient", FakeAsyncClient)

    records, fetched_at, warnings = asyncio.run(azure_pricing.fetch_azure_prices("eastus"))

    assert len(records) == 3
    assert records[0]["pricing_type"] == "OnDemand"
    assert records[0]["hourly_price"] == pytest.approx(0.096)
    assert records[1]["pricing_type"] == "Spot"
    assert records[1]["hourly_price"] == pytest.approx(0.03)
    assert records[2]["hourly_price"] is None
    assert records[2]["currency"] == "EUR"
    assert all(record["vcpu"] is None and record["memory_gb"] is None for record in records)
    assert records[0]["meter_name"] == "D2s v5/D2s v5"
    assert records[0]["sku_id"] == "azure-sku-1"
    assert records[0]["meter_id"] == "azure-meter-1"
    assert records[0]["effective_at"].tzinfo == timezone.utc
    assert fetched_at.tzinfo == timezone.utc
    assert len(warnings) == 1
    assert "capped at" in warnings[0]
    assert "priceType eq 'Consumption'" in FakeAsyncClient.calls[0][1]["$filter"]
    assert "priceType eq 'Spot'" not in FakeAsyncClient.calls[0][1]["$filter"]
    assert FakeAsyncClient.calls[0][1]["$filter"].endswith("armRegionName eq 'eastus'")
    assert FakeAsyncClient.calls[0][1]["api-version"] == azure_pricing.API_VERSION
    assert "meterRegion" not in FakeAsyncClient.calls[0][1]
    assert FakeAsyncClient.calls[1][0].startswith("https://prices.azure.com/")
    assert len(FakeAsyncClient.calls) == azure_pricing.MAX_PAGES
    assert any("capped at" in warning for warning in warnings)


def test_azure_rate_limit_is_not_retried(monkeypatch):
    monkeypatch.setattr(azure_pricing, "settings", SimpleNamespace(azure_pricing_enabled=True))
    FakeAsyncClient.calls = []
    FakeAsyncClient.payloads = [
        Response({}, status_code=429, headers={"Retry-After": "120"}),
        Response({"Items": []}),
    ]
    monkeypatch.setattr(azure_pricing.httpx, "AsyncClient", FakeAsyncClient)

    with pytest.raises(ProviderRequestError, match="120 seconds") as error:
        asyncio.run(azure_pricing.fetch_azure_prices("eastus"))

    assert error.value.status_code == 429
    assert error.value.retry_after_seconds == 120
    assert len(FakeAsyncClient.calls) == 1


def test_azure_model_and_hourly_detection_require_provider_fields():
    assert azure_pricing._pricing_type({"type": "Spot"})[0] == "Spot"
    assert azure_pricing._pricing_type({
        "type": "DevTestConsumption",
        "meterName": "F16s Spot",
    })[0] == "Spot"
    assert azure_pricing._pricing_type({
        "type": "DevTestConsumption",
        "meterName": "F16s",
    })[0] == "Unclassified"
    assert azure_pricing._pricing_type({"type": "Consumption"})[0] == "OnDemand"
    assert azure_pricing._pricing_type({"type": "Reservation"})[0] == "Unclassified"
    assert azure_pricing._hourly_unit("1 Hour")
    assert not azure_pricing._hourly_unit("1 Month")


def test_azure_requires_region_to_avoid_unbounded_catalog_query(monkeypatch):
    monkeypatch.setattr(azure_pricing, "settings", SimpleNamespace(azure_pricing_enabled=True))

    with pytest.raises(ProviderRequestError, match="Enter an Azure region"):
        asyncio.run(azure_pricing.fetch_azure_prices())
