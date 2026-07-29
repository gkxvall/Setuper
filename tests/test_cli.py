"""Tests for the minimal command-line interface."""

import runpy
import subprocess
import sys
from importlib.metadata import version
from pathlib import Path

import pytest

from setuper.cli.app import DESCRIPTION, main
from setuper.infrastructure.paths import SetuperPaths


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


def test_init_command_creates_project_setup(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The CLI initializes a project using injected user-state paths."""
    project = tmp_path / "Project With Spaces"
    project.mkdir()
    paths = SetuperPaths(
        data_directory=tmp_path / "data",
        log_directory=tmp_path / "logs",
        cache_directory=tmp_path / "cache",
    )

    assert main(["init", str(project)], paths=paths) == 0

    assert (project / ".setuper.yaml").is_file()
    assert paths.database_path.is_file()
    assert "Initialized Project With Spaces" in capsys.readouterr().out


def test_init_command_returns_typed_validation_exit(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Expected init failures render to stderr without a traceback."""
    project = tmp_path / "workspace"
    project.mkdir()
    (project / ".setuper.yaml").write_text("existing\n", encoding="utf-8")
    paths = SetuperPaths(
        data_directory=tmp_path / "data",
        log_directory=tmp_path / "logs",
        cache_directory=tmp_path / "cache",
    )

    assert main(["init", str(project)], paths=paths) == 3

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "ERROR [MANIFEST_VALIDATION]" in captured.err
    assert "Traceback" not in captured.err
