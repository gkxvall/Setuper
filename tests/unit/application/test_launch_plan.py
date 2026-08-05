"""Tests for building a fully resolved, per-resource-validated launch plan."""

from uuid import uuid4

import pytest

from setuper.adapters.base import ValidationContext, ValidationResult
from setuper.adapters.registry import AdapterRegistry
from setuper.application.launch_plan import build_launch_plan
from setuper.domain.errors import AdapterUnavailableError, ManifestValidationError
from setuper.domain.models import ResourceSpec, SetupManifest, VariableSpec
from setuper.domain.readiness import TcpReadinessSpec

SETUP_ID = uuid4()
MANIFEST_HASH = "a" * 64


class _FakeAdapter:
    """Adapter stub with a configurable validate() outcome or error."""

    def __init__(
        self,
        type_name: str,
        *,
        result: ValidationResult | None = None,
        error: Exception | None = None,
    ) -> None:
        self.type_name = type_name
        self._result = result or ValidationResult(valid=True)
        self._error = error

    def validate(
        self,
        spec: ResourceSpec,
        context: ValidationContext,
    ) -> ValidationResult:
        """Return the configured result or raise the configured error."""
        if self._error is not None:
            raise self._error
        return self._result


def _resource(
    resource_id: str, resource_type: str = "good", **kwargs: object
) -> ResourceSpec:
    """Build one minimal resource spec of a given type."""
    return ResourceSpec(id=resource_id, type=resource_type, **kwargs)  # type: ignore[arg-type]


def test_build_launch_plan_interpolates_variables_into_config_and_env() -> None:
    """Declared variable defaults are substituted into config and env."""
    manifest = SetupManifest(
        name="demo",
        variables={"PORT": VariableSpec(default="3000")},
        resources=(
            ResourceSpec(
                id="frontend",
                type="good",
                config={"url": "http://127.0.0.1:${PORT}"},
                env={"PORT": "${PORT}"},
            ),
        ),
    )
    registry = AdapterRegistry([_FakeAdapter("good")])

    plan = build_launch_plan(
        manifest,
        setup_id=SETUP_ID,
        manifest_hash=MANIFEST_HASH,
        registry=registry,
    )

    planned = plan.resource("frontend")
    assert planned.spec.config == {"url": "http://127.0.0.1:3000"}
    assert planned.spec.env == {"PORT": "3000"}
    assert planned.validation_error is None


def test_build_launch_plan_applies_only_and_skip_filters() -> None:
    """--only restricts to given IDs; --skip removes given IDs from that set."""
    manifest = SetupManifest(
        name="demo",
        resources=(_resource("a"), _resource("b"), _resource("c")),
    )
    registry = AdapterRegistry([_FakeAdapter("good")])

    plan = build_launch_plan(
        manifest,
        setup_id=SETUP_ID,
        manifest_hash=MANIFEST_HASH,
        registry=registry,
        only=("a", "b"),
        skip=("b",),
    )

    assert [resource.spec.id for resource in plan.resources] == ["a"]


def test_build_launch_plan_excludes_disabled_resources() -> None:
    """A resource with enabled=False is never part of the plan."""
    manifest = SetupManifest(
        name="demo",
        resources=(_resource("a"), _resource("b", enabled=False)),
    )
    registry = AdapterRegistry([_FakeAdapter("good")])

    plan = build_launch_plan(
        manifest,
        setup_id=SETUP_ID,
        manifest_hash=MANIFEST_HASH,
        registry=registry,
    )

    assert [resource.spec.id for resource in plan.resources] == ["a"]


def test_build_launch_plan_uses_profile_overrides() -> None:
    """A named profile's variable overrides take effect during interpolation."""
    manifest = SetupManifest(
        name="demo",
        variables={"PORT": VariableSpec(default="3000")},
        profiles={"dev": {"PORT": "4000"}},
        resources=(_resource("frontend", env={"PORT": "${PORT}"}),),
    )
    registry = AdapterRegistry([_FakeAdapter("good")])

    plan = build_launch_plan(
        manifest,
        setup_id=SETUP_ID,
        manifest_hash=MANIFEST_HASH,
        registry=registry,
        profile="dev",
    )

    assert plan.resource("frontend").spec.env == {"PORT": "4000"}


def test_build_launch_plan_parses_ready_when() -> None:
    """A resource's ready_when body is parsed into a typed readiness spec."""
    manifest = SetupManifest(
        name="demo",
        resources=(
            ResourceSpec(
                id="postgres",
                type="good",
                ready_when={"tcp": {"host": "127.0.0.1", "port": 5432}},
            ),
        ),
    )
    registry = AdapterRegistry([_FakeAdapter("good")])

    plan = build_launch_plan(
        manifest,
        setup_id=SETUP_ID,
        manifest_hash=MANIFEST_HASH,
        registry=registry,
    )

    assert plan.resource("postgres").readiness == TcpReadinessSpec(
        host="127.0.0.1",
        port=5432,
    )


def test_build_launch_plan_isolates_validation_problems_per_resource() -> None:
    """One resource's validation problem never blocks planning the others."""
    manifest = SetupManifest(
        name="demo",
        resources=(
            _resource("ok", "good"),
            _resource("unsupported-type", "unsupported"),
            _resource("invalid", "bad"),
        ),
    )
    registry = AdapterRegistry(
        [
            _FakeAdapter("good"),
            _FakeAdapter(
                "unsupported",
                error=AdapterUnavailableError("does not support validate"),
            ),
            _FakeAdapter(
                "bad", result=ValidationResult(valid=False, errors=("bad config",))
            ),
        ]
    )

    plan = build_launch_plan(
        manifest,
        setup_id=SETUP_ID,
        manifest_hash=MANIFEST_HASH,
        registry=registry,
    )

    assert plan.resource("ok").validation_error is None
    assert (
        plan.resource("unsupported-type").validation_error
        == "does not support validate"
    )
    assert plan.resource("invalid").validation_error == "bad config"


def test_build_launch_plan_rejects_missing_required_variable() -> None:
    """A required variable without a default or override aborts planning."""
    manifest = SetupManifest(
        name="demo",
        variables={"API_KEY": VariableSpec(required=True)},
        resources=(_resource("a"),),
    )
    registry = AdapterRegistry([_FakeAdapter("good")])

    with pytest.raises(ManifestValidationError, match="API_KEY"):
        build_launch_plan(
            manifest,
            setup_id=SETUP_ID,
            manifest_hash=MANIFEST_HASH,
            registry=registry,
        )


def test_build_launch_plan_rejects_unknown_profile() -> None:
    """Requesting an undeclared profile aborts planning."""
    manifest = SetupManifest(name="demo", resources=(_resource("a"),))
    registry = AdapterRegistry([_FakeAdapter("good")])

    with pytest.raises(ManifestValidationError, match="staging"):
        build_launch_plan(
            manifest,
            setup_id=SETUP_ID,
            manifest_hash=MANIFEST_HASH,
            registry=registry,
            profile="staging",
        )


def test_build_launch_plan_rejects_dependency_left_dangling_by_only_filter() -> None:
    """--only leaving a dependency out of the plan aborts planning."""
    manifest = SetupManifest(
        name="demo",
        resources=(
            _resource("postgres"),
            _resource("frontend", depends_on=("postgres",)),
        ),
    )
    registry = AdapterRegistry([_FakeAdapter("good")])

    with pytest.raises(ManifestValidationError, match="postgres"):
        build_launch_plan(
            manifest,
            setup_id=SETUP_ID,
            manifest_hash=MANIFEST_HASH,
            registry=registry,
            only=("frontend",),
        )
