"""Tests for basic macOS running-application detection."""

from pathlib import Path

import pytest

from setuper.adapters.base import CaptureContext, DetectedResource
from setuper.adapters.macos_app import MacOSAppAdapter
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


def test_macos_app_detection_captures_bundle_identified_applications() -> None:
    """A resolvable bundle identifier is fully supported for relaunch."""
    stdout = "Finder\tcom.apple.finder\nSafari\tcom.apple.Safari\n"
    adapter = MacOSAppAdapter(FakeCommandRunner(CommandResult(0, stdout, "")))

    findings = adapter.detect(make_context())

    assert len(findings) == 2
    finder = next(f for f in findings if f.display_name == "Finder")
    assert finder.support is CaptureSupport.SUPPORTED
    assert finder.config == {"name": "Finder", "bundle_id": "com.apple.finder"}
    assert finder.warnings == ()

    resource = adapter.capture(finder)
    assert resource.id == "macos-app-com-apple-finder"
    assert resource.type == "macos_app"


def test_macos_app_detection_flags_missing_bundle_identifier() -> None:
    """An application without a bundle identifier is partially supported."""
    stdout = "SomeApp\t\n"
    adapter = MacOSAppAdapter(FakeCommandRunner(CommandResult(0, stdout, "")))

    finding = adapter.detect(make_context())[0]

    assert finding.support is CaptureSupport.PARTIALLY_SUPPORTED
    assert finding.config == {"name": "SomeApp"}
    assert "Bundle identifier is unavailable" in finding.warnings[0]

    resource = adapter.capture(finding)
    assert resource.id == "macos-app-someapp"


def test_macos_app_detection_handles_unavailable_automation() -> None:
    """A denied or unavailable System Events query yields no findings."""
    adapter = MacOSAppAdapter(FakeCommandRunner(CommandResult(1, "", "not allowed")))

    assert adapter.detect(make_context()) == []


def test_macos_app_detection_rejects_unsupported_platform() -> None:
    """macOS app capture stays within the documented macOS v1 scope."""
    adapter = MacOSAppAdapter(FakeCommandRunner(CommandResult(0, "", "")))

    with pytest.raises(UnsupportedPlatformError):
        adapter.detect(make_context(Platform.LINUX))


def test_macos_app_capture_rejects_foreign_type() -> None:
    """Capture rejects findings produced by a different adapter."""
    adapter = MacOSAppAdapter(FakeCommandRunner(CommandResult(0, "", "")))
    foreign = DetectedResource(
        identity="git:/repo",
        type_name="git",
        display_name="repo",
        support=CaptureSupport.MACHINE_BOUND,
    )

    with pytest.raises(ManifestValidationError):
        adapter.capture(foreign)
