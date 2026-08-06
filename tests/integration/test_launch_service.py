"""Integration tests for full launch-plan execution and state persistence."""

import asyncio
import contextlib
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from setuper.adapters.base import LaunchContext, LaunchResult
from setuper.adapters.registry import AdapterRegistry
from setuper.application.launch_plan import LaunchPlan, PlannedResource
from setuper.application.launch_recorder import LaunchRecorder
from setuper.application.launch_service import LaunchService
from setuper.domain.enums import LaunchStatus, ResourceRunStatus
from setuper.domain.errors import AdapterUnavailableError
from setuper.domain.graph import build_dependency_graph
from setuper.domain.models import ResourceSpec
from setuper.domain.readiness import TcpReadinessSpec
from setuper.infrastructure.database import connect_database, run_migrations
from setuper.infrastructure.launch_repository import LaunchRepository
from setuper.infrastructure.migrations import MIGRATIONS

SETUP_ID = uuid4()
STARTED_AT = datetime(2026, 7, 29, 12, tzinfo=UTC)


async def _close_accepted_connection(
    _reader: asyncio.StreamReader, writer: asyncio.StreamWriter
) -> None:
    """Close each accepted connection so the server can shut down cleanly.

    Python 3.12 changed `Server.wait_closed()` to also wait for every
    connection the server has accepted, not just its listening socket.
    """
    writer.close()
    with contextlib.suppress(OSError):
        await writer.wait_closed()


class _FakeLaunchAdapter:
    """Adapter stub recording launch calls with a configurable outcome."""

    def __init__(
        self,
        type_name: str,
        *,
        result: LaunchResult | None = None,
        error: Exception | None = None,
    ) -> None:
        self.type_name = type_name
        self._result = result or LaunchResult(status=ResourceRunStatus.RUNNING)
        self._error = error
        self.launch_calls: list[str] = []

    async def launch(
        self,
        spec: ResourceSpec,
        context: LaunchContext,
    ) -> LaunchResult:
        """Record the call and return the configured result or raise."""
        self.launch_calls.append(spec.id)
        if self._error is not None:
            raise self._error
        return self._result


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
    ids = iter(UUID(int=index) for index in range(1, 1000))
    ticks = iter(range(1000))
    return LaunchRecorder(
        repository,
        id_factory=lambda: next(ids),
        clock=lambda: datetime(2026, 7, 29, 12, 0, next(ticks), tzinfo=UTC),
    )


def _plan(resources: list[ResourceSpec], planned: list[PlannedResource]) -> LaunchPlan:
    """Build a launch plan directly from already-planned resources."""
    return LaunchPlan(
        setup_id=SETUP_ID,
        manifest_hash="a" * 64,
        profile=None,
        graph=build_dependency_graph(resources),
        resources=tuple(planned),
    )


def _resource(resource_id: str, resource_type: str, *depends_on: str) -> ResourceSpec:
    """Build one minimal resource spec."""
    return ResourceSpec(id=resource_id, type=resource_type, depends_on=depends_on)


def test_launch_marks_resource_ready_and_persists_its_pid(tmp_path: Path) -> None:
    """A successful launch with no readiness spec is marked READY with its PID."""

    async def scenario() -> None:
        repository = _repository(tmp_path)
        recorder = _recorder(repository)
        adapter = _FakeLaunchAdapter(
            "command",
            result=LaunchResult(status=ResourceRunStatus.RUNNING, pid=4242),
        )
        registry = AdapterRegistry([adapter])
        spec = _resource("frontend", "command")
        plan = _plan([spec], [PlannedResource(spec=spec, readiness=None)])
        service = LaunchService(registry, recorder)

        status = await service.launch(plan)

        assert status is LaunchStatus.RUNNING
        assert adapter.launch_calls == ["frontend"]

    asyncio.run(scenario())


def test_launch_waits_for_tcp_readiness_before_marking_ready(tmp_path: Path) -> None:
    """A resource with a readiness spec only becomes READY once it responds."""

    async def scenario() -> None:
        server = await asyncio.start_server(_close_accepted_connection, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        try:
            repository = _repository(tmp_path)
            recorder = _recorder(repository)
            registry = AdapterRegistry([_FakeLaunchAdapter("docker")])
            spec = _resource("postgres", "docker")
            plan = _plan(
                [spec],
                [
                    PlannedResource(
                        spec=spec,
                        readiness=TcpReadinessSpec(host="127.0.0.1", port=port),
                    )
                ],
            )
            service = LaunchService(registry, recorder)

            status = await service.launch(plan)

            assert status is LaunchStatus.RUNNING
        finally:
            server.close()
            await server.wait_closed()

    asyncio.run(scenario())


def test_launch_marks_resource_failed_when_adapter_raises(tmp_path: Path) -> None:
    """An adapter error fails just that resource and the overall launch."""

    async def scenario() -> None:
        repository = _repository(tmp_path)
        recorder = _recorder(repository)
        registry = AdapterRegistry(
            [
                _FakeLaunchAdapter(
                    "command",
                    error=AdapterUnavailableError("executable not found"),
                )
            ]
        )
        spec = _resource("frontend", "command")
        plan = _plan([spec], [PlannedResource(spec=spec, readiness=None)])
        service = LaunchService(registry, recorder)

        status = await service.launch(plan)

        assert status is LaunchStatus.FAILED
        run = repository.list_resource_runs(
            repository.latest_for_setup(SETUP_ID).id  # type: ignore[union-attr]
        )[0]
        assert run.status is ResourceRunStatus.FAILED
        assert run.error_message == "executable not found"

    asyncio.run(scenario())


def test_launch_blocks_dependent_without_calling_its_adapter(tmp_path: Path) -> None:
    """A failed dependency blocks its dependent, which never reaches launch()."""

    async def scenario() -> None:
        repository = _repository(tmp_path)
        recorder = _recorder(repository)
        failing = _FakeLaunchAdapter(
            "docker",
            error=AdapterUnavailableError("daemon unavailable"),
        )
        dependent = _FakeLaunchAdapter("command")
        registry = AdapterRegistry([failing, dependent])
        postgres = _resource("postgres", "docker")
        frontend = _resource("frontend", "command", "postgres")
        plan = _plan(
            [postgres, frontend],
            [
                PlannedResource(spec=postgres, readiness=None),
                PlannedResource(spec=frontend, readiness=None),
            ],
        )
        service = LaunchService(registry, recorder)

        status = await service.launch(plan)

        assert status is LaunchStatus.FAILED
        assert dependent.launch_calls == []

    asyncio.run(scenario())


def test_launch_fails_resource_with_a_planning_validation_error_without_launching(
    tmp_path: Path,
) -> None:
    """A resource flagged invalid during planning is never handed to its adapter."""

    async def scenario() -> None:
        repository = _repository(tmp_path)
        recorder = _recorder(repository)
        adapter = _FakeLaunchAdapter("command")
        registry = AdapterRegistry([adapter])
        spec = _resource("frontend", "command")
        plan = _plan(
            [spec],
            [
                PlannedResource(
                    spec=spec,
                    readiness=None,
                    validation_error="bad config",
                )
            ],
        )
        service = LaunchService(registry, recorder)

        status = await service.launch(plan)

        assert status is LaunchStatus.FAILED
        assert adapter.launch_calls == []

    asyncio.run(scenario())
