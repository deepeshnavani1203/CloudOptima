from fastapi import APIRouter

from app.db import store
from app.schemas import DecisionRequest
from app.services.decisions import recommend

router = APIRouter(prefix="/api/decisions", tags=["decisions"])


@router.post("/recommend")
async def decision_recommend(request: DecisionRequest):
    result = recommend(request, [])
    evaluated_at = result["evaluated_at"]
    result["evaluated_at"] = evaluated_at.isoformat()
    await store.insert("audit_logs", f"decision:{result['evaluated_at']}", {
        "resource_id": "decision",
        "action": "recommend",
        "created_at": evaluated_at,
        "recommended_provider": result["recommended_provider"],
    })
    return result
