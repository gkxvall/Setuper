# Coding Standards

## Python

- Python 3.12+.
- Use `src/` package layout.
- Type annotations for all public and internal function signatures.
- Prefer dataclasses or Pydantic models for structured data.
- Use `pathlib.Path`, not raw path strings internally.
- Use `asyncio` only where concurrency or asynchronous I/O provides value.
- Never use bare `except`.
- Never call `shell=True` with untrusted input.
- No mutable default arguments.
- Dependency injection for system-facing services.

## Tooling

- Ruff for linting and formatting.
- Mypy in strict or near-strict mode.
- Pytest for tests.
- Coverage.py for coverage.
- Pre-commit for local checks.
- Build with `pyproject.toml` and a modern backend.

## Naming

- Modules and functions: `snake_case`.
- Classes: `PascalCase`.
- Constants: `UPPER_SNAKE_CASE`.
- Resource IDs: lowercase kebab-case in manifests.
- Typed errors end with `Error`.

## Functions

- Prefer small single-purpose functions.
- Keep orchestration in services and platform details in adapters.
- Avoid hidden global state.
- Return typed values instead of loosely structured dictionaries.

## Logging

- Use structured logs.
- Never log passwords, tokens, cookies, private keys, or complete environment dumps.
- Include contextual IDs.
- User-facing messages and diagnostic logs are separate concerns.

## Git Discipline

Codex must make the smallest coherent change possible, then run relevant checks, commit, and push.

Examples of acceptable atomic commits:

```text
chore: initialize Python package
feat(cli): add root command
feat(manifest): define setup schema
feat(db): add initial SQLite migration
feat(command): validate working directory
fix(launch): avoid reusing stale pid
```

Do not combine unrelated refactors, tests, documentation, and features in one commit unless they are inseparable.

## Documentation

- Update relevant documentation in the same atomic commit as behavior changes.
- Public interfaces require docstrings.
- Complex decisions require an ADR entry in `decisions.md`.
