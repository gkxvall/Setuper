"""Tests for the minimal command-line interface."""

import json
import runpy
import subprocess
import sys
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from uuid import UUID

import pytest

from setuper.adapters.base import CaptureContext, DetectedResource
from setuper.adapters.registry import AdapterRegistry
from setuper.cli import app
from setuper.cli.app import DESCRIPTION, main
from setuper.domain.enums import CaptureSupport, LaunchStatus
from setuper.domain.models import SetupManifest
from setuper.infrastructure.database import connect_database
from setuper.infrastructure.launch_repository import LaunchRecord, LaunchRepository
from setuper.infrastructure.manifests import load_manifest, save_manifest
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


class _FakeInspectAdapter:
    """Detection-only fake adapter that never touches the real machine."""

    def __init__(self, type_name: str, findings: list[DetectedResource]) -> None:
        self.type_name = type_name
        self._findings = findings

    def detect(self, context: CaptureContext) -> list[DetectedResource]:
        """Return the configured findings regardless of context."""
        return self._findings


def test_inspect_command_renders_findings_and_warnings(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Inspect renders each finding with its support level and warnings."""
    finding = DetectedResource(
        identity="git:/repo",
        type_name="git",
        display_name="repo",
        support=CaptureSupport.MACHINE_BOUND,
        warnings=("Repository path is machine-bound.",),
    )
    registry = AdapterRegistry([_FakeInspectAdapter("git", [finding])])

    assert main(["inspect"], capture_registry=registry) == 0

    output = capsys.readouterr().out
    assert "[git] repo (machine_bound)" in output
    assert "Repository path is machine-bound." in output


def test_inspect_json_returns_a_stable_envelope(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Inspect JSON reports findings and unavailable adapters explicitly."""
    finding = DetectedResource(
        identity="git:/repo",
        type_name="git",
        display_name="repo",
        support=CaptureSupport.MACHINE_BOUND,
    )
    registry = AdapterRegistry([_FakeInspectAdapter("git", [finding])])

    assert main(["inspect", "--json"], capture_registry=registry) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["command"] == "inspect"
    assert payload["data"]["findings"][0]["identity"] == "git:/repo"
    assert payload["data"]["findings"][0]["support"] == "machine_bound"
    assert payload["data"]["issues"] == []


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
    alpha_manifest = load_manifest(first / ".setuper.yaml")
    assert alpha_manifest.id is not None
    with connect_database(paths.database_path) as connection:
        LaunchRepository(connection).create_launch(
            LaunchRecord(
                id=UUID("30ad2e7e-0774-48e1-a93a-5b566bbdcac1"),
                setup_id=alpha_manifest.id,
                manifest_hash="a" * 64,
                profile=None,
                status=LaunchStatus.STOPPED,
                started_at=datetime(2026, 7, 29, 12, 34, tzinfo=UTC),
            )
        )

    assert main(["list"], paths=paths) == 0
    output = capsys.readouterr().out
    assert output.splitlines() == [
        "NAME   RESOURCES  LAST LAUNCHED     STATUS",
        "Alpha  0          2026-07-29 12:34  stopped",
        "Zulu   0          never             -",
    ]


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


def test_rename_command_updates_future_lookup(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The CLI renames a setup across its manifest and database lookup."""
    project = tmp_path / "source"
    project.mkdir()
    paths = SetuperPaths(
        data_directory=tmp_path / "data",
        log_directory=tmp_path / "logs",
        cache_directory=tmp_path / "cache",
    )
    assert main(["init", str(project)], paths=paths) == 0
    capsys.readouterr()

    assert main(["rename", "source", "renamed"], paths=paths) == 0
    assert "Renamed source as renamed" in capsys.readouterr().out
    assert main(["show", "renamed"], paths=paths) == 0
    assert "name: renamed" in capsys.readouterr().out
    assert main(["show", "source"], paths=paths) == 4


def test_delete_command_requires_confirmation_and_preserves_project_file(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The CLI cancels by default and preserves project-owned manifests."""
    project = tmp_path / "source"
    project.mkdir()
    paths = SetuperPaths(
        data_directory=tmp_path / "data",
        log_directory=tmp_path / "logs",
        cache_directory=tmp_path / "cache",
    )
    assert main(["init", str(project)], paths=paths) == 0
    capsys.readouterr()
    monkeypatch.setattr("builtins.input", lambda prompt: "")

    assert main(["delete", "source"], paths=paths) == 0
    assert capsys.readouterr().out == "Delete cancelled.\n"
    assert main(["delete", "source", "--yes"], paths=paths) == 0

    output = capsys.readouterr().out
    assert "Deleted source." in output
    assert "Preserved manifest" in output
    assert (project / ".setuper.yaml").is_file()


def test_delete_command_handles_unavailable_confirmation(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Noninteractive stdin returns an actionable error instead of a traceback."""
    paths = SetuperPaths(
        data_directory=tmp_path / "data",
        log_directory=tmp_path / "logs",
        cache_directory=tmp_path / "cache",
    )

    def end_of_input(prompt: str) -> str:
        raise EOFError

    monkeypatch.setattr("builtins.input", end_of_input)

    assert main(["delete", "source"], paths=paths) == 1

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "use --yes to confirm" in captured.err
    assert "Traceback" not in captured.err


def test_export_command_writes_standalone_yaml(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The CLI exports a stored manifest to an explicit new file."""
    project = tmp_path / "source"
    project.mkdir()
    paths = SetuperPaths(
        data_directory=tmp_path / "data",
        log_directory=tmp_path / "logs",
        cache_directory=tmp_path / "cache",
    )
    output = tmp_path / "transfer" / "source.yaml"
    assert main(["init", str(project)], paths=paths) == 0
    capsys.readouterr()

    assert (
        main(
            ["export", "source", "--output", str(output)],
            paths=paths,
        )
        == 0
    )

    assert f"Exported source to {output}" in capsys.readouterr().out
    assert output.is_file()
    assert list(paths.manifest_directory.glob("*.yaml")) == []


def test_import_command_registers_untrusted_manifest_with_name_override(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The CLI imports safe YAML and clearly surfaces its untrusted state."""
    source = tmp_path / "incoming.yaml"
    save_manifest(source, SetupManifest(name="incoming"))
    paths = SetuperPaths(
        data_directory=tmp_path / "data",
        log_directory=tmp_path / "logs",
        cache_directory=tmp_path / "cache",
    )

    assert (
        main(
            ["import", str(source), "--name", "Imported Setup"],
            paths=paths,
        )
        == 0
    )

    output = capsys.readouterr().out
    assert "Imported Imported Setup" in output
    assert "Trust: untrusted" in output
    assert len(list(paths.manifest_directory.glob("*.yaml"))) == 1
    assert main(["show", "Imported Setup"], paths=paths) == 0


def test_list_json_returns_stable_setup_summaries(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """List JSON uses the documented envelope and stable repository order."""
    project = tmp_path / "Démo"
    project.mkdir()
    paths = SetuperPaths(
        data_directory=tmp_path / "data",
        log_directory=tmp_path / "logs",
        cache_directory=tmp_path / "cache",
    )
    assert main(["init", str(project)], paths=paths) == 0
    capsys.readouterr()

    assert main(["list", "--json"], paths=paths) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["command"] == "list"
    assert payload["warnings"] == []
    assert payload["data"]["setups"][0]["name"] == "Démo"
    assert payload["data"]["setups"][0]["source"] == "project"
    assert payload["data"]["setups"][0]["resource_count"] == 0
    assert payload["data"]["setups"][0]["last_launched_at"] is None
    assert payload["data"]["setups"][0]["status"] is None


def test_show_json_reports_portability_limit(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Show JSON keeps manifest data structured and limitations explicit."""
    project = tmp_path / "workspace"
    project.mkdir()
    paths = SetuperPaths(
        data_directory=tmp_path / "data",
        log_directory=tmp_path / "logs",
        cache_directory=tmp_path / "cache",
    )
    assert main(["init", str(project)], paths=paths) == 0
    capsys.readouterr()

    assert (
        main(
            ["show", "workspace", "--json", "--portability"],
            paths=paths,
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["data"]["manifest"]["name"] == "workspace"
    assert payload["data"]["portability"]["resource_assessment"] == {
        "available": False,
        "reason": "unavailable until adapter validation",
    }
    assert payload["warnings"] == ["Resource portability requires adapter validation."]


def test_show_json_returns_structured_typed_error(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """JSON failures remain one stdout object with the documented exit code."""
    paths = SetuperPaths(
        data_directory=tmp_path / "data",
        log_directory=tmp_path / "logs",
        cache_directory=tmp_path / "cache",
    )

    assert main(["show", "missing", "--json"], paths=paths) == 4

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload == {
        "ok": False,
        "command": "show",
        "error": {
            "code": "SETUP_NOT_FOUND",
            "message": "Setup not found: missing",
            "details": {"name": "missing"},
        },
    }
    assert captured.err == ""
