"""Versioned message protocol for browser extension integration.

Setuper never reads a browser profile directly. A browser extension, once
installed and registered as a native messaging host, exchanges framed JSON
messages with Setuper over that host's standard input and output: each
message is a 4-byte little-endian length prefix followed by that many bytes
of UTF-8 JSON, matching Chrome's Native Messaging transport. This module
defines the versioned request/response envelope and the framing codec; the
extension and its host registration ship and are installed separately.
"""

import json
import struct
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Final
from uuid import uuid4

from pydantic import JsonValue

from setuper.domain.errors import AdapterUnavailableError

PROTOCOL_VERSION: Final = 1
MAX_MESSAGE_BYTES: Final = 1024 * 1024
_LENGTH_PREFIX = struct.Struct("<I")


@dataclass(frozen=True, slots=True)
class BrowserRequest:
    """One versioned request sent to the browser integration host."""

    operation: str
    params: Mapping[str, JsonValue] = field(default_factory=dict)
    request_id: str = field(default_factory=lambda: uuid4().hex)
    protocol_version: int = PROTOCOL_VERSION

    def to_message(self) -> dict[str, JsonValue]:
        """Render this request as a JSON-serializable message."""
        return {
            "protocol_version": self.protocol_version,
            "request_id": self.request_id,
            "operation": self.operation,
            "params": dict(self.params),
        }


@dataclass(frozen=True, slots=True)
class BrowserResponse:
    """One parsed response from the browser integration host."""

    request_id: str
    ok: bool
    result: Mapping[str, JsonValue] = field(default_factory=dict)
    error: str | None = None
    protocol_version: int = PROTOCOL_VERSION


def encode_message(message: Mapping[str, JsonValue]) -> bytes:
    """Frame one JSON message using Native Messaging length-prefixing."""
    payload = json.dumps(message).encode("utf-8")
    if len(payload) > MAX_MESSAGE_BYTES:
        raise AdapterUnavailableError(
            "Browser integration message exceeds the maximum size",
            details={"size": len(payload)},
        )
    return _LENGTH_PREFIX.pack(len(payload)) + payload


def decode_length_prefix(prefix: bytes) -> int:
    """Decode one 4-byte little-endian Native Messaging length prefix."""
    if len(prefix) != _LENGTH_PREFIX.size:
        raise AdapterUnavailableError(
            "Browser integration length prefix is malformed",
        )
    (length,) = _LENGTH_PREFIX.unpack(prefix)
    return int(length)


def split_framed_message(data: bytes) -> tuple[int, bytes]:
    """Split one length-prefixed message into its declared length and payload."""
    if len(data) < _LENGTH_PREFIX.size:
        raise AdapterUnavailableError("Browser integration message is truncated")
    length = decode_length_prefix(data[: _LENGTH_PREFIX.size])
    payload = data[_LENGTH_PREFIX.size : _LENGTH_PREFIX.size + length]
    if len(payload) != length:
        raise AdapterUnavailableError("Browser integration message is truncated")
    return length, payload


def decode_response(raw: bytes, *, expected_request_id: str) -> BrowserResponse:
    """Parse and validate one raw browser host response payload."""
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AdapterUnavailableError(
            "Browser integration host returned a malformed response",
        ) from error
    if not isinstance(data, dict):
        raise AdapterUnavailableError(
            "Browser integration host returned a non-object response",
        )
    if data.get("protocol_version") != PROTOCOL_VERSION:
        raise AdapterUnavailableError(
            "Browser integration host protocol version mismatch",
            details={"received": data.get("protocol_version")},
        )
    if data.get("request_id") != expected_request_id:
        raise AdapterUnavailableError(
            "Browser integration host response does not match the request",
        )
    ok = data.get("ok")
    if not isinstance(ok, bool):
        raise AdapterUnavailableError(
            "Browser integration host response is missing its status",
        )
    result = data.get("result")
    error_message = data.get("error")
    return BrowserResponse(
        request_id=expected_request_id,
        ok=ok,
        result=result if isinstance(result, dict) else {},
        error=error_message if isinstance(error_message, str) else None,
    )
