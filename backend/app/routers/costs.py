from datetime import datetime, timezone
from math import isclose

from fastapi import APIRouter, HTTPException

from app.db import store
from app.schemas import CostExplanationRequest, CostRequest
from app.services.costs import calculate_costs
from app.services.explanations import explain_cost
from app.services.pricing import is_fresh, normalize_price

router = APIRouter(prefix="/api/cost", tags=["cost analysis"])


@router.post("/calculate")
async def cost_calculate(request: CostRequest):
    snapshot_ids = []
    if request.pricing_snapshot_id:
        snapshot = await store.get_by_id("pricing_snapshots", request.pricing_snapshot_id)
        if not snapshot:
            raise HTTPException(status_code=422, detail="Selected pricing snapshot is not available.")
        price = normalize_price(snapshot)
        if (
            price.provider != request.target_provider
            or price.currency != "USD"
            or price.hourly_price is None
            or price.pricing_model_status != "verified"
            or not is_fresh(price.observed_at)
            or not isclose(price.hourly_price, request.target_hourly_cost, rel_tol=1e-9, abs_tol=1e-12)
        ):
            raise HTTPException(
                status_code=422,
                detail="Selected pricing snapshot is stale or does not match the target provider and hourly price.",
            )
        snapshot_ids.append(request.pricing_snapshot_id)
    result = calculate_costs(request)
    result["created_at"] = datetime.now(timezone.utc)
    result["mode"] = "estimate"
    result["persistence"] = {"status": store.status, "mode": store.mode}
    result["pricing_snapshot_ids"] = snapshot_ids
    result["inputs"] = request.model_dump(mode="json")
    document = dict(result)
    await store.insert("cost_analyses", result["created_at"].isoformat(), document)
    await store.insert("audit_logs", f"cost:{result['created_at'].isoformat()}", {
        "resource_id": "cost-analysis",
        "action": "cost_analysis_created",
        "created_at": result["created_at"],
    })
    return result


@router.post("/explain")
async def cost_explain(request: CostExplanationRequest):
    return await explain_cost(request)
