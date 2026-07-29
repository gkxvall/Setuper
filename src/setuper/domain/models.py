"""Validated schema-v1 manifest models."""

from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    StringConstraints,
    model_validator,
)

from setuper.domain.enums import Platform, PortConflictPolicy

NonEmptyString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
ResourceId = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    ),
]


class ManifestModel(BaseModel):
    """Base model with the strict schema-v1 field policy."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class VariableSpec(ManifestModel):
    """One user-resolvable manifest variable."""

    default: JsonValue = None
    required: bool = False
    description: str | None = None


class RetrySpec(ManifestModel):
    """Retry attempts and exponential-delay bounds."""

    attempts: Annotated[int, Field(ge=1)]
    initial_delay_seconds: Annotated[float, Field(ge=0)]
    maximum_delay_seconds: Annotated[float, Field(ge=0)]
    backoff: Annotated[float, Field(ge=1)]

    @model_validator(mode="after")
    def validate_delay_bounds(self) -> Self:
        """Reject a maximum delay below the initial delay."""
        if self.maximum_delay_seconds < self.initial_delay_seconds:
            raise ValueError(
                "maximum_delay_seconds must be greater than or equal to "
                "initial_delay_seconds"
            )
        return self


class HookSpec(ManifestModel):
    """An executable lifecycle hook requiring later trust evaluation."""

    command: NonEmptyString | tuple[NonEmptyString, ...]
    shell: bool = False
    cwd: str | None = None
    env: dict[str, str] = Field(default_factory=dict)


class ResourceSpec(ManifestModel):
    """One launchable, restorable, or validation-only setup resource."""

    id: ResourceId
    type: NonEmptyString
    description: str | None = None
    enabled: bool = True
    depends_on: tuple[ResourceId, ...] = ()
    config: dict[str, JsonValue] = Field(default_factory=dict)
    env: dict[str, str] = Field(default_factory=dict)
    ready_when: dict[str, JsonValue] | None = None
    retry: RetrySpec | None = None
    timeout_seconds: Annotated[float, Field(gt=0)] = 60.0
    on_conflict: PortConflictPolicy = PortConflictPolicy.FAIL
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_dependencies(self) -> Self:
        """Reject duplicate dependencies within a resource."""
        if len(self.depends_on) != len(set(self.depends_on)):
            raise ValueError("depends_on must not contain duplicate resource IDs")
        return self


class SetupManifest(ManifestModel):
    """Complete schema-v1 setup definition."""

    schema_version: Literal[1] = 1
    id: UUID | None = None
    name: NonEmptyString
    description: str | None = None
    platforms: tuple[Platform, ...] = (Platform.MACOS,)
    variables: dict[str, VariableSpec] = Field(default_factory=dict)
    profiles: dict[str, dict[str, JsonValue]] = Field(default_factory=dict)
    resources: tuple[ResourceSpec, ...] = ()
    hooks: dict[str, tuple[HookSpec, ...]] = Field(default_factory=dict)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_resource_references(self) -> Self:
        """Reject duplicate resource IDs and dependencies on missing resources."""
        resource_ids = [resource.id for resource in self.resources]
        known_ids = set(resource_ids)
        if len(resource_ids) != len(known_ids):
            raise ValueError("resource IDs must be unique")

        missing = sorted(
            {
                dependency
                for resource in self.resources
                for dependency in resource.depends_on
                if dependency not in known_ids
            }
        )
        if missing:
            raise ValueError(f"unknown resource dependencies: {', '.join(missing)}")
        return self
