"""Integration tests for exact-hash trust approvals."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest

from setuper.infrastructure.database import connect_database, run_migrations
from setuper.infrastructure.migrations import MIGRATIONS
from setuper.infrastructure.trust_repository import (
    TrustApprovalRecord,
    TrustRepository,
)

SETUP_ID = UUID("a6f16d84-1450-407c-9c59-cbca28bf95fc")
APPROVAL_ID = UUID("93e338c1-fe1b-486a-a0ee-94fb8ccc9acf")
APPROVED_AT = datetime(2026, 7, 29, 12, tzinfo=UTC)
MANIFEST_HASH = "a" * 64


def initialize_repository(tmp_path: Path) -> TrustRepository:
    """Create schema and the setup required by approval foreign keys."""
    connection = connect_database(tmp_path / "state.db")
    run_migrations(connection, MIGRATIONS)
    connection.execute(
        """
        INSERT INTO setups(
            id, name, manifest_path, manifest_hash, source, created_at, updated_at
        ) VALUES (?, 'workspace', '/tmp/workspace.yaml', ?, 'local', ?, ?)
        """,
        (
            str(SETUP_ID),
            MANIFEST_HASH,
            APPROVED_AT.isoformat(),
            APPROVED_AT.isoformat(),
        ),
    )
    connection.commit()
    return TrustRepository(connection)


def make_approval() -> TrustApprovalRecord:
    """Return deterministic approval metadata."""
    return TrustApprovalRecord(
        id=APPROVAL_ID,
        setup_id=SETUP_ID,
        manifest_hash=MANIFEST_HASH,
        approved_at=APPROVED_AT,
    )


def test_approval_is_bound_to_exact_active_hash(tmp_path: Path) -> None:
    """Only an unrevoked approval for the exact revision is active."""
    repository = initialize_repository(tmp_path)
    approval = make_approval()
    repository.create(approval)

    assert repository.active_approval(SETUP_ID, MANIFEST_HASH) == approval
    assert repository.active_approval(SETUP_ID, "b" * 64) is None


def test_revoke_all_invalidates_active_approvals(tmp_path: Path) -> None:
    """Untrust records revocation while retaining approval history."""
    repository = initialize_repository(tmp_path)
    first = make_approval()
    second = replace(
        first,
        id=UUID("1aab7d5b-5433-4a2a-8be4-e3227c7685eb"),
        manifest_hash="b" * 64,
    )
    repository.create(first)
    repository.create(second)
    revoked_at = APPROVED_AT + timedelta(minutes=1)

    assert repository.revoke_all(SETUP_ID, revoked_at) == 2
    assert repository.revoke_all(SETUP_ID, revoked_at) == 0
    assert repository.active_approval(SETUP_ID, MANIFEST_HASH) is None


@pytest.mark.parametrize("manifest_hash", ["short", "G" * 64, "a" * 63 + "-"])
def test_approval_requires_lowercase_sha256(manifest_hash: str) -> None:
    """Approval records cannot be created for malformed revisions."""
    with pytest.raises(ValueError, match="SHA-256"):
        replace(make_approval(), manifest_hash=manifest_hash)


def test_approval_timestamps_must_be_aware(tmp_path: Path) -> None:
    """Approval and revocation timestamps are always unambiguous UTC."""
    repository = initialize_repository(tmp_path)
    naive = datetime(2026, 7, 29)

    with pytest.raises(ValueError, match="timezone-aware"):
        repository.create(replace(make_approval(), approved_at=naive))
    with pytest.raises(ValueError, match="timezone-aware"):
        repository.revoke_all(SETUP_ID, naive)
