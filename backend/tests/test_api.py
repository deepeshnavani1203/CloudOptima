from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.db import store
from app.config import settings
from app.main import app
from app.services import pricing


@pytest.fixture
def client(monkeypatch):
    async def connect():
        store.mode = "memory"
        store.status = "unavailable"
        store._memory.clear()

    async def close():
        return None

    async def mock_gcp_prices():
        return [], datetime.now(timezone.utc)

    async def mock_azure_prices(region=None):
        return [], datetime.now(timezone.utc), []

    monkeypatch.setattr(store, "connect", connect)
    monkeypatch.setattr(store, "close", close)
    monkeypatch.setattr(pricing, "fetch_gcp_prices", mock_gcp_prices)
    monkeypatch.setattr(pricing, "fetch_azure_prices", mock_azure_prices)
    pricing.pricing_service._cache.clear()
    pricing.pricing_service._last_success = {"GCP": None, "Azure": None}
    pricing.pricing_service._last_attempt = {"GCP": None, "Azure": None}
    pricing.pricing_service._provider_status.clear()
    with TestClient(app) as test_client:
        yield test_client


def test_health_and_pricing_report_provider_status_without_exposing_credentials(client):
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["mode"] == "demo"
    assert health.json()["database"]["persistence"] == "memory"
    pricing = client.get("/api/pricing").json()
    assert pricing["mode"] == "demo"
    assert "No pricing data" in pricing["warnings"][0]
    assert pricing["items"] == []
    refreshed = client.post("/api/pricing/refresh").json()
    assert refreshed["items"] == []
    assert refreshed["providers_attempted"] == ["GCP", "Azure"]
    assert refreshed["persistence"]["mode"] == "memory"
    status = client.get("/api/pricing/status").json()
    assert set(status["providers"]) == {"GCP", "Azure"}
    assert "GCP_BILLING_API_KEY" not in str(status)


def test_preflight_allows_configured_frontend_origin(client):
    response = client.options("/api/health", headers={
        "Origin": settings.frontend_origin,
        "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "content-type",
    })

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == settings.frontend_origin


def test_cost_endpoint_validates_and_returns_full_breakdown(client):
    response = client.post("/api/cost/calculate", json={
        "current_provider": "AWS",
        "target_provider": "GCP",
        "current_hourly_cost": 0.1,
        "target_hourly_cost": 0.05,
        "duration_hours": 100,
        "transfer_cost": 2,
        "migration_overhead": 1,
        "other_costs": 0,
        "minimum_savings_percent": 5,
    })
    assert response.status_code == 200
    assert response.json()["target_total_cost"] == 8
    assert response.json()["net_savings"] == 2
    assert response.json()["break_even_hours"] == 60
    assert client.post("/api/cost/calculate", json={
        "current_provider": "AWS",
        "target_provider": "GCP",
        "current_hourly_cost": 1,
        "target_hourly_cost": 1,
        "duration_hours": 0,
    }).status_code == 422


def test_cost_analysis_validates_and_saves_catalog_snapshot_reference(client):
    now = datetime.now(timezone.utc)
    snapshot_id = "test-pricing-snapshot"
    store._memory["pricing_snapshots"][snapshot_id] = {
        "snapshot_id": snapshot_id,
        "provider": "GCP",
        "region": "us-east1",
        "instance_type": "test instance",
        "vcpu": 2,
        "memory_gb": 8,
        "hourly_price": 0.05,
        "currency": "USD",
        "pricing_type": "OnDemand",
        "pricing_model_status": "verified",
        "pricing_evidence": "test fixture",
        "source": "catalog test fixture",
        "observed_at": now,
        "fetched_at": now,
        "freshness": "fresh",
        "availability_evidence": "test fixture",
        "interruption_risk": "unknown",
        "specifications_complete": True,
        "created_at": now,
    }
    response = client.post("/api/cost/calculate", json={
        "current_provider": "Azure",
        "target_provider": "GCP",
        "current_hourly_cost": 0.1,
        "target_hourly_cost": 0.05,
        "duration_hours": 100,
        "pricing_snapshot_id": snapshot_id,
    })
    assert response.status_code == 200
    assert response.json()["pricing_snapshot_ids"] == [snapshot_id]


def test_migration_api_enforces_simulation_and_health_gate(client):
    created = client.post("/api/migrations", json={
        "source_provider": "AWS",
        "target_provider": "GCP",
        "simulation": True,
    })
    assert created.status_code == 201
    migration_id = created.json()["migration_id"]
    assert created.json()["simulation"] is True
    assert client.post("/api/migrations", json={
        "source_provider": "AWS",
        "target_provider": "GCP",
        "simulation": False,
    }).status_code == 403

    for _ in range(3):
        result = client.post(f"/api/migrations/{migration_id}/advance", json={})
        assert result.status_code == 200
    failed = client.post(f"/api/migrations/{migration_id}/advance", json={"health_check_passed": False})
    assert failed.status_code == 200
    assert failed.json()["state"] == "FAILED"
    assert failed.json()["source_workload_active"] is True


def test_recommendation_stays_put_without_prices_and_not_found_migration(client):
    response = client.post("/api/decisions/recommend", json={
        "current_provider": "AWS",
        "duration_hours": 720,
        "current_hourly_cost": 0.1,
        "required_vcpu": 2,
        "required_memory_gb": 8,
        "transfer_cost": 1,
        "migration_overhead": 1,
        "minimum_savings_percent": 10,
        "region": "us-east-1",
    })
    assert response.status_code == 200
    assert response.json()["recommended_provider"] == "AWS"
    assert response.json()["estimated_net_savings"] is None
    assert response.json()["candidates"] == []
    assert client.get("/api/migrations/missing").status_code == 404


def test_decision_endpoint_loads_validated_snapshots_and_saves_references(client):
    now = datetime.now(timezone.utc)
    snapshot_id = "decision-snapshot"
    store._memory["pricing_snapshots"][snapshot_id] = {
        "snapshot_id": snapshot_id,
        "provider": "Azure",
        "region": "eastus",
        "instance_type": "Standard_D2s_v5",
        "vcpu": 2,
        "memory_gb": 8,
        "hourly_price": 0.03,
        "currency": "USD",
        "pricing_type": "OnDemand",
        "pricing_model_status": "verified",
        "pricing_evidence": "test fixture",
        "source": "catalog test fixture",
        "observed_at": now,
        "fetched_at": now,
        "freshness": "fresh",
        "availability_evidence": "test fixture",
        "interruption_risk": "unknown",
        "specifications_complete": True,
        "created_at": now,
    }
    response = client.post("/api/decisions/recommend", json={
        "current_provider": "GCP",
        "duration_hours": 720,
        "current_hourly_cost": 0.1,
        "required_vcpu": 2,
        "required_memory_gb": 8,
        "minimum_savings_percent": 10,
        "region": "us-east-1",
        "pricing_type": "OnDemand",
    })
    assert response.status_code == 200
    body = response.json()
    assert body["recommended_provider"] == "Azure"
    assert body["candidates"][0]["pricing_snapshot_id"] == snapshot_id
