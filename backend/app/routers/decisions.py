from fastapi import APIRouter

from app.db import store
from app.schemas import DecisionExplanationRequest, DecisionRequest
from app.services.decisions import recommend
from app.services.explanations import explain_decision
from app.services.pricing import normalize_price

router = APIRouter(prefix="/api/decisions", tags=["decisions"])


@router.post("/recommend")
async def decision_recommend(request: DecisionRequest):
    records = await store.list("pricing_snapshots", limit=1000)
    prices = [normalize_price(record) for record in records]
    result = recommend(request, prices)
    evaluated_at = result["evaluated_at"]
    result["evaluated_at"] = evaluated_at.isoformat()
    result["mode"] = "live_catalog" if prices else "unavailable"
    result["persistence"] = {"status": store.status, "mode": store.mode}
    document = {
        **result,
        "inputs": request.model_dump(mode="json"),
        "created_at": evaluated_at,
    }
    await store.insert("decision_analyses", evaluated_at.isoformat(), document)
    await store.insert("audit_logs", f"decision:{result['evaluated_at']}", {
        "resource_id": "decision",
        "action": "recommend",
        "created_at": evaluated_at,
        "recommended_provider": result["recommended_provider"],
    })
    return result


@router.post("/explain")
async def decision_explain(request: DecisionExplanationRequest):
    return await explain_decision(request)
