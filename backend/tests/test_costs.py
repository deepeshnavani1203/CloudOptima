import pytest
from pydantic import ValidationError

from app.schemas import CostRequest
from app.services.costs import calculate_costs


def request(**overrides):
    values = {
        "current_hourly_cost": 0.1,
        "target_hourly_cost": 0.05,
        "duration_hours": 100,
        "transfer_cost": 5,
        "migration_overhead": 2,
        "other_costs": 3,
        "minimum_savings_percent": 20,
        "current_provider": "AWS",
        "target_provider": "GCP",
    }
    values.update(overrides)
    return CostRequest(**values)


def test_cost_breakdown_and_savings_percentage():
    result = calculate_costs(request())
    assert result["current_cost"] == 10
    assert result["target_compute_cost"] == 5
    assert result["target_total_cost"] == 15
    assert result["net_savings"] == -5
    assert result["savings_percent"] == -50
    assert result["break_even_hours"] == 200
    assert not result["meets_savings_threshold"]


def test_break_even_is_not_reported_when_hourly_cost_does_not_drop():
    assert calculate_costs(request(target_hourly_cost=0.1))["break_even_hours"] is None


def test_zero_current_total_has_zero_percentage_without_division_error():
    result = calculate_costs(request(current_hourly_cost=0, target_hourly_cost=0))
    assert result["savings_percent"] == 0
    assert result["break_even_hours"] is None


@pytest.mark.parametrize("field,value", [("duration_hours", 0), ("transfer_cost", -1), ("current_hourly_cost", -1)])
def test_cost_request_rejects_invalid_inputs(field, value):
    with pytest.raises(ValidationError):
        request(**{field: value})
