"""Pure comparison between a stored manifest and freshly captured resources."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from setuper.domain.models import ResourceSpec

DiffStatus = Literal["unchanged", "changed", "missing", "added"]


@dataclass(frozen=True, slots=True)
class ResourceDiff:
    """One resource's comparison between stored and current capture."""

    resource_id: str
    type_name: str
    status: DiffStatus


@dataclass(frozen=True, slots=True)
class DiffResult:
    """Aggregate comparison between a stored manifest and current capture."""

    entries: tuple[ResourceDiff, ...]


def diff_resources(
    stored: Sequence[ResourceSpec],
    current: Sequence[ResourceSpec],
) -> DiffResult:
    """Compare stored manifest resources against freshly captured resources."""
    stored_by_id = {resource.id: resource for resource in stored}
    current_by_id = {resource.id: resource for resource in current}
    stored_ids = set(stored_by_id)
    current_ids = set(current_by_id)

    entries: list[ResourceDiff] = []
    for resource_id in stored_ids & current_ids:
        stored_resource = stored_by_id[resource_id]
        current_resource = current_by_id[resource_id]
        status: DiffStatus = (
            "changed"
            if stored_resource.config != current_resource.config
            else "unchanged"
        )
        entries.append(ResourceDiff(resource_id, stored_resource.type, status))
    for resource_id in stored_ids - current_ids:
        entries.append(
            ResourceDiff(resource_id, stored_by_id[resource_id].type, "missing")
        )
    for resource_id in current_ids - stored_ids:
        entries.append(
            ResourceDiff(resource_id, current_by_id[resource_id].type, "added")
        )
    entries.sort(key=lambda entry: entry.resource_id)
    return DiffResult(entries=tuple(entries))
