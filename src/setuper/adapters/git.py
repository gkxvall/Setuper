"""Git repository detection without modifying user work."""

import re
from pathlib import Path
from urllib.parse import SplitResult, urlsplit, urlunsplit

from pydantic import JsonValue

from setuper.adapters.base import (
    BaseResourceAdapter,
    CaptureContext,
    DetectedResource,
)
from setuper.domain.enums import CaptureSupport, Platform
from setuper.domain.errors import ManifestValidationError, UnsupportedPlatformError
from setuper.domain.models import ResourceSpec
from setuper.infrastructure.commands import CommandResult, CommandRunner


class GitAdapter(BaseResourceAdapter):
    """Detect the repository containing the capture working directory."""

    type_name = "git"

    def __init__(self, runner: CommandRunner) -> None:
        """Create a Git adapter with an injectable command boundary."""
        self._runner = runner

    def detect(self, context: CaptureContext) -> list[DetectedResource]:
        """Detect one containing repository and its non-destructive state."""
        if context.platform is not Platform.MACOS:
            raise UnsupportedPlatformError(
                f"Git detection is unsupported on: {context.platform.value}",
                details={"platform": context.platform.value},
            )
        root_result = self._git(
            context.current_directory,
            "rev-parse",
            "--show-toplevel",
        )
        if root_result.returncode != 0:
            return []
        root_text = root_result.stdout.strip()
        if not root_text:
            return []
        root = Path(root_text).expanduser().resolve()

        branch_result = self._git(root, "symbolic-ref", "--quiet", "--short", "HEAD")
        branch = (
            branch_result.stdout.strip()
            if branch_result.returncode == 0
            else None
        )
        commit_result = self._git(root, "rev-parse", "--short=12", "HEAD")
        commit = (
            commit_result.stdout.strip()
            if commit_result.returncode == 0
            else None
        )
        remote_result = self._git(root, "remote", "get-url", "origin")
        remote = (
            _redact_remote(remote_result.stdout.strip())
            if remote_result.returncode == 0
            else None
        )
        status_result = self._git(
            root,
            "status",
            "--porcelain=v1",
            "--untracked-files=normal",
        )
        dirty = status_result.returncode == 0 and bool(status_result.stdout.strip())

        config: dict[str, JsonValue] = {
            "root": str(root),
            "dirty": dirty,
        }
        if branch:
            config["branch"] = branch
        if commit:
            config["commit"] = commit
        if remote:
            config["remote"] = remote
        warnings = [
            "Repository path is machine-bound; Git state is validation-only."
        ]
        if branch is None and commit is not None:
            warnings.append("Repository is in detached HEAD state.")
        if status_result.output_truncated:
            warnings.append("Dirty-state output was truncated.")
        return [
            DetectedResource(
                identity=f"git:{root}",
                type_name=self.type_name,
                display_name=root.name or str(root),
                support=CaptureSupport.MACHINE_BOUND,
                config=config,
                metadata={"capture_source": "git"},
                warnings=tuple(warnings),
            )
        ]

    def capture(self, resource: DetectedResource) -> ResourceSpec:
        """Convert one Git finding into a validation resource."""
        if resource.type_name != self.type_name:
            raise ManifestValidationError(
                f"Git adapter cannot capture type: {resource.type_name}",
                details={"type": resource.type_name},
            )
        root = resource.config.get("root")
        if not isinstance(root, str):
            raise ManifestValidationError("Detected Git repository is missing its root")
        metadata: dict[str, JsonValue] = dict(resource.metadata)
        metadata["capture_support"] = resource.support.value
        metadata["capture_warnings"] = list(resource.warnings)
        return ResourceSpec(
            id=f"git-{_resource_slug(Path(root).name)}",
            type=self.type_name,
            description=resource.display_name,
            config=dict(resource.config),
            metadata=metadata,
        )

    def _git(self, directory: Path, *arguments: str) -> CommandResult:
        """Run one read-only Git query with hooks and optional locks disabled."""
        return self._runner.run(
            (
                "git",
                "--no-optional-locks",
                "-c",
                "core.fsmonitor=false",
                "-C",
                str(directory),
                *arguments,
            )
        )


def _redact_remote(remote: str) -> str:
    """Remove URL userinfo that may contain embedded credentials."""
    parsed = urlsplit(remote)
    if parsed.scheme not in {"http", "https"} or parsed.hostname is None:
        return remote
    host = parsed.hostname
    if parsed.port is not None:
        host = f"{host}:{parsed.port}"
    return urlunsplit(
        SplitResult(
            scheme=parsed.scheme,
            netloc=host,
            path=parsed.path,
            query=parsed.query,
            fragment=parsed.fragment,
        )
    )


def _resource_slug(value: str) -> str:
    """Create a schema-valid stable resource ID suffix."""
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "repository"
