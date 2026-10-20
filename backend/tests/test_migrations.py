import pytest
from fastapi import HTTPException

from app.services.migrations import advance_migration, cancel_migration, new_migration


def progress_to_health_check(migration):
    for _ in range(3):
        migration = advance_migration(migration, True)
    return migration


def test_migration_requires_health_gate_before_ready_to_switch():
    migration = progress_to_health_check(new_migration("AWS", "GCP", "test"))
    assert migration["state"] == "HEALTH_CHECK"
    failed = advance_migration(migration, False)
    assert failed["state"] == "FAILED"
    assert failed["source_workload_active"]
    assert "Health check" in failed["error"]


def test_migration_completed_only_after_verification_transition():
    migration = new_migration("AWS", "GCP", "test")
    for _ in range(7):
        migration = advance_migration(migration, True)
    assert migration["state"] == "COMPLETED"
    assert not migration["source_workload_active"]


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
