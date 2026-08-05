"""Basic macOS running-application detection via System Events."""

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
from setuper.infrastructure.commands import CommandRunner

_LIST_RUNNING_APPLICATIONS: tuple[str, ...] = (
    "osascript",
    "-e",
    'tell application "System Events"',
    "-e",
    'set outputText to ""',
    "-e",
    "repeat with proc in (every application process whose background only is false)",
    "-e",
    "set procName to name of proc",
    "-e",
    'set procBundle to ""',
    "-e",
    "try",
    "-e",
    "set procBundle to bundle identifier of proc",
    "-e",
    "end try",
    "-e",
    "set outputText to outputText & procName & tab & procBundle & linefeed",
    "-e",
    "end repeat",
    "-e",
    "end tell",
    "-e",
    "return outputText",
)
NO_BUNDLE_WARNING = (
    "Bundle identifier is unavailable; relaunching by name is less reliable."
)


class MacOSAppAdapter(BaseResourceAdapter):
    """Detect visible foreground applications through System Events."""

    type_name = "macos_app"

    def __init__(self, runner: CommandRunner) -> None:
        """Create a macOS app adapter with an injectable command boundary."""
        self._runner = runner

    def detect(self, context: CaptureContext) -> list[DetectedResource]:
        """Detect foreground running applications and their bundle identity."""
        if context.platform is not Platform.MACOS:
            raise UnsupportedPlatformError(
                f"macOS app detection is unsupported on: {context.platform.value}",
                details={"platform": context.platform.value},
            )
        result = self._runner.run(_LIST_RUNNING_APPLICATIONS)
        if result.returncode != 0:
            return []

        findings: list[DetectedResource] = []
        for line in result.stdout.splitlines():
            if not line.strip():
                continue
            name, _, bundle_id = line.partition("\t")
            name = name.strip()
            bundle_id = bundle_id.strip()
            if not name:
                continue
            support = (
                CaptureSupport.SUPPORTED
                if bundle_id
                else CaptureSupport.PARTIALLY_SUPPORTED
            )
            config: dict[str, JsonValue] = {"name": name}
            if bundle_id:
                config["bundle_id"] = bundle_id
            findings.append(
                DetectedResource(
                    identity=f"macos_app:{bundle_id or name}",
                    type_name=self.type_name,
                    display_name=name,
                    support=support,
                    config=config,
                    metadata={"capture_source": "macos_app"},
                    warnings=() if bundle_id else (NO_BUNDLE_WARNING,),
                )
            )
        return sorted(findings, key=lambda finding: finding.identity)

    def capture(self, resource: DetectedResource) -> ResourceSpec:
        """Convert one application finding into a review-required resource."""
        if resource.type_name != self.type_name:
            raise ManifestValidationError(
                f"macOS app adapter cannot capture type: {resource.type_name}",
                details={"type": resource.type_name},
            )
        name = resource.config.get("name")
        if not isinstance(name, str) or not name:
            raise ManifestValidationError(
                "Detected application is missing its name",
            )
        bundle_id = resource.config.get("bundle_id")
        metadata: dict[str, JsonValue] = dict(resource.metadata)
        metadata["capture_support"] = resource.support.value
        metadata["capture_warnings"] = list(resource.warnings)
        slug_source = bundle_id if isinstance(bundle_id, str) and bundle_id else name
        return ResourceSpec(
            id=f"macos-app-{resource_slug(slug_source, fallback='application')}",
            type=self.type_name,
            description=resource.display_name,
            config=dict(resource.config),
            metadata=metadata,
        )
