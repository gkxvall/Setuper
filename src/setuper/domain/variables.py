"""Pure ${VAR_NAME} variable resolution, profile merging, and interpolation."""

import re
from collections.abc import Mapping

from pydantic import JsonValue

from setuper.domain.errors import ManifestValidationError
from setuper.domain.models import VariableSpec

_REFERENCE_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def resolve_profile_overrides(
    profiles: Mapping[str, Mapping[str, JsonValue]],
    profile_name: str | None,
) -> dict[str, JsonValue]:
    """Return one named profile's variable overrides, or none when unspecified."""
    if profile_name is None:
        return {}
    if profile_name not in profiles:
        raise ManifestValidationError(
            f"Unknown profile: {profile_name}",
            details={"profile": profile_name},
        )
    return dict(profiles[profile_name])


def resolve_variable_values(
    variables: Mapping[str, VariableSpec],
    overrides: Mapping[str, JsonValue],
) -> dict[str, JsonValue]:
    """Resolve one concrete value per declared manifest variable."""
    unknown = sorted(set(overrides) - set(variables))
    if unknown:
        raise ManifestValidationError(
            f"Unknown variable override(s): {', '.join(unknown)}",
            details={"variables": unknown},
        )

    resolved: dict[str, JsonValue] = {}
    missing: list[str] = []
    for name, spec in variables.items():
        if name in overrides:
            resolved[name] = overrides[name]
        elif spec.default is not None:
            resolved[name] = spec.default
        elif spec.required:
            missing.append(name)
        else:
            resolved[name] = None
    if missing:
        raise ManifestValidationError(
            f"Missing required variable(s): {', '.join(missing)}",
            details={"variables": missing},
        )
    return resolved


def interpolate(value: JsonValue, values: Mapping[str, JsonValue]) -> JsonValue:
    """Recursively substitute ${VAR_NAME} references in string leaves."""
    if isinstance(value, str):
        return _interpolate_string(value, values)
    if isinstance(value, dict):
        return {key: interpolate(item, values) for key, item in value.items()}
    if isinstance(value, list):
        return [interpolate(item, values) for item in value]
    return value


def _interpolate_string(text: str, values: Mapping[str, JsonValue]) -> str:
    """Replace every ${VAR_NAME} reference with its resolved string value."""

    def _replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in values:
            raise ManifestValidationError(
                f"Reference to unknown variable: {name}",
                details={"variable": name},
            )
        resolved = values[name]
        if resolved is None:
            raise ManifestValidationError(
                f"Variable has no resolved value: {name}",
                details={"variable": name},
            )
        return _stringify(resolved)

    return _REFERENCE_PATTERN.sub(_replace, text)


def _stringify(value: JsonValue) -> str:
    """Render a resolved variable value as template text."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return value
    return str(value)
