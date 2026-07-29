# Database Design

## Purpose

SQLite stores operational metadata, not setup definitions. Setup manifests remain human-readable YAML files.

Default location:

```text
~/Library/Application Support/setuper/state.db
```

## Database Rules

- Enable foreign keys.
- Use WAL mode.
- Use explicit migrations.
- Store UTC timestamps in ISO 8601 format.
- Never store secret values.
- Make launch and approval records append-oriented.

## Tables

### schema_migrations

| Column | Type | Notes |
|---|---|---|
| version | INTEGER PK | Migration number |
| applied_at | TEXT | UTC timestamp |

### setups

| Column | Type | Notes |
|---|---|---|
| id | TEXT PK | Stable UUID |
| name | TEXT UNIQUE | Normalized setup name |
| manifest_path | TEXT | Absolute path |
| manifest_hash | TEXT | SHA-256 |
| source | TEXT | local, project, imported |
| created_at | TEXT | UTC |
| updated_at | TEXT | UTC |

### trust_approvals

| Column | Type | Notes |
|---|---|---|
| id | TEXT PK | UUID |
| setup_id | TEXT FK | Setup |
| manifest_hash | TEXT | Approved hash |
| approved_at | TEXT | UTC |
| approval_scope | TEXT | local-machine in v1 |
| revoked_at | TEXT NULL | UTC |

### launches

| Column | Type | Notes |
|---|---|---|
| id | TEXT PK | Launch UUID |
| setup_id | TEXT FK | Setup |
| manifest_hash | TEXT | Launched revision |
| profile | TEXT NULL | Selected profile |
| status | TEXT | starting, running, partial, failed, stopped |
| started_at | TEXT | UTC |
| completed_at | TEXT NULL | UTC |
| stopped_at | TEXT NULL | UTC |
| initiated_by | TEXT | cli |

### resource_runs

| Column | Type | Notes |
|---|---|---|
| id | TEXT PK | UUID |
| launch_id | TEXT FK | Parent launch |
| resource_id | TEXT | Manifest resource ID |
| resource_type | TEXT | Adapter type |
| status | TEXT | pending/validating/starting/running/ready/skipped/blocked/failed/stopping/stopped |
| pid | INTEGER NULL | Owned PID |
| external_id | TEXT NULL | Container or app identifier |
| started_at | TEXT NULL | UTC |
| ready_at | TEXT NULL | UTC |
| stopped_at | TEXT NULL | UTC |
| exit_code | INTEGER NULL | Process exit code |
| error_code | TEXT NULL | Typed error |
| error_message | TEXT NULL | Redacted message |

### launch_events

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK AUTOINCREMENT | Sequence |
| launch_id | TEXT FK | Launch |
| resource_run_id | TEXT NULL FK | Resource |
| event_type | TEXT | Structured event |
| payload_json | TEXT | Redacted JSON |
| created_at | TEXT | UTC |

### capture_history

| Column | Type | Notes |
|---|---|---|
| id | TEXT PK | UUID |
| setup_id | TEXT NULL FK | Saved target |
| command | TEXT | inspect, save, update |
| summary_json | TEXT | Counts and statuses |
| created_at | TEXT | UTC |

## Indexes

- `setups(name)` unique.
- `launches(setup_id, started_at DESC)`.
- `resource_runs(launch_id, resource_id)`.
- `launch_events(launch_id, created_at)`.
- `trust_approvals(setup_id, manifest_hash)`.

## Retention

Default retention:

- Launch metadata: 90 days.
- Event rows: 30 days.
- Current running launches: never pruned.
- User may configure retention or run `setuper maintenance prune` in a later release.

## Migrations

Migrations live under `src/setuper/infrastructure/migrations/` and are applied transactionally at startup. Never edit an applied migration; create a new one.
