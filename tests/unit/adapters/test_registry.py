"""Tests for adapter interfaces and registry behavior."""

from pathlib import Path

import pytest

from setuper.adapters.base import (
    BaseResourceAdapter,
    CaptureContext,
    DetectedResource,
    ResourceAdapter,
)
from setuper.adapters.registry import AdapterRegistry
from setuper.domain.enums import CaptureSupport, Platform
from setuper.domain.errors import AdapterUnavailableError


class FakeAdapter(BaseResourceAdapter):
    """Deterministic system-free adapter test double."""

    def __init__(self, type_name: str) -> None:
        self.type_name = type_name

    def detect(self, context: CaptureContext) -> list[DetectedResource]:
        """Return one finding without reading the real machine."""
        return [
            DetectedResource(
                identity=f"{self.type_name}:fixture",
                type_name=self.type_name,
                display_name="Fixture",
                support=CaptureSupport.SUPPORTED,
            )
        ]


def test_registry_orders_and_resolves_protocol_adapters() -> None:
    """Adapters are available by type and listed deterministically."""
    process = FakeAdapter("process")
    docker = FakeAdapter("docker")
    registry = AdapterRegistry((process, docker))

    assert isinstance(process, ResourceAdapter)
    assert registry.get("process") is process
    assert registry.type_names() == ("docker", "process")
    assert registry.all() == (docker, process)
    assert (
        process.detect(
            CaptureContext(
                platform=Platform.MACOS,
                current_directory=Path("/tmp"),
                environment_names=frozenset({"PATH"}),
            )
        )[0].config
        == {}
    )


def test_registry_rejects_invalid_or_duplicate_registration() -> None:
    """Registry configuration mistakes fail before capture starts."""
    registry = AdapterRegistry((FakeAdapter("process"),))

    with pytest.raises(ValueError, match="already registered"):
        registry.register(FakeAdapter("process"))
    with pytest.raises(ValueError, match="must not be empty"):
        registry.register(FakeAdapter(" "))


def test_missing_and_unsupported_operations_are_typed() -> None:
    """Unavailable adapters and operations use the documented error model."""
    registry = AdapterRegistry()
    adapter = FakeAdapter("process")

    with pytest.raises(AdapterUnavailableError):
        registry.get("missing")
    finding = DetectedResource(
        identity="process:fixture",
        type_name="process",
        display_name="Fixture",
        support=CaptureSupport.SUPPORTED,
    )
    with pytest.raises(AdapterUnavailableError, match="does not support capture"):
        adapter.capture(finding)
