"""SQLite persistence for launches and resource runs."""

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from setuper.domain.enums import LaunchStatus, ResourceRunStatus
from setuper.domain.errors import DatabaseError


@dataclass(frozen=True, slots=True)
class LaunchRecord:
    """One aggregate setup launch."""

    id: UUID
    setup_id: UUID
    manifest_hash: str
    profile: str | None
    status: LaunchStatus
    started_at: datetime
    completed_at: datetime | None = None
    stopped_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class ResourceRunRecord:
    """Runtime and ownership metadata for one launched resource."""

    id: UUID
    launch_id: UUID
    resource_id: str
    resource_type: str
    status: ResourceRunStatus
    pid: int | None = None
    external_id: str | None = None
    started_at: datetime | None = None
    ready_at: datetime | None = None
    stopped_at: datetime | None = None
    exit_code: int | None = None
    error_code: str | None = None
    error_message: str | None = None


class LaunchRepository:
    """Persist launch state transitions without executing resources."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        """Bind the repository to an initialized SQLite connection."""
        self._connection = connection

    def create_launch(self, record: LaunchRecord) -> None:
        """Insert a launch before any resource starts."""
        self._execute_write(
            """
            INSERT INTO launches(
                id, setup_id, manifest_hash, profile, status, started_at,
                completed_at, stopped_at, initiated_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'cli')
            """,
            _launch_parameters(record),
            operation="create launch",
            details={"launch_id": str(record.id)},
        )

    def update_launch(self, record: LaunchRecord) -> None:
        """Persist the current aggregate launch state."""
        self._execute_write(
            """
            UPDATE launches
            SET manifest_hash = ?, profile = ?, status = ?, started_at = ?,
                completed_at = ?, stopped_at = ?
            WHERE id = ?
            """,
            (
                record.manifest_hash,
                record.profile,
                record.status.value,
                _utc_iso(record.started_at),
                _optional_utc_iso(record.completed_at),
                _optional_utc_iso(record.stopped_at),
                str(record.id),
            ),
            operation="update launch",
            details={"launch_id": str(record.id)},
            require_row=True,
        )

    def get_launch(self, launch_id: UUID) -> LaunchRecord:
        """Return one launch by ID."""
        try:
            row = self._connection.execute(
                "SELECT * FROM launches WHERE id = ?",
                (str(launch_id),),
            ).fetchone()
        except sqlite3.Error as error:
            raise DatabaseError(
                "Could not query launch",
                details={"launch_id": str(launch_id)},
            ) from error
        if row is None:
            raise DatabaseError(
                "Launch record not found",
                details={"launch_id": str(launch_id)},
            )
        return _row_to_launch(row)

    def latest_for_setup(self, setup_id: UUID) -> LaunchRecord | None:
        """Return the latest launch for a setup, if one exists."""
        try:
            row = self._connection.execute(
                """
                SELECT * FROM launches
                WHERE setup_id = ?
                ORDER BY started_at DESC, id DESC
                LIMIT 1
                """,
                (str(setup_id),),
            ).fetchone()
        except sqlite3.Error as error:
            raise DatabaseError(
                "Could not query latest launch",
                details={"setup_id": str(setup_id)},
            ) from error
        return None if row is None else _row_to_launch(row)

    def create_resource_run(self, record: ResourceRunRecord) -> None:
        """Insert resource state before invoking its adapter."""
        self._execute_write(
            """
            INSERT INTO resource_runs(
                id, launch_id, resource_id, resource_type, status, pid,
                external_id, started_at, ready_at, stopped_at, exit_code,
                error_code, error_message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            _resource_parameters(record),
            operation="create resource run",
            details={
                "launch_id": str(record.launch_id),
                "resource_id": record.resource_id,
            },
        )

    def update_resource_run(self, record: ResourceRunRecord) -> None:
        """Persist a resource state transition and ownership metadata."""
        parameters = _resource_parameters(record)
        self._execute_write(
            """
            UPDATE resource_runs
            SET launch_id = ?, resource_id = ?, resource_type = ?, status = ?,
                pid = ?, external_id = ?, started_at = ?, ready_at = ?,
                stopped_at = ?, exit_code = ?, error_code = ?, error_message = ?
            WHERE id = ?
            """,
            (*parameters[1:], parameters[0]),
            operation="update resource run",
            details={
                "launch_id": str(record.launch_id),
                "resource_id": record.resource_id,
            },
            require_row=True,
        )

    def list_resource_runs(self, launch_id: UUID) -> tuple[ResourceRunRecord, ...]:
        """Return resource runs in stable manifest-resource order."""
        try:
            rows = self._connection.execute(
                """
                SELECT * FROM resource_runs
                WHERE launch_id = ?
                ORDER BY resource_id, id
                """,
                (str(launch_id),),
            ).fetchall()
        except sqlite3.Error as error:
            raise DatabaseError(
                "Could not list resource runs",
                details={"launch_id": str(launch_id)},
            ) from error
        return tuple(_row_to_resource(row) for row in rows)

    def _execute_write(
        self,
        statement: str,
        parameters: tuple[object, ...],
        *,
        operation: str,
        details: dict[str, object],
        require_row: bool = False,
    ) -> None:
        """Execute one parameterized write and translate SQLite failures."""
        try:
            with self._connection:
                cursor = self._connection.execute(statement, parameters)
                if require_row and cursor.rowcount == 0:
                    raise DatabaseError(
                        f"Could not {operation}: record not found",
                        details=details,
                    )
        except DatabaseError:
            raise
        except sqlite3.Error as error:
            raise DatabaseError(
                f"Could not {operation}",
                details=details,
            ) from error


def _launch_parameters(record: LaunchRecord) -> tuple[object, ...]:
    """Serialize one launch record for insertion."""
    return (
        str(record.id),
        str(record.setup_id),
        record.manifest_hash,
        record.profile,
        record.status.value,
        _utc_iso(record.started_at),
        _optional_utc_iso(record.completed_at),
        _optional_utc_iso(record.stopped_at),
    )


def _resource_parameters(record: ResourceRunRecord) -> tuple[object, ...]:
    """Serialize one resource-run record for insertion."""
    return (
        str(record.id),
        str(record.launch_id),
        record.resource_id,
        record.resource_type,
        record.status.value,
        record.pid,
        record.external_id,
        _optional_utc_iso(record.started_at),
        _optional_utc_iso(record.ready_at),
        _optional_utc_iso(record.stopped_at),
        record.exit_code,
        record.error_code,
        record.error_message,
    )


def _row_to_launch(row: sqlite3.Row) -> LaunchRecord:
    """Deserialize one launch row."""
    return LaunchRecord(
        id=UUID(row["id"]),
        setup_id=UUID(row["setup_id"]),
        manifest_hash=row["manifest_hash"],
        profile=row["profile"],
        status=LaunchStatus(row["status"]),
        started_at=datetime.fromisoformat(row["started_at"]),
        completed_at=_optional_datetime(row["completed_at"]),
        stopped_at=_optional_datetime(row["stopped_at"]),
    )


def _row_to_resource(row: sqlite3.Row) -> ResourceRunRecord:
    """Deserialize one resource-run row."""
    return ResourceRunRecord(
        id=UUID(row["id"]),
        launch_id=UUID(row["launch_id"]),
        resource_id=row["resource_id"],
        resource_type=row["resource_type"],
        status=ResourceRunStatus(row["status"]),
        pid=row["pid"],
        external_id=row["external_id"],
        started_at=_optional_datetime(row["started_at"]),
        ready_at=_optional_datetime(row["ready_at"]),
        stopped_at=_optional_datetime(row["stopped_at"]),
        exit_code=row["exit_code"],
        error_code=row["error_code"],
        error_message=row["error_message"],
    )


def _utc_iso(value: datetime) -> str:
    """Serialize an aware timestamp in UTC."""
    if value.tzinfo is None:
        raise ValueError("database timestamps must be timezone-aware")
    return value.astimezone(UTC).isoformat()


def _optional_utc_iso(value: datetime | None) -> str | None:
    """Serialize an optional aware timestamp."""
    return None if value is None else _utc_iso(value)


def _optional_datetime(value: str | None) -> datetime | None:
    """Deserialize an optional ISO timestamp."""
    return None if value is None else datetime.fromisoformat(value)
