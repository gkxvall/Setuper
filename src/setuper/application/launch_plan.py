"""Build a fully resolved, per-resource-validated, not-yet-executed launch plan."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import cast
from uuid import UUID

from pydantic import JsonValue

from setuper.adapters.base import ValidationContext
from setuper.adapters.registry import AdapterRegistry
from setuper.domain.enums import Platform
from setuper.domain.errors import AdapterUnavailableError
from setuper.domain.graph import DependencyGraph, build_dependency_graph
from setuper.domain.models import ResourceSpec, SetupManifest
from setuper.domain.readiness import ReadinessSpec, parse_readiness_spec
from setuper.domain.variables import (
    interpolate,
    resolve_profile_overrides,
    resolve_variable_values,
)


@dataclass(frozen=True, slots=True)
class PlannedResource:
    """One resource with variables resolved, ready to validate and launch."""

    spec: ResourceSpec
    readiness: ReadinessSpec | None
    validation_error: str | None = None


@dataclass(frozen=True, slots=True)
class LaunchPlan:
    """A fully resolved launch: every resource interpolated, graphed, and validated."""

    setup_id: UUID
    manifest_hash: str
    profile: str | None
    graph: DependencyGraph
    resources: tuple[PlannedResource, ...]

    def resource(self, resource_id: str) -> PlannedResource:
        """Return one planned resource by ID."""
        for planned in self.resources:
            if planned.spec.id == resource_id:
                return planned
        raise KeyError(resource_id)


def build_launch_plan(
    manifest: SetupManifest,
    *,
    setup_id: UUID,
    manifest_hash: str,
    registry: AdapterRegistry,
    profile: str | None = None,
    only: Sequence[str] = (),
    skip: Sequence[str] = (),
    variable_overrides: Mapping[str, JsonValue] | None = None,
    platform: Platform = Platform.MACOS,
) -> LaunchPlan:
    """Filter, resolve variables for, validate, and graph a launch plan.

    Manifest-authoring problems (an unknown profile, a missing required
    variable, a reference to an undeclared variable, an unparseable
    `ready_when`, or a dependency cycle) raise immediately: they apply
    regardless of which adapters are available and the user must fix the
    manifest before any resource can run. A resource-specific validation
    problem (the adapter doesn't support validation yet, or reports the
    resource itself as invalid) is instead recorded on that resource alone,
    so unrelated resources can still be planned and launched.
    """
    selected = _select_resources(manifest.resources, only=only, skip=skip)

    overrides = dict(resolve_profile_overrides(manifest.profiles, profile))
    if variable_overrides:
        overrides.update(variable_overrides)
    values = resolve_variable_values(manifest.variables, overrides)

    context = ValidationContext(platform=platform)
    planned: list[PlannedResource] = []
    for resource in selected:
        interpolated_config = cast(
            dict[str, JsonValue],
            interpolate(dict(resource.config), values),
        )
        interpolated_env = {
            key: cast(str, interpolate(value, values))
            for key, value in resource.env.items()
        }
        readiness = parse_readiness_spec(resource.ready_when)
        interpolated_spec = resource.model_copy(
            update={"config": interpolated_config, "env": interpolated_env}
        )
        planned.append(
            PlannedResource(
                spec=interpolated_spec,
                readiness=readiness,
                validation_error=_validate_resource(
                    interpolated_spec, registry, context
                ),
            )
        )

    graph = build_dependency_graph(tuple(resource.spec for resource in planned))
    return LaunchPlan(
        setup_id=setup_id,
        manifest_hash=manifest_hash,
        profile=profile,
        graph=graph,
        resources=tuple(planned),
    )


def _select_resources(
    resources: Sequence[ResourceSpec],
    *,
    only: Sequence[str],
    skip: Sequence[str],
) -> tuple[ResourceSpec, ...]:
    """Apply enabled, --only, and --skip filtering to manifest resources."""
    only_ids = set(only)
    skip_ids = set(skip)
    selected = tuple(resource for resource in resources if resource.enabled)
    if only_ids:
        selected = tuple(resource for resource in selected if resource.id in only_ids)
    if not skip_ids:
        return selected
    return tuple(resource for resource in selected if resource.id not in skip_ids)


def _validate_resource(
    spec: ResourceSpec,
    registry: AdapterRegistry,
    context: ValidationContext,
) -> str | None:
    """Validate one resource, capturing any issue instead of aborting planning."""
    try:
        adapter = registry.get(spec.type)
        result = adapter.validate(spec, context)
    except AdapterUnavailableError as error:
        return error.message
    if not result.valid:
        return "; ".join(result.errors) or "validation failed"
    return None
