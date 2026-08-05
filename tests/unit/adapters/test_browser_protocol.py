"""Tests for the versioned, length-prefixed browser integration protocol."""

import json

import pytest

from setuper.adapters.browser_protocol import (
    MAX_MESSAGE_BYTES,
    PROTOCOL_VERSION,
    BrowserRequest,
    decode_response,
    encode_message,
    split_framed_message,
)
from setuper.domain.errors import AdapterUnavailableError


def test_request_to_message_carries_protocol_version_and_operation() -> None:
    """A request renders a versioned, request-identified message."""
    request = BrowserRequest(operation="list_windows")

    message = request.to_message()

    assert message["protocol_version"] == PROTOCOL_VERSION
    assert message["operation"] == "list_windows"
    assert message["request_id"] == request.request_id


def test_encode_and_split_round_trip_a_message() -> None:
    """A framed message can be split back into its exact JSON payload."""
    message = {"protocol_version": 1, "request_id": "abc", "operation": "list_windows"}

    framed = encode_message(message)
    length, payload = split_framed_message(framed)

    assert length == len(payload)
    assert json.loads(payload) == message


def test_encode_message_rejects_oversized_payload() -> None:
    """A payload above the maximum size is rejected before framing."""
    huge = {"params": {"padding": "x" * (MAX_MESSAGE_BYTES + 10)}}

    with pytest.raises(AdapterUnavailableError):
        encode_message(huge)


def test_split_framed_message_rejects_truncated_data() -> None:
    """A short prefix or short payload is treated as truncation, not a crash."""
    with pytest.raises(AdapterUnavailableError):
        split_framed_message(b"\x01\x00")

    framed = encode_message({"a": 1})
    with pytest.raises(AdapterUnavailableError):
        split_framed_message(framed[:-1])


def test_decode_response_accepts_a_valid_response() -> None:
    """A well-formed response with a matching request ID parses cleanly."""
    payload = json.dumps(
        {
            "protocol_version": PROTOCOL_VERSION,
            "request_id": "abc",
            "ok": True,
            "result": {"windows": []},
        }
    ).encode("utf-8")

    response = decode_response(payload, expected_request_id="abc")

    assert response.ok is True
    assert response.result == {"windows": []}


@pytest.mark.parametrize(
    "payload",
    [
        b"not json",
        json.dumps(["not", "an", "object"]).encode("utf-8"),
        json.dumps({"protocol_version": 999, "request_id": "abc", "ok": True}).encode(
            "utf-8"
        ),
        json.dumps(
            {"protocol_version": PROTOCOL_VERSION, "request_id": "other", "ok": True}
        ).encode("utf-8"),
        json.dumps({"protocol_version": PROTOCOL_VERSION, "request_id": "abc"}).encode(
            "utf-8"
        ),
    ],
)
def test_decode_response_rejects_malformed_or_mismatched_responses(
    payload: bytes,
) -> None:
    """Malformed JSON, wrong version, wrong request ID, or missing status all fail."""
    with pytest.raises(AdapterUnavailableError):
        decode_response(payload, expected_request_id="abc")
