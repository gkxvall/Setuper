"""Tests for schema-v1 manifest models."""

from uuid import UUID

import pytest
from pydantic import ValidationError

from setuper.domain.enums import Platform, PortConflictPolicy
from setuper.domain.models import ResourceSpec, RetrySpec, SetupManifest


def test_canonical_manifest_shape_is_valid_without_id() -> None:
    """The documented example shape parses without generating an ID."""
    manifest = SetupManifest.model_validate(
        {
            "schema_version": 1,
            "name": "ansade-development",
            "platforms": ["macos"],
            "variables": {"FRONTEND_PORT": {"default": "3000"}},
            "resources": [
                {
                    "id": "frontend",
                    "type": "command",
                    "config": {
                        "cwd": "~/Projects/ANSADE-data-portal",
                        "command": "npm run dev",
                    },
                    "env": {"PORT": "${FRONTEND_PORT}"},
                    "ready_when": {
                        "http": {
                            "url": "http://127.0.0.1:${FRONTEND_PORT}",
                            "expected_status": 200,
                        }
                    },
                }
            ],
        }
    )

    assert manifest.id is None
    assert manifest.platforms == (Platform.MACOS,)
    assert manifest.resources[0].timeout_seconds == 60
    assert manifest.resources[0].on_conflict is PortConflictPolicy.FAIL
    assert manifest.resources[0].config["command"] == "npm run dev"


def test_explicit_manifest_id_is_a_uuid() -> None:
    """Persisted manifests retain their stable UUID."""
    manifest = SetupManifest(
        id="e84b8d08-e05d-49de-a7ab-4e38f919eb89",
        name="workspace",
    )

    assert manifest.id == UUID("e84b8d08-e05d-49de-a7ab-4e38f919eb89")


@pytest.mark.parametrize(
    "payload",
    [
        {"schema_version": 2, "name": "workspace"},
        {"schema_version": "1", "name": "workspace"},
        {"schema_version": 1, "name": "workspace", "unexpected": True},
        {
            "schema_version": 1,
            "name": "workspace",
            "resources": [
                {"id": "invalid_id", "type": "command"},
            ],
        },
        {
            "schema_version": 1,
            "name": "workspace",
            "resources": [
                {"id": "frontend", "type": "command", "unexpected": True},
            ],
        },
    ],
)
def test_invalid_or_unknown_schema_fields_are_rejected(
    payload: dict[str, object],
) -> None:
    """Wrong versions, invalid IDs, and unknown fields fail validation."""
    with pytest.raises(ValidationError):
        SetupManifest.model_validate(payload)


def test_duplicate_and_unknown_dependencies_are_rejected() -> None:
    """Resource identity and dependency references are locally consistent."""
    with pytest.raises(ValidationError, match="resource IDs must be unique"):
        SetupManifest(
            name="workspace",
            resources=[
                ResourceSpec(id="service", type="command"),
                ResourceSpec(id="service", type="browser"),
            ],
        )

    with pytest.raises(ValidationError, match="unknown resource dependencies"):
        SetupManifest(
            name="workspace",
            resources=[
                ResourceSpec(
                    id="frontend",
                    type="command",
                    depends_on=["database"],
                )
            ],
        )

    with pytest.raises(ValidationError, match="must not contain duplicate"):
        ResourceSpec(
            id="frontend",
            type="command",
            depends_on=["database", "database"],
        )


def test_retry_delay_bounds_are_validated() -> None:
    """Retry delays cannot shrink below their initial value."""
    with pytest.raises(ValidationError, match="maximum_delay_seconds"):
        RetrySpec(
            attempts=3,
            initial_delay_seconds=2,
            maximum_delay_seconds=1,
            backoff=2,
        )


def test_manifest_fields_are_frozen() -> None:
    """Validated model fields cannot be reassigned accidentally."""
    manifest = SetupManifest(name="workspace")

    with pytest.raises(ValidationError):
        manifest.name = "changed"
