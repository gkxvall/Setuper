"""Tests for read-only, per-adapter-isolated capture orchestration."""

from pathlib import Path

from setuper.adapters.base import CaptureContext, DetectedResource
from setuper.adapters.registry import AdapterRegistry
from setuper.application.capture_service import (
    CaptureService,
    build_capture_context,
)
from setuper.domain.enums import CaptureSupport, Platform
from setuper.domain.errors import AdapterUnavailableError, UnsupportedPlatformError


class FakeAdapter:
    """Detection-only fake adapter returning a fixed result or raising."""

    def __init__(
        self,
        type_name: str,
        *,
        findings: list[DetectedResource] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.type_name = type_name
        self._findings = findings or []
        self._error = error

    def detect(self, context: CaptureContext) -> list[DetectedResource]:
        """Return the configured findings or raise the configured error."""
        if self._error is not None:
            raise self._error
        return self._findings


def make_context() -> CaptureContext:
    """Create a deterministic capture context."""
    return CaptureContext(platform=Platform.MACOS, current_directory=Path("/repo"))


def _finding(type_name: str, identity: str) -> DetectedResource:
    """Build one minimal detected resource for a fake adapter."""
    return DetectedResource(
        identity=identity,
        type_name=type_name,
        display_name=identity,
        support=CaptureSupport.SUPPORTED,
    )


def test_inspect_aggregates_findings_across_adapters_in_stable_order() -> None:
    """Findings from every adapter are combined and sorted deterministically."""
    registry = AdapterRegistry(
        [
            FakeAdapter(
                "zeta", findings=[_finding("zeta", "z2"), _finding("zeta", "z1")]
            ),
            FakeAdapter("alpha", findings=[_finding("alpha", "a1")]),
        ]
    )
    service = CaptureService(registry)

    result = service.inspect(make_context())

    assert [finding.identity for finding in result.findings] == ["a1", "z1", "z2"]
    assert result.issues == ()


def test_inspect_isolates_one_adapter_failure_from_the_rest() -> None:
    """An unavailable or unsupported adapter is reported, not raised."""
    registry = AdapterRegistry(
        [
            FakeAdapter("broken", error=AdapterUnavailableError("tool missing")),
            FakeAdapter(
                "unsupported",
                error=UnsupportedPlatformError("wrong platform"),
            ),
            FakeAdapter("ok", findings=[_finding("ok", "ok1")]),
        ]
    )
    service = CaptureService(registry)

    result = service.inspect(make_context())

    assert [finding.identity for finding in result.findings] == ["ok1"]
    assert {issue.type_name for issue in result.issues} == {"broken", "unsupported"}


def test_build_capture_context_carries_only_environment_names() -> None:
    """The live context never carries environment variable values."""
    context = build_capture_context(
        environment={"HOME": "/Users/dev", "SECRET": "shh"},
        platform_name="darwin",
    )

    assert context.platform is Platform.MACOS
    assert context.environment_names == frozenset({"HOME", "SECRET"})
    assert "shh" not in repr(context.environment_names)


def test_build_capture_context_maps_platform_identifiers() -> None:
    """Raw platform identifiers map onto the domain platform enum."""
    assert build_capture_context(platform_name="darwin").platform is Platform.MACOS
    assert build_capture_context(platform_name="linux").platform is Platform.LINUX
    assert build_capture_context(platform_name="win32").platform is Platform.WINDOWS
