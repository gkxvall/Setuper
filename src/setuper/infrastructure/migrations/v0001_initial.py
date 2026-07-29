"""Initial operational-state database schema."""

from setuper.infrastructure.database import Migration

INITIAL_SCHEMA = Migration(
    version=1,
    description="create operational state tables",
    statements=(
        """
        CREATE TABLE setups (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            manifest_path TEXT NOT NULL,
            manifest_hash TEXT NOT NULL,
            source TEXT NOT NULL
                CHECK (source IN ('local', 'project', 'imported')),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE trust_approvals (
            id TEXT PRIMARY KEY,
            setup_id TEXT NOT NULL
                REFERENCES setups(id) ON DELETE CASCADE,
            manifest_hash TEXT NOT NULL,
            approved_at TEXT NOT NULL,
            approval_scope TEXT NOT NULL
                CHECK (approval_scope = 'local-machine'),
            revoked_at TEXT
        )
        """,
        """
        CREATE TABLE launches (
            id TEXT PRIMARY KEY,
            setup_id TEXT NOT NULL
                REFERENCES setups(id) ON DELETE CASCADE,
            manifest_hash TEXT NOT NULL,
            profile TEXT,
            status TEXT NOT NULL
                CHECK (
                    status IN (
                        'starting', 'running', 'partial', 'failed', 'stopped'
                    )
                ),
            started_at TEXT NOT NULL,
            completed_at TEXT,
            stopped_at TEXT,
            initiated_by TEXT NOT NULL CHECK (initiated_by = 'cli')
        )
        """,
        """
        CREATE TABLE resource_runs (
            id TEXT PRIMARY KEY,
            launch_id TEXT NOT NULL
                REFERENCES launches(id) ON DELETE CASCADE,
            resource_id TEXT NOT NULL,
            resource_type TEXT NOT NULL,
            status TEXT NOT NULL
                CHECK (
                    status IN (
                        'pending', 'validating', 'starting', 'running', 'ready',
                        'skipped', 'blocked', 'failed', 'stopping', 'stopped'
                    )
                ),
            pid INTEGER,
            external_id TEXT,
            started_at TEXT,
            ready_at TEXT,
            stopped_at TEXT,
            exit_code INTEGER,
            error_code TEXT,
            error_message TEXT
        )
        """,
        """
        CREATE TABLE launch_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            launch_id TEXT NOT NULL
                REFERENCES launches(id) ON DELETE CASCADE,
            resource_run_id TEXT
                REFERENCES resource_runs(id) ON DELETE SET NULL,
            event_type TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE capture_history (
            id TEXT PRIMARY KEY,
            setup_id TEXT
                REFERENCES setups(id) ON DELETE SET NULL,
            command TEXT NOT NULL
                CHECK (command IN ('inspect', 'save', 'update')),
            summary_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """,
        """
        CREATE INDEX idx_launches_setup_started
        ON launches(setup_id, started_at DESC)
        """,
        """
        CREATE INDEX idx_resource_runs_launch_resource
        ON resource_runs(launch_id, resource_id)
        """,
        """
        CREATE INDEX idx_launch_events_launch_created
        ON launch_events(launch_id, created_at)
        """,
        """
        CREATE INDEX idx_trust_approvals_setup_hash
        ON trust_approvals(setup_id, manifest_hash)
        """,
    ),
)
