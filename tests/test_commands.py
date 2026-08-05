"""Tests for bounded integration command execution."""

import subprocess

import pytest

from setuper.domain.errors import AdapterUnavailableError
from setuper.infrastructure import commands
from setuper.infrastructure.commands import SubprocessCommandRunner


def test_runner_uses_no_shell_and_allowlisted_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Integration commands receive an argument vector and no secret environment."""
    captured: dict[str, object] = {}

    def fake_run(
        arguments: tuple[str, ...],
        **kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        captured["arguments"] = arguments
        captured.update(kwargs)
        return subprocess.CompletedProcess(arguments, 0, "output", "")

    monkeypatch.setattr(commands.subprocess, "run", fake_run)
    runner = SubprocessCommandRunner(
        environment={
            "PATH": "/usr/bin",
            "HOME": "/tmp/home",
            "SECRET_TOKEN": "must-not-pass",
        }
    )

    result = runner.run(("git", "status"))

    assert result.stdout == "output"
    assert captured["arguments"] == ("git", "status")
    assert captured["env"] == {"PATH": "/usr/bin", "HOME": "/tmp/home"}
    assert "shell" not in captured
    assert captured["stdin"] is subprocess.DEVNULL


def test_runner_caps_output_and_types_missing_executable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Output is bounded and missing tools use the adapter error model."""
    runner = SubprocessCommandRunner(environment={}, max_capture_characters=4)
    monkeypatch.setattr(
        commands.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            ("tool",),
            0,
            "abcdef",
            "uvwxyz",
        ),
    )

    result = runner.run(("tool",))

    assert result.stdout == "abcd"
    assert result.stderr == "uvwx"
    assert result.output_truncated is True

    def missing(*args: object, **kwargs: object) -> None:
        raise FileNotFoundError

    monkeypatch.setattr(commands.subprocess, "run", missing)
    with pytest.raises(AdapterUnavailableError, match="not found"):
        runner.run(("missing",))
