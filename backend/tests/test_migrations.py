import pytest
from fastapi import HTTPException

from app.services.migrations import advance_migration, cancel_migration, new_migration


def advance_safely(migration, health_check_passed=True):
    return advance_migration(
        migration,
        health_check_passed,
        backup_confirmed=migration["state"] == "PENDING",
        approval_confirmed=migration["state"] == "READY_TO_SWITCH",
    )


def progress_to_health_check(migration):
    for _ in range(3):
        migration = advance_safely(migration)
    return migration


def progress_to_state(migration, target_state):
    while migration["state"] != target_state:
        migration = advance_safely(migration)
    return migration


def test_migration_requires_simulated_backup_confirmation_before_progress():
    migration = new_migration("GCP", "Azure", "test")

    with pytest.raises(HTTPException) as error:
        advance_migration(migration, True)

    assert error.value.status_code == 409
    assert migration["state"] == "PENDING"
    progressed = advance_migration(migration, True, backup_confirmed=True)
    assert progressed["state"] == "PROVISIONING"
    assert progressed["safety_checks"][0]["check"] == "BACKUP_CONFIRMATION"
    assert progressed["safety_checks"][0]["status"] == "PASSED"


def test_migration_requires_health_gate_before_ready_to_switch():
    migration = progress_to_health_check(new_migration("AWS", "GCP", "test"))
    assert migration["state"] == "HEALTH_CHECK"
    failed = advance_migration(migration, False)
    assert failed["state"] == "FAILED"
    assert failed["source_workload_active"]
    assert "Health check" in failed["error"]
    assert failed["safety_checks"][-1]["status"] == "FAILED"
    assert failed["history"][-1]["at"] is not None


def test_migration_requires_explicit_approval_before_traffic_switch():
    migration = progress_to_state(new_migration("GCP", "Azure", "test"), "READY_TO_SWITCH")

    with pytest.raises(HTTPException) as error:
        advance_migration(migration, True)

    assert error.value.status_code == 409
    assert migration["state"] == "READY_TO_SWITCH"
    switched = advance_migration(migration, True, approval_confirmed=True)
    assert switched["state"] == "SWITCHING_TRAFFIC"
    assert switched["safety_checks"][-1]["check"] == "TRAFFIC_SWITCH_APPROVAL"
    assert switched["safety_checks"][-1]["status"] == "APPROVED"


def test_migration_completes_only_after_approved_post_switch_verification():
    migration = new_migration("AWS", "GCP", "test")
    migration = progress_to_state(migration, "VERIFYING")
    migration = advance_safely(migration)
    assert migration["state"] == "COMPLETED"
    assert not migration["source_workload_active"]
    assert migration["safety_checks"][-1]["check"] == "POST_SWITCH_HEALTH_CHECK"
    assert migration["safety_checks"][-1]["status"] == "PASSED"


def test_post_switch_health_failure_runs_simulated_rollback_to_source():
    migration = progress_to_state(new_migration("GCP", "Azure", "test"), "VERIFYING")

    rollback = advance_migration(migration, False)
    assert rollback["state"] == "ROLLING_BACK"
    assert rollback["source_workload_active"] is True
    assert rollback["safety_checks"][-1]["status"] == "FAILED"
    assert "rollback" in rollback["history"][-1]["message"].lower()

    recovered = advance_migration(rollback, True)
    assert recovered["state"] == "ROLLED_BACK"
    assert recovered["source_workload_active"] is True
    assert "source" in recovered["history"][-1]["message"].lower()
    with pytest.raises(HTTPException):
        advance_migration(recovered, True)


def test_terminal_migration_cannot_advance_or_cancel():
    migration = new_migration("AWS", "GCP", "test")
    migration["state"] = "COMPLETED"
    with pytest.raises(HTTPException):
        advance_migration(migration, True)
    with pytest.raises(HTTPException):
        cancel_migration(migration)


def test_cancellation_preserves_source_workload():
    migration = cancel_migration(new_migration("AWS", "GCP", "test"))
    assert migration["state"] == "CANCELLED"
    assert migration["source_workload_active"]


def progress_spot_to_verification(migration):
    migration = advance_migration(migration, True)
    assert migration["state"] == "TARGET_SELECTION"
    migration = advance_migration(migration, True)
    assert migration["state"] == "BACKUP_CONFIRMATION"
    migration = advance_migration(migration, True, backup_confirmed=True)
    assert migration["state"] == "HEALTH_CHECK"
    migration = advance_migration(migration, True)
    assert migration["state"] == "APPROVAL_GATE"
    migration = advance_migration(migration, True, approval_confirmed=True)
    assert migration["state"] == "SIMULATED_TRAFFIC_SWITCH"
    migration = advance_migration(migration, True)
    assert migration["state"] == "VERIFICATION"
    return migration


def test_spot_simulator_enforces_workflow_gates_and_completes():
    migration = new_migration("GCP", "Azure", "spot-demo", workflow_type="spot")
    assert migration["state"] == "PRICE_ALERT"
    migration = advance_migration(migration, True)
    migration = advance_migration(migration, True)

    with pytest.raises(HTTPException) as error:
        advance_migration(migration, True)
    assert error.value.status_code == 409

    migration = advance_migration(migration, True, backup_confirmed=True)
    migration = advance_migration(migration, True)
    with pytest.raises(HTTPException) as error:
        advance_migration(migration, True)
    assert error.value.status_code == 409

    migration = advance_migration(migration, True, approval_confirmed=True)
    migration = advance_migration(migration, True)
    completed = advance_migration(migration, True)
    assert completed["state"] == "COMPLETED"
    assert completed["source_workload_active"] is False
    assert [event["state"] for event in completed["history"]] == [
        "PRICE_ALERT", "TARGET_SELECTION", "BACKUP_CONFIRMATION", "HEALTH_CHECK",
        "APPROVAL_GATE", "SIMULATED_TRAFFIC_SWITCH", "VERIFICATION", "COMPLETED",
    ]
    assert all(check["at"] for check in completed["safety_checks"])


@pytest.mark.parametrize("failed_state", ["HEALTH_CHECK", "VERIFICATION"])
def test_spot_simulator_offers_explicit_rollback_after_failed_check(failed_state):
    migration = new_migration("GCP", "Azure", "spot-demo", workflow_type="spot")
    if failed_state == "VERIFICATION":
        migration = progress_spot_to_verification(migration)
    else:
        for _ in range(3):
            migration = advance_migration(
                migration,
                True,
                backup_confirmed=migration["state"] == "BACKUP_CONFIRMATION",
            )
        assert migration["state"] == "HEALTH_CHECK"

    failed = advance_migration(migration, False)
    expected_failure = "HEALTH_CHECK_FAILED" if failed_state == "HEALTH_CHECK" else "VERIFICATION_FAILED"
    assert failed["state"] == expected_failure
    assert failed["source_workload_active"] is True
    with pytest.raises(HTTPException):
        advance_migration(failed, True)

    rolling_back = advance_migration(failed, True, rollback_confirmed=True)
    assert rolling_back["state"] == "ROLLING_BACK"
    rolled_back = advance_migration(rolling_back, True)
    assert rolled_back["state"] == "ROLLED_BACK"
    assert rolled_back["source_workload_active"] is True
