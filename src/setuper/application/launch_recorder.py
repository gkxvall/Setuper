"""Bridge between launch orchestration and persisted launch/resource state."""

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

from setuper.domain.enums import LaunchStatus, ResourceRunStatus
from setuper.infrastructure.launch_repository import (
    LaunchRecord,
    LaunchRepository,
    ResourceRunRecord,
)


@dataclass(frozen=True, slots=True)
class ResourceOutcome:
    """One resource's state to persist after it starts, readies, or fails."""

    status: ResourceRunStatus
    pid: int | None = None
    external_id: str | None = None
    exit_code: int | None = None
    error_code: str | None = None
    error_message: str | None = None


class LaunchRecorder:
    """Persist one launch's lifecycle and per-resource state transitions."""

    def __init__(
        self,
        repository: LaunchRepository,
        *,
        id_factory: Callable[[], UUID] = uuid4,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        """Create a recorder bound to one repository and injectable identity/time."""
        self._repository = repository
        self._id_factory = id_factory
        self._clock = clock
        self._launch: LaunchRecord | None = None
        self._resource_record_ids: dict[str, UUID] = {}

    def start_launch(
        self,
        *,
        setup_id: UUID,
        manifest_hash: str,
        profile: str | None,
        resources: Mapping[str, str],
    ) -> UUID:
        """Create the aggregate launch and one pending record per resource."""
        launch_id = self._id_factory()
        launch = LaunchRecord(
            id=launch_id,
            setup_id=setup_id,
            manifest_hash=manifest_hash,
            profile=profile,
            status=LaunchStatus.STARTING,
            started_at=self._clock(),
        )
        self._repository.create_launch(launch)
        self._launch = launch
        self._resource_record_ids = {}
        for resource_id, resource_type in resources.items():
            record_id = self._id_factory()
            self._resource_record_ids[resource_id] = record_id
            self._repository.create_resource_run(
                ResourceRunRecord(
                    id=record_id,
                    launch_id=launch_id,
                    resource_id=resource_id,
                    resource_type=resource_type,
                    status=ResourceRunStatus.PENDING,
                )
            )
        return launch_id

    def record_resource_outcome(
        self,
        resource_id: str,
        outcome: ResourceOutcome,
    ) -> None:
        """Persist one resource's status and ownership metadata."""
        launch = self._require_launch()
        record_id = self._resource_record_ids[resource_id]
        existing = next(
            record
            for record in self._repository.list_resource_runs(launch.id)
            if record.id == record_id
        )
        timestamp = self._clock()
        terminal_stop_states = (ResourceRunStatus.STOPPED, ResourceRunStatus.FAILED)
        updated = replace(
            existing,
            status=outcome.status,
            pid=outcome.pid if outcome.pid is not None else existing.pid,
            external_id=outcome.external_id or existing.external_id,
            started_at=existing.started_at or timestamp,
            ready_at=(
                timestamp
                if outcome.status is ResourceRunStatus.READY
                else existing.ready_at
            ),
            stopped_at=(
                timestamp
                if outcome.status in terminal_stop_states
                else existing.stopped_at
            ),
            exit_code=(
                outcome.exit_code
                if outcome.exit_code is not None
                else existing.exit_code
            ),
            error_code=outcome.error_code or existing.error_code,
            error_message=outcome.error_message or existing.error_message,
        )
        self._repository.update_resource_run(updated)

    def finalize_launch(
        self,
        statuses: Mapping[str, ResourceRunStatus],
    ) -> LaunchStatus:
        """Compute and persist the aggregate launch status from resource outcomes."""
        launch = self._require_launch()
        aggregate = _aggregate_status(statuses.values())
        updated = replace(launch, status=aggregate, completed_at=self._clock())
        self._repository.update_launch(updated)
        self._launch = updated
        return aggregate

    def _require_launch(self) -> LaunchRecord:
        """Return the active launch, or fail clearly if none was started."""
        if self._launch is None:
            raise RuntimeError("start_launch must be called before this method")
        return self._launch


def _aggregate_status(statuses: Iterable[ResourceRunStatus]) -> LaunchStatus:
    """Derive the aggregate launch status from individual resource outcomes."""
    values = list(statuses)
    if not values or all(status is ResourceRunStatus.READY for status in values):
        return LaunchStatus.RUNNING
    if any(status is ResourceRunStatus.READY for status in values):
        return LaunchStatus.PARTIAL
    return LaunchStatus.FAILED
