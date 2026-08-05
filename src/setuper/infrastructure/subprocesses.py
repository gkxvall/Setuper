"""Async subprocess supervision with graceful-then-forced termination."""

import asyncio
import asyncio.subprocess
import contextlib
import os
import signal
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from setuper.domain.errors import AdapterUnavailableError

DEFAULT_GRACEFUL_TIMEOUT_SECONDS = 10.0


@dataclass(frozen=True, slots=True)
class SupervisedProcess:
    """A running subprocess owned by one Setuper launch."""

    pid: int
    process: asyncio.subprocess.Process

    @property
    def exit_code(self) -> int | None:
        """Return the process exit code, or None while still running."""
        return self.process.returncode


class ProcessSupervisor:
    """Start, monitor, and terminate one OS process asynchronously."""

    async def start(
        self,
        command: Sequence[str],
        *,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
    ) -> SupervisedProcess:
        """Start one subprocess, detached into its own process group."""
        if not command:
            raise ValueError("command must not be empty")
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                cwd=cwd,
                env=dict(env) if env is not None else None,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
                start_new_session=True,
            )
        except FileNotFoundError as error:
            raise AdapterUnavailableError(
                f"Command executable not found: {command[0]}",
                details={"executable": command[0]},
            ) from error
        except OSError as error:
            raise AdapterUnavailableError(
                f"Could not start command: {command[0]}",
                details={"executable": command[0]},
            ) from error
        return SupervisedProcess(pid=process.pid, process=process)

    def is_running(self, supervised: SupervisedProcess) -> bool:
        """Return whether the supervised process is still running."""
        return supervised.exit_code is None

    async def wait(self, supervised: SupervisedProcess) -> int:
        """Wait for the supervised process to exit and return its exit code."""
        return await supervised.process.wait()

    async def stop(
        self,
        supervised: SupervisedProcess,
        *,
        force: bool = False,
        graceful_timeout_seconds: float = DEFAULT_GRACEFUL_TIMEOUT_SECONDS,
    ) -> int:
        """Terminate gracefully by default, escalating to a forced kill."""
        if not self.is_running(supervised):
            return await self.wait(supervised)
        if force:
            _send_signal(supervised.pid, signal.SIGKILL)
        else:
            _send_signal(supervised.pid, signal.SIGTERM)
            try:
                await asyncio.wait_for(
                    self.wait(supervised),
                    timeout=graceful_timeout_seconds,
                )
            except TimeoutError:
                _send_signal(supervised.pid, signal.SIGKILL)
        return await self.wait(supervised)


def _send_signal(pid: int, sig: signal.Signals) -> None:
    """Signal a supervised process's whole group, ignoring a vanished process."""
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(os.getpgid(pid), sig)
