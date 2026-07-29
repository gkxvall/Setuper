"""Root command-line application."""

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from setuper import __version__
from setuper.application.setup_service import SetupService
from setuper.domain.errors import SetuperError
from setuper.infrastructure.database import connect_database, run_migrations
from setuper.infrastructure.migrations import MIGRATIONS
from setuper.infrastructure.paths import SetuperPaths, resolve_paths
from setuper.infrastructure.setup_repository import SetupRepository

DESCRIPTION = "Capture and restore reproducible work setups."


def build_parser() -> argparse.ArgumentParser:
    """Build the root argument parser."""
    parser = argparse.ArgumentParser(prog="setuper", description=DESCRIPTION)
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("version", help="show the installed Setuper version")
    init_parser = subparsers.add_parser(
        "init",
        help="create a project-local setup manifest",
    )
    init_parser.add_argument(
        "path",
        nargs="?",
        type=Path,
        default=Path.cwd(),
        help="project directory (default: current directory)",
    )
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    paths: SetuperPaths | None = None,
) -> int:
    """Run the Setuper command-line application."""
    parser = build_parser()
    arguments = parser.parse_args(argv)

    try:
        if arguments.command == "version":
            print(f"setuper {__version__}")
            return 0
        if arguments.command == "init":
            return _run_init(arguments.path, paths=paths)
    except SetuperError as error:
        print(f"ERROR [{error.error_code}] {error.message}", file=sys.stderr)
        return int(error.exit_code)

    parser.print_help()
    return 0


def _run_init(project_path: Path, *, paths: SetuperPaths | None) -> int:
    """Initialize one project and render a stable success message."""
    active_paths = paths or resolve_paths()
    active_paths.ensure_directories()
    connection = connect_database(active_paths.database_path)
    try:
        run_migrations(connection, MIGRATIONS)
        service = SetupService(SetupRepository(connection))
        result = service.init_project(project_path)
    finally:
        connection.close()
    print(f"Initialized {result.manifest.name} at {result.manifest_path}")
    return 0
