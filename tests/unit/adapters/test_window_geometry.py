"""Tests for window bounds detection without display or Space data."""

from pathlib import Path

import pytest

from setuper.adapters.base import CaptureContext, DetectedResource
from setuper.adapters.window_geometry import WindowGeometryAdapter
from setuper.domain.enums import CaptureSupport, Platform
from setuper.domain.errors import ManifestValidationError, UnsupportedPlatformError
from setuper.infrastructure.commands import CommandResult


class FakeCommandRunner:
    """Command boundary returning one configured result."""

    def __init__(self, result: CommandResult) -> None:
        self._result = result
        self.calls: list[tuple[str, ...]] = []

    def run(
        self,
        arguments: tuple[str, ...],
        *,
        cwd: Path | None = None,
        timeout_seconds: float = 5.0,
    ) -> CommandResult:
        """Return the configured result and record the call."""
        self.calls.append(arguments)
        return self._result


def make_context(platform: Platform = Platform.MACOS) -> CaptureContext:
    """Create a deterministic capture context."""
    return CaptureContext(platform=platform, current_directory=Path("/repo"))


def test_window_geometry_detection_captures_bounds_without_space_or_display() -> None:
    """Bounds are captured; display identity and Space are never claimed."""
    stdout = "Safari\tcom.apple.Safari\tGitHub\t100\t200\t1200\t800\n"
    adapter = WindowGeometryAdapter(FakeCommandRunner(CommandResult(0, stdout, "")))

    finding = adapter.detect(make_context())[0]

    assert finding.support is CaptureSupport.MACHINE_BOUND
    assert finding.config == {
        "process_name": "Safari",
        "x": 100,
        "y": 200,
        "width": 1200,
        "height": 800,
        "bundle_id": "com.apple.Safari",
        "window_title": "GitHub",
    }
    assert "Display identity and macOS Space are not captured" in " ".join(
        finding.warnings
    )

    resource = adapter.capture(finding)
    assert resource.id == "window-com-apple-safari-github"
    assert resource.type == "window_geometry"


def test_window_geometry_detection_skips_malformed_lines() -> None:
    """Lines with the wrong field count or non-numeric bounds are skipped."""
    stdout = "TooFewFields\ta\tb\nSafari\tcom.apple.Safari\tGitHub\tNaN\t0\t0\t0\n"
    adapter = WindowGeometryAdapter(FakeCommandRunner(CommandResult(0, stdout, "")))

    assert adapter.detect(make_context()) == []


def test_window_geometry_detection_handles_unavailable_automation() -> None:
    """A denied or unavailable System Events query yields no findings."""
    adapter = WindowGeometryAdapter(FakeCommandRunner(CommandResult(1, "", "denied")))

    assert adapter.detect(make_context()) == []


def test_window_geometry_detection_rejects_unsupported_platform() -> None:
    """Window geometry capture stays within the documented macOS v1 scope."""
    adapter = WindowGeometryAdapter(FakeCommandRunner(CommandResult(0, "", "")))

    with pytest.raises(UnsupportedPlatformError):
        adapter.detect(make_context(Platform.LINUX))


def test_window_geometry_capture_rejects_foreign_type() -> None:
    """Capture rejects findings produced by a different adapter."""
    adapter = WindowGeometryAdapter(FakeCommandRunner(CommandResult(0, "", "")))
    foreign = DetectedResource(
        identity="git:/repo",
        type_name="git",
        display_name="repo",
        support=CaptureSupport.MACHINE_BOUND,
    )

    with pytest.raises(ManifestValidationError):
        adapter.capture(foreign)
