from fastapi import APIRouter

from app.db import store

router = APIRouter(prefix="/api", tags=["health and settings"])


@router.get("/health")
async def health():
    return {
        "status": "ok",
        "mode": "demo",
        "live_integrations_enabled": False,
        "database": {"status": store.status, "persistence": store.mode},
        "integrations": {
            "aws_pricing": "unavailable",
            "gcp_pricing": "unavailable",
            "azure_pricing": "unavailable",
            "cloud_provisioning": "disabled",
            "dns": "mock",
        },
    }


@router.get("/settings/status")
async def settings_status():
    return await health()
