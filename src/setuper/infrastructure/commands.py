"""Bounded argument-vector subprocess execution for trusted integrations."""

import os
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from setuper.domain.errors import AdapterUnavailableError

DEFAULT_TIMEOUT_SECONDS = 5.0
MAX_CAPTURE_CHARACTERS = 256 * 1024
ALLOWED_ENVIRONMENT_NAMES = (
    "HOME",
    "LANG",
    "LC_ALL",
    "PATH",
    "TMPDIR",
)


@dataclass(frozen=True, slots=True)
class CommandResult:
    """Bounded subprocess output and exit status."""

    returncode: int
    stdout: str
    stderr: str
    output_truncated: bool = False


class CommandRunner(Protocol):
    """Argument-vector command boundary replaceable by test fakes."""

    def run(
        self,
        arguments: Sequence[str],
        *,
        cwd: Path | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> CommandResult:
        """Execute one bounded command without a shell."""


class SubprocessCommandRunner:
    """Run trusted integration tools with conservative process settings."""

    def __init__(
        self,
        *,
        environment: Mapping[str, str] | None = None,
        max_capture_characters: int = MAX_CAPTURE_CHARACTERS,
    ) -> None:
        """Create a runner with an explicit or allowlisted environment."""
        source_environment = os.environ if environment is None else environment
        self._environment = {
            name: source_environment[name]
            for name in ALLOWED_ENVIRONMENT_NAMES
            if name in source_environment
        }
        if max_capture_characters < 1:
            raise ValueError("max_capture_characters must be positive")
        self._max_capture_characters = max_capture_characters

    def run(
        self,
        arguments: Sequence[str],
        *,
        cwd: Path | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> CommandResult:
        """Execute one bounded command without shell interpretation."""
        if not arguments:
            raise ValueError("command arguments must not be empty")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        command = tuple(arguments)
        try:
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                stdin=subprocess.DEVNULL,
                cwd=cwd,
                env=self._environment,
                timeout=timeout_seconds,
            )
        except FileNotFoundError as error:
            raise AdapterUnavailableError(
                f"Integration executable not found: {command[0]}",
                details={"executable": command[0]},
            ) from error
        except subprocess.TimeoutExpired as error:
            raise AdapterUnavailableError(
                f"Integration command timed out: {command[0]}",
                details={
                    "executable": command[0],
                    "timeout_seconds": timeout_seconds,
                },
            ) from error
        except OSError as error:
            raise AdapterUnavailableError(
                f"Could not run integration executable: {command[0]}",
                details={"executable": command[0]},
            ) from error

        stdout, stdout_truncated = self._truncate(completed.stdout)
        stderr, stderr_truncated = self._truncate(completed.stderr)
        return CommandResult(
            returncode=completed.returncode,
            stdout=stdout,
            stderr=stderr,
            output_truncated=stdout_truncated or stderr_truncated,
        )

    def _truncate(self, value: str) -> tuple[str, bool]:
        """Cap retained integration output."""
        if len(value) <= self._max_capture_characters:
            return value, False
        return value[: self._max_capture_characters], True
