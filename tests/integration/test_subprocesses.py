"""Integration tests for async subprocess supervision."""

import asyncio
import sys

import pytest

from setuper.domain.errors import AdapterUnavailableError
from setuper.infrastructure.subprocesses import ProcessSupervisor


def test_start_reports_a_running_process_and_force_stop_terminates_it() -> None:
    """A started process is observed running, then force-stopped promptly."""

    async def scenario() -> None:
        supervisor = ProcessSupervisor()
        supervised = await supervisor.start(
            [sys.executable, "-c", "import time; time.sleep(5)"]
        )

        assert supervisor.is_running(supervised) is True
        assert supervised.pid > 0

        exit_code = await supervisor.stop(supervised, force=True)

        assert exit_code != 0
        assert supervisor.is_running(supervised) is False

    asyncio.run(scenario())


def test_stop_terminates_a_cooperative_process_gracefully() -> None:
    """A process without a SIGTERM handler exits promptly on graceful stop."""

    async def scenario() -> None:
        supervisor = ProcessSupervisor()
        supervised = await supervisor.start(
            [sys.executable, "-c", "import time; time.sleep(30)"]
        )

        exit_code = await supervisor.stop(
            supervised,
            graceful_timeout_seconds=5.0,
        )

        assert exit_code != 0

    asyncio.run(scenario())


def test_stop_escalates_to_a_forced_kill_when_sigterm_is_ignored() -> None:
    """A process ignoring SIGTERM is force-killed once the timeout elapses."""

    async def scenario() -> None:
        supervisor = ProcessSupervisor()
        script = (
            "import signal, time; "
            "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
            "time.sleep(30)"
        )
        supervised = await supervisor.start([sys.executable, "-c", script])

        exit_code = await supervisor.stop(
            supervised,
            graceful_timeout_seconds=0.2,
        )

        assert exit_code != 0
        assert supervisor.is_running(supervised) is False

    asyncio.run(scenario())


def test_stop_on_an_already_exited_process_returns_its_exit_code() -> None:
    """Stopping a process that already exited returns its real exit code."""

    async def scenario() -> None:
        supervisor = ProcessSupervisor()
        supervised = await supervisor.start(
            [sys.executable, "-c", "raise SystemExit(3)"]
        )
        await supervisor.wait(supervised)

        exit_code = await supervisor.stop(supervised)

        assert exit_code == 3

    asyncio.run(scenario())


def test_start_raises_adapter_unavailable_for_missing_executable() -> None:
    """A missing executable uses the adapter error model, not a raw OSError."""

    async def scenario() -> None:
        await ProcessSupervisor().start(["/definitely/missing/executable"])

    with pytest.raises(AdapterUnavailableError):
        asyncio.run(scenario())
