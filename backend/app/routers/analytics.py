from fastapi import APIRouter

from app.db import store

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/savings")
async def analytics_savings():
    analyses = await store.list("cost_analyses")
    decisions = await store.list("decision_analyses")
    migrations = await store.list("migrations")
    snapshots = await store.list("pricing_snapshots")
    return {
        "items": analyses,
        "decision_items": decisions,
        "pricing_snapshots": snapshots[:100],
        "migration_counts": {
            "completed": sum(item.get("state") == "COMPLETED" for item in migrations),
            "failed": sum(item.get("state") == "FAILED" for item in migrations),
        },
        "persistence": store.mode,
        "note": "History includes only records saved in the current persistence mode; memory-only records are lost when the API stops.",
    }
