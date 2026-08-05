"""Root command-line application."""

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from setuper import __version__
from setuper.adapters.cursor import CursorAdapter
from setuper.adapters.docker import DockerAdapter
from setuper.adapters.docker_compose import DockerComposeAdapter
from setuper.adapters.git import GitAdapter
from setuper.adapters.macos_app import MacOSAppAdapter
from setuper.adapters.process import ProcessAdapter
from setuper.adapters.registry import AdapterRegistry
from setuper.adapters.vscode import VSCodeAdapter
from setuper.adapters.window_geometry import WindowGeometryAdapter
from setuper.application.capture_service import (
    CaptureService,
    build_capture_context,
    filter_findings,
)
from setuper.application.setup_service import SetupService
from setuper.cli.json_output import render_json_error, render_json_success
from setuper.domain.errors import SetuperError
from setuper.infrastructure.commands import SubprocessCommandRunner
from setuper.infrastructure.database import connect_database, run_migrations
from setuper.infrastructure.editor import open_editor
from setuper.infrastructure.launch_repository import LaunchRepository
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
    inspect_parser = subparsers.add_parser(
        "inspect",
        help="detect capturable machine resources",
    )
    inspect_parser.add_argument(
        "--json",
        action="store_true",
        help="emit a deterministic JSON envelope",
    )
    list_parser = subparsers.add_parser("list", help="list stored setups")
    list_parser.add_argument(
        "--json",
        action="store_true",
        help="emit a deterministic JSON envelope",
    )
    show_parser = subparsers.add_parser("show", help="show full setup details")
    show_parser.add_argument("name", help="stored setup name")
    show_parser.add_argument(
        "--json",
        action="store_true",
        help="emit a deterministic JSON envelope",
    )
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
    export_parser = subparsers.add_parser(
        "export",
        help="export a setup manifest",
    )
    export_parser.add_argument("name", help="stored setup name")
    export_parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="new YAML output file",
    )
    import_parser = subparsers.add_parser(
        "import",
        help="import an untrusted setup manifest",
    )
    import_parser.add_argument("file", type=Path, help="YAML manifest file")
    import_parser.add_argument(
        "--name",
        help="override the imported setup name",
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
    save_parser = subparsers.add_parser(
        "save",
        help="capture the current machine into a new setup",
    )
    save_parser.add_argument("name", help="new setup name")
    save_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="preview captured resources without saving",
    )
    save_parser.add_argument(
        "--include",
        action="append",
        default=[],
        metavar="TYPE",
        help="capture only this resource type (repeatable)",
    )
    save_parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="TYPE",
        help="omit this resource type (repeatable)",
    )
    update_parser = subparsers.add_parser(
        "update",
        help="refresh a stored setup from current machine state",
    )
    update_parser.add_argument("name", help="stored setup name")
    update_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="preview refreshed resources without saving",
    )
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    paths: SetuperPaths | None = None,
    capture_registry: AdapterRegistry | None = None,
) -> int:
    """Run the Setuper command-line application."""
    parser = build_parser()
    arguments = parser.parse_args(argv)

    try:
        if arguments.command == "version":
            print(f"setuper {__version__}")
            return 0
        if arguments.command == "inspect":
            return _run_inspect(json_output=arguments.json, registry=capture_registry)
        if arguments.command == "save":
            return _run_save(
                arguments.name,
                dry_run=arguments.dry_run,
                include=arguments.include,
                exclude=arguments.exclude,
                paths=paths,
                registry=capture_registry,
            )
        if arguments.command == "update":
            return _run_update(
                arguments.name,
                dry_run=arguments.dry_run,
                paths=paths,
                registry=capture_registry,
            )
        if arguments.command == "init":
            return _run_init(arguments.path, paths=paths)
        if arguments.command == "list":
            return _run_list(json_output=arguments.json, paths=paths)
        if arguments.command == "show":
            return _run_show(
                arguments.name,
                portability=arguments.portability,
                json_output=arguments.json,
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
        if arguments.command == "export":
            return _run_export(
                arguments.name,
                arguments.output,
                paths=paths,
            )
        if arguments.command == "import":
            return _run_import(
                arguments.file,
                name=arguments.name,
                paths=paths,
            )
    except SetuperError as error:
        if getattr(arguments, "json", False):
            print(render_json_error(arguments.command, error))
            return int(error.exit_code)
        print(f"ERROR [{error.error_code}] {error.message}", file=sys.stderr)
        return int(error.exit_code)

    parser.print_help()
    return 0


def _build_capture_registry() -> AdapterRegistry:
    """Build the default read-only capture adapter registry."""
    runner = SubprocessCommandRunner()
    return AdapterRegistry(
        [
            ProcessAdapter(),
            GitAdapter(runner),
            DockerAdapter(runner),
            DockerComposeAdapter(runner),
            VSCodeAdapter(),
            CursorAdapter(),
            MacOSAppAdapter(runner),
            WindowGeometryAdapter(runner),
        ]
    )


def _run_inspect(*, json_output: bool, registry: AdapterRegistry | None) -> int:
    """Detect capturable machine resources without persisting anything."""
    active_registry = registry or _build_capture_registry()
    result = CaptureService(active_registry).inspect(build_capture_context())
    if json_output:
        print(
            render_json_success(
                "inspect",
                {
                    "findings": [
                        {
                            "type": finding.type_name,
                            "identity": finding.identity,
                            "display_name": finding.display_name,
                            "support": finding.support,
                            "config": dict(finding.config),
                            "warnings": list(finding.warnings),
                        }
                        for finding in result.findings
                    ],
                    "issues": [
                        {"adapter": issue.type_name, "message": issue.message}
                        for issue in result.issues
                    ],
                },
            )
        )
        return 0
    if not result.findings:
        print("No capturable resources found.")
    for finding in result.findings:
        print(f"[{finding.type_name}] {finding.display_name} ({finding.support.value})")
        for warning in finding.warnings:
            print(f"  ! {warning}")
    if result.issues:
        print("\nUnavailable adapters:")
        for issue in result.issues:
            print(f"  {issue.type_name}: {issue.message}")
    return 0


def _run_save(
    name: str,
    *,
    dry_run: bool,
    include: list[str],
    exclude: list[str],
    paths: SetuperPaths | None,
    registry: AdapterRegistry | None,
) -> int:
    """Capture the current machine into a new setup, or preview it."""
    active_registry = registry or _build_capture_registry()
    capture_result = CaptureService(active_registry).inspect(build_capture_context())
    selected = filter_findings(
        capture_result.findings, include=include, exclude=exclude
    )

    active_paths = paths or resolve_paths()
    active_paths.ensure_directories()
    connection = connect_database(active_paths.database_path)
    try:
        run_migrations(connection, MIGRATIONS)
        service = SetupService(SetupRepository(connection))
        if dry_run:
            manifest = service.build_manifest_from_findings(
                name,
                selected,
                active_registry,
            )
            count = len(manifest.resources)
            print(f"Would save {manifest.name} with {count} resource(s):")
            for resource in manifest.resources:
                print(f"  {resource.id} ({resource.type})")
            return 0
        result = service.save_setup(
            name,
            active_paths.manifest_directory,
            selected,
            active_registry,
        )
    finally:
        connection.close()
    print(
        f"Saved {result.manifest.name} with {len(result.manifest.resources)} "
        f"resource(s) at {result.manifest_path}"
    )
    if capture_result.issues:
        print("Some adapters were unavailable during capture:")
        for issue in capture_result.issues:
            print(f"  {issue.type_name}: {issue.message}")
    return 0


def _run_update(
    name: str,
    *,
    dry_run: bool,
    paths: SetuperPaths | None,
    registry: AdapterRegistry | None,
) -> int:
    """Refresh a stored setup's resources from the current machine, or preview it."""
    active_registry = registry or _build_capture_registry()
    capture_result = CaptureService(active_registry).inspect(build_capture_context())

    active_paths = paths or resolve_paths()
    active_paths.ensure_directories()
    connection = connect_database(active_paths.database_path)
    try:
        run_migrations(connection, MIGRATIONS)
        service = SetupService(SetupRepository(connection))
        if dry_run:
            manifest = service.build_updated_manifest(
                name,
                capture_result.findings,
                active_registry,
            )
            count = len(manifest.resources)
            print(f"Would update {manifest.name} to {count} resource(s):")
            for resource in manifest.resources:
                print(f"  {resource.id} ({resource.type})")
            return 0
        result = service.update_setup(name, capture_result.findings, active_registry)
    finally:
        connection.close()
    print(
        f"Updated {result.manifest.name} to {len(result.manifest.resources)} "
        f"resource(s) at {result.manifest_path}"
    )
    if capture_result.issues:
        print("Some adapters were unavailable during capture:")
        for issue in capture_result.issues:
            print(f"  {issue.type_name}: {issue.message}")
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


def _run_list(
    *,
    json_output: bool,
    paths: SetuperPaths | None,
) -> int:
    """Render stored setup names in stable order."""
    active_paths = paths or resolve_paths()
    active_paths.ensure_directories()
    connection = connect_database(active_paths.database_path)
    try:
        run_migrations(connection, MIGRATIONS)
        summaries = SetupService(
            SetupRepository(connection),
            launch_repository=LaunchRepository(connection),
        ).list_setups()
    finally:
        connection.close()
    if json_output:
        print(
            render_json_success(
                "list",
                {
                    "setups": [
                        {
                            "id": summary.record.id,
                            "name": summary.record.name,
                            "source": summary.record.source,
                            "manifest_path": summary.record.manifest_path,
                            "manifest_hash": summary.record.manifest_hash,
                            "created_at": summary.record.created_at,
                            "updated_at": summary.record.updated_at,
                            "resource_count": summary.resource_count,
                            "last_launched_at": summary.last_launched_at,
                            "status": summary.status,
                        }
                        for summary in summaries
                    ]
                },
            )
        )
        return 0
    if not summaries:
        print("No setups found.")
        return 0
    rows = [
        (
            summary.record.name,
            str(summary.resource_count),
            (
                "never"
                if summary.last_launched_at is None
                else summary.last_launched_at.strftime("%Y-%m-%d %H:%M")
            ),
            "-" if summary.status is None else summary.status.value,
        )
        for summary in summaries
    ]
    _print_table(("NAME", "RESOURCES", "LAST LAUNCHED", "STATUS"), rows)
    return 0


def _print_table(
    headers: tuple[str, ...],
    rows: Sequence[tuple[str, ...]],
) -> None:
    """Print a stable plain-text table without terminal-specific control codes."""
    widths = [
        max(len(header), *(len(row[index]) for row in rows))
        for index, header in enumerate(headers)
    ]
    print(_format_table_row(headers, widths))
    for row in rows:
        print(_format_table_row(row, widths))


def _format_table_row(values: tuple[str, ...], widths: list[int]) -> str:
    """Format one table row without trailing whitespace."""
    return "  ".join(
        value if index == len(values) - 1 else value.ljust(widths[index])
        for index, value in enumerate(values)
    )


def _run_show(
    name: str,
    *,
    portability: bool,
    json_output: bool,
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
    if json_output:
        portability_data: dict[str, object] | None = None
        warnings: tuple[str, ...] = ()
        if portability:
            portability_data = {
                "declared_platforms": result.manifest.platforms,
                "resource_assessment": {
                    "available": False,
                    "reason": "unavailable until adapter validation",
                },
            }
            warnings = ("Resource portability requires adapter validation.",)
        print(
            render_json_success(
                "show",
                {
                    "manifest": result.manifest.model_dump(
                        mode="json",
                        exclude_none=True,
                    ),
                    "manifest_path": result.record.manifest_path,
                    "manifest_hash": result.record.manifest_hash,
                    "source": result.record.source,
                    "portability": portability_data,
                },
                warnings=warnings,
            )
        )
        return 0
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


def _run_export(
    name: str,
    output: Path,
    *,
    paths: SetuperPaths | None,
) -> int:
    """Export one setup as a standalone validated YAML manifest."""
    active_paths = paths or resolve_paths()
    active_paths.ensure_directories()
    connection = connect_database(active_paths.database_path)
    try:
        run_migrations(connection, MIGRATIONS)
        result = SetupService(SetupRepository(connection)).export_setup(name, output)
    finally:
        connection.close()
    print(f"Exported {result.manifest.name} to {result.output_path}")
    return 0


def _run_import(
    source: Path,
    *,
    name: str | None,
    paths: SetuperPaths | None,
) -> int:
    """Import one manifest into untrusted managed storage."""
    active_paths = paths or resolve_paths()
    active_paths.ensure_directories()
    connection = connect_database(active_paths.database_path)
    try:
        run_migrations(connection, MIGRATIONS)
        result = SetupService(SetupRepository(connection)).import_setup(
            source,
            active_paths.manifest_directory,
            name=name,
        )
    finally:
        connection.close()
    print(f"Imported {result.manifest.name} from {result.source_path}")
    print("Trust: untrusted; inspect the manifest before trusting it")
    return 0
