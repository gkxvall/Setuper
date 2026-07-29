"""Integration tests for YAML manifest persistence."""

from pathlib import Path

import pytest

from setuper.domain.errors import ManifestIOError, ManifestValidationError
from setuper.domain.models import ResourceSpec, SetupManifest
from setuper.infrastructure.manifests import load_manifest, save_manifest


def test_manifest_round_trip_is_readable_and_deterministic(tmp_path: Path) -> None:
    """Unicode and paths with spaces survive deterministic YAML persistence."""
    manifest_path = tmp_path / "setups with spaces" / "développement.yaml"
    manifest = SetupManifest(
        name="développement",
        description="Éditeur et services",
        resources=[
            ResourceSpec(
                id="editor",
                type="vscode",
                config={"paths": ["/tmp/Project With Spaces"]},
            )
        ],
    )

    save_manifest(manifest_path, manifest)
    first_contents = manifest_path.read_text(encoding="utf-8")
    save_manifest(manifest_path, manifest)

    assert load_manifest(manifest_path) == manifest
    assert manifest_path.read_text(encoding="utf-8") == first_contents
    assert "développement" in first_contents
    assert "!!python" not in first_contents


@pytest.mark.parametrize(
    "contents",
    [
        "schema_version: [",
        "schema_version: 2\nname: workspace\n",
        "!!python/object/apply:os.system [['echo', 'unsafe']]\n",
    ],
)
def test_invalid_or_unsafe_yaml_is_a_typed_validation_error(
    tmp_path: Path,
    contents: str,
) -> None:
    """Syntax, schema, and unsafe constructor input never escape raw errors."""
    manifest_path = tmp_path / "invalid.yaml"
    manifest_path.write_text(contents, encoding="utf-8")

    with pytest.raises(ManifestValidationError) as raised:
        load_manifest(manifest_path)

    assert raised.value.details["path"] == str(manifest_path)


def test_schema_error_details_are_structured_and_do_not_echo_input(
    tmp_path: Path,
) -> None:
    """Validation diagnostics expose locations without copying input values."""
    manifest_path = tmp_path / "invalid.yaml"
    manifest_path.write_text(
        "schema_version: 1\nname: workspace\nunexpected: super-secret-value\n",
        encoding="utf-8",
    )

    with pytest.raises(ManifestValidationError) as raised:
        load_manifest(manifest_path)

    assert raised.value.details["issues"] == [
        {
            "location": "unexpected",
            "message": "Extra inputs are not permitted",
            "type": "extra_forbidden",
        }
    ]
    assert "super-secret-value" not in str(raised.value.details)


def test_failed_atomic_replace_preserves_existing_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A replacement failure leaves the prior manifest and no temp file."""
    manifest_path = tmp_path / "workspace.yaml"
    manifest_path.write_text("existing contents\n", encoding="utf-8")

    def fail_replace(source: Path, destination: Path) -> None:
        raise OSError("simulated replacement failure")

    monkeypatch.setattr("setuper.infrastructure.manifests.os.replace", fail_replace)

    with pytest.raises(ManifestIOError):
        save_manifest(manifest_path, SetupManifest(name="workspace"))

    assert manifest_path.read_text(encoding="utf-8") == "existing contents\n"
    assert list(tmp_path.glob(".workspace.yaml.*.tmp")) == []


def test_missing_manifest_is_a_typed_io_error(tmp_path: Path) -> None:
    """Filesystem failures do not leak raw operating-system exceptions."""
    missing_path = tmp_path / "missing.yaml"

    with pytest.raises(ManifestIOError) as raised:
        load_manifest(missing_path)

    assert raised.value.details == {"path": str(missing_path)}
