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
    "ROLLING_BACK",
    "ROLLED_BACK",
)
TERMINAL_STATES = {"COMPLETED", "FAILED", "CANCELLED", "ROLLED_BACK"}


def new_migration(
    source_provider: str,
    target_provider: str,
    workload_name: str,
    workflow_type: str = "standard",
) -> dict:
    now = datetime.now(timezone.utc)
    initial_state = "PRICE_ALERT" if workflow_type == "spot" else "PENDING"
    return {
        "migration_id": str(uuid4()),
        "source_provider": source_provider,
        "target_provider": target_provider,
        "workload_name": workload_name,
        "workflow_type": workflow_type,
        "simulation": True,
        "state": initial_state,
        "created_at": now,
        "updated_at": now,
        "source_workload_active": True,
        "history": [{
            "state": initial_state,
            "at": now,
            "message": (
                "SIMULATED: Price alert scenario created from selected inputs; no live alert or cloud operation."
                if workflow_type == "spot"
                else "SIMULATED: Migration created; no cloud resources provisioned."
            ),
        }],
        "safety_checks": [],
        "error": None,
    }


def advance_migration(
    migration: dict,
    health_check_passed: bool,
    backup_confirmed: bool = False,
    approval_confirmed: bool = False,
    rollback_confirmed: bool = False,
) -> dict:
    state = migration["state"]
    if state in TERMINAL_STATES:
        raise HTTPException(status_code=409, detail=f"Migration in state {state} cannot be advanced.")

    now = datetime.now(timezone.utc)
    checks = list(migration.get("safety_checks", []))
    if migration.get("workflow_type") == "spot":
        transitions = {
            "PRICE_ALERT": ("TARGET_SELECTION", "SIMULATED: Price alert acknowledged; no live alert was detected."),
            "TARGET_SELECTION": ("BACKUP_CONFIRMATION", "SIMULATED: Target selected; no provider capacity was reserved."),
            "BACKUP_CONFIRMATION": ("HEALTH_CHECK", "SIMULATED: Backup confirmation recorded; no backup was created."),
            "APPROVAL_GATE": ("SIMULATED_TRAFFIC_SWITCH", "SIMULATED: Traffic-switch stage approved; no traffic was changed."),
            "SIMULATED_TRAFFIC_SWITCH": ("VERIFICATION", "SIMULATED: Traffic-switch stage completed; no production traffic changed."),
            "ROLLING_BACK": ("ROLLED_BACK", "SIMULATED: Rollback complete; source remains the recovery target."),
        }
        if state == "BACKUP_CONFIRMATION" and not backup_confirmed:
            raise HTTPException(status_code=409, detail="Confirm the simulated backup before continuing.")
        if state == "APPROVAL_GATE" and not approval_confirmed:
            raise HTTPException(status_code=409, detail="Approve the simulated switch before continuing.")
        if state in {"HEALTH_CHECK", "VERIFICATION"}:
            name = "TARGET_HEALTH_CHECK" if state == "HEALTH_CHECK" else "POST_SWITCH_VERIFICATION"
            checks.append({
                "check": name,
                "status": "PASSED" if health_check_passed else "FAILED",
                "at": now,
                "message": (
                    "SIMULATED: Check passed; no live health probe was run."
                    if health_check_passed
                    else "SIMULATED: Check failed; no production system was affected."
                ),
            })
            if not health_check_passed:
                next_state = "HEALTH_CHECK_FAILED" if state == "HEALTH_CHECK" else "VERIFICATION_FAILED"
                message = f"SIMULATED: {name.replace('_', ' ').lower()} failed; source remains available for recovery."
                error = f"{name.replace('_', ' ').title()} failed; simulated rollback is available."
            else:
                next_state = "APPROVAL_GATE" if state == "HEALTH_CHECK" else "COMPLETED"
                message = (
                    "SIMULATED: Target health check passed."
                    if state == "HEALTH_CHECK"
                    else "SIMULATED: Verification passed; workflow completed without real resource changes."
                )
                error = None
        elif state in {"HEALTH_CHECK_FAILED", "VERIFICATION_FAILED"}:
            if not rollback_confirmed:
                raise HTTPException(status_code=409, detail="Explicitly confirm the simulated rollback.")
            next_state = "ROLLING_BACK"
            message = "SIMULATED: Rollback to the source recovery target started."
            error = migration.get("error")
            checks.append({
                "check": "ROLLBACK_CONFIRMATION",
                "status": "APPROVED",
                "at": now,
                "message": "SIMULATED: Rollback confirmed; no production traffic or resources changed.",
            })
        elif state in transitions:
            next_state, message = transitions[state]
            error = None
            if state == "BACKUP_CONFIRMATION":
                checks.append({
                    "check": "BACKUP_CONFIRMATION",
                    "status": "PASSED",
                    "at": now,
                    "message": "SIMULATED: User confirmed a backup; no real backup was created.",
                })
            elif state == "APPROVAL_GATE":
                checks.append({
                    "check": "TRAFFIC_SWITCH_APPROVAL",
                    "status": "APPROVED",
                    "at": now,
                    "message": "SIMULATED: User approved the switch; no real traffic was changed.",
                })
        else:
            raise HTTPException(status_code=409, detail=f"Migration in state {state} cannot be advanced.")
        return {
            **migration,
            "state": next_state,
            "updated_at": now,
            "source_workload_active": next_state != "COMPLETED",
            "history": [*migration["history"], {"state": next_state, "at": now, "message": message}],
            "safety_checks": checks,
            "error": error,
        }

    if state == "PENDING":
        if not backup_confirmed:
            raise HTTPException(status_code=409, detail="Confirm the simulated backup before advancing.")
        checks.append({
            "check": "BACKUP_CONFIRMATION",
            "status": "PASSED",
            "at": now,
            "message": "SIMULATED: User confirmed a backup; no real backup was created.",
        })
    if state == "READY_TO_SWITCH":
        if not approval_confirmed:
            raise HTTPException(status_code=409, detail="Explicitly approve the simulated traffic switch before advancing.")
        checks.append({
            "check": "TRAFFIC_SWITCH_APPROVAL",
            "status": "APPROVED",
            "at": now,
            "message": "SIMULATED: User approved the traffic-switch stage; no traffic was changed.",
        })

    if state in {"HEALTH_CHECK", "VERIFYING"}:
        check_name = "TARGET_HEALTH_CHECK" if state == "HEALTH_CHECK" else "POST_SWITCH_HEALTH_CHECK"
        checks.append({
            "check": check_name,
            "status": "PASSED" if health_check_passed else "FAILED",
            "at": now,
            "message": (
                "SIMULATED: Target health check passed; no live health probe was run."
                if health_check_passed
                else "SIMULATED: Target health check failed."
            ),
        })

    if state == "HEALTH_CHECK" and not health_check_passed:
        next_state = "FAILED"
        message = "SIMULATED: Pre-switch target health check failed; source remains the recovery target."
        error = "Health check gate did not pass."
    elif state == "VERIFYING" and not health_check_passed:
        next_state = "ROLLING_BACK"
        message = "SIMULATED: Post-switch health check failed; rollback to the source is in progress."
        error = "Post-switch health check failed; simulated rollback started."
    elif state == "VERIFYING":
        next_state = "COMPLETED"
        message = "SIMULATED: Post-switch verification passed; no live traffic or resources changed."
        error = None
    elif state == "ROLLING_BACK":
        next_state = "ROLLED_BACK"
        message = "SIMULATED: Rollback complete; source environment remains the intended recovery target."
        error = migration.get("error")
    else:
        next_state = MIGRATION_STATES[MIGRATION_STATES.index(state) + 1]
        message = "SIMULATED: State transition only; no cloud operation was executed."
        error = None

    return {
        **migration,
        "state": next_state,
        "updated_at": now,
        "source_workload_active": next_state != "COMPLETED",
        "history": [*migration["history"], {"state": next_state, "at": now, "message": message}],
        "safety_checks": checks,
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
        "history": [*migration["history"], {
            "state": "CANCELLED",
            "at": now,
            "message": "SIMULATED: Simulation cancelled; source remains the recovery target.",
        }],
    }
