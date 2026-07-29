"""Tests for the minimal command-line interface."""

import runpy
import subprocess
import sys
from importlib.metadata import version

import pytest

from setuper.cli.app import DESCRIPTION, main


def test_root_command_shows_help(capsys: pytest.CaptureFixture[str]) -> None:
    """Invoking the root command without arguments is informative."""
    assert main([]) == 0

    output = capsys.readouterr().out
    assert DESCRIPTION in output
    assert "version" in output


def test_version_command_uses_package_metadata(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The version subcommand reports the installed distribution version."""
    assert main(["version"]) == 0

    output = capsys.readouterr().out
    assert output == f"setuper {version('setuper')}\n"


def test_module_entrypoint_supports_version_flag() -> None:
    """The Python module entry point exposes the root version flag."""
    result = subprocess.run(
        [sys.executable, "-m", "setuper", "--version"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert result.stdout == f"setuper {version('setuper')}\n"
    assert result.stderr == ""


def test_module_entrypoint_exits_cleanly(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The module wrapper translates the CLI return value into an exit status."""
    monkeypatch.setattr(sys, "argv", ["setuper", "version"])

    with pytest.raises(SystemExit) as raised:
        runpy.run_module("setuper", run_name="__main__")

    assert raised.value.code == 0
    assert capsys.readouterr().out == f"setuper {version('setuper')}\n"
