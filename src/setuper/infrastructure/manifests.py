"""YAML manifest loading and atomic persistence."""

import os
import tempfile
from pathlib import Path

import yaml
from pydantic import ValidationError

from setuper.domain.errors import ManifestIOError, ManifestValidationError
from setuper.domain.models import SetupManifest


def load_manifest(path: Path) -> SetupManifest:
    """Load and validate one UTF-8 YAML manifest."""
    try:
        serialized = path.read_text(encoding="utf-8")
    except OSError as error:
        raise ManifestIOError(
            f"Could not read manifest: {path}",
            details={"path": str(path)},
        ) from error

    try:
        payload = yaml.safe_load(serialized)
    except yaml.YAMLError as error:
        raise ManifestValidationError(
            f"Invalid YAML manifest: {path}",
            details={"path": str(path)},
        ) from error

    try:
        return SetupManifest.model_validate(payload)
    except ValidationError as error:
        issues = [
            {
                "location": ".".join(str(part) for part in issue["loc"]),
                "message": issue["msg"],
                "type": issue["type"],
            }
            for issue in error.errors(
                include_url=False,
                include_context=False,
                include_input=False,
            )
        ]
        raise ManifestValidationError(
            f"Manifest schema validation failed: {path}",
            details={"path": str(path), "issues": issues},
        ) from error


def save_manifest(path: Path, manifest: SetupManifest) -> None:
    """Atomically save one validated manifest as readable UTF-8 YAML."""
    parent = path.parent
    temporary_path: Path | None = None
    try:
        parent.mkdir(parents=True, exist_ok=True)
        serialized = yaml.safe_dump(
            manifest.model_dump(mode="json", exclude_none=True),
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
        )
        file_descriptor, temporary_name = tempfile.mkstemp(
            dir=parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            text=True,
        )
        temporary_path = Path(temporary_name)
        with os.fdopen(file_descriptor, "w", encoding="utf-8") as temporary_file:
            temporary_file.write(serialized)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_path, path)
        temporary_path = None
        _sync_directory(parent)
    except OSError as error:
        raise ManifestIOError(
            f"Could not save manifest: {path}",
            details={"path": str(path)},
        ) from error
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def _sync_directory(directory: Path) -> None:
    """Persist a directory entry update where the platform permits it."""
    directory_descriptor = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(directory_descriptor)
    finally:
        os.close(directory_descriptor)
