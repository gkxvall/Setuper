"""Tests for safe process detection and capture."""

from pathlib import Path

import pytest

from setuper.adapters import process
from setuper.adapters.base import CaptureContext, DetectedResource
from setuper.adapters.ports import ListeningPort, PortDetectionResult
from setuper.adapters.process import (
    ProcessAdapter,
    ProcessSnapshot,
    PsutilProcessProvider,
)
from setuper.domain.enums import CaptureSupport, Platform
from setuper.domain.errors import ManifestValidationError, UnsupportedPlatformError


class FakeProcessProvider:
    """Deterministic process source that never reads the host machine."""

    def __init__(self, snapshots: tuple[ProcessSnapshot, ...]) -> None:
        self._snapshots = snapshots

    def iter_processes(self) -> tuple[ProcessSnapshot, ...]:
        """Return configured snapshots."""
        return self._snapshots


class FakePortProvider:
    """Deterministic listener source."""

    def __init__(
        self,
        listeners: tuple[ListeningPort, ...] = (),
        warnings: tuple[str, ...] = (),
    ) -> None:
        self._result = PortDetectionResult(
            listeners=listeners,
            warnings=warnings,
        )

    def detect_listeners(self) -> PortDetectionResult:
        """Return configured listener detection."""
        return self._result


def make_snapshot(
    pid: int,
    *,
    username: str = "developer",
    executable: str | None = "/usr/local/bin/server",
    arguments: tuple[str, ...] = ("server", "--port", "3000"),
) -> ProcessSnapshot:
    """Build a deterministic process snapshot."""
    return ProcessSnapshot(
        pid=pid,
        parent_pid=1,
        name="server",
        executable=executable,
        arguments=arguments,
        working_directory="/tmp/Project With Spaces",
        create_time=100.5,
        username=username,
    )


def test_process_detection_scopes_user_and_redacts_credentials() -> None:
    """Detection excludes other users and never retains credential flag values."""
    adapter = ProcessAdapter(
        FakeProcessProvider(
            (
                make_snapshot(
                    20,
                    arguments=(
                        "server",
                        "--token",
                        "literal-secret",
                        "--password=hunter2",
                    ),
                ),
                make_snapshot(10, username="root"),
                make_snapshot(30),
            )
        ),
        port_provider=FakePortProvider(
            listeners=(
                ListeningPort(
                    pid=20,
                    host="127.0.0.1",
                    port=3000,
                    address_family="ipv4",
                ),
            )
        ),
        current_username="developer",
        own_pid=30,
    )

    findings = adapter.detect(
        CaptureContext(
            platform=Platform.MACOS,
            current_directory=Path("/tmp"),
        )
    )

    assert len(findings) == 1
    finding = findings[0]
    assert finding.identity == "process:20:100.5"
    assert finding.support is CaptureSupport.PARTIALLY_SUPPORTED
    assert finding.config["arguments"] == [
        "server",
        "--token",
        "<redacted>",
        "--password=<redacted>",
    ]
    assert "literal-secret" not in str(finding.config)
    assert "hunter2" not in str(finding.config)
    assert finding.config["listening_ports"] == [
        {
            "host": "127.0.0.1",
            "port": 3000,
            "address_family": "ipv4",
            "protocol": "tcp",
        }
    ]
    assert any("cannot be restored" in warning for warning in finding.warnings)


def test_process_without_executable_is_honestly_unsupported() -> None:
    """Missing executable metadata is surfaced instead of guessed."""
    adapter = ProcessAdapter(
        FakeProcessProvider((make_snapshot(20, executable=None),)),
        port_provider=FakePortProvider(
            warnings=("Listening-port detection unavailable.",)
        ),
        current_username="developer",
        own_pid=30,
    )

    finding = adapter.detect(
        CaptureContext(
            platform=Platform.MACOS,
            current_directory=Path("/tmp"),
        )
    )[0]

    assert finding.support is CaptureSupport.UNSUPPORTED
    assert "executable" not in finding.config
    assert "Executable path is unavailable." in finding.warnings
    assert "Listening-port detection unavailable." in finding.warnings


def test_process_capture_produces_review_required_resource() -> None:
    """Capture preserves redacted semantic metadata and support limitations."""
    adapter = ProcessAdapter(
        FakeProcessProvider((make_snapshot(20),)),
        port_provider=FakePortProvider(),
        current_username="developer",
        own_pid=30,
    )
    finding = adapter.detect(
        CaptureContext(
            platform=Platform.MACOS,
            current_directory=Path("/tmp"),
        )
    )[0]

    resource = adapter.capture(finding)

    assert resource.id == "process-20"
    assert resource.type == "process"
    assert resource.metadata["capture_support"] == "partially_supported"
    assert resource.config["cwd"] == "/tmp/Project With Spaces"


def test_process_capture_rejects_foreign_finding() -> None:
    """Adapters cannot silently capture another adapter's finding."""
    adapter = ProcessAdapter(
        FakeProcessProvider(()),
        port_provider=FakePortProvider(),
        current_username="developer",
        own_pid=30,
    )
    finding = DetectedResource(
        identity="git:/tmp",
        type_name="git",
        display_name="repo",
        support=CaptureSupport.SUPPORTED,
    )

    with pytest.raises(ManifestValidationError):
        adapter.capture(finding)


def test_process_detection_rejects_unsupported_platform() -> None:
    """Platform abstractions do not imply undocumented production support."""
    adapter = ProcessAdapter(
        FakeProcessProvider(()),
        port_provider=FakePortProvider(),
        current_username="developer",
        own_pid=30,
    )

    with pytest.raises(UnsupportedPlatformError):
        adapter.detect(
            CaptureContext(
                platform=Platform.LINUX,
                current_directory=Path("/tmp"),
            )
        )


def test_psutil_provider_skips_races_and_normalizes_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The real provider boundary tolerates vanished or inaccessible processes."""

    class AccessibleProcess:
        @property
        def info(self) -> dict[str, object]:
            return {
                "pid": 20,
                "ppid": 1,
                "name": "server",
                "exe": Path("/usr/local/bin/server"),
                "cmdline": ["server", "--port", 3000],
                "cwd": Path("/tmp/project"),
                "create_time": 100,
                "username": "developer",
            }

    class VanishedProcess:
        @property
        def info(self) -> dict[str, object]:
            raise process.psutil.NoSuchProcess(99)

    monkeypatch.setattr(
        process.psutil,
        "process_iter",
        lambda attributes, ad_value: [VanishedProcess(), AccessibleProcess()],
    )

    snapshots = list(PsutilProcessProvider().iter_processes())

    assert snapshots == [
        ProcessSnapshot(
            pid=20,
            parent_pid=1,
            name="server",
            executable="/usr/local/bin/server",
            arguments=("server", "--port", "3000"),
            working_directory="/tmp/project",
            create_time=100.0,
            username="developer",
        )
    ]
