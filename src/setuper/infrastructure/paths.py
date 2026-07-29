"""Platform-standard filesystem locations."""

import sys
from dataclasses import dataclass
from pathlib import Path

from setuper.domain.errors import UnsupportedPlatformError

APP_DIRECTORY_NAME = "setuper"


@dataclass(frozen=True, slots=True)
class SetuperPaths:
    """Resolved user-owned locations used by Setuper."""

    data_directory: Path
    log_directory: Path
    cache_directory: Path

    @property
    def manifest_directory(self) -> Path:
        """Return the directory containing user setup manifests."""
        return self.data_directory / "setups"

    @property
    def plugin_directory(self) -> Path:
        """Return the directory containing executable plugins."""
        return self.data_directory / "plugins"

    @property
    def database_path(self) -> Path:
        """Return the operational SQLite database path."""
        return self.data_directory / "state.db"

    @property
    def config_path(self) -> Path:
        """Return the user configuration file path."""
        return self.data_directory / "config.yaml"

    def ensure_directories(self) -> None:
        """Create private directories required for normal operation."""
        for directory in (
            self.data_directory,
            self.manifest_directory,
            self.plugin_directory,
            self.log_directory,
            self.cache_directory,
        ):
            directory.mkdir(mode=0o700, parents=True, exist_ok=True)


def resolve_paths(
    *,
    home: Path | None = None,
    platform_name: str | None = None,
) -> SetuperPaths:
    """Resolve Setuper's platform-standard paths for the current user."""
    active_platform = platform_name or sys.platform
    if active_platform != "darwin":
        raise UnsupportedPlatformError(
            f"Setuper v1.0.0 does not support platform: {active_platform}",
            details={"platform": active_platform},
        )

    user_home = (home or Path.home()).expanduser()
    application_support = (
        user_home / "Library" / "Application Support" / APP_DIRECTORY_NAME
    )
    return SetuperPaths(
        data_directory=application_support,
        log_directory=user_home / "Library" / "Logs" / APP_DIRECTORY_NAME,
        cache_directory=user_home / "Library" / "Caches" / APP_DIRECTORY_NAME,
    )
