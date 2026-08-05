"""Tests for dependency graph construction, cycles, and topological order."""

import pytest

from setuper.domain.errors import DependencyCycleError, ManifestValidationError
from setuper.domain.graph import build_dependency_graph
from setuper.domain.models import ResourceSpec


def _resource(resource_id: str, *depends_on: str) -> ResourceSpec:
    """Build one minimal resource spec with the given dependencies."""
    return ResourceSpec(id=resource_id, type="command", depends_on=depends_on)


def test_build_dependency_graph_orders_dependencies_before_dependents() -> None:
    """A linear chain resolves in dependency order."""
    resources = [
        _resource("frontend", "postgres"),
        _resource("postgres"),
        _resource("editor", "frontend"),
    ]

    graph = build_dependency_graph(resources)

    assert graph.order.index("postgres") < graph.order.index("frontend")
    assert graph.order.index("frontend") < graph.order.index("editor")
    assert graph.dependencies_of("frontend") == ("postgres",)
    assert graph.dependents_of("postgres") == ("frontend",)


def test_build_dependency_graph_orders_independent_resources_deterministically() -> (
    None
):
    """Resources with no interdependency are ordered alphabetically for stability."""
    resources = [_resource("zeta"), _resource("alpha"), _resource("mid")]

    graph = build_dependency_graph(resources)

    assert graph.order == ("alpha", "mid", "zeta")


def test_build_dependency_graph_rejects_a_direct_cycle() -> None:
    """A depends on B and B depends on A is rejected as a cycle."""
    resources = [_resource("a", "b"), _resource("b", "a")]

    with pytest.raises(DependencyCycleError, match="a"):
        build_dependency_graph(resources)


def test_build_dependency_graph_rejects_a_longer_cycle() -> None:
    """A cycle spanning more than two resources is still detected."""
    resources = [_resource("a", "b"), _resource("b", "c"), _resource("c", "a")]

    with pytest.raises(DependencyCycleError):
        build_dependency_graph(resources)


def test_build_dependency_graph_rejects_dependency_on_a_filtered_out_resource() -> None:
    """A dependency outside the given resource set is a clear, typed error."""
    resources = [_resource("frontend", "postgres")]

    with pytest.raises(ManifestValidationError, match="postgres"):
        build_dependency_graph(resources)


def test_build_dependency_graph_handles_no_resources() -> None:
    """An empty resource set produces an empty, valid graph."""
    graph = build_dependency_graph([])

    assert graph.order == ()
