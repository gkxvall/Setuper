"""Docker Compose project detection without mutating project state."""

import json
from typing import cast

from pydantic import JsonValue

from setuper.adapters.base import (
    BaseResourceAdapter,
    CaptureContext,
    DetectedResource,
)
from setuper.adapters.identity import resource_slug
from setuper.domain.enums import CaptureSupport, Platform
from setuper.domain.errors import ManifestValidationError, UnsupportedPlatformError
from setuper.domain.models import ResourceSpec
from setuper.infrastructure.commands import CommandResult, CommandRunner


class DockerComposeAdapter(BaseResourceAdapter):
    """Detect active Compose projects through the Compose CLI plugin."""

    type_name = "docker_compose"

    def __init__(self, runner: CommandRunner) -> None:
        """Create a Compose adapter with an injectable command boundary."""
        self._runner = runner

    def detect(self, context: CaptureContext) -> list[DetectedResource]:
        """Detect active Compose projects and their config file references."""
        if context.platform is not Platform.MACOS:
            raise UnsupportedPlatformError(
                f"Docker Compose detection is unsupported on: {context.platform.value}",
                details={"platform": context.platform.value},
            )
        result = self._runner.run(("docker", "compose", "ls", "--format", "json"))
        if result.returncode != 0:
            return []
        projects = _parse_projects(result)
        findings = [
            finding
            for project in projects
            if (finding := self._finding_for(project)) is not None
        ]
        return sorted(findings, key=lambda finding: finding.identity)

    def capture(self, resource: DetectedResource) -> ResourceSpec:
        """Convert one Compose finding into a review-required resource."""
        if resource.type_name != self.type_name:
            raise ManifestValidationError(
                f"Docker Compose adapter cannot capture type: {resource.type_name}",
                details={"type": resource.type_name},
            )
        name = resource.config.get("project_name")
        if not isinstance(name, str) or not name:
            raise ManifestValidationError(
                "Detected Compose project is missing its project name",
            )
        metadata: dict[str, JsonValue] = dict(resource.metadata)
        metadata["capture_support"] = resource.support.value
        metadata["capture_warnings"] = list(resource.warnings)
        return ResourceSpec(
            id=f"compose-{resource_slug(name, fallback='project')}",
            type=self.type_name,
            description=resource.display_name,
            config=dict(resource.config),
            metadata=metadata,
        )

    def _finding_for(self, project: dict[str, JsonValue]) -> DetectedResource | None:
        """Build one finding from a `docker compose ls` project record."""
        name = project.get("Name")
        if not isinstance(name, str) or not name:
            return None
        status = project.get("Status")
        config_files_raw = project.get("ConfigFiles")
        config_files = (
            [path for path in config_files_raw.split(",") if path]
            if isinstance(config_files_raw, str)
            else []
        )

        config: dict[str, JsonValue] = {"project_name": name}
        if isinstance(status, str) and status:
            config["status"] = status
        if config_files:
            config["config_files"] = cast(JsonValue, config_files)

        support = (
            CaptureSupport.PARTIALLY_SUPPORTED
            if config_files
            else CaptureSupport.MACHINE_BOUND
        )
        warnings = ["Compose config file paths are machine-bound."]
        if not config_files:
            warnings.append(
                "Compose project detection is ambiguous without a config file."
            )

        return DetectedResource(
            identity=f"docker_compose:{name}",
            type_name=self.type_name,
            display_name=name,
            support=support,
            config=config,
            metadata={"capture_source": "docker_compose"},
            warnings=tuple(warnings),
        )


def _parse_projects(result: CommandResult) -> list[dict[str, JsonValue]]:
    """Parse best-effort `docker compose ls` JSON output."""
    text = result.stdout.strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [entry for entry in parsed if isinstance(entry, dict)]
