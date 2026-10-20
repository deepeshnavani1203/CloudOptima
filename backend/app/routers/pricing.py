from fastapi import APIRouter

from app.db import store

router = APIRouter(prefix="/api/pricing", tags=["pricing"])


@router.get("")
async def get_pricing():
    return {
        "items": [],
        "mode": "demo",
        "source": "none",
        "persistence": store.mode,
        "warnings": ["No pricing data is available.", "Live provider pricing adapters are not configured."],
    }


@router.post("/refresh")
async def refresh_pricing():
    return {
        "items": [],
        "message": "No pricing adapters are configured. No provider API was queried.",
        "mode": "demo",
        "persistence": store.mode,
    }
