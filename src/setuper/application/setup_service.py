"""Application service for setup lifecycle operations."""

import os
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Never
from uuid import UUID, uuid4

from pydantic import ValidationError

from setuper.adapters.base import DetectedResource
from setuper.adapters.registry import AdapterRegistry
from setuper.domain.enums import LaunchStatus, Platform, SetupSource
from setuper.domain.errors import (
    DatabaseError,
    ManifestIOError,
    ManifestValidationError,
    SetupNotFoundError,
)
from setuper.domain.models import SetupManifest
from setuper.infrastructure.hashing import hash_manifest
from setuper.infrastructure.launch_repository import LaunchRepository
from setuper.infrastructure.manifests import load_manifest, save_manifest
from setuper.infrastructure.setup_repository import SetupRecord, SetupRepository

PROJECT_MANIFEST_NAME = ".setuper.yaml"


@dataclass(frozen=True, slots=True)
class InitResult:
    """Result of initializing one project-local setup."""

    manifest: SetupManifest
    manifest_path: Path


@dataclass(frozen=True, slots=True)
class SetupSummary:
    """Stored setup details required by list renderers."""

    record: SetupRecord
    resource_count: int
    last_launched_at: datetime | None
    status: LaunchStatus | None


@dataclass(frozen=True, slots=True)
class ShowResult:
    """Validated manifest and metadata selected by a stored setup name."""

    manifest: SetupManifest
    record: SetupRecord


@dataclass(frozen=True, slots=True)
class EditResult:
    """Validated setup committed after a successful editor session."""

    manifest: SetupManifest
    manifest_path: Path


@dataclass(frozen=True, slots=True)
class CloneResult:
    """New independently identified setup cloned from a stored manifest."""

    manifest: SetupManifest
    manifest_path: Path


@dataclass(frozen=True, slots=True)
class RenameResult:
    """Renamed setup retaining its stable identity and manifest location."""

    manifest: SetupManifest
    manifest_path: Path


@dataclass(frozen=True, slots=True)
class DeleteResult:
    """Deleted setup metadata and manifest ownership outcome."""

    record: SetupRecord
    manifest_deleted: bool


@dataclass(frozen=True, slots=True)
class ExportResult:
    """Manifest exported without operational metadata or approvals."""

    manifest: SetupManifest
    output_path: Path


@dataclass(frozen=True, slots=True)
class ImportResult:
    """Imported untrusted manifest and its managed storage location."""

    manifest: SetupManifest
    manifest_path: Path
    source_path: Path


@dataclass(frozen=True, slots=True)
class SaveResult:
    """New setup captured from selected findings and persisted to storage."""

    manifest: SetupManifest
    manifest_path: Path


class SetupService:
    """Coordinate setup manifests and their operational metadata."""

    def __init__(
        self,
        repository: SetupRepository,
        *,
        launch_repository: LaunchRepository | None = None,
        id_factory: Callable[[], UUID] = uuid4,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        """Create a setup service with injectable identity and time sources."""
        self._repository = repository
        self._launch_repository = launch_repository
        self._id_factory = id_factory
        self._clock = clock or _utc_now

    def init_project(self, project_path: Path) -> InitResult:
        """Create and register a new project-local manifest."""
        resolved_project = _resolve_path(
            project_path,
            purpose="project path",
            strict=True,
        )
        if not resolved_project.is_dir():
            raise ManifestValidationError(
                f"Project path is not a directory: {resolved_project}",
                details={"path": str(resolved_project)},
            )
        if not resolved_project.name:
            raise ManifestValidationError(
                "Cannot derive a setup name from the filesystem root",
                details={"path": str(resolved_project)},
            )

        manifest_path = resolved_project / PROJECT_MANIFEST_NAME
        if os.path.lexists(manifest_path):
            raise ManifestValidationError(
                f"Project manifest already exists: {manifest_path}",
                details={"path": str(manifest_path)},
            )

        setup_id = self._id_factory()
        manifest = SetupManifest(
            id=setup_id,
            name=resolved_project.name,
            platforms=(Platform.MACOS,),
        )
        save_manifest(manifest_path, manifest)
        timestamp = self._clock()
        record = SetupRecord(
            id=setup_id,
            name=manifest.name,
            manifest_path=manifest_path,
            manifest_hash=hash_manifest(manifest_path),
            source=SetupSource.PROJECT,
            created_at=timestamp,
            updated_at=timestamp,
        )
        try:
            self._repository.create(record)
        except DatabaseError as error:
            raise DatabaseError(
                f"Manifest created but registration failed: {manifest_path}",
                details={"path": str(manifest_path), "name": manifest.name},
            ) from error
        return InitResult(manifest=manifest, manifest_path=manifest_path)

    def list_setups(self) -> tuple[SetupSummary, ...]:
        """Return stored setup summaries in stable name order."""
        if self._launch_repository is None:
            raise DatabaseError("Launch repository is required to list setups")
        summaries: list[SetupSummary] = []
        for record in self._repository.list():
            manifest = load_manifest(record.manifest_path)
            latest_launch = self._launch_repository.latest_for_setup(record.id)
            summaries.append(
                SetupSummary(
                    record=record,
                    resource_count=len(manifest.resources),
                    last_launched_at=(
                        None if latest_launch is None else latest_launch.started_at
                    ),
                    status=None if latest_launch is None else latest_launch.status,
                )
            )
        return tuple(summaries)

    def show_setup(self, name: str) -> ShowResult:
        """Load and validate the manifest registered for one setup."""
        record = self._repository.get_by_name(name)
        return ShowResult(manifest=load_manifest(record.manifest_path), record=record)

    def edit_setup(
        self,
        name: str,
        editor: Callable[[Path], None],
    ) -> EditResult:
        """Edit, validate, and atomically commit one setup manifest."""
        record = self._repository.get_by_name(name)
        original = load_manifest(record.manifest_path)
        try:
            file_descriptor, temporary_name = tempfile.mkstemp(
                dir=record.manifest_path.parent,
                prefix=f".{record.manifest_path.name}.edit.",
                suffix=".yaml",
                text=True,
            )
        except OSError as error:
            raise ManifestIOError(
                f"Could not create temporary editor file: "
                f"{record.manifest_path.parent}",
                details={"path": str(record.manifest_path)},
            ) from error
        os.close(file_descriptor)
        temporary_path = Path(temporary_name)
        try:
            save_manifest(temporary_path, original)
            editor(temporary_path)
            edited = load_manifest(temporary_path)
            if edited.id != original.id or edited.name != original.name:
                raise ManifestValidationError(
                    "Use the rename command to change setup identity",
                    details={"name": name},
                )
            save_manifest(record.manifest_path, edited)
        finally:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError as error:
                raise ManifestIOError(
                    f"Could not remove temporary editor file: {temporary_path}",
                    details={"path": str(temporary_path)},
                ) from error

        updated_record = replace(
            record,
            manifest_hash=hash_manifest(record.manifest_path),
            updated_at=self._clock(),
        )
        try:
            self._repository.update(updated_record)
        except DatabaseError as error:
            raise DatabaseError(
                f"Manifest edited but metadata update failed: {record.manifest_path}",
                details={"path": str(record.manifest_path), "name": record.name},
            ) from error
        return EditResult(manifest=edited, manifest_path=record.manifest_path)

    def clone_setup(
        self,
        source_name: str,
        target_name: str,
        manifest_directory: Path,
    ) -> CloneResult:
        """Clone a setup under a new identity without copying trust."""
        source = self.show_setup(source_name)
        target_name = self._require_available_name(target_name)
        setup_id = self._id_factory()
        cloned = SetupManifest.model_validate(
            {
                **source.manifest.model_dump(mode="python"),
                "id": setup_id,
                "name": target_name,
            }
        )
        manifest_path = _managed_manifest_path(manifest_directory, setup_id)
        if os.path.lexists(manifest_path):
            raise ManifestValidationError(
                f"Clone destination already exists: {manifest_path}",
                details={"path": str(manifest_path)},
            )
        save_manifest(manifest_path, cloned)
        timestamp = self._clock()
        record = SetupRecord(
            id=setup_id,
            name=cloned.name,
            manifest_path=manifest_path,
            manifest_hash=hash_manifest(manifest_path),
            source=SetupSource.LOCAL,
            created_at=timestamp,
            updated_at=timestamp,
        )
        try:
            self._repository.create(record)
        except DatabaseError as database_error:
            _rollback_managed_manifest(manifest_path, database_error)
        return CloneResult(manifest=cloned, manifest_path=manifest_path)

    def rename_setup(self, old_name: str, new_name: str) -> RenameResult:
        """Rename one setup while retaining its ID and manifest path."""
        current = self.show_setup(old_name)
        new_name = self._require_available_name(new_name)
        renamed = SetupManifest.model_validate(
            {
                **current.manifest.model_dump(mode="python"),
                "name": new_name,
            }
        )
        save_manifest(current.record.manifest_path, renamed)
        updated_record = replace(
            current.record,
            name=renamed.name,
            manifest_hash=hash_manifest(current.record.manifest_path),
            updated_at=self._clock(),
        )
        try:
            self._repository.update(updated_record)
        except DatabaseError:
            save_manifest(current.record.manifest_path, current.manifest)
            raise
        return RenameResult(
            manifest=renamed,
            manifest_path=current.record.manifest_path,
        )

    def delete_setup(
        self,
        name: str,
        manifest_directory: Path,
    ) -> DeleteResult:
        """Delete metadata and only a Setuper-owned manifest file."""
        record = self._repository.delete(name)
        if record.source is SetupSource.PROJECT or not _is_managed_manifest(
            record,
            manifest_directory,
        ):
            return DeleteResult(record=record, manifest_deleted=False)
        try:
            record.manifest_path.unlink(missing_ok=True)
        except OSError as error:
            raise ManifestIOError(
                f"Setup metadata deleted but manifest removal failed: "
                f"{record.manifest_path}",
                details={"path": str(record.manifest_path), "name": record.name},
            ) from error
        return DeleteResult(record=record, manifest_deleted=True)

    def export_setup(self, name: str, output_path: Path) -> ExportResult:
        """Export one validated manifest without overwriting a destination."""
        setup = self.show_setup(name)
        destination = _resolve_path(output_path, purpose="export destination")
        if os.path.lexists(destination):
            raise ManifestValidationError(
                f"Export destination already exists: {destination}",
                details={"path": str(destination)},
            )
        save_manifest(destination, setup.manifest)
        return ExportResult(manifest=setup.manifest, output_path=destination)

    def import_setup(
        self,
        source_path: Path,
        manifest_directory: Path,
        *,
        name: str | None = None,
    ) -> ImportResult:
        """Validate and copy one untrusted manifest into managed storage."""
        source = _resolve_path(source_path, purpose="import source")
        imported = load_manifest(source)
        imported_name = self._require_available_name(
            imported.name if name is None else name
        )
        setup_id = imported.id or self._id_factory()
        self._require_available_id(setup_id)
        normalized = SetupManifest.model_validate(
            {
                **imported.model_dump(mode="python"),
                "id": setup_id,
                "name": imported_name,
            }
        )
        manifest_path = _managed_manifest_path(manifest_directory, setup_id)
        if os.path.lexists(manifest_path):
            raise ManifestValidationError(
                f"Import destination already exists: {manifest_path}",
                details={"path": str(manifest_path)},
            )
        save_manifest(manifest_path, normalized)
        timestamp = self._clock()
        record = SetupRecord(
            id=setup_id,
            name=normalized.name,
            manifest_path=manifest_path,
            manifest_hash=hash_manifest(manifest_path),
            source=SetupSource.IMPORTED,
            created_at=timestamp,
            updated_at=timestamp,
        )
        try:
            self._repository.create(record)
        except DatabaseError as database_error:
            _rollback_managed_manifest(manifest_path, database_error)
        return ImportResult(
            manifest=normalized,
            manifest_path=manifest_path,
            source_path=source,
        )

    def build_manifest_from_findings(
        self,
        name: str,
        findings: Sequence[DetectedResource],
        registry: AdapterRegistry,
        *,
        platforms: tuple[Platform, ...] = (Platform.MACOS,),
    ) -> SetupManifest:
        """Build a validated in-memory manifest from selected findings."""
        validated_name = self._require_available_name(name)
        resources = tuple(
            registry.get(finding.type_name).capture(finding) for finding in findings
        )
        return SetupManifest(
            name=validated_name,
            platforms=platforms,
            resources=resources,
        )

    def save_setup(
        self,
        name: str,
        manifest_directory: Path,
        findings: Sequence[DetectedResource],
        registry: AdapterRegistry,
        *,
        platforms: tuple[Platform, ...] = (Platform.MACOS,),
    ) -> SaveResult:
        """Capture selected findings into a new, persisted setup manifest."""
        built = self.build_manifest_from_findings(
            name,
            findings,
            registry,
            platforms=platforms,
        )
        setup_id = self._id_factory()
        manifest = SetupManifest.model_validate(
            {**built.model_dump(mode="python"), "id": setup_id}
        )
        manifest_path = _managed_manifest_path(manifest_directory, setup_id)
        if os.path.lexists(manifest_path):
            raise ManifestValidationError(
                f"Save destination already exists: {manifest_path}",
                details={"path": str(manifest_path)},
            )
        save_manifest(manifest_path, manifest)
        timestamp = self._clock()
        record = SetupRecord(
            id=setup_id,
            name=manifest.name,
            manifest_path=manifest_path,
            manifest_hash=hash_manifest(manifest_path),
            source=SetupSource.LOCAL,
            created_at=timestamp,
            updated_at=timestamp,
        )
        try:
            self._repository.create(record)
        except DatabaseError as database_error:
            _rollback_managed_manifest(manifest_path, database_error)
        return SaveResult(manifest=manifest, manifest_path=manifest_path)

    def _require_available_name(self, name: str) -> str:
        """Reject an invalid or already stored setup name."""
        try:
            validated = SetupManifest(name=name).name
        except ValidationError as error:
            raise ManifestValidationError(
                "Setup name must not be empty",
            ) from error
        try:
            self._repository.get_by_name(validated)
        except SetupNotFoundError:
            return validated
        raise ManifestValidationError(
            f"Setup name already exists: {validated}",
            details={"name": validated},
        )

    def _require_available_id(self, setup_id: UUID) -> None:
        """Reject a stable setup identity already registered locally."""
        try:
            self._repository.get_by_id(setup_id)
        except SetupNotFoundError:
            return
        serialized_id = str(setup_id)
        raise ManifestValidationError(
            f"Setup ID already exists: {serialized_id}",
            details={"setup_id": serialized_id},
        )


def _utc_now() -> datetime:
    """Return the current aware UTC time."""
    return datetime.now(UTC)


def _is_managed_manifest(
    record: SetupRecord,
    manifest_directory: Path,
) -> bool:
    """Return whether a regular UUID manifest is directly in managed storage."""
    try:
        return (
            record.manifest_path.parent == manifest_directory.resolve()
            and record.manifest_path.name == f"{record.id}.yaml"
            and not record.manifest_path.is_symlink()
        )
    except (OSError, RuntimeError):
        return False


def _resolve_path(
    path: Path,
    *,
    purpose: str,
    strict: bool = False,
) -> Path:
    """Resolve a user-facing path and translate filesystem edge cases."""
    try:
        return path.expanduser().resolve(strict=strict)
    except (OSError, RuntimeError) as error:
        raise ManifestIOError(
            f"Could not resolve {purpose}: {path}",
            details={"path": str(path)},
        ) from error


def _managed_manifest_path(directory: Path, setup_id: UUID) -> Path:
    """Build a UUID filename under a resolvable managed directory."""
    resolved_directory = _resolve_path(
        directory,
        purpose="managed manifest directory",
    )
    return resolved_directory / f"{setup_id}.yaml"


def _rollback_managed_manifest(
    manifest_path: Path,
    database_error: DatabaseError,
) -> Never:
    """Remove an unregistered managed manifest or report rollback failure."""
    try:
        manifest_path.unlink(missing_ok=True)
    except OSError as cleanup_error:
        raise DatabaseError(
            f"Setup registration and manifest cleanup failed: {manifest_path}",
            details={"path": str(manifest_path)},
        ) from cleanup_error
    raise database_error
