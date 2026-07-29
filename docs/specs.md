# Setuper v1.0.0 Specifications

## Functional Requirements

### Setup lifecycle

- Create a setup with `setuper save <name>`.
- Create a project-local setup with `setuper init`.
- List setups with filters and machine-readable output.
- Show full setup details.
- Edit manifests in the configured editor.
- Rename, clone, delete, import, and export setups.
- Update an existing setup from current state.
- Compare saved and current state.

### Capture

Setuper must detect, when permitted:

- Running applications.
- Process executable, arguments, parent, working directory, and listening ports.
- Git repository root, remote, current branch, and dirty-state indicator.
- Docker containers and Docker Compose projects.
- Supported editor workspaces.
- Supported browser windows and tabs.
- Window bounds, display, and macOS Space when reliable.
- Environment variable names, never secret values by default.

Capture must assign each finding one status:

- `supported`
- `partially_supported`
- `machine_bound`
- `sensitive`
- `unsupported`

### Launch

- Parse and validate the manifest.
- Resolve variables and secret references.
- Build a dependency graph.
- Reject cycles.
- Run independent resources concurrently within configured limits.
- Wait for readiness checks.
- Retry according to policy.
- Record process IDs and ownership metadata.
- Restore windows only after the related application is launched.
- Print a final summary with success, skipped, reused, and failed resources.

### Stop

- Stop only resources started by the relevant Setuper launch unless the user explicitly overrides this behavior.
- Use graceful termination before force termination.
- Support adapter-specific stop behavior.
- Preserve unrelated user processes.

### Safety

- Imported setups begin untrusted.
- Any executable command, hook, or shell interpolation must be shown during audit.
- First launch of a changed trusted setup requires reapproval.
- Secrets must be referenced from environment variables or the OS keychain.
- Sensitive values must be redacted from logs.

## CLI Contract

```text
setuper init [PATH]
setuper inspect [--json]
setuper save NAME [--dry-run] [--include TYPE] [--exclude TYPE]
setuper update NAME [--dry-run]
setuper launch NAME [--profile NAME] [--only IDS] [--skip IDS] [--dry-run]
setuper stop NAME [--force]
setuper status [NAME] [--json]
setuper list [--json]
setuper show NAME [--json] [--portability]
setuper diff NAME [--json]
setuper doctor [NAME] [--json]
setuper logs NAME [--follow]
setuper edit NAME
setuper clone SOURCE TARGET
setuper rename OLD NEW
setuper delete NAME [--yes]
setuper export NAME --output FILE
setuper import FILE [--name NAME]
setuper trust NAME
setuper untrust NAME
setuper audit NAME
setuper config get KEY
setuper config set KEY VALUE
setuper plugin list
```

## Exit Codes

- `0`: success.
- `1`: general failure.
- `2`: invalid CLI usage.
- `3`: validation failure.
- `4`: setup not found.
- `5`: permission missing.
- `6`: launch partially failed.
- `7`: security or trust rejection.
- `8`: dependency cycle.
- `9`: port conflict.
- `10`: unsupported platform or adapter.

## Nonfunctional Requirements

- CLI startup under 300 ms on a typical supported machine, excluding Python interpreter cold-start variance.
- No unhandled tracebacks in normal user flows.
- Atomic manifest writes.
- Concurrent launch limit configurable, default `4`.
- All public Python functions type-annotated.
- Core package test coverage target: at least 85%.
- Deterministic JSON output for automation.
- Compatible with paths containing spaces and Unicode.
- Logs must include timestamps, setup ID, launch ID, resource ID, and event type.

## Compatibility

- Python 3.12 and 3.13.
- macOS 14 or newer for official v1.0.0 support.
- Apple Silicon and Intel where dependencies support both.
- Shells: zsh and bash.

## Configuration precedence

1. CLI arguments.
2. Profile values.
3. Setup manifest.
4. Project-local configuration.
5. User configuration.
6. Built-in defaults.
