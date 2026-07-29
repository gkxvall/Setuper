"""Registry for resource adapters keyed by manifest type."""

from collections.abc import Iterable

from setuper.adapters.base import ResourceAdapter
from setuper.domain.errors import AdapterUnavailableError


class AdapterRegistry:
    """Own a unique, deterministically ordered set of resource adapters."""

    def __init__(self, adapters: Iterable[ResourceAdapter] = ()) -> None:
        """Register an initial adapter collection."""
        self._adapters: dict[str, ResourceAdapter] = {}
        for adapter in adapters:
            self.register(adapter)

    def register(self, adapter: ResourceAdapter) -> None:
        """Register one adapter and reject empty or duplicate type names."""
        type_name = adapter.type_name.strip()
        if not type_name:
            raise ValueError("adapter type_name must not be empty")
        if type_name in self._adapters:
            raise ValueError(f"adapter already registered: {type_name}")
        self._adapters[type_name] = adapter

    def get(self, type_name: str) -> ResourceAdapter:
        """Return one adapter or a typed unavailable error."""
        try:
            return self._adapters[type_name]
        except KeyError as error:
            raise AdapterUnavailableError(
                f"Adapter unavailable: {type_name}",
                details={"adapter": type_name},
            ) from error

    def all(self) -> tuple[ResourceAdapter, ...]:
        """Return every adapter in stable type-name order."""
        return tuple(self._adapters[name] for name in sorted(self._adapters))

    def type_names(self) -> tuple[str, ...]:
        """Return registered manifest type names in stable order."""
        return tuple(sorted(self._adapters))
