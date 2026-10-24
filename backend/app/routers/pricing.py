from typing import Literal

from fastapi import APIRouter, Query

from app.db import store
from app.services.pricing import pricing_service

router = APIRouter(prefix="/api/pricing", tags=["pricing"])


@router.get("")
async def get_pricing(
    provider: Literal["GCP", "Azure"] | None = None,
    region: str | None = Query(default=None, min_length=1, max_length=80),
    pricing_model: Literal["Spot", "OnDemand", "Unclassified"] | None = None,
    search: str | None = Query(default=None, min_length=1, max_length=100),
    freshness: Literal["fresh", "stale"] | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0, le=10000),
):
    return await pricing_service.list_records(
        provider=provider,
        region=region,
        pricing_model=pricing_model,
        search=search,
        freshness=freshness,
        limit=limit,
        offset=offset,
    )


@router.post("/refresh")
async def refresh_pricing(
    region: str | None = Query(default=None, min_length=2, max_length=40, pattern=r"^[A-Za-z0-9-]+$"),
):
    result = await pricing_service.refresh(azure_region=region)
    history = await pricing_service.list_records(limit=500)
    result["items"] = history["items"]
    result["total"] = history["total"]
    await store.insert(
        "audit_logs",
        f"pricing-refresh:{result['fetched_at'].isoformat()}",
        {
            "resource_id": "pricing",
            "action": "pricing_refresh",
            "created_at": result["fetched_at"],
            "providers_attempted": result["providers_attempted"],
            "records_normalized": result["records_normalized"],
            "errors": result["errors"],
        },
    )
    return result


@router.get("/status")
async def pricing_status():
    return await pricing_service.get_status()
