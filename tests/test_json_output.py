"""Tests for deterministic CLI JSON envelopes."""

import json
from pathlib import Path
from types import MappingProxyType
from uuid import UUID

from setuper.cli.json_output import render_json_error, render_json_success
from setuper.domain.errors import ManifestValidationError


def test_success_envelope_is_deterministic_and_unicode_safe() -> None:
    """Success output is one compact object with stable key ordering."""
    rendered = render_json_success(
        "list",
        {
            "path": Path("/tmp/Démo With Spaces"),
            "id": UUID("e84b8d08-e05d-49de-a7ab-4e38f919eb89"),
        },
    )

    assert rendered == (
        '{"command":"list","data":{"id":"e84b8d08-e05d-49de-a7ab-'
        '4e38f919eb89","path":"/tmp/Démo With Spaces"},"ok":true,"warnings":[]}'
    )
    assert json.loads(rendered)["data"]["path"] == "/tmp/Démo With Spaces"


def test_error_envelope_normalizes_immutable_details() -> None:
    """Typed error details remain structured rather than becoming a string."""
    error = ManifestValidationError(
        "Invalid setup",
        details=MappingProxyType({"issues": [{"location": "name"}]}),
    )

    rendered = render_json_error("show", error)

    assert json.loads(rendered) == {
        "ok": False,
        "command": "show",
        "error": {
            "code": "MANIFEST_VALIDATION",
            "message": "Invalid setup",
            "details": {"issues": [{"location": "name"}]},
        },
    }
