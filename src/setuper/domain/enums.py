"""Enumerations shared by Setuper's domain model."""

from enum import IntEnum, StrEnum


class Platform(StrEnum):
    """Platforms understood by schema version 1."""

    MACOS = "macos"
    LINUX = "linux"
    WINDOWS = "windows"


class CaptureSupport(StrEnum):
    """Portability and capture support assigned to a detected resource."""

    SUPPORTED = "supported"
    PARTIALLY_SUPPORTED = "partially_supported"
    MACHINE_BOUND = "machine_bound"
    SENSITIVE = "sensitive"
    UNSUPPORTED = "unsupported"


class ResourceRunStatus(StrEnum):
    """Lifecycle states for one resource in a launch."""

    PENDING = "pending"
    VALIDATING = "validating"
    STARTING = "starting"
    RUNNING = "running"
    READY = "ready"
    SKIPPED = "skipped"
    BLOCKED = "blocked"
    FAILED = "failed"
    STOPPING = "stopping"
    STOPPED = "stopped"


class LaunchStatus(StrEnum):
    """Lifecycle states for an aggregate launch."""

    STARTING = "starting"
    RUNNING = "running"
    PARTIAL = "partial"
    FAILED = "failed"
    STOPPED = "stopped"


class PortConflictPolicy(StrEnum):
    """Allowed behavior when a desired port is already occupied."""

    FAIL = "fail"
    REUSE = "reuse"
    STOP_OWNED = "stop_owned"
    INCREMENT = "increment"


class SetupSource(StrEnum):
    """Origin of a stored setup manifest."""

    LOCAL = "local"
    PROJECT = "project"
    IMPORTED = "imported"


class ApprovalScope(StrEnum):
    """Scope attached to a trust approval."""

    LOCAL_MACHINE = "local-machine"


class ExitCode(IntEnum):
    """Stable process exit codes from the v1 CLI contract."""

    SUCCESS = 0
    GENERAL_FAILURE = 1
    INVALID_USAGE = 2
    VALIDATION_FAILURE = 3
    SETUP_NOT_FOUND = 4
    PERMISSION_MISSING = 5
    PARTIAL_LAUNCH = 6
    SECURITY_REJECTION = 7
    DEPENDENCY_CYCLE = 8
    PORT_CONFLICT = 9
    UNSUPPORTED = 10
