from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException

MIGRATION_STATES = (
    "PENDING",
    "PROVISIONING",
    "DEPLOYING",
    "HEALTH_CHECK",
    "READY_TO_SWITCH",
    "SWITCHING_TRAFFIC",
    "VERIFYING",
    "COMPLETED",
)
TERMINAL_STATES = {"COMPLETED", "FAILED", "CANCELLED"}


def new_migration(source_provider: str, target_provider: str, workload_name: str) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "migration_id": str(uuid4()),
        "source_provider": source_provider,
        "target_provider": target_provider,
        "workload_name": workload_name,
        "simulation": True,
        "state": "PENDING",
        "created_at": now,
        "updated_at": now,
        "source_workload_active": True,
        "history": [{"state": "PENDING", "at": now, "message": "Simulation created; no cloud resources provisioned."}],
        "error": None,
    }


def advance_migration(migration: dict, health_check_passed: bool) -> dict:
    state = migration["state"]
    if state in TERMINAL_STATES:
        raise HTTPException(status_code=409, detail=f"Migration in state {state} cannot be advanced.")
    if state == "HEALTH_CHECK" and not health_check_passed:
        next_state = "FAILED"
        message = "Health check failed; source workload remains active."
        error = "Health check gate did not pass."
    else:
        next_state = MIGRATION_STATES[MIGRATION_STATES.index(state) + 1]
        message = "Simulated state transition; no cloud operation was executed."
        error = None

    now = datetime.now(timezone.utc)
    return {
        **migration,
        "state": next_state,
        "updated_at": now,
        "source_workload_active": next_state != "COMPLETED",
        "history": [*migration["history"], {"state": next_state, "at": now, "message": message}],
        "error": error,
    }


def cancel_migration(migration: dict) -> dict:
    if migration["state"] in TERMINAL_STATES:
        raise HTTPException(status_code=409, detail=f"Migration in state {migration['state']} cannot be cancelled.")
    now = datetime.now(timezone.utc)
    return {
        **migration,
        "state": "CANCELLED",
        "updated_at": now,
        "source_workload_active": True,
        "history": [*migration["history"], {"state": "CANCELLED", "at": now, "message": "Simulation cancelled; source remains active."}],
    }
