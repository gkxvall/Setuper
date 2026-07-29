"""Tests for listening TCP port detection."""

import socket
from collections import namedtuple

import pytest

from setuper.adapters import ports
from setuper.adapters.ports import ListeningPort, PsutilPortProvider

Address = namedtuple("Address", ("ip", "port"))
Connection = namedtuple("Connection", ("status", "pid", "laddr", "family"))


def test_port_provider_filters_sorts_and_deduplicates_listeners(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only process-owned TCP listeners enter deterministic capture results."""
    listener = Connection(
        status=ports.psutil.CONN_LISTEN,
        pid=20,
        laddr=Address("127.0.0.1", 3000),
        family=socket.AF_INET,
    )
    ignored = Connection(
        status="ESTABLISHED",
        pid=20,
        laddr=Address("127.0.0.1", 443),
        family=socket.AF_INET,
    )
    monkeypatch.setattr(
        ports.psutil,
        "net_connections",
        lambda kind: [listener, ignored, listener],
    )

    result = PsutilPortProvider().detect_listeners()

    assert result.warnings == ()
    assert result.listeners == (
        ListeningPort(
            pid=20,
            host="127.0.0.1",
            port=3000,
            address_family="ipv4",
        ),
    )


def test_port_provider_surfaces_permission_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Denied system inspection returns a warning rather than an empty claim."""

    def deny(kind: str) -> list[object]:
        raise ports.psutil.AccessDenied

    monkeypatch.setattr(ports.psutil, "net_connections", deny)

    result = PsutilPortProvider().detect_listeners()

    assert result.listeners == ()
    assert result.warnings == (
        "Listening-port detection unavailable; macOS denied access.",
    )
