"""Pure readiness-check specifications parsed from manifest `ready_when`."""

from collections.abc import Mapping
from dataclasses import dataclass

from pydantic import JsonValue

from setuper.domain.errors import ManifestValidationError

DEFAULT_HTTP_METHOD = "GET"
DEFAULT_HTTP_EXPECTED_STATUS = 200
DEFAULT_COMMAND_EXPECTED_EXIT_CODE = 0

_KNOWN_KINDS = ("tcp", "http", "command")


@dataclass(frozen=True, slots=True)
class TcpReadinessSpec:
    """Wait for a TCP listener to accept a connection."""

    host: str
    port: int


@dataclass(frozen=True, slots=True)
class HttpReadinessSpec:
    """Wait for an HTTP endpoint to return an expected status."""

    url: str
    method: str = DEFAULT_HTTP_METHOD
    expected_status: int = DEFAULT_HTTP_EXPECTED_STATUS


@dataclass(frozen=True, slots=True)
class CommandReadinessSpec:
    """Wait for a probe command to exit with an expected status."""

    command: tuple[str, ...]
    expected_exit_code: int = DEFAULT_COMMAND_EXPECTED_EXIT_CODE


ReadinessSpec = TcpReadinessSpec | HttpReadinessSpec | CommandReadinessSpec


def parse_readiness_spec(
    ready_when: Mapping[str, JsonValue] | None,
) -> ReadinessSpec | None:
    """Parse one manifest `ready_when` mapping into a typed readiness spec."""
    if not ready_when:
        return None
    present = [kind for kind in _KNOWN_KINDS if kind in ready_when]
    if len(present) != 1:
        raise ManifestValidationError(
            "ready_when must declare exactly one of: tcp, http, command",
            details={"ready_when": dict(ready_when)},
        )
    kind = present[0]
    body = ready_when[kind]
    if not isinstance(body, dict):
        raise ManifestValidationError(
            f"ready_when.{kind} must be a mapping",
            details={"kind": kind},
        )
    if kind == "tcp":
        return _parse_tcp(body)
    if kind == "http":
        return _parse_http(body)
    return _parse_command(body)


def _parse_tcp(body: Mapping[str, JsonValue]) -> TcpReadinessSpec:
    """Parse and validate a `ready_when.tcp` body."""
    host = body.get("host")
    port = body.get("port")
    if not isinstance(host, str) or not host:
        raise ManifestValidationError("ready_when.tcp.host must be a non-empty string")
    if not isinstance(port, int) or isinstance(port, bool):
        raise ManifestValidationError("ready_when.tcp.port must be an integer")
    return TcpReadinessSpec(host=host, port=port)


def _parse_http(body: Mapping[str, JsonValue]) -> HttpReadinessSpec:
    """Parse and validate a `ready_when.http` body."""
    url = body.get("url")
    if not isinstance(url, str) or not url:
        raise ManifestValidationError("ready_when.http.url must be a non-empty string")
    method = body.get("method", DEFAULT_HTTP_METHOD)
    if not isinstance(method, str) or not method:
        raise ManifestValidationError(
            "ready_when.http.method must be a non-empty string"
        )
    expected_status = body.get("expected_status", DEFAULT_HTTP_EXPECTED_STATUS)
    if not isinstance(expected_status, int) or isinstance(expected_status, bool):
        raise ManifestValidationError(
            "ready_when.http.expected_status must be an integer"
        )
    return HttpReadinessSpec(url=url, method=method, expected_status=expected_status)


def _parse_command(body: Mapping[str, JsonValue]) -> CommandReadinessSpec:
    """Parse and validate a `ready_when.command` body."""
    raw_command = body.get("command")
    command: tuple[str, ...]
    if isinstance(raw_command, str) and raw_command:
        command = (raw_command,)
    elif isinstance(raw_command, list) and raw_command:
        string_items = [item for item in raw_command if isinstance(item, str)]
        if len(string_items) != len(raw_command):
            raise ManifestValidationError(
                "ready_when.command.command must be a non-empty string "
                "or list of strings"
            )
        command = tuple(string_items)
    else:
        raise ManifestValidationError(
            "ready_when.command.command must be a non-empty string or list of strings"
        )
    expected_exit_code = body.get(
        "expected_exit_code",
        DEFAULT_COMMAND_EXPECTED_EXIT_CODE,
    )
    if not isinstance(expected_exit_code, int) or isinstance(expected_exit_code, bool):
        raise ManifestValidationError(
            "ready_when.command.expected_exit_code must be an integer"
        )
    return CommandReadinessSpec(
        command=command,
        expected_exit_code=expected_exit_code,
    )
