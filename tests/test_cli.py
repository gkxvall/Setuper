"""Tests for the minimal command-line interface."""

import runpy
import subprocess
import sys
from importlib.metadata import version
from pathlib import Path

import pytest

from setuper.cli import app
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


def test_list_command_renders_empty_and_sorted_results(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The CLI lists setup names in repository order with a clear empty state."""
    paths = SetuperPaths(
        data_directory=tmp_path / "data",
        log_directory=tmp_path / "logs",
        cache_directory=tmp_path / "cache",
    )

    assert main(["list"], paths=paths) == 0
    assert capsys.readouterr().out == "No setups found.\n"

    second = tmp_path / "Zulu"
    first = tmp_path / "Alpha"
    second.mkdir()
    first.mkdir()
    assert main(["init", str(second)], paths=paths) == 0
    assert main(["init", str(first)], paths=paths) == 0
    capsys.readouterr()

    assert main(["list"], paths=paths) == 0
    assert capsys.readouterr().out == "Alpha\nZulu\n"


def test_show_command_renders_validated_manifest_and_portability_limit(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The CLI shows manifest details and an honest adapter assessment fallback."""
    project = tmp_path / "Démo"
    project.mkdir()
    paths = SetuperPaths(
        data_directory=tmp_path / "data",
        log_directory=tmp_path / "logs",
        cache_directory=tmp_path / "cache",
    )
    assert main(["init", str(project)], paths=paths) == 0
    capsys.readouterr()

    assert main(["show", "Démo", "--portability"], paths=paths) == 0

    output = capsys.readouterr().out
    assert "schema_version: 1" in output
    assert "name: Démo" in output
    assert "Declared platforms: macos" in output
    assert "unavailable until adapter validation" in output


def test_show_command_returns_not_found_exit(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """An unknown setup returns the documented not-found exit code."""
    paths = SetuperPaths(
        data_directory=tmp_path / "data",
        log_directory=tmp_path / "logs",
        cache_directory=tmp_path / "cache",
    )

    assert main(["show", "missing"], paths=paths) == 4

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "ERROR [SETUP_NOT_FOUND]" in captured.err


def test_edit_command_updates_manifest_through_editor(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The CLI delegates edits and reports the committed manifest."""
    project = tmp_path / "workspace"
    project.mkdir()
    paths = SetuperPaths(
        data_directory=tmp_path / "data",
        log_directory=tmp_path / "logs",
        cache_directory=tmp_path / "cache",
    )
    assert main(["init", str(project)], paths=paths) == 0
    capsys.readouterr()

    def edit_description(path: Path) -> None:
        path.write_text(
            path.read_text(encoding="utf-8") + "description: From editor\n",
            encoding="utf-8",
        )

    monkeypatch.setattr(app, "open_editor", edit_description)

    assert main(["edit", "workspace"], paths=paths) == 0

    assert "Updated workspace" in capsys.readouterr().out
    assert "description: From editor" in (project / ".setuper.yaml").read_text(
        encoding="utf-8"
    )


def test_clone_command_creates_independent_managed_setup(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The CLI clones a stored setup into its managed manifest directory."""
    project = tmp_path / "source"
    project.mkdir()
    paths = SetuperPaths(
        data_directory=tmp_path / "data",
        log_directory=tmp_path / "logs",
        cache_directory=tmp_path / "cache",
    )
    assert main(["init", str(project)], paths=paths) == 0
    capsys.readouterr()

    assert main(["clone", "source", "target copy"], paths=paths) == 0

    assert "Cloned source as target copy" in capsys.readouterr().out
    cloned_files = list(paths.manifest_directory.glob("*.yaml"))
    assert len(cloned_files) == 1
    assert "name: target copy" in cloned_files[0].read_text(encoding="utf-8")
