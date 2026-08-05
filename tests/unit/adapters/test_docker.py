"""Tests for non-destructive Docker container detection."""

import json
from pathlib import Path

import pytest

from setuper.adapters.base import CaptureContext
from setuper.adapters.docker import DockerAdapter
from setuper.domain.enums import CaptureSupport, Platform
from setuper.domain.errors import ManifestValidationError, UnsupportedPlatformError
from setuper.infrastructure.commands import CommandResult


class FakeCommandRunner:
    """Command boundary returning results keyed by the Docker subcommand."""

    def __init__(self, results: dict[str, CommandResult]) -> None:
        self._results = results
        self.calls: list[tuple[str, ...]] = []

    def run(
        self,
        arguments: tuple[str, ...],
        *,
        cwd: Path | None = None,
        timeout_seconds: float = 5.0,
    ) -> CommandResult:
        """Return a configured result for the Docker subcommand token."""
        self.calls.append(arguments)
        subcommand = arguments[1] if len(arguments) > 1 else ""
        return self._results.get(subcommand, CommandResult(1, "", ""))


def make_context(platform: Platform = Platform.MACOS) -> CaptureContext:
    """Create a deterministic capture context."""
    return CaptureContext(platform=platform, current_directory=Path("/repo"))


CONTAINER = {
    "Id": "a" * 64,
    "Name": "/web",
    "Config": {
        "Image": "nginx:latest",
        "Cmd": ["nginx", "-g", "daemon off;"],
        "WorkingDir": "/usr/share/nginx",
        "Env": ["PATH=/usr/bin", "API_TOKEN=super-secret"],
    },
    "NetworkSettings": {
        "Ports": {
            "80/tcp": [{"HostIp": "0.0.0.0", "HostPort": "8080"}],
            "443/tcp": None,
        }
    },
    "Mounts": [
        {
            "Type": "bind",
            "Source": "/Users/dev/site",
            "Destination": "/usr/share/nginx/html",
            "Mode": "rw",
            "RW": True,
        }
    ],
}


def test_docker_detection_captures_container_state_without_env_values() -> None:
    """Docker findings expose restart-relevant config without secret values."""
    runner = FakeCommandRunner(
        {
            "ps": CommandResult(0, f"{CONTAINER['Id']}\n", ""),
            "inspect": CommandResult(0, json.dumps([CONTAINER]), ""),
        }
    )
    adapter = DockerAdapter(runner)

    finding = adapter.detect(make_context())[0]

    assert finding.support is CaptureSupport.PARTIALLY_SUPPORTED
    assert finding.config["container_id"] == CONTAINER["Id"][:12]
    assert finding.config["container_name"] == "web"
    assert finding.config["image"] == "nginx:latest"
    assert finding.config["env_names"] == ["API_TOKEN", "PATH"]
    assert "super-secret" not in str(finding.config)
    assert finding.config["ports"] == [
        {"container_port": 443, "protocol": "tcp"},
        {
            "container_port": 80,
            "protocol": "tcp",
            "host_ip": "0.0.0.0",
            "host_port": 8080,
        },
    ]
    assert finding.config["mounts"] == [
        {
            "type": "bind",
            "source": "/Users/dev/site",
            "destination": "/usr/share/nginx/html",
            "mode": "rw",
            "read_write": True,
        }
    ]
    assert "Mount source paths are machine-bound." in finding.warnings

    resource = adapter.capture(finding)
    assert resource.id == "docker-web"
    assert resource.type == "docker"


def test_docker_detection_handles_no_containers_and_daemon_unavailable() -> None:
    """No running containers and an unreachable daemon both yield no findings."""
    assert (
        DockerAdapter(FakeCommandRunner({"ps": CommandResult(0, "", "")})).detect(
            make_context()
        )
        == []
    )
    assert (
        DockerAdapter(
            FakeCommandRunner({"ps": CommandResult(1, "", "daemon not running")})
        ).detect(make_context())
        == []
    )


def test_docker_detection_skips_containers_missing_an_image() -> None:
    """A container without a resolvable image is marked unsupported."""
    incomplete = {"Id": "b" * 64, "Name": "/broken", "Config": {}}
    runner = FakeCommandRunner(
        {
            "ps": CommandResult(0, f"{incomplete['Id']}\n", ""),
            "inspect": CommandResult(0, json.dumps([incomplete]), ""),
        }
    )

    finding = DockerAdapter(runner).detect(make_context())[0]

    assert finding.support is CaptureSupport.UNSUPPORTED


def test_docker_detection_rejects_unsupported_platform() -> None:
    """Docker capture stays within the documented macOS v1 scope."""
    adapter = DockerAdapter(FakeCommandRunner({}))

    with pytest.raises(UnsupportedPlatformError):
        adapter.detect(make_context(Platform.LINUX))


def test_docker_capture_rejects_foreign_type() -> None:
    """Capture rejects findings produced by a different adapter."""
    from setuper.adapters.base import DetectedResource

    adapter = DockerAdapter(FakeCommandRunner({}))
    foreign = DetectedResource(
        identity="git:/repo",
        type_name="git",
        display_name="repo",
        support=CaptureSupport.MACHINE_BOUND,
    )

    with pytest.raises(ManifestValidationError):
        adapter.capture(foreign)
