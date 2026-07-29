"""SQLite persistence for stored setup metadata."""

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from setuper.domain.enums import SetupSource
from setuper.domain.errors import DatabaseError, SetupNotFoundError


@dataclass(frozen=True, slots=True)
class SetupRecord:
    """One setup row stored alongside a YAML manifest."""

    id: UUID
    name: str
    manifest_path: Path
    manifest_hash: str
    source: SetupSource
    created_at: datetime
    updated_at: datetime


class SetupRepository:
    """Persist and query setup metadata without owning manifest contents."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        """Bind the repository to an initialized SQLite connection."""
        self._connection = connection

    def create(self, record: SetupRecord) -> None:
        """Insert one new setup record."""
        try:
            with self._connection:
                self._connection.execute(
                    """
                    INSERT INTO setups(
                        id, name, manifest_path, manifest_hash, source,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    _record_parameters(record),
                )
        except sqlite3.Error as error:
            raise DatabaseError(
                f"Could not create setup metadata: {record.name}",
                details={"name": record.name},
            ) from error

    def update(self, record: SetupRecord) -> None:
        """Replace mutable metadata for an existing setup ID."""
        try:
            with self._connection:
                cursor = self._connection.execute(
                    """
                    UPDATE setups
                    SET name = ?, manifest_path = ?, manifest_hash = ?,
                        source = ?, created_at = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        record.name,
                        str(record.manifest_path),
                        record.manifest_hash,
                        record.source.value,
                        _utc_iso(record.created_at),
                        _utc_iso(record.updated_at),
                        str(record.id),
                    ),
                )
                if cursor.rowcount == 0:
                    raise SetupNotFoundError(
                        f"Setup not found: {record.name}",
                        details={"name": record.name},
                    )
        except SetupNotFoundError:
            raise
        except sqlite3.Error as error:
            raise DatabaseError(
                f"Could not update setup metadata: {record.name}",
                details={"name": record.name},
            ) from error

    def get_by_name(self, name: str) -> SetupRecord:
        """Return one setup by its normalized name."""
        try:
            row = self._connection.execute(
                "SELECT * FROM setups WHERE name = ?",
                (name,),
            ).fetchone()
        except sqlite3.Error as error:
            raise DatabaseError(
                f"Could not query setup metadata: {name}",
                details={"name": name},
            ) from error
        if row is None:
            raise SetupNotFoundError(
                f"Setup not found: {name}",
                details={"name": name},
            )
        return _row_to_record(row)

    def list(self) -> tuple[SetupRecord, ...]:
        """Return all setups in stable name order."""
        try:
            rows = self._connection.execute(
                "SELECT * FROM setups ORDER BY name"
            ).fetchall()
        except sqlite3.Error as error:
            raise DatabaseError("Could not list setup metadata") from error
        return tuple(_row_to_record(row) for row in rows)

    def delete(self, name: str) -> SetupRecord:
        """Delete one setup row and return the removed record."""
        record = self.get_by_name(name)
        try:
            with self._connection:
                self._connection.execute(
                    "DELETE FROM setups WHERE id = ?",
                    (str(record.id),),
                )
        except sqlite3.Error as error:
            raise DatabaseError(
                f"Could not delete setup metadata: {name}",
                details={"name": name},
            ) from error
        return record


def _record_parameters(record: SetupRecord) -> tuple[str, ...]:
    """Serialize one setup record for insertion."""
    return (
        str(record.id),
        record.name,
        str(record.manifest_path),
        record.manifest_hash,
        record.source.value,
        _utc_iso(record.created_at),
        _utc_iso(record.updated_at),
    )


def _row_to_record(row: sqlite3.Row) -> SetupRecord:
    """Deserialize one SQLite setup row."""
    return SetupRecord(
        id=UUID(row["id"]),
        name=row["name"],
        manifest_path=Path(row["manifest_path"]),
        manifest_hash=row["manifest_hash"],
        source=SetupSource(row["source"]),
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


def _utc_iso(value: datetime) -> str:
    """Serialize an aware timestamp in UTC."""
    if value.tzinfo is None:
        raise ValueError("database timestamps must be timezone-aware")
    return value.astimezone(UTC).isoformat()
