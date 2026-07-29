"""SQLite persistence for exact-hash trust approvals."""

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from setuper.domain.enums import ApprovalScope
from setuper.domain.errors import DatabaseError


@dataclass(frozen=True, slots=True)
class TrustApprovalRecord:
    """One append-oriented local-machine approval."""

    id: UUID
    setup_id: UUID
    manifest_hash: str
    approved_at: datetime
    approval_scope: ApprovalScope = ApprovalScope.LOCAL_MACHINE
    revoked_at: datetime | None = None

    def __post_init__(self) -> None:
        """Require a lowercase SHA-256 digest."""
        if len(self.manifest_hash) != 64 or any(
            character not in "0123456789abcdef" for character in self.manifest_hash
        ):
            raise ValueError("manifest_hash must be a lowercase SHA-256 digest")


class TrustRepository:
    """Store and revoke approvals without evaluating executable content."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        """Bind the repository to an initialized SQLite connection."""
        self._connection = connection

    def create(self, record: TrustApprovalRecord) -> None:
        """Append one trust approval."""
        try:
            with self._connection:
                self._connection.execute(
                    """
                    INSERT INTO trust_approvals(
                        id, setup_id, manifest_hash, approved_at,
                        approval_scope, revoked_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(record.id),
                        str(record.setup_id),
                        record.manifest_hash,
                        _utc_iso(record.approved_at),
                        record.approval_scope.value,
                        _optional_utc_iso(record.revoked_at),
                    ),
                )
        except sqlite3.Error as error:
            raise DatabaseError(
                "Could not create trust approval",
                details={"setup_id": str(record.setup_id)},
            ) from error

    def active_approval(
        self,
        setup_id: UUID,
        manifest_hash: str,
    ) -> TrustApprovalRecord | None:
        """Return the newest active approval for an exact manifest hash."""
        try:
            row = self._connection.execute(
                """
                SELECT * FROM trust_approvals
                WHERE setup_id = ? AND manifest_hash = ? AND revoked_at IS NULL
                ORDER BY approved_at DESC, id DESC
                LIMIT 1
                """,
                (str(setup_id), manifest_hash),
            ).fetchone()
        except sqlite3.Error as error:
            raise DatabaseError(
                "Could not query trust approval",
                details={"setup_id": str(setup_id)},
            ) from error
        return None if row is None else _row_to_record(row)

    def revoke_all(self, setup_id: UUID, revoked_at: datetime) -> int:
        """Revoke every active approval for a setup and return the count."""
        serialized_revoked_at = _utc_iso(revoked_at)
        try:
            with self._connection:
                cursor = self._connection.execute(
                    """
                    UPDATE trust_approvals
                    SET revoked_at = ?
                    WHERE setup_id = ? AND revoked_at IS NULL
                    """,
                    (serialized_revoked_at, str(setup_id)),
                )
        except sqlite3.Error as error:
            raise DatabaseError(
                "Could not revoke trust approvals",
                details={"setup_id": str(setup_id)},
            ) from error
        return cursor.rowcount


def _row_to_record(row: sqlite3.Row) -> TrustApprovalRecord:
    """Deserialize one approval row."""
    return TrustApprovalRecord(
        id=UUID(row["id"]),
        setup_id=UUID(row["setup_id"]),
        manifest_hash=row["manifest_hash"],
        approved_at=datetime.fromisoformat(row["approved_at"]),
        approval_scope=ApprovalScope(row["approval_scope"]),
        revoked_at=_optional_datetime(row["revoked_at"]),
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
