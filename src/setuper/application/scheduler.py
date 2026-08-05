"""Bounded-concurrency scheduling of a resource dependency graph."""

import asyncio
from collections.abc import Awaitable, Callable

from setuper.domain.enums import ResourceRunStatus
from setuper.domain.graph import DependencyGraph

DEFAULT_CONCURRENCY = 4

RunResource = Callable[[str], Awaitable[ResourceRunStatus]]


async def run_scheduled(
    graph: DependencyGraph,
    run_resource: RunResource,
    *,
    concurrency: int = DEFAULT_CONCURRENCY,
    continue_on_dependency_failure: bool = False,
) -> dict[str, ResourceRunStatus]:
    """Run every resource in dependency order within a concurrency limit.

    A resource whose dependency did not become ready is marked `BLOCKED`
    without being run, unless `continue_on_dependency_failure` is set. The
    returned mapping always has one entry per resource in the graph.
    """
    semaphore = asyncio.Semaphore(max(1, concurrency))
    results: dict[str, ResourceRunStatus] = {}
    remaining = set(graph.order)

    async def run_one(resource_id: str) -> None:
        async with semaphore:
            results[resource_id] = await run_resource(resource_id)

    while remaining:
        ready_ids: list[str] = []
        blocked_ids: list[str] = []
        for resource_id in sorted(remaining):
            dependencies = graph.dependencies_of(resource_id)
            statuses = [results.get(dependency) for dependency in dependencies]
            if any(status is None for status in statuses):
                continue
            all_dependencies_ready = all(
                status is ResourceRunStatus.READY for status in statuses
            )
            if all_dependencies_ready or continue_on_dependency_failure:
                ready_ids.append(resource_id)
            else:
                blocked_ids.append(resource_id)

        for resource_id in blocked_ids:
            results[resource_id] = ResourceRunStatus.BLOCKED
            remaining.discard(resource_id)

        if not ready_ids:
            if blocked_ids:
                continue
            raise RuntimeError("Scheduler stalled on an unresolved dependency chain")

        await asyncio.gather(*(run_one(resource_id) for resource_id in ready_ids))
        remaining -= set(ready_ids)

    return results
