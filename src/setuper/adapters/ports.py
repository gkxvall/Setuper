"""Listening TCP port detection through an injectable psutil boundary."""

import socket
from dataclasses import dataclass
from typing import Protocol

import psutil


@dataclass(frozen=True, slots=True, order=True)
class ListeningPort:
    """One process-owned TCP listener."""

    pid: int
    host: str
    port: int
    address_family: str


@dataclass(frozen=True, slots=True)
class PortDetectionResult:
    """Detected listeners plus honest limitations."""

    listeners: tuple[ListeningPort, ...] = ()
    warnings: tuple[str, ...] = ()


class PortProvider(Protocol):
    """Listening-port source replaceable by deterministic fakes."""

    def detect_listeners(self) -> PortDetectionResult:
        """Return accessible process-owned TCP listeners."""


class PsutilPortProvider:
    """Detect TCP listeners without parsing shell-tool output."""

    def detect_listeners(self) -> PortDetectionResult:
        """Return stable listeners or an honest permission warning."""
        try:
            connections = psutil.net_connections(kind="tcp")
        except (psutil.AccessDenied, OSError):
            return PortDetectionResult(
                warnings=("Listening-port detection unavailable; macOS denied access.",)
            )

        listeners: set[ListeningPort] = set()
        for connection in connections:
            if connection.status != psutil.CONN_LISTEN or connection.pid is None:
                continue
            address = connection.laddr
            if not address:
                continue
            host = str(address.ip)
            port = int(address.port)
            family = _family_name(connection.family)
            listeners.add(
                ListeningPort(
                    pid=connection.pid,
                    host=host,
                    port=port,
                    address_family=family,
                )
            )
        return PortDetectionResult(listeners=tuple(sorted(listeners)))


def _family_name(family: socket.AddressFamily) -> str:
    """Return a stable address-family name."""
    if family == socket.AF_INET:
        return "ipv4"
    if family == socket.AF_INET6:
        return "ipv6"
    return str(int(family))
