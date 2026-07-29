# Setuper — Product Idea

## Product

**Setuper** is a Python CLI that captures, stores, inspects, launches, updates, and stops named work environments.

A setup represents the reproducible intent of a workspace rather than an impossible byte-for-byte snapshot of every process. It may include applications, projects, terminal sessions, commands, ports, Docker services, Git repositories, browser tabs, window placement, environment references, health checks, dependencies, and launch hooks.

```bash
setuper save ansade
setuper launch ansade
setuper list
setuper show ansade
setuper stop ansade
```

## v1.0.0 Vision

Version 1.0.0 must provide a dependable macOS-first implementation for developers while keeping the design portable to Windows and Linux.

The user should be able to:

1. Inspect what Setuper can detect.
2. Save a named setup from the current machine state.
3. Review and edit the generated manifest.
4. Validate the setup before launch.
5. Launch resources in dependency order.
6. Wait for ports and health checks.
7. Restore supported apps, projects, terminals, browser tabs, and windows.
8. Stop resources started by Setuper.
9. Compare a setup with the current environment.
10. Export, import, clone, rename, and delete setups.

## Core Principles

- **Reconstruct intent, not raw memory.**
- **Readable manifests over opaque snapshots.**
- **Safe by default.** Imported commands and hooks are untrusted until approved.
- **Adapter-based integrations.** Application-specific behavior must not leak into the core.
- **Partial success is explicit.** Unsupported resources are reported, never silently ignored.
- **Idempotent launches.** Re-launching a running setup should reuse, skip, or clearly resolve conflicts.
- **Small commits.** Every atomic change is committed and pushed independently.

## Initial Audience

- Software developers switching between projects.
- Teams onboarding contributors.
- Students managing course workspaces.
- Designers and analysts who use repeatable groups of apps and documents.
- Power users who want named terminal-driven work contexts.

## v1.0.0 Scope

### Included

- macOS support.
- Python 3.12+.
- CLI commands and structured terminal output.
- YAML setup manifests.
- SQLite runtime metadata.
- Process and listening-port discovery.
- Git repository detection.
- Docker and Docker Compose integration.
- VS Code and Cursor project launching.
- Terminal command registration and launching.
- Chrome-based browser tab capture through a browser extension or supported automation bridge.
- App and window capture where macOS permissions permit it.
- Dependency graph execution.
- HTTP and TCP readiness checks.
- Environment and secret references.
- Trust and audit workflow.
- Setup import/export.
- Logging and launch history.
- Unit, integration, and end-to-end tests.

### Not Included

- Exact process-memory restoration.
- Restoration of live TCP sockets.
- Restoration of database transactions.
- Transfer of browser cookies or secrets between machines.
- Perfect restoration for every macOS application.
- Windows and Linux production support.
- Cloud synchronization.
- Remote execution.
- GUI desktop application.

## Example Manifest

```yaml
schema_version: 1
name: ansade-development
description: ANSADE data portal workspace
platforms: [macos]

variables:
  FRONTEND_PORT:
    default: "3000"

resources:
  - id: postgres
    type: docker_compose
    config:
      project_dir: ~/Projects/ANSADE-data-portal
      services: [postgres]
    ready_when:
      tcp:
        host: 127.0.0.1
        port: 5432

  - id: frontend
    type: command
    depends_on: [postgres]
    config:
      cwd: ~/Projects/ANSADE-data-portal
      command: npm run dev
    env:
      PORT: ${FRONTEND_PORT}
    ready_when:
      http:
        url: http://127.0.0.1:${FRONTEND_PORT}
        expected_status: 200

  - id: editor
    type: vscode
    depends_on: [frontend]
    config:
      paths: [~/Projects/ANSADE-data-portal]

  - id: browser
    type: browser
    depends_on: [frontend]
    config:
      browser: chrome
      tabs:
        - http://127.0.0.1:${FRONTEND_PORT}
```

## Success Criteria

v1.0.0 is complete when a clean macOS machine with documented prerequisites can install Setuper, create a setup, inspect the manifest, launch it reliably, stop managed resources, and reproduce the workflow using automated tests and release artifacts.
