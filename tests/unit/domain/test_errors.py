"""Tests for typed domain errors."""

import pytest

from setuper.domain.enums import ExitCode
from setuper.domain.errors import (
    AdapterUnavailableError,
    DependencyCycleError,
    ManifestIOError,
    ManifestValidationError,
    PartialLaunchError,
    PermissionDeniedError,
    PortConflictError,
    ReadinessTimeoutError,
    SetuperError,
    SetupNotFoundError,
    UnsupportedPlatformError,
    UntrustedSetupError,
)


@pytest.mark.parametrize(
    ("error_type", "error_code", "exit_code"),
    [
        (ManifestValidationError, "MANIFEST_VALIDATION", ExitCode.VALIDATION_FAILURE),
        (ManifestIOError, "MANIFEST_IO", ExitCode.GENERAL_FAILURE),
        (SetupNotFoundError, "SETUP_NOT_FOUND", ExitCode.SETUP_NOT_FOUND),
        (PermissionDeniedError, "PERMISSION_DENIED", ExitCode.PERMISSION_MISSING),
        (PartialLaunchError, "PARTIAL_LAUNCH", ExitCode.PARTIAL_LAUNCH),
        (UntrustedSetupError, "UNTRUSTED_SETUP", ExitCode.SECURITY_REJECTION),
        (DependencyCycleError, "DEPENDENCY_CYCLE", ExitCode.DEPENDENCY_CYCLE),
        (PortConflictError, "PORT_CONFLICT", ExitCode.PORT_CONFLICT),
        (AdapterUnavailableError, "ADAPTER_UNAVAILABLE", ExitCode.UNSUPPORTED),
        (UnsupportedPlatformError, "UNSUPPORTED_PLATFORM", ExitCode.UNSUPPORTED),
        (ReadinessTimeoutError, "READINESS_TIMEOUT", ExitCode.GENERAL_FAILURE),
    ],
)
def test_error_types_expose_stable_cli_metadata(
    error_type: type[SetuperError],
    error_code: str,
    exit_code: ExitCode,
) -> None:
    """Expected failures map to stable machine and process codes."""
    error = error_type("safe message")

    assert str(error) == "safe message"
    assert error.message == "safe message"
    assert error.error_code == error_code
    assert error.exit_code is exit_code


def test_error_details_are_copied_and_immutable() -> None:
    """Callers cannot mutate diagnostic context after error creation."""
    source_details: dict[str, object] = {"resource_id": "frontend"}
    error = SetuperError("failed", details=source_details)
    source_details["resource_id"] = "changed"

    assert error.details == {"resource_id": "frontend"}
    with pytest.raises(TypeError):
        error.details["resource_id"] = "changed"  # type: ignore[index]


def test_errors_do_not_share_default_details() -> None:
    """Errors created without details receive independent empty mappings."""
    first = SetuperError("first")
    second = SetuperError("second")

    assert first.details == {}
    assert second.details == {}
    assert first.details is not second.details
