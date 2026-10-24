from dataclasses import replace

import pytest

from app.config import Settings, _boolean


@pytest.mark.parametrize(("value", "expected"), [
    ("true", True),
    ("1", True),
    ("false", False),
    ("off", False),
])
def test_boolean_environment_values_are_validated(monkeypatch, value, expected):
    monkeypatch.setenv("TEST_FLAG", value)
    assert _boolean("TEST_FLAG", not expected) is expected


def test_invalid_boolean_environment_value_is_rejected(monkeypatch):
    monkeypatch.setenv("TEST_FLAG", "sometimes")
    with pytest.raises(ValueError, match="TEST_FLAG"):
        _boolean("TEST_FLAG", False)


def test_settings_reject_invalid_frontend_origin_and_mongodb_scheme():
    with pytest.raises(ValueError, match="FRONTEND_ORIGIN"):
        replace(Settings(), frontend_origin="file:///tmp")
    with pytest.raises(ValueError, match="MONGODB_URI"):
        replace(Settings(), mongodb_uri="https://example.invalid")


def test_secret_values_are_not_in_settings_repr():
    configured = replace(Settings(), gcp_billing_api_key="test-secret-value")
    assert "test-secret-value" not in repr(configured)
