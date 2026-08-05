"""Tests for non-destructive Git repository detection."""

from pathlib import Path

import pytest

from setuper.adapters.base import CaptureContext
from setuper.adapters.git import GitAdapter
from setuper.domain.enums import CaptureSupport, Platform
from setuper.domain.errors import UnsupportedPlatformError
from setuper.infrastructure.commands import CommandResult


class FakeCommandRunner:
    """Command boundary returning results by Git subcommand."""

    def __init__(self, results: dict[str, CommandResult]) -> None:
        self._results = results
        self.calls: list[tuple[str, ...]] = []

    def run(
        self,
        arguments: tuple[str, ...],
        *,
        cwd: Path | None = None,
        timeout_seconds: float = 5.0,
    ) -> CommandResult:
        """Return a configured result for the first matching command token."""
        self.calls.append(arguments)
        for command, result in self._results.items():
            if command in arguments:
                return result
        return CommandResult(1, "", "")


def make_context(
    directory: Path,
    platform: Platform = Platform.MACOS,
) -> CaptureContext:
    """Create a deterministic capture context rooted at a real directory."""
    return CaptureContext(
        platform=platform,
        current_directory=directory / "subdir",
    )


def test_git_detection_captures_state_and_redacts_remote_credentials(
    tmp_path: Path,
) -> None:
    """Git findings retain semantic state without embedded remote credentials."""
    root = tmp_path / "Project With Spaces"
    resolved_root = str(root.resolve())
    runner = FakeCommandRunner(
        {
            "--show-toplevel": CommandResult(0, f"{root}\n", ""),
            "--short": CommandResult(0, "main\n", ""),
            "--short=12": CommandResult(0, "abc123def456\n", ""),
            "get-url": CommandResult(
                0,
                "https://developer:literal-token@example.com/org/repo.git\n",
                "",
            ),
            "--porcelain=v1": CommandResult(0, " M src/app.py\n", ""),
        }
    )
    adapter = GitAdapter(runner)

    finding = adapter.detect(make_context(root))[0]

    assert finding.support is CaptureSupport.MACHINE_BOUND
    assert finding.config == {
        "root": resolved_root,
        "dirty": True,
        "branch": "main",
        "commit": "abc123def456",
        "remote": "https://example.com/org/repo.git",
    }
    assert "literal-token" not in str(finding.config)
    assert all("--no-optional-locks" in call for call in runner.calls)
    assert all("core.fsmonitor=false" in call for call in runner.calls)

    resource = adapter.capture(finding)
    assert resource.id == "git-project-with-spaces"
    assert resource.type == "git"


def test_git_detection_handles_non_repository_and_detached_head(
    tmp_path: Path,
) -> None:
    """A non-repository is absent; detached HEAD is explicitly surfaced."""
    assert GitAdapter(
        FakeCommandRunner({"--show-toplevel": CommandResult(1, "", "")})
    ).detect(make_context(tmp_path)) == []

    root = tmp_path / "repository"
    adapter = GitAdapter(
        FakeCommandRunner(
            {
                "--show-toplevel": CommandResult(0, f"{root}\n", ""),
                "--short": CommandResult(1, "", ""),
                "--short=12": CommandResult(0, "abc123\n", ""),
                "--porcelain=v1": CommandResult(0, "", ""),
            }
        )
    )

    finding = adapter.detect(make_context(root))[0]

    assert "branch" not in finding.config
    assert finding.config["commit"] == "abc123"
    assert "Repository is in detached HEAD state." in finding.warnings


def test_git_detection_rejects_unsupported_platform(tmp_path: Path) -> None:
    """Git capture stays within the documented macOS v1 scope."""
    adapter = GitAdapter(FakeCommandRunner({}))

    with pytest.raises(UnsupportedPlatformError):
        adapter.detect(make_context(tmp_path, Platform.LINUX))
