"""Dependency graph construction, cycle detection, and topological ordering."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from setuper.domain.errors import DependencyCycleError, ManifestValidationError
from setuper.domain.models import ResourceSpec


@dataclass(frozen=True, slots=True)
class DependencyGraph:
    """A validated, acyclic dependency graph over one resource-ID namespace."""

    dependencies: Mapping[str, tuple[str, ...]]
    dependents: Mapping[str, tuple[str, ...]]
    order: tuple[str, ...]

    def dependencies_of(self, resource_id: str) -> tuple[str, ...]:
        """Return the direct dependencies of one resource."""
        return self.dependencies.get(resource_id, ())

    def dependents_of(self, resource_id: str) -> tuple[str, ...]:
        """Return the direct dependents of one resource."""
        return self.dependents.get(resource_id, ())


def build_dependency_graph(resources: Sequence[ResourceSpec]) -> DependencyGraph:
    """Build a validated dependency graph, rejecting cycles and unknown edges."""
    known_ids = {resource.id for resource in resources}
    dependencies: dict[str, tuple[str, ...]] = {}
    dependents: dict[str, list[str]] = {resource.id: [] for resource in resources}

    for resource in resources:
        missing = sorted(set(resource.depends_on) - known_ids)
        if missing:
            raise ManifestValidationError(
                f"Resource {resource.id!r} depends on unknown resource(s): "
                f"{', '.join(missing)}",
                details={"resource": resource.id, "missing": missing},
            )
        dependencies[resource.id] = resource.depends_on
        for dependency in resource.depends_on:
            dependents[dependency].append(resource.id)

    _detect_cycle(dependencies)
    order = _topological_order(dependencies, dependents, known_ids)
    return DependencyGraph(
        dependencies=dependencies,
        dependents={key: tuple(value) for key, value in dependents.items()},
        order=order,
    )


def _detect_cycle(dependencies: Mapping[str, tuple[str, ...]]) -> None:
    """Raise a typed error when the dependency graph contains a cycle."""
    white, gray, black = 0, 1, 2
    color: dict[str, int] = dict.fromkeys(dependencies, white)
    path: list[str] = []

    def visit(node: str) -> None:
        color[node] = gray
        path.append(node)
        for dependency in dependencies.get(node, ()):
            if color[dependency] == gray:
                cycle_start = path.index(dependency)
                cycle = (*path[cycle_start:], dependency)
                raise DependencyCycleError(
                    f"Dependency cycle detected: {' -> '.join(cycle)}",
                    details={"cycle": list(cycle)},
                )
            if color[dependency] == white:
                visit(dependency)
        path.pop()
        color[node] = black

    for node in sorted(dependencies):
        if color[node] == white:
            visit(node)


def _topological_order(
    dependencies: Mapping[str, tuple[str, ...]],
    dependents: Mapping[str, list[str]],
    known_ids: set[str],
) -> tuple[str, ...]:
    """Return one stable topological order via Kahn's algorithm."""
    in_degree = {node: len(dependencies.get(node, ())) for node in known_ids}
    ready = sorted(node for node, degree in in_degree.items() if degree == 0)
    order: list[str] = []
    while ready:
        node = ready.pop(0)
        order.append(node)
        for dependent in dependents.get(node, ()):
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                ready.append(dependent)
        ready.sort()
    return tuple(order)
