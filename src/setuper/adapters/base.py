"""Resource adapter contracts shared by capture and runtime integrations."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable
from uuid import UUID

from pydantic import JsonValue

from setuper.domain.enums import CaptureSupport, Platform, ResourceRunStatus
from setuper.domain.errors import AdapterUnavailableError
from setuper.domain.models import ResourceSpec


@dataclass(frozen=True, slots=True)
class CaptureContext:
    """Machine context exposed to detection without environment values."""

    platform: Platform
    current_directory: Path
    environment_names: frozenset[str] = frozenset()


@dataclass(frozen=True, slots=True)
class DetectedResource:
    """Structured machine finding before manifest capture."""

    identity: str
    type_name: str
    display_name: str
    support: CaptureSupport
    config: Mapping[str, JsonValue] = field(default_factory=dict)
    metadata: Mapping[str, JsonValue] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ValidationContext:
    """Context available while validating one resource specification."""

    platform: Platform


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """Adapter validation outcome without terminal side effects."""

    valid: bool
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class LaunchContext:
    """Identifiers and explicit environment supplied to a launch adapter."""

    setup_id: UUID
    launch_id: UUID
    environment: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class LaunchResult:
    """Structured launch outcome returned by an adapter."""

    status: ResourceRunStatus
    pid: int | None = None
    external_id: str | None = None
    message: str | None = None


@dataclass(frozen=True, slots=True)
class StatusContext:
    """Identifiers available to adapter status checks."""

    setup_id: UUID
    launch_id: UUID


@dataclass(frozen=True, slots=True)
class ResourceStatus:
    """Current adapter-reported resource status."""

    status: ResourceRunStatus
    message: str | None = None


@dataclass(frozen=True, slots=True)
class StopContext:
    """Identifiers and force policy supplied to a stop adapter."""

    setup_id: UUID
    launch_id: UUID
    force: bool = False


@dataclass(frozen=True, slots=True)
class StopResult:
    """Structured stop outcome returned by an adapter."""

    status: ResourceRunStatus
    message: str | None = None


@runtime_checkable
class ResourceAdapter(Protocol):
    """Complete adapter interface; operations may report unsupported."""

    type_name: str

    def detect(self, context: CaptureContext) -> list[DetectedResource]:
        """Detect resources available to this adapter."""

    def capture(self, resource: DetectedResource) -> ResourceSpec:
        """Convert one finding into a manifest resource."""

    def validate(
        self,
        spec: ResourceSpec,
        context: ValidationContext,
    ) -> ValidationResult:
        """Validate one resource without launching it."""

    async def launch(
        self,
        spec: ResourceSpec,
        context: LaunchContext,
    ) -> LaunchResult:
        """Launch one resource."""

    async def status(
        self,
        spec: ResourceSpec,
        context: StatusContext,
    ) -> ResourceStatus:
        """Inspect one launched resource."""

    async def stop(
        self,
        spec: ResourceSpec,
        context: StopContext,
    ) -> StopResult:
        """Stop one owned resource."""


class BaseResourceAdapter:
    """Defaults for adapters that support only a subset of operations."""

    type_name = ""

    def detect(self, context: CaptureContext) -> list[DetectedResource]:
        """Return no findings when detection is unsupported."""
        return []

    def capture(self, resource: DetectedResource) -> ResourceSpec:
        """Reject unsupported capture explicitly."""
        raise self._unsupported("capture")

    def validate(
        self,
        spec: ResourceSpec,
        context: ValidationContext,
    ) -> ValidationResult:
        """Reject unsupported validation explicitly."""
        raise self._unsupported("validate")

    async def launch(
        self,
        spec: ResourceSpec,
        context: LaunchContext,
    ) -> LaunchResult:
        """Reject unsupported launch explicitly."""
        raise self._unsupported("launch")

    async def status(
        self,
        spec: ResourceSpec,
        context: StatusContext,
    ) -> ResourceStatus:
        """Reject unsupported status explicitly."""
        raise self._unsupported("status")

    async def stop(
        self,
        spec: ResourceSpec,
        context: StopContext,
    ) -> StopResult:
        """Reject unsupported stop explicitly."""
        raise self._unsupported("stop")

    def _unsupported(self, operation: str) -> AdapterUnavailableError:
        """Build one typed unsupported-operation error."""
        return AdapterUnavailableError(
            f"Adapter {self.type_name!r} does not support {operation}",
            details={"adapter": self.type_name, "operation": operation},
        )
