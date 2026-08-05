"""Window bounds capture via System Events, without unreliable Space data.

macOS Spaces have no stable public API for reliable assignment, and display
identity cannot be resolved through System Events alone. Both are
deliberately omitted rather than guessed; only window position, size, and
owning application identity are captured.
"""

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

_FIELD_COUNT = 7
_LIST_WINDOW_BOUNDS: tuple[str, ...] = (
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
    "try",
    "-e",
    "repeat with win in (every window of proc)",
    "-e",
    'set winName to ""',
    "-e",
    "try",
    "-e",
    "set winName to name of win",
    "-e",
    "end try",
    "-e",
    "set winPos to position of win",
    "-e",
    "set winSize to size of win",
    "-e",
    "set outputText to outputText & procName & tab & procBundle & tab & "
    "winName & tab & (item 1 of winPos) & tab & (item 2 of winPos) & tab & "
    "(item 1 of winSize) & tab & (item 2 of winSize) & linefeed",
    "-e",
    "end repeat",
    "-e",
    "end try",
    "-e",
    "end repeat",
    "-e",
    "end tell",
    "-e",
    "return outputText",
)
DISPLAY_AND_SPACE_WARNING = (
    "Display identity and macOS Space are not captured; neither is reliably "
    "available through public APIs."
)
MACHINE_BOUND_WARNING = (
    "Window bounds are tied to the current display arrangement and may not "
    "restore identically on another arrangement."
)


class WindowGeometryAdapter(BaseResourceAdapter):
    """Detect window position and size for visible application windows."""

    type_name = "window_geometry"

    def __init__(self, runner: CommandRunner) -> None:
        """Create a window geometry adapter with an injectable command boundary."""
        self._runner = runner

    def detect(self, context: CaptureContext) -> list[DetectedResource]:
        """Detect visible window bounds without display or Space assignment."""
        if context.platform is not Platform.MACOS:
            raise UnsupportedPlatformError(
                f"Window geometry detection is unsupported on: "
                f"{context.platform.value}",
                details={"platform": context.platform.value},
            )
        result = self._runner.run(_LIST_WINDOW_BOUNDS)
        if result.returncode != 0:
            return []

        findings = [
            finding
            for line in result.stdout.splitlines()
            if line.strip()
            if (finding := self._finding_for_line(line)) is not None
        ]
        return sorted(findings, key=lambda finding: finding.identity)

    def _finding_for_line(self, line: str) -> DetectedResource | None:
        """Parse one tab-separated window record into a finding."""
        fields = line.split("\t")
        if len(fields) != _FIELD_COUNT:
            return None
        (
            process_name,
            bundle_id,
            window_title,
            x_text,
            y_text,
            width_text,
            height_text,
        ) = (field.strip() for field in fields)
        if not process_name:
            return None
        try:
            x, y, width, height = (
                int(x_text),
                int(y_text),
                int(width_text),
                int(height_text),
            )
        except ValueError:
            return None

        config: dict[str, JsonValue] = {
            "process_name": process_name,
            "x": x,
            "y": y,
            "width": width,
            "height": height,
        }
        if bundle_id:
            config["bundle_id"] = bundle_id
        if window_title:
            config["window_title"] = window_title

        owner = bundle_id or process_name
        identity_title = window_title or "window"
        return DetectedResource(
            identity=f"window_geometry:{owner}:{identity_title}:{x}:{y}",
            type_name=self.type_name,
            display_name=f"{process_name}: {window_title}"
            if window_title
            else process_name,
            support=CaptureSupport.MACHINE_BOUND,
            config=config,
            metadata={"capture_source": "window_geometry"},
            warnings=(MACHINE_BOUND_WARNING, DISPLAY_AND_SPACE_WARNING),
        )

    def capture(self, resource: DetectedResource) -> ResourceSpec:
        """Convert one window-bounds finding into a review-required resource."""
        if resource.type_name != self.type_name:
            raise ManifestValidationError(
                f"Window geometry adapter cannot capture type: {resource.type_name}",
                details={"type": resource.type_name},
            )
        process_name = resource.config.get("process_name")
        if not isinstance(process_name, str) or not process_name:
            raise ManifestValidationError(
                "Detected window is missing its owning process name",
            )
        bundle_id = resource.config.get("bundle_id")
        window_title = resource.config.get("window_title")
        owner = bundle_id if isinstance(bundle_id, str) and bundle_id else process_name
        title = (
            window_title if isinstance(window_title, str) and window_title else "window"
        )
        metadata: dict[str, JsonValue] = dict(resource.metadata)
        metadata["capture_support"] = resource.support.value
        metadata["capture_warnings"] = list(resource.warnings)
        slug = resource_slug(f"{owner}-{title}", fallback="window")
        return ResourceSpec(
            id=f"window-{slug}",
            type=self.type_name,
            description=resource.display_name,
            config=dict(resource.config),
            metadata=metadata,
        )
