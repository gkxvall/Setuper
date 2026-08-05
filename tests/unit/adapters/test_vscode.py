"""Tests for recency-based VS Code workspace detection."""

from pathlib import Path

import pytest

from setuper.adapters.base import CaptureContext, DetectedResource
from setuper.adapters.vscode import VSCodeAdapter
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


def test_vscode_detection_reports_only_existing_workspaces(tmp_path: Path) -> None:
    """Only workspaces still present on disk are reported."""
    existing = tmp_path / "project-one"
    existing.mkdir()
    missing = tmp_path / "deleted-project"
    storage = {
        "openedPathsList": {
            "entries": [
                {"folderUri": f"file://{existing}"},
                {"folderUri": f"file://{missing}"},
            ]
        }
    }
    adapter = VSCodeAdapter(FakeWorkspaceStorageReader(storage))

    findings = adapter.detect(make_context())

    assert len(findings) == 1
    finding = findings[0]
    assert finding.support is CaptureSupport.PARTIALLY_SUPPORTED
    assert finding.config == {"workspace_path": str(existing)}
    assert "currently open editor windows cannot be" in " ".join(finding.warnings)

    resource = adapter.capture(finding)
    assert resource.id == "vscode-project-one"
    assert resource.type == "vscode"


def test_vscode_detection_deduplicates_and_caps_recent_entries(tmp_path: Path) -> None:
    """Duplicate URIs collapse and results are capped to a bounded count."""
    directories = [tmp_path / f"project-{index}" for index in range(8)]
    for directory in directories:
        directory.mkdir()
    entries = [{"folderUri": f"file://{directory}"} for directory in directories]
    entries.append(entries[0])
    storage = {"openedPathsList": {"entries": entries}}
    adapter = VSCodeAdapter(FakeWorkspaceStorageReader(storage))

    findings = adapter.detect(make_context())

    assert len(findings) == 5


def test_vscode_detection_handles_unreadable_storage() -> None:
    """Missing or unparsable storage yields no findings."""
    assert VSCodeAdapter(FakeWorkspaceStorageReader(None)).detect(make_context()) == []


def test_vscode_detection_rejects_unsupported_platform() -> None:
    """VS Code capture stays within the documented macOS v1 scope."""
    adapter = VSCodeAdapter(FakeWorkspaceStorageReader({}))

    with pytest.raises(UnsupportedPlatformError):
        adapter.detect(make_context(Platform.LINUX))


def test_vscode_capture_rejects_foreign_type() -> None:
    """Capture rejects findings produced by a different adapter."""
    adapter = VSCodeAdapter(FakeWorkspaceStorageReader({}))
    foreign = DetectedResource(
        identity="git:/repo",
        type_name="git",
        display_name="repo",
        support=CaptureSupport.MACHINE_BOUND,
    )

    with pytest.raises(ManifestValidationError):
        adapter.capture(foreign)
