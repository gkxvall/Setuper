"""Async execution of TCP, HTTP, and command readiness checks."""

import asyncio
import contextlib
import urllib.error
import urllib.request

from setuper.domain.errors import AdapterUnavailableError, ReadinessTimeoutError
from setuper.domain.readiness import (
    CommandReadinessSpec,
    HttpReadinessSpec,
    ReadinessSpec,
    TcpReadinessSpec,
)
from setuper.infrastructure.commands import CommandRunner

DEFAULT_PROBE_TIMEOUT_SECONDS = 2.0
DEFAULT_POLL_INTERVAL_SECONDS = 0.5


async def check_once(
    spec: ReadinessSpec,
    *,
    runner: CommandRunner | None = None,
    probe_timeout_seconds: float = DEFAULT_PROBE_TIMEOUT_SECONDS,
) -> bool:
    """Run one readiness probe and return whether it currently succeeds."""
    if isinstance(spec, TcpReadinessSpec):
        return await _check_tcp(spec, probe_timeout_seconds)
    if isinstance(spec, HttpReadinessSpec):
        return await asyncio.to_thread(_check_http, spec, probe_timeout_seconds)
    if runner is None:
        raise ValueError("command readiness checks require a command runner")
    return await asyncio.to_thread(_check_command, spec, runner, probe_timeout_seconds)


async def wait_until_ready(
    spec: ReadinessSpec,
    *,
    timeout_seconds: float,
    poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS,
    runner: CommandRunner | None = None,
) -> None:
    """Poll a readiness spec until it succeeds or the timeout elapses."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout_seconds
    while True:
        if await check_once(spec, runner=runner):
            return
        remaining = deadline - loop.time()
        if remaining <= 0:
            raise ReadinessTimeoutError(
                "Resource did not become ready before its timeout",
                details={"timeout_seconds": timeout_seconds},
            )
        await asyncio.sleep(min(poll_interval_seconds, remaining))


async def _check_tcp(spec: TcpReadinessSpec, timeout_seconds: float) -> bool:
    """Return whether a TCP connection to the given host and port succeeds."""
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(spec.host, spec.port),
            timeout=timeout_seconds,
        )
    except (OSError, TimeoutError):
        return False
    writer.close()
    with contextlib.suppress(OSError):
        await writer.wait_closed()
    return True


def _check_http(spec: HttpReadinessSpec, timeout_seconds: float) -> bool:
    """Return whether an HTTP request returns the expected status code."""
    request = urllib.request.Request(spec.url, method=spec.method)
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            return int(response.status) == spec.expected_status
    except urllib.error.HTTPError as error:
        return error.code == spec.expected_status
    except (urllib.error.URLError, OSError, TimeoutError):
        return False


def _check_command(
    spec: CommandReadinessSpec,
    runner: CommandRunner,
    timeout_seconds: float,
) -> bool:
    """Return whether a probe command exits with the expected status."""
    try:
        result = runner.run(spec.command, timeout_seconds=timeout_seconds)
    except AdapterUnavailableError:
        return False
    return result.returncode == spec.expected_exit_code
