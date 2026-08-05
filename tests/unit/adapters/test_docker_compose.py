"""Tests for non-destructive Docker Compose project detection."""

import json
from pathlib import Path

import pytest

from setuper.adapters.base import CaptureContext, DetectedResource
from setuper.adapters.docker_compose import DockerComposeAdapter
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


def test_compose_detection_captures_project_with_config_files() -> None:
    """A Compose project with known config files is partially supported."""
    projects = [
        {
            "Name": "myapp",
            "Status": "running(2)",
            "ConfigFiles": "/Users/dev/myapp/docker-compose.yml",
        }
    ]
    runner = FakeCommandRunner(CommandResult(0, json.dumps(projects), ""))
    adapter = DockerComposeAdapter(runner)

    finding = adapter.detect(make_context())[0]

    assert finding.support is CaptureSupport.PARTIALLY_SUPPORTED
    assert finding.config == {
        "project_name": "myapp",
        "status": "running(2)",
        "config_files": ["/Users/dev/myapp/docker-compose.yml"],
    }
    assert "Compose config file paths are machine-bound." in finding.warnings

    resource = adapter.capture(finding)
    assert resource.id == "compose-myapp"
    assert resource.type == "docker_compose"


def test_compose_detection_flags_ambiguity_without_config_files() -> None:
    """A project without a resolvable config file is machine-bound and ambiguous."""
    projects = [{"Name": "myapp", "Status": "running(1)", "ConfigFiles": ""}]
    runner = FakeCommandRunner(CommandResult(0, json.dumps(projects), ""))

    finding = DockerComposeAdapter(runner).detect(make_context())[0]

    assert finding.support is CaptureSupport.MACHINE_BOUND
    assert (
        "Compose project detection is ambiguous without a config file."
        in finding.warnings
    )


def test_compose_detection_handles_no_projects_and_unavailable_plugin() -> None:
    """No active projects and a missing Compose plugin both yield no findings."""
    assert (
        DockerComposeAdapter(FakeCommandRunner(CommandResult(0, "[]", ""))).detect(
            make_context()
        )
        == []
    )
    assert (
        DockerComposeAdapter(
            FakeCommandRunner(CommandResult(1, "", "unknown command"))
        ).detect(make_context())
        == []
    )


def test_compose_detection_rejects_unsupported_platform() -> None:
    """Compose capture stays within the documented macOS v1 scope."""
    adapter = DockerComposeAdapter(FakeCommandRunner(CommandResult(0, "[]", "")))

    with pytest.raises(UnsupportedPlatformError):
        adapter.detect(make_context(Platform.LINUX))


def test_compose_capture_rejects_foreign_type() -> None:
    """Capture rejects findings produced by a different adapter."""
    adapter = DockerComposeAdapter(FakeCommandRunner(CommandResult(0, "[]", "")))
    foreign = DetectedResource(
        identity="git:/repo",
        type_name="git",
        display_name="repo",
        support=CaptureSupport.MACHINE_BOUND,
    )

    with pytest.raises(ManifestValidationError):
        adapter.capture(foreign)
