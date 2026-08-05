"""VS Code workspace detection from recently opened workspace storage."""

from pathlib import Path

from setuper.adapters.electron_workspace import (
    ElectronWorkspaceAdapter,
    JsonFileWorkspaceStorageReader,
    WorkspaceStorageReader,
)


def default_storage_path() -> Path:
    """Return the default macOS VS Code workspace storage file."""
    return Path.home() / "Library" / "Application Support" / "Code" / "storage.json"


class VSCodeAdapter(ElectronWorkspaceAdapter):
    """Detect reachable recently opened VS Code workspaces."""

    type_name = "vscode"
    display_label = "VS Code"

    def __init__(self, reader: WorkspaceStorageReader | None = None) -> None:
        """Create a VS Code adapter defaulting to VS Code's storage file."""
        super().__init__(
            reader or JsonFileWorkspaceStorageReader(default_storage_path())
        )
