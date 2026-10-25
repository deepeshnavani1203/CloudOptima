from fastapi import APIRouter

from app.config import settings
from app.db import store
from app.services.pricing import pricing_service

router = APIRouter(prefix="/api", tags=["health and settings"])


@router.get("/health")
async def health():
    pricing_status = await pricing_service.get_status()
    return {
        "status": "ok",
        "mode": "demo" if settings.demo_mode else "live_catalog",
        "live_integrations_enabled": any(
            provider["enabled"] for provider in pricing_status["providers"].values()
        ),
        "database": {
            "status": store.status,
            "persistence": store.mode,
            "connection_error": store.connection_error,
        },
        "integrations": {
            "gcp_pricing": pricing_status["providers"]["GCP"]["status"],
            "azure_pricing": pricing_status["providers"]["Azure"]["status"],
            "groq_explanations": "configured" if settings.groq_api_key else "not_configured",
            "cloud_provisioning": "disabled",
            "dns": "mock" if settings.dns_adapter == "mock" else "disabled",
        },
    }


@router.get("/settings/status")
async def settings_status():
    result = await health()
    result["pricing"] = await pricing_service.get_status()
    return result
