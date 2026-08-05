"""Cursor workspace detection from recently opened workspace storage."""

from pathlib import Path

from setuper.adapters.electron_workspace import (
    ElectronWorkspaceAdapter,
    JsonFileWorkspaceStorageReader,
    WorkspaceStorageReader,
)


def default_storage_path() -> Path:
    """Return the default macOS Cursor workspace storage file."""
    return Path.home() / "Library" / "Application Support" / "Cursor" / "storage.json"


class CursorAdapter(ElectronWorkspaceAdapter):
    """Detect reachable recently opened Cursor workspaces."""

    type_name = "cursor"
    display_label = "Cursor"

    def __init__(self, reader: WorkspaceStorageReader | None = None) -> None:
        """Create a Cursor adapter defaulting to Cursor's storage file."""
        super().__init__(
            reader or JsonFileWorkspaceStorageReader(default_storage_path())
        )
