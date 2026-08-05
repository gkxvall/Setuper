"""Execute a launch plan: schedule, run, wait for readiness, and record."""

from uuid import UUID

from setuper.adapters.base import LaunchContext
from setuper.adapters.registry import AdapterRegistry
from setuper.application.launch_plan import LaunchPlan, PlannedResource
from setuper.application.launch_recorder import LaunchRecorder, ResourceOutcome
from setuper.application.scheduler import DEFAULT_CONCURRENCY, run_scheduled
from setuper.domain.enums import LaunchStatus, ResourceRunStatus
from setuper.infrastructure.commands import CommandRunner, SubprocessCommandRunner
from setuper.infrastructure.readiness_checks import wait_until_ready
from setuper.infrastructure.retry import run_with_retry


class LaunchService:
    """Coordinate a full launch: schedule, execute, wait, and persist state."""

    def __init__(
        self,
        registry: AdapterRegistry,
        recorder: LaunchRecorder,
        *,
        command_runner: CommandRunner | None = None,
        concurrency: int = DEFAULT_CONCURRENCY,
    ) -> None:
        """Create a launch service with injectable adapter and readiness boundaries."""
        self._registry = registry
        self._recorder = recorder
        self._command_runner = command_runner or SubprocessCommandRunner()
        self._concurrency = concurrency

    async def launch(self, plan: LaunchPlan) -> LaunchStatus:
        """Execute a launch plan end to end and persist its outcome."""
        launch_id = self._recorder.start_launch(
            setup_id=plan.setup_id,
            manifest_hash=plan.manifest_hash,
            profile=plan.profile,
            resources={
                resource.spec.id: resource.spec.type for resource in plan.resources
            },
        )

        async def run_resource(resource_id: str) -> ResourceRunStatus:
            planned = plan.resource(resource_id)
            if planned.validation_error is not None:
                self._recorder.record_resource_outcome(
                    resource_id,
                    ResourceOutcome(
                        status=ResourceRunStatus.FAILED,
                        error_code="VALIDATION",
                        error_message=planned.validation_error,
                    ),
                )
                return ResourceRunStatus.FAILED
            return await self._run_one(plan.setup_id, launch_id, planned)

        statuses = await run_scheduled(
            plan.graph,
            run_resource,
            concurrency=self._concurrency,
        )
        return self._recorder.finalize_launch(statuses)

    async def _run_one(
        self,
        setup_id: UUID,
        launch_id: UUID,
        planned: PlannedResource,
    ) -> ResourceRunStatus:
        """Launch one resource, wait for its readiness, and record the outcome."""
        spec = planned.spec

        async def attempt() -> int | None:
            adapter = self._registry.get(spec.type)
            result = await adapter.launch(
                spec,
                LaunchContext(
                    setup_id=setup_id, launch_id=launch_id, environment=spec.env
                ),
            )
            if planned.readiness is not None:
                await wait_until_ready(
                    planned.readiness,
                    timeout_seconds=spec.timeout_seconds,
                    runner=self._command_runner,
                )
            return result.pid

        try:
            pid = await run_with_retry(
                attempt,
                retry=spec.retry,
                timeout_seconds=spec.timeout_seconds,
            )
        except Exception as error:
            self._recorder.record_resource_outcome(
                spec.id,
                ResourceOutcome(
                    status=ResourceRunStatus.FAILED,
                    error_code=str(getattr(error, "error_code", "GENERAL_FAILURE")),
                    error_message=str(error),
                ),
            )
            return ResourceRunStatus.FAILED

        self._recorder.record_resource_outcome(
            spec.id,
            ResourceOutcome(status=ResourceRunStatus.READY, pid=pid),
        )
        return ResourceRunStatus.READY
