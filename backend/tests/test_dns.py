import asyncio

import pytest
from fastapi import HTTPException

from app.adapters.dns import MockDnsAdapter


def test_mock_dns_adapter_only_simulates_valid_healthy_endpoint():
    result = asyncio.run(MockDnsAdapter().switch("https://service.example.com", True))
    assert result["status"] == "simulated"
    assert "propagation" in result["message"]


@pytest.mark.parametrize(("endpoint", "healthy", "status_code"), [
    ("service.example.com", True, 422),
    ("https://service.example.com", False, 409),
])
def test_mock_dns_adapter_rejects_bad_endpoint_or_unhealthy_target(endpoint, healthy, status_code):
    with pytest.raises(HTTPException) as error:
        asyncio.run(MockDnsAdapter().switch(endpoint, healthy))
    assert error.value.status_code == status_code
