from datetime import datetime, timezone

from fastapi import APIRouter

from app.db import store
from app.schemas import CostRequest
from app.services.costs import calculate_costs

router = APIRouter(prefix="/api/cost", tags=["cost analysis"])


@router.post("/calculate")
async def cost_calculate(request: CostRequest):
    result = calculate_costs(request)
    result["created_at"] = datetime.now(timezone.utc)
    result["mode"] = "demo"
    await store.insert("cost_analyses", result["created_at"].isoformat(), result)
    return result
