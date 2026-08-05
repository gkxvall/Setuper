"""Integration tests for TCP, HTTP, and command readiness checks."""

import asyncio
import http.server
import socket
import threading
from collections.abc import Iterator

import pytest

from setuper.domain.errors import ReadinessTimeoutError
from setuper.domain.readiness import (
    CommandReadinessSpec,
    HttpReadinessSpec,
    TcpReadinessSpec,
)
from setuper.infrastructure.commands import SubprocessCommandRunner
from setuper.infrastructure.readiness_checks import check_once, wait_until_ready


def _unused_port() -> int:
    """Return one currently unused TCP port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


class _OkHandler(http.server.BaseHTTPRequestHandler):
    """Minimal HTTP handler returning 200 for every request."""

    def do_GET(self) -> None:
        """Answer every GET request with a bare 200 status."""
        self.send_response(200)
        self.end_headers()

    def log_message(self, log_format: str, *args: object) -> None:
        """Silence request logging during tests."""


@pytest.fixture
def http_server() -> Iterator[int]:
    """Run a minimal HTTP server on an ephemeral localhost port."""
    server = http.server.HTTPServer(("127.0.0.1", 0), _OkHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_port
    finally:
        server.shutdown()
        thread.join()


def test_tcp_readiness_succeeds_against_a_listening_server() -> None:
    """A TCP check succeeds once a listener is accepting connections."""

    async def scenario() -> None:
        server = await asyncio.start_server(lambda r, w: None, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        try:
            spec = TcpReadinessSpec(host="127.0.0.1", port=port)
            assert await check_once(spec) is True
        finally:
            server.close()
            await server.wait_closed()

    asyncio.run(scenario())


def test_tcp_readiness_fails_against_a_closed_port() -> None:
    """A TCP check fails when nothing is listening on the port."""

    async def scenario() -> None:
        spec = TcpReadinessSpec(host="127.0.0.1", port=_unused_port())
        assert await check_once(spec, probe_timeout_seconds=0.5) is False

    asyncio.run(scenario())


def test_http_readiness_succeeds_for_expected_status(http_server: int) -> None:
    """An HTTP check succeeds when the response matches the expected status."""

    async def scenario() -> None:
        spec = HttpReadinessSpec(url=f"http://127.0.0.1:{http_server}/")
        assert await check_once(spec) is True

    asyncio.run(scenario())


def test_http_readiness_fails_for_unreachable_server() -> None:
    """An HTTP check fails cleanly when the server is unreachable."""

    async def scenario() -> None:
        spec = HttpReadinessSpec(url=f"http://127.0.0.1:{_unused_port()}/")
        assert await check_once(spec, probe_timeout_seconds=0.5) is False

    asyncio.run(scenario())


def test_command_readiness_matches_expected_exit_code() -> None:
    """A command check succeeds only when the exit code matches expectation."""

    async def scenario() -> None:
        runner = SubprocessCommandRunner()
        succeeding = CommandReadinessSpec(command=("true",), expected_exit_code=0)
        failing = CommandReadinessSpec(command=("false",), expected_exit_code=0)

        assert await check_once(succeeding, runner=runner) is True
        assert await check_once(failing, runner=runner) is False

    asyncio.run(scenario())


def test_wait_until_ready_returns_once_probe_succeeds(http_server: int) -> None:
    """Polling stops as soon as the readiness probe first succeeds."""

    async def scenario() -> None:
        spec = HttpReadinessSpec(url=f"http://127.0.0.1:{http_server}/")
        await wait_until_ready(spec, timeout_seconds=2.0, poll_interval_seconds=0.05)

    asyncio.run(scenario())


def test_wait_until_ready_raises_typed_timeout_when_never_ready() -> None:
    """Polling raises a typed timeout error once the deadline passes."""

    async def scenario() -> None:
        spec = TcpReadinessSpec(host="127.0.0.1", port=_unused_port())
        await wait_until_ready(spec, timeout_seconds=0.3, poll_interval_seconds=0.05)

    with pytest.raises(ReadinessTimeoutError):
        asyncio.run(scenario())
