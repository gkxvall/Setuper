"""Tests for bounded-concurrency, dependency-aware resource scheduling."""

import asyncio

from setuper.application.scheduler import run_scheduled
from setuper.domain.enums import ResourceRunStatus
from setuper.domain.graph import build_dependency_graph
from setuper.domain.models import ResourceSpec


def _resource(resource_id: str, *depends_on: str) -> ResourceSpec:
    """Build one minimal resource spec with the given dependencies."""
    return ResourceSpec(id=resource_id, type="command", depends_on=depends_on)


def test_run_scheduled_respects_dependency_order() -> None:
    """A dependent resource only runs after its dependency completes."""

    async def scenario() -> None:
        graph = build_dependency_graph(
            [_resource("postgres"), _resource("frontend", "postgres")]
        )
        start_order: list[str] = []

        async def run_resource(resource_id: str) -> ResourceRunStatus:
            start_order.append(resource_id)
            return ResourceRunStatus.READY

        results = await run_scheduled(graph, run_resource)

        assert results == {
            "postgres": ResourceRunStatus.READY,
            "frontend": ResourceRunStatus.READY,
        }
        assert start_order.index("postgres") < start_order.index("frontend")

    asyncio.run(scenario())


def test_run_scheduled_bounds_concurrent_execution() -> None:
    """No more than the configured concurrency limit runs at once."""

    async def scenario() -> None:
        graph = build_dependency_graph(
            [_resource("a"), _resource("b"), _resource("c"), _resource("d")]
        )
        in_flight = 0
        max_in_flight = 0
        lock = asyncio.Lock()

        async def run_resource(resource_id: str) -> ResourceRunStatus:
            nonlocal in_flight, max_in_flight
            async with lock:
                in_flight += 1
                max_in_flight = max(max_in_flight, in_flight)
            await asyncio.sleep(0.05)
            async with lock:
                in_flight -= 1
            return ResourceRunStatus.READY

        results = await run_scheduled(graph, run_resource, concurrency=2)

        assert all(status is ResourceRunStatus.READY for status in results.values())
        assert max_in_flight <= 2

    asyncio.run(scenario())


def test_run_scheduled_blocks_dependents_of_a_failed_dependency() -> None:
    """A failed resource blocks its dependents without running them."""

    async def scenario() -> None:
        graph = build_dependency_graph(
            [
                _resource("a"),
                _resource("b", "a"),
                _resource("c", "b"),
            ]
        )
        ran: list[str] = []

        async def run_resource(resource_id: str) -> ResourceRunStatus:
            ran.append(resource_id)
            return (
                ResourceRunStatus.FAILED
                if resource_id == "a"
                else ResourceRunStatus.READY
            )

        results = await run_scheduled(graph, run_resource)

        assert results["a"] is ResourceRunStatus.FAILED
        assert results["b"] is ResourceRunStatus.BLOCKED
        assert results["c"] is ResourceRunStatus.BLOCKED
        assert ran == ["a"]

    asyncio.run(scenario())


def test_run_scheduled_continue_on_dependency_failure_runs_dependents_anyway() -> None:
    """With the override enabled, dependents run despite a failed dependency."""

    async def scenario() -> None:
        graph = build_dependency_graph([_resource("a"), _resource("b", "a")])

        async def run_resource(resource_id: str) -> ResourceRunStatus:
            return (
                ResourceRunStatus.FAILED
                if resource_id == "a"
                else ResourceRunStatus.READY
            )

        results = await run_scheduled(
            graph,
            run_resource,
            continue_on_dependency_failure=True,
        )

        assert results["a"] is ResourceRunStatus.FAILED
        assert results["b"] is ResourceRunStatus.READY

    asyncio.run(scenario())


def test_run_scheduled_returns_an_entry_for_every_resource() -> None:
    """The result mapping covers every resource, run or blocked."""

    async def scenario() -> None:
        graph = build_dependency_graph([_resource("solo")])

        async def run_resource(resource_id: str) -> ResourceRunStatus:
            return ResourceRunStatus.READY

        results = await run_scheduled(graph, run_resource)

        assert set(results) == {"solo"}

    asyncio.run(scenario())
