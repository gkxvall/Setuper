"""Application service for read-only machine resource capture."""

import os
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from setuper.adapters.base import CaptureContext, DetectedResource
from setuper.adapters.registry import AdapterRegistry
from setuper.domain.enums import Platform
from setuper.domain.errors import AdapterUnavailableError, UnsupportedPlatformError


@dataclass(frozen=True, slots=True)
class CaptureIssue:
    """One adapter that could not run detection on this machine."""

    type_name: str
    message: str


@dataclass(frozen=True, slots=True)
class InspectResult:
    """Aggregate capture findings and honestly reported adapter issues."""

    findings: tuple[DetectedResource, ...]
    issues: tuple[CaptureIssue, ...]


class CaptureService:
    """Run every registered adapter's detection over one machine context."""

    def __init__(self, registry: AdapterRegistry) -> None:
        """Create a capture service bound to one adapter registry."""
        self._registry = registry

    def inspect(self, context: CaptureContext) -> InspectResult:
        """Detect resources across every registered adapter."""
        findings: list[DetectedResource] = []
        issues: list[CaptureIssue] = []
        for adapter in self._registry.all():
            try:
                findings.extend(adapter.detect(context))
            except (AdapterUnavailableError, UnsupportedPlatformError) as error:
                issues.append(
                    CaptureIssue(type_name=adapter.type_name, message=error.message)
                )
        findings.sort(key=lambda finding: (finding.type_name, finding.identity))
        issues.sort(key=lambda issue: issue.type_name)
        return InspectResult(findings=tuple(findings), issues=tuple(issues))


def filter_findings(
    findings: Sequence[DetectedResource],
    *,
    include: Sequence[str] = (),
    exclude: Sequence[str] = (),
) -> tuple[DetectedResource, ...]:
    """Filter capture findings by resource-type inclusion and exclusion."""
    include_types = set(include)
    excluded_types = set(exclude)
    selected = (
        tuple(finding for finding in findings if finding.type_name in include_types)
        if include_types
        else tuple(findings)
    )
    return tuple(
        finding for finding in selected if finding.type_name not in excluded_types
    )


def build_capture_context(
    *,
    current_directory: Path | None = None,
    environment: dict[str, str] | None = None,
    platform_name: str | None = None,
) -> CaptureContext:
    """Build a capture context from the live machine, without secret values."""
    active_environment = os.environ if environment is None else environment
    return CaptureContext(
        platform=_resolve_platform(platform_name),
        current_directory=current_directory or Path.cwd(),
        environment_names=frozenset(active_environment.keys()),
    )


def _resolve_platform(platform_name: str | None) -> Platform:
    """Map a raw platform identifier onto the domain platform enum."""
    active = platform_name or sys.platform
    if active == "darwin":
        return Platform.MACOS
    if active.startswith("linux"):
        return Platform.LINUX
    return Platform.WINDOWS
