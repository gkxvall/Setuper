# Architecture

## Overview

Setuper uses a layered, adapter-driven architecture.

```text
CLI
  -> Application services
      -> Domain models and policies
          -> Adapter interfaces
              -> macOS, process, browser, editor, Docker, Git adapters
      -> Persistence interfaces
          -> YAML manifests, SQLite state, filesystem logs
```

## Package Layout

```text
src/setuper/
├── __init__.py
├── __main__.py
├── cli/
│   ├── app.py
│   ├── common.py
│   └── commands/
├── application/
│   ├── capture_service.py
│   ├── launch_service.py
│   ├── stop_service.py
│   ├── setup_service.py
│   ├── trust_service.py
│   └── doctor_service.py
├── domain/
│   ├── models.py
│   ├── enums.py
│   ├── errors.py
│   ├── graph.py
│   ├── readiness.py
│   └── policies.py
├── adapters/
│   ├── base.py
│   ├── registry.py
│   ├── process.py
│   ├── command.py
│   ├── docker.py
│   ├── docker_compose.py
│   ├── git.py
│   ├── vscode.py
│   ├── cursor.py
│   ├── browser.py
│   ├── terminal.py
│   └── macos_windows.py
├── infrastructure/
│   ├── config.py
│   ├── manifests.py
│   ├── database.py
│   ├── keychain.py
│   ├── subprocesses.py
│   ├── logging.py
│   └── paths.py
└── plugins/
    ├── protocol.py
    └── loader.py
```

## Layer Rules

- `domain` imports no CLI, database, operating-system, or third-party adapter implementation.
- `application` coordinates use cases and depends on interfaces.
- `adapters` implement capture, validate, launch, status, and stop operations.
- `infrastructure` handles persistence and platform services.
- `cli` translates terminal input into application calls and domain errors into user-facing output.

## Adapter Interface

Each adapter supports only applicable operations.

```python
class ResourceAdapter(Protocol):
    type_name: str

    def detect(self, context: CaptureContext) -> list[DetectedResource]: ...
    def capture(self, resource: DetectedResource) -> ResourceSpec: ...
    def validate(
        self, spec: ResourceSpec, context: ValidationContext
    ) -> ValidationResult: ...
    async def launch(
        self, spec: ResourceSpec, context: LaunchContext
    ) -> LaunchResult: ...
    async def status(
        self, spec: ResourceSpec, context: StatusContext
    ) -> ResourceStatus: ...
    async def stop(self, spec: ResourceSpec, context: StopContext) -> StopResult: ...
```

Adapters must not print directly. They return structured results.

## Launch Engine

1. Load manifest.
2. Validate schema.
3. Verify trust.
4. Resolve variables and references.
5. Filter `--only` and `--skip` resources.
6. Build directed acyclic graph.
7. Validate all resources.
8. Present dry-run or approval prompt.
9. Schedule ready nodes with bounded concurrency.
10. Run readiness checks.
11. Persist resource runtime state.
12. Restore windows.
13. Return aggregate result.

A failed dependency blocks dependent resources unless `continue_on_dependency_failure` is explicitly enabled.

## Plugin Protocol

External plugins use JSON Lines over standard input and output. Version 1.0.0 may ship the protocol and plugin discovery while keeping third-party plugin execution experimental.

Every request contains:

```json
{"protocol_version":1,"request_id":"...","operation":"validate","resource":{}}
```

Every response contains:

```json
{"protocol_version":1,"request_id":"...","ok":true,"result":{}}
```

No arbitrary plugin is loaded into the Setuper Python process.

## Error Model

Errors are typed and mapped to exit codes. Domain errors include:

- `SetupNotFoundError`
- `ManifestValidationError`
- `UntrustedSetupError`
- `DependencyCycleError`
- `AdapterUnavailableError`
- `PermissionDeniedError`
- `PortConflictError`
- `ReadinessTimeoutError`
- `PartialLaunchError`

## Concurrency

Use `asyncio` for launch orchestration and readiness checks. Blocking system calls must run in a worker thread with `asyncio.to_thread`.

## Data Ownership

- YAML manifests are the source of truth for setup definitions.
- SQLite is the source of truth for launches, approvals, process ownership, and history.
- Logs are append-only diagnostic records.
