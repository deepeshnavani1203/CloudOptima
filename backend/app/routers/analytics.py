from fastapi import APIRouter

from app.db import store

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/savings")
async def analytics_savings():
    analyses = await store.list("cost_analyses")
    migrations = await store.list("migrations")
    return {
        "items": analyses,
        "migration_counts": {
            "completed": sum(item.get("state") == "COMPLETED" for item in migrations),
            "failed": sum(item.get("state") == "FAILED" for item in migrations),
        },
        "persistence": store.mode,
        "note": "Only API calculations saved in the current persistence mode are included.",
    }
