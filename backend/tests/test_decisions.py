from datetime import datetime, timezone

from app.schemas import DecisionRequest
from app.services.decisions import recommend
from app.schemas import PriceRecord


def decision(**overrides):
    values = {
        "current_provider": "AWS",
        "duration_hours": 720,
        "current_hourly_cost": 0.1,
        "required_vcpu": 2,
        "required_memory_gb": 8,
        "transfer_cost": 1,
        "migration_overhead": 1,
        "minimum_savings_percent": 10,
        "region": "us-east-1",
    }
    values.update(overrides)
    return DecisionRequest(**values)


def price(provider, region, hourly_price, freshness="fresh"):
    return PriceRecord(
        provider=provider,
        region=region,
        instance_type="test-instance",
        vcpu=2,
        memory_gb=8,
        hourly_price=hourly_price,
        pricing_type="Spot",
        source="test fixture",
        observed_at=datetime.now(timezone.utc),
        freshness=freshness,
        availability_evidence="test only",
        interruption_risk="unknown",
    )


def test_decision_selects_lowest_total_eligible_candidate():
    result = recommend(decision(), [price("GCP", "us-east1", 0.03), price("Azure", "eastus", 0.04)])
    assert result["recommended_provider"] == "GCP"
    assert result["candidates"][0]["provider"] == "GCP"
    assert result["candidates"][0]["total_cost"] < result["candidates"][1]["total_cost"]


def test_decision_stays_put_when_threshold_is_not_met():
    result = recommend(decision(current_hourly_cost=0.04, minimum_savings_percent=90), [price("GCP", "us-east1", 0.03)])
    assert result["recommended_provider"] == "AWS"
    assert result["estimated_net_savings"] == 0


def test_decision_rejects_stale_or_incompatible_candidates():
    prices = [price("GCP", "us-east1", 0.03, freshness="stale"), price("Azure", "eastus", 0.04)]
    result = recommend(decision(region="europe-west"), prices)
    assert result["recommended_provider"] == "AWS"
    assert len(result["rejected_candidates"]) == 2


def test_decision_does_not_invent_savings_when_no_provider_prices_exist():
    result = recommend(decision(), [])
    assert result["recommended_provider"] == "AWS"
    assert result["estimated_net_savings"] is None
    assert result["candidates"] == []
    assert "No pricing records" in result["reason"]
