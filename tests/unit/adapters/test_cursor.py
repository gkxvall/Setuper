"""Tests for recency-based Cursor workspace detection."""

from pathlib import Path

import pytest

from setuper.adapters.base import CaptureContext, DetectedResource
from setuper.adapters.cursor import CursorAdapter
from setuper.domain.enums import CaptureSupport, Platform
from setuper.domain.errors import ManifestValidationError, UnsupportedPlatformError


class FakeWorkspaceStorageReader:
    """Storage reader returning one configured parsed document."""

    def __init__(self, storage: object | None) -> None:
        self._storage = storage

    def read(self) -> object | None:
        """Return the configured storage document."""
        return self._storage


def make_context(platform: Platform = Platform.MACOS) -> CaptureContext:
    """Create a deterministic capture context."""
    return CaptureContext(platform=platform, current_directory=Path("/repo"))


def test_cursor_detection_reports_only_existing_workspaces(tmp_path: Path) -> None:
    """Only workspaces still present on disk are reported."""
    existing = tmp_path / "project-one"
    existing.mkdir()
    storage = {"openedPathsList": {"entries": [{"folderUri": f"file://{existing}"}]}}
    adapter = CursorAdapter(FakeWorkspaceStorageReader(storage))

    findings = adapter.detect(make_context())

    assert len(findings) == 1
    finding = findings[0]
    assert finding.support is CaptureSupport.PARTIALLY_SUPPORTED
    assert finding.config == {"workspace_path": str(existing)}

    resource = adapter.capture(finding)
    assert resource.id == "cursor-project-one"
    assert resource.type == "cursor"


def test_cursor_detection_handles_unreadable_storage() -> None:
    """Missing or unparsable storage yields no findings."""
    assert CursorAdapter(FakeWorkspaceStorageReader(None)).detect(make_context()) == []


def test_cursor_detection_rejects_unsupported_platform() -> None:
    """Cursor capture stays within the documented macOS v1 scope."""
    adapter = CursorAdapter(FakeWorkspaceStorageReader({}))

    with pytest.raises(UnsupportedPlatformError):
        adapter.detect(make_context(Platform.LINUX))


def test_cursor_capture_rejects_foreign_type() -> None:
    """Capture rejects findings produced by a different adapter."""
    adapter = CursorAdapter(FakeWorkspaceStorageReader({}))
    foreign = DetectedResource(
        identity="git:/repo",
        type_name="git",
        display_name="repo",
        support=CaptureSupport.MACHINE_BOUND,
    )

    with pytest.raises(ManifestValidationError):
        adapter.capture(foreign)
