"""Setuper captures and restores reproducible work setups."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("setuper")
except PackageNotFoundError:
    __version__ = "0+unknown"

__all__ = ["__version__"]
