# Components

## CLI Components

- Root command application.
- Shared option and output helpers.
- Command modules for every supported action.
- Prompt and confirmation service.
- JSON formatter.
- Human-readable Rich renderer.

## Domain Components

### SetupManifest

Validated representation of a setup.

### ResourceSpec

One launchable or restorable unit.

### DependencyGraph

Validates resource IDs, detects cycles, and provides ready execution batches.

### ReadinessSpec

Supports TCP, HTTP, process, file, and command checks.

### RetryPolicy

Defines attempts, initial delay, maximum delay, and backoff.

### PortPolicy

Defines conflict behavior: `fail`, `reuse`, `stop_owned`, or `increment`.

## Application Components

- Capture service.
- Setup CRUD service.
- Launch coordinator.
- Stop coordinator.
- Status service.
- Doctor service.
- Audit and trust service.
- Diff service.

## Infrastructure Components

- Manifest repository.
- SQLite repository.
- Configuration loader.
- Platform path resolver.
- Structured logger.
- Secret provider.
- Subprocess supervisor.
- Permission checker.

## Built-in Adapters

### command

Launches explicit commands with controlled environment, working directory, log capture, readiness, and stop behavior.

### process

Captures process metadata. Automatic relaunch is restricted unless a semantic command can be reconstructed safely.

### docker

Captures and restores selected containers.

### docker_compose

Restores services using project directory and compose files.

### git

Captures repository metadata and validates branch and dirty state. It does not automatically discard user changes.

### vscode and cursor

Open folders or workspace files using application CLIs.

### browser

Capture and reopen browser tabs through supported integration. Do not export cookies or credentials.

### terminal

Opens terminal windows or tabs and launches approved commands.

### macos_window

Captures and restores app window bounds when accessibility permissions and app behavior allow it.

## Test Doubles

Every system-facing component must have an interface and a fake implementation for deterministic tests.
