import asyncio
from types import SimpleNamespace

import httpx
import pytest
from fastapi import HTTPException

from app.schemas import CostExplanationRequest, DecisionExplanationRequest
from app.services import explanations


class FakeResponse:
    def __init__(self, status_code, body):
        self.status_code = status_code
        self._body = body

    def json(self):
        return self._body


def decision_request():
    return DecisionExplanationRequest(
        recommended_provider="GCP",
        reason="No candidate passed all requirements.",
        estimated_net_savings=None,
        candidates=[],
        rejected_candidates=[{
            "provider": "Azure",
            "eligible": False,
            "reason": "Verified machine specifications are unavailable.",
        }],
        limitations=["Retail prices are estimates."],
    )


def cost_request():
    return CostExplanationRequest(
        current_provider="GCP",
        target_provider="Azure",
        current_hourly_cost=0.12,
        target_hourly_cost=0.8,
        duration_hours=720,
        current_cost=86.4,
        target_compute_cost=576,
        transfer_cost=5,
        migration_overhead=2,
        other_costs=0,
        target_total_cost=583,
        net_savings=-496.6,
        savings_percent=-574.77,
        break_even_hours=None,
        minimum_savings_percent=10,
        meets_savings_threshold=False,
        missing_cost_categories=["Taxes and negotiated discounts"],
    )


def test_explain_decision_calls_groq_with_bounded_decision_data(monkeypatch):
    calls = []

    class FakeAsyncClient:
        def __init__(self, timeout):
            assert timeout.connect == 20

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, url, headers, json):
            calls.append((url, headers, json))
            return FakeResponse(200, {
                "choices": [{"message": {"content": "The rules engine kept the current provider."}}],
            })

    monkeypatch.setattr(explanations, "settings", SimpleNamespace(
        groq_api_key="test-key",
        groq_model="test-model",
    ))
    monkeypatch.setattr(explanations.httpx, "AsyncClient", FakeAsyncClient)

    result = asyncio.run(explanations.explain_decision(decision_request()))

    assert result == {
        "explanation": "The rules engine kept the current provider.",
        "model": "test-model",
    }
    assert calls[0][0] == explanations.GROQ_CHAT_COMPLETIONS_URL
    assert calls[0][1] == {"Authorization": "Bearer test-key"}
    assert calls[0][2]["model"] == "test-model"
    assert "not change" in calls[0][2]["messages"][0]["content"].lower()
    assert "No candidate passed all requirements." in calls[0][2]["messages"][1]["content"]


def test_explain_cost_calls_groq_and_emphasizes_negative_savings(monkeypatch):
    calls = []

    class FakeAsyncClient:
        def __init__(self, timeout):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, url, headers, json):
            calls.append(json)
            return FakeResponse(200, {
                "choices": [{"message": {"content": "The target estimate is higher."}}],
            })

    monkeypatch.setattr(explanations, "settings", SimpleNamespace(
        groq_api_key="test-key",
        groq_model="test-model",
    ))
    monkeypatch.setattr(explanations.httpx, "AsyncClient", FakeAsyncClient)

    result = asyncio.run(explanations.explain_cost(cost_request()))

    assert result["explanation"] == "The target estimate is higher."
    assert "negative" in calls[0]["messages"][0]["content"].lower()
    assert "-496.6" in calls[0]["messages"][1]["content"]
    assert "583" in calls[0]["messages"][1]["content"]


def test_explain_decision_reports_missing_key(monkeypatch):
    monkeypatch.setattr(explanations, "settings", SimpleNamespace(
        groq_api_key=None,
        groq_model="test-model",
    ))

    with pytest.raises(HTTPException) as error:
        asyncio.run(explanations.explain_decision(decision_request()))

    assert error.value.status_code == 503


def test_explain_decision_surfaces_groq_http_failure(monkeypatch):
    class FakeAsyncClient:
        def __init__(self, timeout):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, *_args, **_kwargs):
            return FakeResponse(429, {})

    monkeypatch.setattr(explanations, "settings", SimpleNamespace(
        groq_api_key="test-key",
        groq_model="test-model",
    ))
    monkeypatch.setattr(explanations.httpx, "AsyncClient", FakeAsyncClient)

    with pytest.raises(HTTPException) as error:
        asyncio.run(explanations.explain_decision(decision_request()))

    assert error.value.status_code == 502
    assert "HTTP 429" in error.value.detail
