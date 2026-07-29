"""Integration tests for launch and resource-run persistence."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest

from setuper.domain.enums import LaunchStatus, ResourceRunStatus
from setuper.domain.errors import DatabaseError
from setuper.infrastructure.database import connect_database, run_migrations
from setuper.infrastructure.launch_repository import (
    LaunchRecord,
    LaunchRepository,
    ResourceRunRecord,
)
from setuper.infrastructure.migrations import MIGRATIONS

SETUP_ID = UUID("a6f16d84-1450-407c-9c59-cbca28bf95fc")
LAUNCH_ID = UUID("6425ddcb-d919-4743-9b88-9f5906a81c47")
STARTED_AT = datetime(2026, 7, 29, 12, tzinfo=UTC)


def initialize_repository(tmp_path: Path) -> LaunchRepository:
    """Create schema and its required setup parent."""
    connection = connect_database(tmp_path / "state.db")
    run_migrations(connection, MIGRATIONS)
    connection.execute(
        """
        INSERT INTO setups(
            id, name, manifest_path, manifest_hash, source, created_at, updated_at
        ) VALUES (?, 'workspace', '/tmp/workspace.yaml', 'hash', 'local', ?, ?)
        """,
        (str(SETUP_ID), STARTED_AT.isoformat(), STARTED_AT.isoformat()),
    )
    connection.commit()
    return LaunchRepository(connection)


def make_launch() -> LaunchRecord:
    """Return deterministic launch metadata."""
    return LaunchRecord(
        id=LAUNCH_ID,
        setup_id=SETUP_ID,
        manifest_hash="a" * 64,
        profile=None,
        status=LaunchStatus.STARTING,
        started_at=STARTED_AT,
    )


def test_launch_create_update_get_and_latest(tmp_path: Path) -> None:
    """Launch lifecycle state round-trips and latest lookup is deterministic."""
    repository = initialize_repository(tmp_path)
    original = make_launch()
    repository.create_launch(original)
    updated = replace(
        original,
        status=LaunchStatus.RUNNING,
        completed_at=STARTED_AT + timedelta(seconds=3),
    )

    repository.update_launch(updated)

    assert repository.get_launch(LAUNCH_ID) == updated
    assert repository.latest_for_setup(SETUP_ID) == updated


def test_latest_launch_returns_none_for_unlaunched_setup(tmp_path: Path) -> None:
    """A setup with no launches has no synthetic runtime record."""
    repository = initialize_repository(tmp_path)

    assert repository.latest_for_setup(SETUP_ID) is None


def test_resource_runs_create_update_and_list_in_stable_order(
    tmp_path: Path,
) -> None:
    """Resource state and ownership data round-trip in resource-ID order."""
    repository = initialize_repository(tmp_path)
    repository.create_launch(make_launch())
    frontend = ResourceRunRecord(
        id=UUID("2a465495-5dcc-47f0-813c-b785759a64ca"),
        launch_id=LAUNCH_ID,
        resource_id="frontend",
        resource_type="command",
        status=ResourceRunStatus.PENDING,
    )
    database = ResourceRunRecord(
        id=UUID("e2876ec7-5540-43ef-a3bd-15a5d12185aa"),
        launch_id=LAUNCH_ID,
        resource_id="database",
        resource_type="docker_compose",
        status=ResourceRunStatus.PENDING,
    )
    repository.create_resource_run(frontend)
    repository.create_resource_run(database)
    ready_frontend = replace(
        frontend,
        status=ResourceRunStatus.READY,
        pid=1234,
        started_at=STARTED_AT,
        ready_at=STARTED_AT + timedelta(seconds=2),
    )

    repository.update_resource_run(ready_frontend)

    assert repository.list_resource_runs(LAUNCH_ID) == (
        database,
        ready_frontend,
    )


def test_missing_updates_and_reads_are_typed(tmp_path: Path) -> None:
    """Missing runtime rows produce redacted database failures."""
    repository = initialize_repository(tmp_path)
    missing_launch = make_launch()
    missing_resource = ResourceRunRecord(
        id=UUID("2a465495-5dcc-47f0-813c-b785759a64ca"),
        launch_id=LAUNCH_ID,
        resource_id="frontend",
        resource_type="command",
        status=ResourceRunStatus.PENDING,
    )

    with pytest.raises(DatabaseError):
        repository.get_launch(LAUNCH_ID)
    with pytest.raises(DatabaseError):
        repository.update_launch(missing_launch)
    with pytest.raises(DatabaseError):
        repository.update_resource_run(missing_resource)


def test_launch_rejects_naive_timestamp(tmp_path: Path) -> None:
    """Launch writes never persist ambiguous local timestamps."""
    repository = initialize_repository(tmp_path)
    launch = replace(make_launch(), started_at=datetime(2026, 7, 29))

    with pytest.raises(ValueError, match="timezone-aware"):
        repository.create_launch(launch)
