"""Root command-line application."""

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from setuper import __version__
from setuper.application.setup_service import SetupService
from setuper.domain.errors import SetuperError
from setuper.infrastructure.database import connect_database, run_migrations
from setuper.infrastructure.editor import open_editor
from setuper.infrastructure.manifests import serialize_manifest
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
    subparsers.add_parser("list", help="list stored setups")
    show_parser = subparsers.add_parser("show", help="show full setup details")
    show_parser.add_argument("name", help="stored setup name")
    show_parser.add_argument(
        "--portability",
        action="store_true",
        help="include the currently available portability assessment",
    )
    edit_parser = subparsers.add_parser(
        "edit",
        help="edit a setup manifest in the configured editor",
    )
    edit_parser.add_argument("name", help="stored setup name")
    clone_parser = subparsers.add_parser(
        "clone",
        help="clone a stored setup under a new name",
    )
    clone_parser.add_argument("source", help="source setup name")
    clone_parser.add_argument("target", help="new setup name")
    rename_parser = subparsers.add_parser(
        "rename",
        help="rename a stored setup",
    )
    rename_parser.add_argument("old", help="current setup name")
    rename_parser.add_argument("new", help="new setup name")
    delete_parser = subparsers.add_parser(
        "delete",
        help="delete a stored setup",
    )
    delete_parser.add_argument("name", help="stored setup name")
    delete_parser.add_argument(
        "--yes",
        action="store_true",
        help="delete without an interactive confirmation",
    )
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
        if arguments.command == "list":
            return _run_list(paths=paths)
        if arguments.command == "show":
            return _run_show(
                arguments.name,
                portability=arguments.portability,
                paths=paths,
            )
        if arguments.command == "edit":
            return _run_edit(arguments.name, paths=paths)
        if arguments.command == "clone":
            return _run_clone(
                arguments.source,
                arguments.target,
                paths=paths,
            )
        if arguments.command == "rename":
            return _run_rename(
                arguments.old,
                arguments.new,
                paths=paths,
            )
        if arguments.command == "delete":
            return _run_delete(
                arguments.name,
                assume_yes=arguments.yes,
                paths=paths,
            )
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


def _run_list(*, paths: SetuperPaths | None) -> int:
    """Render stored setup names in stable order."""
    active_paths = paths or resolve_paths()
    active_paths.ensure_directories()
    connection = connect_database(active_paths.database_path)
    try:
        run_migrations(connection, MIGRATIONS)
        records = SetupService(SetupRepository(connection)).list_setups()
    finally:
        connection.close()
    if not records:
        print("No setups found.")
        return 0
    for record in records:
        print(record.name)
    return 0


def _run_show(
    name: str,
    *,
    portability: bool,
    paths: SetuperPaths | None,
) -> int:
    """Render one validated setup manifest and optional portability limits."""
    active_paths = paths or resolve_paths()
    active_paths.ensure_directories()
    connection = connect_database(active_paths.database_path)
    try:
        run_migrations(connection, MIGRATIONS)
        result = SetupService(SetupRepository(connection)).show_setup(name)
    finally:
        connection.close()
    print(serialize_manifest(result.manifest), end="")
    if portability:
        platforms = ", ".join(platform.value for platform in result.manifest.platforms)
        print("\nPortability:")
        print(f"  Declared platforms: {platforms}")
        print("  Resource assessment: unavailable until adapter validation")
    return 0


def _run_edit(name: str, *, paths: SetuperPaths | None) -> int:
    """Edit one setup through the configured external editor."""
    active_paths = paths or resolve_paths()
    active_paths.ensure_directories()
    connection = connect_database(active_paths.database_path)
    try:
        run_migrations(connection, MIGRATIONS)
        result = SetupService(SetupRepository(connection)).edit_setup(name, open_editor)
    finally:
        connection.close()
    print(f"Updated {result.manifest.name} at {result.manifest_path}")
    return 0


def _run_clone(
    source: str,
    target: str,
    *,
    paths: SetuperPaths | None,
) -> int:
    """Clone one setup into Setuper-owned manifest storage."""
    active_paths = paths or resolve_paths()
    active_paths.ensure_directories()
    connection = connect_database(active_paths.database_path)
    try:
        run_migrations(connection, MIGRATIONS)
        result = SetupService(SetupRepository(connection)).clone_setup(
            source,
            target,
            active_paths.manifest_directory,
        )
    finally:
        connection.close()
    print(f"Cloned {source} as {result.manifest.name} at {result.manifest_path}")
    return 0


def _run_rename(
    old: str,
    new: str,
    *,
    paths: SetuperPaths | None,
) -> int:
    """Rename one stored setup and its manifest metadata."""
    active_paths = paths or resolve_paths()
    active_paths.ensure_directories()
    connection = connect_database(active_paths.database_path)
    try:
        run_migrations(connection, MIGRATIONS)
        result = SetupService(SetupRepository(connection)).rename_setup(old, new)
    finally:
        connection.close()
    print(f"Renamed {old} as {result.manifest.name}")
    return 0


def _run_delete(
    name: str,
    *,
    assume_yes: bool,
    paths: SetuperPaths | None,
) -> int:
    """Confirm and delete one setup without deleting user-owned projects."""
    if not assume_yes and not _confirm_delete(name):
        print("Delete cancelled.")
        return 0
    active_paths = paths or resolve_paths()
    active_paths.ensure_directories()
    connection = connect_database(active_paths.database_path)
    try:
        run_migrations(connection, MIGRATIONS)
        result = SetupService(SetupRepository(connection)).delete_setup(
            name,
            active_paths.manifest_directory,
        )
    finally:
        connection.close()
    print(f"Deleted {result.record.name}.")
    if not result.manifest_deleted:
        print(f"Preserved manifest at {result.record.manifest_path}")
    return 0


def _confirm_delete(name: str) -> bool:
    """Read one conservative interactive delete confirmation."""
    try:
        response = input(f"Delete setup {name!r}? [y/N] ")
    except EOFError as error:
        raise SetuperError(
            "Delete confirmation unavailable; use --yes to confirm",
        ) from error
    return response.strip().lower() in {"y", "yes"}
