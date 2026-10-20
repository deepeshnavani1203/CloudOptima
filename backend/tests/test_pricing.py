from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.services.pricing import is_fresh, normalize_price


def test_normalize_price_adds_default_currency():
    record = {
        "provider": "AWS",
        "region": "test-region",
        "instance_type": "test-instance",
        "vcpu": 2,
        "memory_gb": 8,
        "hourly_price": 0.1,
        "pricing_type": "Spot",
        "source": "test fixture",
        "observed_at": datetime.now(timezone.utc),
        "freshness": "fresh",
        "availability_evidence": "test only",
        "interruption_risk": "unknown",
    }
    normalized = normalize_price(record)
    assert normalized.currency == "USD"
    assert normalized.provider == "AWS"


def test_normalize_price_rejects_negative_hourly_price():
    record = {
        "provider": "AWS",
        "region": "test-region",
        "instance_type": "test-instance",
        "vcpu": 2,
        "memory_gb": 8,
        "hourly_price": -0.01,
        "pricing_type": "Spot",
        "source": "test fixture",
        "observed_at": datetime.now(timezone.utc),
        "freshness": "fresh",
        "availability_evidence": "test only",
        "interruption_risk": "unknown",
    }
    with pytest.raises(ValidationError):
        normalize_price(record)


def test_pricing_freshness_uses_24_hour_window_and_rejects_future():
    now = datetime.now(timezone.utc)
    assert is_fresh(now - timedelta(hours=23), now)
    assert not is_fresh(now - timedelta(hours=25), now)
    assert not is_fresh(now + timedelta(minutes=1), now)
