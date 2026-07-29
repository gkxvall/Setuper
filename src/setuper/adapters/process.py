"""Current-user process detection with honest reconstruction limits."""

import getpass
import os
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import psutil
from pydantic import JsonValue

from setuper.adapters.base import (
    BaseResourceAdapter,
    CaptureContext,
    DetectedResource,
)
from setuper.domain.enums import CaptureSupport, Platform
from setuper.domain.errors import ManifestValidationError, UnsupportedPlatformError
from setuper.domain.models import ResourceSpec

REDACTED_ARGUMENT = "<redacted>"
SENSITIVE_ARGUMENT_MARKERS = (
    "api-key",
    "apikey",
    "auth",
    "credential",
    "password",
    "secret",
    "token",
)


@dataclass(frozen=True, slots=True)
class ProcessSnapshot:
    """Process metadata obtainable without retaining a live psutil object."""

    pid: int
    parent_pid: int
    name: str
    executable: str | None
    arguments: tuple[str, ...]
    working_directory: str | None
    create_time: float | None
    username: str | None


class ProcessProvider(Protocol):
    """System process source replaceable by deterministic fakes."""

    def iter_processes(self) -> Iterable[ProcessSnapshot]:
        """Yield accessible process snapshots."""


class PsutilProcessProvider:
    """Read process metadata through psutil instead of parsing shell output."""

    def iter_processes(self) -> Iterable[ProcessSnapshot]:
        """Yield accessible snapshots while skipping process races."""
        attributes = (
            "pid",
            "ppid",
            "name",
            "exe",
            "cmdline",
            "cwd",
            "create_time",
            "username",
        )
        for process in psutil.process_iter(attributes, ad_value=None):
            try:
                info = process.info
                pid = info.get("pid")
                parent_pid = info.get("ppid")
                if not isinstance(pid, int) or not isinstance(parent_pid, int):
                    continue
                arguments_value = info.get("cmdline")
                arguments = (
                    tuple(str(argument) for argument in arguments_value)
                    if isinstance(arguments_value, list | tuple)
                    else ()
                )
                create_time_value = info.get("create_time")
                yield ProcessSnapshot(
                    pid=pid,
                    parent_pid=parent_pid,
                    name=str(info.get("name") or ""),
                    executable=_optional_string(info.get("exe")),
                    arguments=arguments,
                    working_directory=_optional_string(info.get("cwd")),
                    create_time=(
                        float(create_time_value)
                        if isinstance(create_time_value, int | float)
                        else None
                    ),
                    username=_optional_string(info.get("username")),
                )
            except (psutil.AccessDenied, psutil.NoSuchProcess, psutil.ZombieProcess):
                continue


class ProcessAdapter(BaseResourceAdapter):
    """Detect processes without promising arbitrary process restoration."""

    type_name = "process"

    def __init__(
        self,
        provider: ProcessProvider | None = None,
        *,
        current_username: str | None = None,
        own_pid: int | None = None,
    ) -> None:
        """Create a process adapter with injectable system identity."""
        self._provider = provider or PsutilProcessProvider()
        self._current_username = current_username or getpass.getuser()
        self._own_pid = own_pid or os.getpid()

    def detect(self, context: CaptureContext) -> list[DetectedResource]:
        """Detect accessible current-user processes except Setuper itself."""
        if context.platform is not Platform.MACOS:
            raise UnsupportedPlatformError(
                f"Process detection is unsupported on: {context.platform.value}",
                details={"platform": context.platform.value},
            )
        findings: list[DetectedResource] = []
        for process in self._provider.iter_processes():
            if process.pid == self._own_pid:
                continue
            if process.username != self._current_username:
                continue
            redacted_arguments, redacted = _redact_arguments(process.arguments)
            support = (
                CaptureSupport.PARTIALLY_SUPPORTED
                if process.executable
                else CaptureSupport.UNSUPPORTED
            )
            warnings = [
                "Arbitrary process state cannot be restored; review the command."
            ]
            if redacted:
                warnings.append("Credential-like command arguments were redacted.")
            if not process.executable:
                warnings.append("Executable path is unavailable.")
            config: dict[str, JsonValue] = {
                "pid": process.pid,
                "parent_pid": process.parent_pid,
                "name": process.name,
                "arguments": list(redacted_arguments),
            }
            if process.executable is not None:
                config["executable"] = process.executable
            if process.working_directory is not None:
                config["cwd"] = process.working_directory
            if process.create_time is not None:
                config["start_time"] = process.create_time
            display_name = process.name or (
                Path(process.executable).name
                if process.executable
                else f"PID {process.pid}"
            )
            identity_time = (
                "unknown" if process.create_time is None else process.create_time
            )
            findings.append(
                DetectedResource(
                    identity=f"process:{process.pid}:{identity_time}",
                    type_name=self.type_name,
                    display_name=display_name,
                    support=support,
                    config=config,
                    metadata={"capture_source": "psutil"},
                    warnings=tuple(warnings),
                )
            )
        return sorted(findings, key=lambda finding: finding.identity)

    def capture(self, resource: DetectedResource) -> ResourceSpec:
        """Convert one process finding into a review-required resource."""
        if resource.type_name != self.type_name:
            raise ManifestValidationError(
                f"Process adapter cannot capture type: {resource.type_name}",
                details={"type": resource.type_name},
            )
        pid = resource.config.get("pid")
        if not isinstance(pid, int):
            raise ManifestValidationError(
                "Detected process is missing an integer PID",
            )
        metadata: dict[str, JsonValue] = dict(resource.metadata)
        metadata["capture_support"] = resource.support.value
        metadata["capture_warnings"] = list(resource.warnings)
        return ResourceSpec(
            id=f"process-{pid}",
            type=self.type_name,
            description=resource.display_name,
            config=dict(resource.config),
            metadata=metadata,
        )


def _redact_arguments(arguments: tuple[str, ...]) -> tuple[tuple[str, ...], bool]:
    """Redact values associated with credential-like command flags."""
    redacted: list[str] = []
    redact_next = False
    changed = False
    for argument in arguments:
        if redact_next:
            redacted.append(REDACTED_ARGUMENT)
            redact_next = False
            changed = True
            continue
        lowered = argument.lower()
        sensitive = any(marker in lowered for marker in SENSITIVE_ARGUMENT_MARKERS)
        if argument.startswith("-") and sensitive and "=" in argument:
            flag, _, _ = argument.partition("=")
            redacted.append(f"{flag}={REDACTED_ARGUMENT}")
            changed = True
            continue
        redacted.append(argument)
        if argument.startswith("-") and sensitive:
            redact_next = True
    return tuple(redacted), changed


def _optional_string(value: object) -> str | None:
    """Normalize an optional psutil string field."""
    return None if value is None else str(value)
