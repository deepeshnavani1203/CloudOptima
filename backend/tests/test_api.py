import pytest
from fastapi.testclient import TestClient

from app.db import store
from app.main import app


@pytest.fixture
def client(monkeypatch):
    async def connect():
        store.mode = "memory"
        store.status = "unavailable"
        store._memory.clear()

    async def close():
        return None

    monkeypatch.setattr(store, "connect", connect)
    monkeypatch.setattr(store, "close", close)
    with TestClient(app) as test_client:
        yield test_client


def test_health_and_pricing_report_unavailable_live_sources_without_fabricating_prices(client):
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
    assert "No pricing adapters" in refreshed["message"]


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
