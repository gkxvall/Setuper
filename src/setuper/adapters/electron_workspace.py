"""Shared recency-based workspace detection for Electron-based editors.

These editors expose no public API to enumerate currently open windows, so
detection reads each editor's recently opened workspace storage as an honest
proxy: only entries that still exist on disk are reported, and every finding
carries an explicit warning that this is recency, not a live window list.
"""

import json
from pathlib import Path
from typing import Protocol, cast
from urllib.parse import unquote, urlparse

from pydantic import JsonValue

from setuper.adapters.base import (
    BaseResourceAdapter,
    CaptureContext,
    DetectedResource,
)
from setuper.adapters.identity import resource_slug
from setuper.domain.enums import CaptureSupport, Platform
from setuper.domain.errors import ManifestValidationError, UnsupportedPlatformError
from setuper.domain.models import ResourceSpec

MAX_WORKSPACES = 5
RECENCY_WARNING = (
    "Recently opened workspace; currently open editor windows cannot be "
    "enumerated on this platform."
)
MACHINE_BOUND_WARNING = "Workspace path is machine-bound."


class WorkspaceStorageReader(Protocol):
    """Workspace storage source replaceable by deterministic fakes."""

    def read(self) -> JsonValue | None:
        """Return parsed workspace storage, or None if unavailable."""


class JsonFileWorkspaceStorageReader:
    """Read an editor's workspace storage JSON file directly from disk."""

    def __init__(self, storage_path: Path) -> None:
        """Create a reader bound to one storage file path."""
        self._storage_path = storage_path

    def read(self) -> JsonValue | None:
        """Return parsed storage content, or None if unreadable."""
        try:
            text = self._storage_path.read_text(encoding="utf-8")
        except OSError:
            return None
        try:
            return cast(JsonValue, json.loads(text))
        except json.JSONDecodeError:
            return None


class ElectronWorkspaceAdapter(BaseResourceAdapter):
    """Detect reachable recently opened workspaces for one editor."""

    type_name = ""
    display_label = ""

    def __init__(self, reader: WorkspaceStorageReader) -> None:
        """Create an editor adapter with an injectable storage reader."""
        self._reader = reader

    def detect(self, context: CaptureContext) -> list[DetectedResource]:
        """Detect recently opened workspaces that still exist on disk."""
        if context.platform is not Platform.MACOS:
            raise UnsupportedPlatformError(
                f"{self.display_label} detection is unsupported on: "
                f"{context.platform.value}",
                details={"platform": context.platform.value},
            )
        storage = self._reader.read()
        if storage is None:
            return []
        findings: list[DetectedResource] = []
        for path in _extract_workspace_paths(storage)[:MAX_WORKSPACES]:
            if not path.exists():
                continue
            findings.append(
                DetectedResource(
                    identity=f"{self.type_name}:{path}",
                    type_name=self.type_name,
                    display_name=path.name or str(path),
                    support=CaptureSupport.PARTIALLY_SUPPORTED,
                    config={"workspace_path": str(path)},
                    metadata={"capture_source": self.type_name},
                    warnings=(RECENCY_WARNING, MACHINE_BOUND_WARNING),
                )
            )
        return sorted(findings, key=lambda finding: finding.identity)

    def capture(self, resource: DetectedResource) -> ResourceSpec:
        """Convert one workspace finding into a review-required resource."""
        if resource.type_name != self.type_name:
            raise ManifestValidationError(
                f"{self.display_label} adapter cannot capture type: "
                f"{resource.type_name}",
                details={"type": resource.type_name},
            )
        workspace_path = resource.config.get("workspace_path")
        if not isinstance(workspace_path, str) or not workspace_path:
            raise ManifestValidationError(
                f"Detected {self.display_label} workspace is missing its path",
            )
        metadata: dict[str, JsonValue] = dict(resource.metadata)
        metadata["capture_support"] = resource.support.value
        metadata["capture_warnings"] = list(resource.warnings)
        slug = resource_slug(Path(workspace_path).name, fallback="workspace")
        return ResourceSpec(
            id=f"{self.type_name}-{slug}",
            type=self.type_name,
            description=resource.display_name,
            config=dict(resource.config),
            metadata=metadata,
        )


def _extract_workspace_paths(node: JsonValue) -> list[Path]:
    """Recursively collect unique, decoded `file://` workspace paths."""
    uris: list[str] = []
    _collect_file_uris(node, uris)
    seen: set[str] = set()
    paths: list[Path] = []
    for uri in uris:
        if uri in seen:
            continue
        seen.add(uri)
        path = _file_uri_to_path(uri)
        if path is not None:
            paths.append(path)
    return paths


def _collect_file_uris(node: JsonValue, sink: list[str]) -> None:
    """Walk arbitrary storage JSON collecting URI- or path-named `file://` values."""
    if isinstance(node, dict):
        for key, value in node.items():
            if (
                isinstance(value, str)
                and value.startswith("file://")
                and _is_uri_key(key)
            ):
                sink.append(value)
            else:
                _collect_file_uris(value, sink)
    elif isinstance(node, list):
        for item in node:
            _collect_file_uris(item, sink)


def _is_uri_key(key: str) -> bool:
    """Return whether a key name plausibly holds a workspace URI."""
    lowered = key.lower()
    return "uri" in lowered or "path" in lowered


def _file_uri_to_path(uri: str) -> Path | None:
    """Decode a `file://` URI into a local filesystem path."""
    parsed = urlparse(uri)
    if parsed.scheme != "file" or not parsed.path:
        return None
    return Path(unquote(parsed.path))
