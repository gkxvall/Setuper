"""Integration tests for persisted launch and resource-run state."""

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from setuper.application.launch_recorder import LaunchRecorder, ResourceOutcome
from setuper.domain.enums import LaunchStatus, ResourceRunStatus
from setuper.infrastructure.database import connect_database, run_migrations
from setuper.infrastructure.launch_repository import LaunchRepository
from setuper.infrastructure.migrations import MIGRATIONS

SETUP_ID = UUID("a6f16d84-1450-407c-9c59-cbca28bf95fc")
STARTED_AT = datetime(2026, 7, 29, 12, tzinfo=UTC)


def _repository(tmp_path: Path) -> LaunchRepository:
    """Create schema and its required parent setup row."""
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


def _recorder(repository: LaunchRepository) -> LaunchRecorder:
    """Build a recorder with deterministic, incrementing identity and time."""
    ids = iter(UUID(int=index) for index in range(1, 100))
    ticks = iter(range(100))
    return LaunchRecorder(
        repository,
        id_factory=lambda: next(ids),
        clock=lambda: datetime(2026, 7, 29, 12, next(ticks), tzinfo=UTC),
    )


def test_start_launch_creates_launch_and_pending_resource_runs(
    tmp_path: Path,
) -> None:
    """Starting a launch records the aggregate launch and one row per resource."""
    repository = _repository(tmp_path)
    recorder = _recorder(repository)

    launch_id = recorder.start_launch(
        setup_id=SETUP_ID,
        manifest_hash="a" * 64,
        profile="dev",
        resources={"postgres": "docker", "frontend": "command"},
    )

    launch = repository.get_launch(launch_id)
    assert launch.status is LaunchStatus.STARTING
    assert launch.profile == "dev"

    runs = repository.list_resource_runs(launch_id)
    assert {run.resource_id: run.status for run in runs} == {
        "postgres": ResourceRunStatus.PENDING,
        "frontend": ResourceRunStatus.PENDING,
    }


def test_record_resource_outcome_persists_pid_and_ready_timestamp(
    tmp_path: Path,
) -> None:
    """A READY outcome persists its PID and stamps a ready timestamp."""
    repository = _repository(tmp_path)
    recorder = _recorder(repository)
    launch_id = recorder.start_launch(
        setup_id=SETUP_ID,
        manifest_hash="a" * 64,
        profile=None,
        resources={"frontend": "command"},
    )

    recorder.record_resource_outcome(
        "frontend",
        ResourceOutcome(status=ResourceRunStatus.READY, pid=4242),
    )

    run = repository.list_resource_runs(launch_id)[0]
    assert run.status is ResourceRunStatus.READY
    assert run.pid == 4242
    assert run.started_at is not None
    assert run.ready_at is not None


def test_record_resource_outcome_persists_failure_details(tmp_path: Path) -> None:
    """A FAILED outcome persists its error code, message, and stop timestamp."""
    repository = _repository(tmp_path)
    recorder = _recorder(repository)
    launch_id = recorder.start_launch(
        setup_id=SETUP_ID,
        manifest_hash="a" * 64,
        profile=None,
        resources={"frontend": "command"},
    )

    recorder.record_resource_outcome(
        "frontend",
        ResourceOutcome(
            status=ResourceRunStatus.FAILED,
            error_code="ADAPTER_UNAVAILABLE",
            error_message="command not found",
        ),
    )

    run = repository.list_resource_runs(launch_id)[0]
    assert run.status is ResourceRunStatus.FAILED
    assert run.error_code == "ADAPTER_UNAVAILABLE"
    assert run.error_message == "command not found"
    assert run.stopped_at is not None


def test_finalize_launch_reports_running_when_all_resources_ready(
    tmp_path: Path,
) -> None:
    """An all-READY resource set finalizes the launch as RUNNING."""
    repository = _repository(tmp_path)
    recorder = _recorder(repository)
    launch_id = recorder.start_launch(
        setup_id=SETUP_ID,
        manifest_hash="a" * 64,
        profile=None,
        resources={"a": "command", "b": "command"},
    )

    status = recorder.finalize_launch(
        {"a": ResourceRunStatus.READY, "b": ResourceRunStatus.READY}
    )

    assert status is LaunchStatus.RUNNING
    assert repository.get_launch(launch_id).completed_at is not None


def test_finalize_launch_reports_partial_when_some_resources_fail(
    tmp_path: Path,
) -> None:
    """A mix of READY and FAILED resources finalizes the launch as PARTIAL."""
    repository = _repository(tmp_path)
    recorder = _recorder(repository)
    recorder.start_launch(
        setup_id=SETUP_ID,
        manifest_hash="a" * 64,
        profile=None,
        resources={"a": "command", "b": "command"},
    )

    status = recorder.finalize_launch(
        {"a": ResourceRunStatus.READY, "b": ResourceRunStatus.FAILED}
    )

    assert status is LaunchStatus.PARTIAL


def test_finalize_launch_reports_failed_when_no_resources_ready(
    tmp_path: Path,
) -> None:
    """No resource reaching READY finalizes the launch as FAILED."""
    repository = _repository(tmp_path)
    recorder = _recorder(repository)
    recorder.start_launch(
        setup_id=SETUP_ID,
        manifest_hash="a" * 64,
        profile=None,
        resources={"a": "command"},
    )

    status = recorder.finalize_launch({"a": ResourceRunStatus.FAILED})

    assert status is LaunchStatus.FAILED
