"""Typed errors raised by Setuper's domain and application layers."""

from collections.abc import Mapping
from types import MappingProxyType
from typing import ClassVar

from setuper.domain.enums import ExitCode


class SetuperError(Exception):
    """Base class for expected failures that the CLI can render safely."""

    error_code: ClassVar[str] = "GENERAL_FAILURE"
    exit_code: ClassVar[ExitCode] = ExitCode.GENERAL_FAILURE

    def __init__(
        self,
        message: str,
        *,
        details: Mapping[str, object] | None = None,
    ) -> None:
        """Create an error with immutable structured diagnostic details."""
        super().__init__(message)
        self.message = message
        self.details: Mapping[str, object] = MappingProxyType(dict(details or {}))


class ManifestValidationError(SetuperError):
    """A setup manifest does not conform to schema or policy."""

    error_code = "MANIFEST_VALIDATION"
    exit_code = ExitCode.VALIDATION_FAILURE


class ManifestIOError(SetuperError):
    """A manifest could not be read or written safely."""

    error_code = "MANIFEST_IO"


class DatabaseError(SetuperError):
    """SQLite state could not be opened or queried safely."""

    error_code = "DATABASE"


class DatabaseMigrationError(DatabaseError):
    """A transactional database migration failed."""

    error_code = "DATABASE_MIGRATION"


class SetupNotFoundError(SetuperError):
    """A requested setup name is not stored."""

    error_code = "SETUP_NOT_FOUND"
    exit_code = ExitCode.SETUP_NOT_FOUND


class PermissionDeniedError(SetuperError):
    """A required operating-system permission is unavailable."""

    error_code = "PERMISSION_DENIED"
    exit_code = ExitCode.PERMISSION_MISSING


class PartialLaunchError(SetuperError):
    """A launch completed with one or more resource failures."""

    error_code = "PARTIAL_LAUNCH"
    exit_code = ExitCode.PARTIAL_LAUNCH


class UntrustedSetupError(SetuperError):
    """Execution was rejected because the manifest is not trusted."""

    error_code = "UNTRUSTED_SETUP"
    exit_code = ExitCode.SECURITY_REJECTION


class DependencyCycleError(SetuperError):
    """Resource dependencies contain a directed cycle."""

    error_code = "DEPENDENCY_CYCLE"
    exit_code = ExitCode.DEPENDENCY_CYCLE


class PortConflictError(SetuperError):
    """A required port is occupied and policy does not resolve it."""

    error_code = "PORT_CONFLICT"
    exit_code = ExitCode.PORT_CONFLICT


class AdapterUnavailableError(SetuperError):
    """A resource adapter is unavailable on the current machine."""

    error_code = "ADAPTER_UNAVAILABLE"
    exit_code = ExitCode.UNSUPPORTED


class UnsupportedPlatformError(SetuperError):
    """The requested operation is unsupported on the current platform."""

    error_code = "UNSUPPORTED_PLATFORM"
    exit_code = ExitCode.UNSUPPORTED


class ReadinessTimeoutError(SetuperError):
    """A resource did not become ready before its timeout."""

    error_code = "READINESS_TIMEOUT"
