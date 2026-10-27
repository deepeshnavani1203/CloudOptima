from datetime import datetime

from fastapi import APIRouter, HTTPException

from app.config import settings
from app.db import store
from app.schemas import MigrationAdvance, MigrationCreate
from app.services.migrations import advance_migration, cancel_migration, new_migration

router = APIRouter(prefix="/api/migrations", tags=["migrations"])


def serialize(document: dict) -> dict:
    return {
        key: value.isoformat() if isinstance(value, datetime) else value
        for key, value in document.items()
    }


@router.post("", status_code=201)
async def create_migration(request: MigrationCreate):
    if not request.simulation or not settings.demo_mode:
        raise HTTPException(status_code=403, detail="Real cloud migrations are disabled; only explicit demo simulations are supported.")
    if request.source_provider == request.target_provider:
        raise HTTPException(status_code=422, detail="Source and target providers must differ.")
    migration = new_migration(
        request.source_provider,
        request.target_provider,
        request.workload_name,
        workflow_type=request.workflow_type,
    )
    await store.insert("migrations", migration["migration_id"], migration)
    await store.insert("audit_logs", f"migration:{migration['migration_id']}:created", {
        "resource_id": migration["migration_id"],
        "action": "simulation_created",
        "created_at": migration["created_at"],
    })
    return serialize(migration)


@router.get("")
async def list_migrations():
    return {"items": await store.list("migrations"), "persistence": store.mode}


@router.get("/{migration_id}")
async def get_migration(migration_id: str):
    migration = await store.get("migrations", migration_id)
    if not migration:
        raise HTTPException(status_code=404, detail="Migration not found.")
    return serialize(migration)


@router.post("/{migration_id}/advance")
async def advance(migration_id: str, request: MigrationAdvance):
    if request.confirm_live:
        raise HTTPException(status_code=403, detail="Live operations are disabled in this build.")
    migration = await store.get("migrations", migration_id)
    if not migration:
        raise HTTPException(status_code=404, detail="Migration not found.")
    updated = advance_migration(
        migration,
        request.health_check_passed,
        backup_confirmed=request.backup_confirmed,
        approval_confirmed=request.approval_confirmed,
        rollback_confirmed=request.rollback_confirmed,
    )
    await store.replace("migrations", migration_id, updated)
    await store.insert("audit_logs", f"migration:{migration_id}:{updated['updated_at'].isoformat()}", {
        "resource_id": migration_id,
        "action": "simulation_transition",
        "state": updated["state"],
        "created_at": updated["updated_at"],
    })
    return serialize(updated)


@router.post("/{migration_id}/cancel")
async def cancel(migration_id: str):
    migration = await store.get("migrations", migration_id)
    if not migration:
        raise HTTPException(status_code=404, detail="Migration not found.")
    updated = cancel_migration(migration)
    await store.replace("migrations", migration_id, updated)
    await store.insert("audit_logs", f"migration:{migration_id}:{updated['updated_at'].isoformat()}", {
        "resource_id": migration_id,
        "action": "simulation_cancelled",
        "created_at": updated["updated_at"],
    })
    return serialize(updated)
