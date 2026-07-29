"""Tests for stable domain enum values."""

from setuper.domain.enums import (
    ApprovalScope,
    CaptureSupport,
    ExitCode,
    LaunchStatus,
    Platform,
    PortConflictPolicy,
    ResourceRunStatus,
    SetupSource,
)


def enum_values(enum_type: type) -> set[str | int]:
    """Return the serialized values declared by an enum."""
    return {item.value for item in enum_type}


def test_platform_and_capture_values_match_schema_v1() -> None:
    """Platform and support values remain stable for manifest serialization."""
    assert enum_values(Platform) == {"macos", "linux", "windows"}
    assert enum_values(CaptureSupport) == {
        "supported",
        "partially_supported",
        "machine_bound",
        "sensitive",
        "unsupported",
    }


def test_runtime_status_values_cover_documented_state_machines() -> None:
    """Runtime enums include every documented launch and resource state."""
    assert enum_values(ResourceRunStatus) == {
        "pending",
        "validating",
        "starting",
        "running",
        "ready",
        "skipped",
        "blocked",
        "failed",
        "stopping",
        "stopped",
    }
    assert enum_values(LaunchStatus) == {
        "starting",
        "running",
        "partial",
        "failed",
        "stopped",
    }


def test_policy_and_persistence_values_are_stable() -> None:
    """Policy, source, and approval enums match their persisted spellings."""
    assert enum_values(PortConflictPolicy) == {
        "fail",
        "reuse",
        "stop_owned",
        "increment",
    }
    assert enum_values(SetupSource) == {"local", "project", "imported"}
    assert enum_values(ApprovalScope) == {"local-machine"}


def test_exit_codes_match_cli_contract() -> None:
    """Every documented exit code keeps its public numeric value."""
    assert [exit_code.value for exit_code in ExitCode] == list(range(11))
