# Internal and Plugin API

## Scope

Setuper v1.0.0 is a CLI product and does not expose an HTTP server. This document defines stable Python service interfaces, adapter contracts, JSON output, and the external plugin protocol.

## Application Service API

```python
class SetupService:
    def list_setups(self) -> list[SetupSummary]: ...
    def get_setup(self, name: str) -> SetupManifest: ...
    def save_setup(self, request: SaveSetupRequest) -> SaveSetupResult: ...
    def update_setup(self, request: UpdateSetupRequest) -> UpdateSetupResult: ...
    def delete_setup(self, name: str) -> None: ...
    def clone_setup(self, source: str, target: str) -> SetupManifest: ...
```

```python
class LaunchService:
    async def launch(self, request: LaunchRequest) -> LaunchSummary: ...
    async def stop(self, request: StopRequest) -> StopSummary: ...
    async def status(self, name: str | None) -> list[SetupRuntimeStatus]: ...
```

## JSON CLI Output

Commands supporting `--json` must return one JSON object to stdout and diagnostics to stderr.

Success envelope:

```json
{
  "ok": true,
  "command": "list",
  "data": {},
  "warnings": []
}
```

Failure envelope:

```json
{
  "ok": false,
  "command": "launch",
  "error": {
    "code": "PORT_CONFLICT",
    "message": "Port 3000 is already in use",
    "details": {}
  }
}
```

## Manifest API

Top-level fields:

- `schema_version`
- `id`
- `name`
- `description`
- `platforms`
- `variables`
- `profiles`
- `resources`
- `hooks`
- `metadata`

Resource fields:

- `id`
- `type`
- `description`
- `enabled`
- `depends_on`
- `config`
- `env`
- `ready_when`
- `retry`
- `timeout_seconds`
- `on_conflict`
- `metadata`

Unknown fields are rejected by default in v1.0.0 to catch mistakes early.

## Plugin Discovery

Executable plugins are discovered from configured plugin directories. Names follow:

```text
setuper-plugin-<name>
```

Setuper invokes the executable with a JSON Lines protocol.

Supported operations:

- `handshake`
- `detect`
- `capture`
- `validate`
- `launch`
- `status`
- `stop`

Plugins declare capabilities during handshake. Unsupported operations must return a structured error.

## Compatibility

- Manifest schema version is integer `1` for v1.0.0.
- Plugin protocol version is integer `1`.
- Additive fields may be introduced in minor releases only when older clients safely ignore them.
- Breaking schema changes require a migration path and a major release.
