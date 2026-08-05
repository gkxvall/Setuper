"""Tests for pure variable resolution, profile merging, and interpolation."""

import pytest

from setuper.domain.errors import ManifestValidationError
from setuper.domain.models import VariableSpec
from setuper.domain.variables import (
    interpolate,
    resolve_profile_overrides,
    resolve_variable_values,
)


def test_resolve_variable_values_prefers_override_over_default() -> None:
    """An explicit override takes precedence over the declared default."""
    variables = {"PORT": VariableSpec(default="3000")}

    resolved = resolve_variable_values(variables, {"PORT": "4000"})

    assert resolved == {"PORT": "4000"}


def test_resolve_variable_values_falls_back_to_default() -> None:
    """Without an override, the declared default is used."""
    variables = {"PORT": VariableSpec(default="3000")}

    resolved = resolve_variable_values(variables, {})

    assert resolved == {"PORT": "3000"}


def test_resolve_variable_values_allows_optional_unset_variable() -> None:
    """An optional variable with no default and no override resolves to None."""
    variables = {"OPTIONAL": VariableSpec()}

    resolved = resolve_variable_values(variables, {})

    assert resolved == {"OPTIONAL": None}


def test_resolve_variable_values_rejects_missing_required_variable() -> None:
    """A required variable without a default or override is rejected."""
    variables = {"API_KEY": VariableSpec(required=True)}

    with pytest.raises(ManifestValidationError, match="API_KEY"):
        resolve_variable_values(variables, {})


def test_resolve_variable_values_rejects_unknown_override() -> None:
    """An override for an undeclared variable is rejected as a likely typo."""
    variables = {"PORT": VariableSpec(default="3000")}

    with pytest.raises(ManifestValidationError, match="TYPO"):
        resolve_variable_values(variables, {"TYPO": "1"})


def test_resolve_profile_overrides_returns_empty_when_unspecified() -> None:
    """No profile name means no overrides, regardless of declared profiles."""
    profiles = {"dev": {"PORT": "4000"}}

    assert resolve_profile_overrides(profiles, None) == {}


def test_resolve_profile_overrides_returns_named_profile_values() -> None:
    """A known profile name returns its declared variable overrides."""
    profiles = {"dev": {"PORT": "4000"}}

    assert resolve_profile_overrides(profiles, "dev") == {"PORT": "4000"}


def test_resolve_profile_overrides_rejects_unknown_profile() -> None:
    """An unknown profile name is rejected rather than silently ignored."""
    with pytest.raises(ManifestValidationError, match="staging"):
        resolve_profile_overrides({"dev": {}}, "staging")


def test_interpolate_substitutes_references_within_text() -> None:
    """A reference embedded in surrounding text is replaced in place."""
    result = interpolate("http://127.0.0.1:${PORT}/health", {"PORT": 3000})

    assert result == "http://127.0.0.1:3000/health"


def test_interpolate_walks_nested_dicts_and_lists() -> None:
    """Interpolation recurses through nested mappings and sequences."""
    value = {"env": {"PORT": "${PORT}"}, "args": ["--port", "${PORT}"]}

    result = interpolate(value, {"PORT": 3000})

    assert result == {"env": {"PORT": "3000"}, "args": ["--port", "3000"]}


def test_interpolate_renders_booleans_as_lowercase() -> None:
    """Boolean values render as lowercase text, not Python's True/False."""
    assert interpolate("${DEBUG}", {"DEBUG": True}) == "true"
    assert interpolate("${DEBUG}", {"DEBUG": False}) == "false"


def test_interpolate_passes_through_non_string_leaves() -> None:
    """Non-string, non-container leaves are returned unchanged."""
    assert interpolate(3000, {}) == 3000
    assert interpolate(None, {}) is None


def test_interpolate_rejects_reference_to_unknown_variable() -> None:
    """A reference to an undeclared variable is rejected rather than left as-is."""
    with pytest.raises(ManifestValidationError, match="TYPO"):
        interpolate("${TYPO}", {"PORT": 3000})


def test_interpolate_rejects_reference_with_no_resolved_value() -> None:
    """A reference to an optional, unset variable is rejected when used."""
    with pytest.raises(ManifestValidationError, match="OPTIONAL"):
        interpolate("${OPTIONAL}", {"OPTIONAL": None})
