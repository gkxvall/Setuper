"""Tests for pure `ready_when` readiness-spec parsing."""

import pytest

from setuper.domain.errors import ManifestValidationError
from setuper.domain.readiness import (
    CommandReadinessSpec,
    HttpReadinessSpec,
    TcpReadinessSpec,
    parse_readiness_spec,
)


def test_parse_readiness_spec_returns_none_for_no_ready_when() -> None:
    """A resource without ready_when has no readiness check to run."""
    assert parse_readiness_spec(None) is None
    assert parse_readiness_spec({}) is None


def test_parse_readiness_spec_parses_tcp() -> None:
    """A tcp body parses into a typed TCP readiness spec."""
    spec = parse_readiness_spec({"tcp": {"host": "127.0.0.1", "port": 5432}})

    assert spec == TcpReadinessSpec(host="127.0.0.1", port=5432)


def test_parse_readiness_spec_parses_http_with_defaults() -> None:
    """An http body applies documented defaults for method and status."""
    spec = parse_readiness_spec({"http": {"url": "http://127.0.0.1:3000"}})

    assert spec == HttpReadinessSpec(url="http://127.0.0.1:3000")


def test_parse_readiness_spec_parses_http_with_overrides() -> None:
    """An http body honors explicit method and expected status overrides."""
    spec = parse_readiness_spec(
        {
            "http": {
                "url": "http://127.0.0.1:3000/health",
                "method": "HEAD",
                "expected_status": 204,
            }
        }
    )

    assert spec == HttpReadinessSpec(
        url="http://127.0.0.1:3000/health",
        method="HEAD",
        expected_status=204,
    )


def test_parse_readiness_spec_parses_command_with_string_and_list() -> None:
    """A command body accepts either a single string or a list of arguments."""
    assert parse_readiness_spec({"command": {"command": "pg_isready"}}) == (
        CommandReadinessSpec(command=("pg_isready",))
    )
    assert parse_readiness_spec(
        {"command": {"command": ["pg_isready", "-q"], "expected_exit_code": 0}}
    ) == CommandReadinessSpec(command=("pg_isready", "-q"), expected_exit_code=0)


def test_parse_readiness_spec_rejects_multiple_kinds() -> None:
    """Declaring more than one readiness kind at once is rejected."""
    with pytest.raises(ManifestValidationError):
        parse_readiness_spec(
            {
                "tcp": {"host": "127.0.0.1", "port": 5432},
                "http": {"url": "http://127.0.0.1:3000"},
            }
        )


@pytest.mark.parametrize(
    "body",
    [
        {"tcp": {"port": 5432}},
        {"tcp": {"host": "127.0.0.1", "port": "5432"}},
        {"tcp": {"host": "127.0.0.1", "port": True}},
        {"http": {}},
        {"http": {"url": "http://x", "expected_status": "200"}},
        {"command": {}},
        {"command": {"command": ""}},
        {"command": {"command": 5}},
        {"command": {"command": "x", "expected_exit_code": "0"}},
        {"tcp": "not-a-mapping"},
    ],
)
def test_parse_readiness_spec_rejects_invalid_bodies(body: dict[str, object]) -> None:
    """Missing fields, wrong types, and non-mapping bodies are all rejected."""
    with pytest.raises(ManifestValidationError):
        parse_readiness_spec(body)
