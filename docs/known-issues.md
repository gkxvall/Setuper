# Known Issues and Limitations

## Fundamental Limitations

- Setuper cannot restore arbitrary process memory.
- Existing TCP connections cannot generally be resumed.
- Database transactions and in-memory application state are not portable.
- Some applications do not expose enough state for reliable capture.

## macOS

- Accessibility and Automation permissions are required for some window and application operations.
- macOS Spaces are not consistently controllable through stable public APIs.
- Window restoration can differ across display arrangements.
- Full-screen application windows may not restore to the same state.
- Application names and bundle identifiers may change between editions.

## Browsers

- Browser capture requires an extension or explicit automation support.
- Incognito/private tabs are excluded.
- Cookies, form content, and authentication state are not exported.
- Browser policies may block extension installation in managed environments.

## Terminals

- Setuper cannot safely infer every command from an arbitrary terminal process tree.
- Shell history is not a reliable source of the currently running command.
- Captured terminal commands require user review.

## Processes and Ports

- A PID may be reused; Setuper must verify process identity.
- A process may change ports after capture.
- Port increment policies may require applications to support environment-based port configuration.

## Docker

- Container state outside volumes may be lost when recreated.
- Compose project detection can be ambiguous when metadata is incomplete.
- Docker Desktop must already be available or started through an approved adapter.

## Cross-machine Portability

- Absolute paths, installed application names, display IDs, and local browser profiles are machine-bound.
- Setup manifests may require variables or path mappings on another machine.

## v1.0.0 Platform Scope

Windows and Linux are not production-supported in v1.0.0. Platform abstractions must exist, but behavior may return a clear unsupported-platform error.
