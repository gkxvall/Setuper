# Testing Strategy

## Goals

- Verify behavior without relying on the developer's real desktop.
- Keep most tests deterministic and fast.
- Test system integrations through fakes plus a controlled macOS integration suite.

## Test Pyramid

### Unit tests

Cover:

- Manifest validation.
- Variable interpolation.
- Dependency graph construction and cycle detection.
- Retry and timeout policies.
- Port conflict policies.
- Trust hash behavior.
- State transitions.
- Error-to-exit-code mapping.

### Integration tests

Cover:

- SQLite repositories and migrations.
- Atomic YAML persistence.
- Subprocess supervision using fixture scripts.
- TCP and HTTP readiness checks.
- Docker Compose adapter using a tiny fixture stack when Docker is available.
- Plugin JSON protocol.

### End-to-end tests

Run the packaged CLI against temporary directories:

- `init`, `save`, `list`, `show`, `clone`, `rename`, `delete`.
- Launch a test HTTP server command and verify readiness.
- Stop the launched process and verify cleanup.
- Test JSON output and exit codes.

### macOS smoke tests

Manual or dedicated CI runner tests:

- Accessibility permission detection.
- Launch VS Code or Cursor fixture project.
- Open browser fixture URLs.
- Capture and restore basic window geometry.

## Fixtures

Create fixture executables for:

- delayed HTTP server;
- TCP server;
- process that exits with a chosen code;
- process that ignores graceful termination;
- process that prints fake secrets to test redaction.

## Coverage

- Core package target: 85% minimum.
- Security, graph, manifest, and subprocess supervision modules: 95% target.
- Coverage must not be increased using meaningless assertions.

## CI Checks

Every pushed commit must run:

```bash
ruff check .
ruff format --check .
mypy src
pytest -q
```

Additional release checks:

```bash
pytest -q --cov=setuper --cov-report=term-missing
python -m build
twine check dist/*
```

## Definition of Done

A task is not done until tests are added or updated, relevant docs are updated, all checks pass, and the atomic commit is pushed.
