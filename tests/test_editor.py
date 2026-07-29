"""Tests for safe editor invocation."""

from pathlib import Path

import pytest

from setuper.domain.errors import AdapterUnavailableError, SetuperError
from setuper.infrastructure import editor


def test_editor_uses_argument_vector_without_shell(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Editor settings are parsed into arguments and never passed to a shell."""
    captured: list[str] = []

    def capture(arguments: tuple[str, ...]) -> None:
        captured.extend(arguments)

    monkeypatch.setattr(editor, "_run_editor", capture)

    editor.open_editor(
        Path("/tmp/Project With Spaces/setup.yaml"),
        environment={"VISUAL": "code --wait"},
        platform="linux",
    )

    assert captured == [
        "code",
        "--wait",
        "/tmp/Project With Spaces/setup.yaml",
    ]


def test_missing_editor_is_a_typed_unsupported_error() -> None:
    """Unsupported platforms require an explicit editor configuration."""
    with pytest.raises(AdapterUnavailableError):
        editor.open_editor(
            Path("/tmp/setup.yaml"),
            environment={},
            platform="linux",
        )


def test_malformed_editor_command_is_typed() -> None:
    """Invalid shell-style quoting cannot escape as an unhandled exception."""
    with pytest.raises(AdapterUnavailableError):
        editor.open_editor(
            Path("/tmp/setup.yaml"),
            environment={"EDITOR": "'unterminated"},
            platform="linux",
        )


def test_nonzero_editor_exit_is_typed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed editor process does not escape as an unhandled exception."""

    class Result:
        returncode = 12

    monkeypatch.setattr(editor.subprocess, "run", lambda *args, **kwargs: Result())

    with pytest.raises(SetuperError) as raised:
        editor.open_editor(
            Path("/tmp/setup.yaml"),
            environment={"EDITOR": "false"},
            platform="linux",
        )

    assert raised.value.details == {"exit_code": 12}
