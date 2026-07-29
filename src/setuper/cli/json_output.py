"""Deterministic JSON envelopes for automation-friendly CLI output."""

import json
from collections.abc import Mapping, Sequence
from datetime import datetime
from enum import Enum
from pathlib import Path
from uuid import UUID

from setuper.domain.errors import SetuperError


def render_json_success(
    command: str,
    data: Mapping[str, object],
    *,
    warnings: Sequence[str] = (),
) -> str:
    """Render one documented success envelope."""
    return _serialize(
        {
            "ok": True,
            "command": command,
            "data": data,
            "warnings": list(warnings),
        }
    )


def render_json_error(command: str, error: SetuperError) -> str:
    """Render one documented typed-error envelope."""
    return _serialize(
        {
            "ok": False,
            "command": command,
            "error": {
                "code": error.error_code,
                "message": error.message,
                "details": dict(error.details),
            },
        }
    )


def _serialize(payload: Mapping[str, object]) -> str:
    """Serialize supported structured values with stable ordering."""
    return json.dumps(
        _normalize(payload),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _normalize(value: object) -> object:
    """Convert public domain values into JSON-compatible primitives."""
    if isinstance(value, Enum):
        return _normalize(value.value)
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, Path | UUID | datetime):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _normalize(item) for key, item in value.items()}
    if isinstance(value, Sequence):
        return [_normalize(item) for item in value]
    return str(value)
