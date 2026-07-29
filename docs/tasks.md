# v1.0.0 Task Plan

Codex must complete tasks in order. Each checkbox should produce one or more smallest-possible commits. After every atomic commit, push the current branch.

## Phase 0 — Repository foundation

- [ ] Initialize Git repository if needed.
- [ ] Add Python `src/` package layout.
- [ ] Add `pyproject.toml`.
- [ ] Add license, README, changelog, contributing, code of conduct, and security policy.
- [ ] Add Ruff, Mypy, Pytest, Coverage, and pre-commit configuration.
- [ ] Add CI workflow.
- [ ] Add a minimal root CLI and version command.

## Phase 1 — Domain and persistence

- [ ] Define domain enums and typed errors.
- [ ] Define manifest Pydantic models.
- [ ] Implement YAML load, validate, and atomic save.
- [ ] Implement platform-standard paths.
- [ ] Add SQLite connection and migration runner.
- [ ] Add initial database schema.
- [ ] Add setup repository and launch repository.
- [ ] Add manifest hashing and trust approvals.

## Phase 2 — Setup commands

- [ ] Implement `init`.
- [ ] Implement `list`.
- [ ] Implement `show`.
- [ ] Implement `edit`.
- [ ] Implement `clone`.
- [ ] Implement `rename`.
- [ ] Implement `delete`.
- [ ] Implement `import` and `export`.
- [ ] Add JSON output for supported commands.

## Phase 3 — Capture system

- [ ] Define adapter interfaces and registry.
- [ ] Implement process detection.
- [ ] Implement listening-port detection.
- [ ] Implement Git detection.
- [ ] Implement Docker detection.
- [ ] Implement Docker Compose detection.
- [ ] Implement VS Code detection.
- [ ] Implement Cursor detection.
- [ ] Implement basic macOS app detection.
- [ ] Implement window geometry capture.
- [ ] Implement browser integration protocol.
- [ ] Implement `inspect`.
- [ ] Implement `save` with dry-run.
- [ ] Implement `update`.
- [ ] Implement `diff`.

## Phase 4 — Launch engine

- [ ] Implement variable resolution.
- [ ] Implement profile merging.
- [ ] Implement dependency graph and cycle errors.
- [ ] Implement subprocess supervisor.
- [ ] Implement TCP readiness check.
- [ ] Implement HTTP readiness check.
- [ ] Implement command readiness check.
- [ ] Implement retry and timeout policies.
- [ ] Implement bounded-concurrency scheduler.
- [ ] Implement resource state persistence.
- [ ] Implement dry-run launch plan.
- [ ] Implement `launch`.

## Phase 5 — Built-in launch adapters

- [ ] Command adapter.
- [ ] Docker adapter.
- [ ] Docker Compose adapter.
- [ ] Git validation adapter.
- [ ] VS Code adapter.
- [ ] Cursor adapter.
- [ ] Terminal adapter.
- [ ] Browser adapter.
- [ ] macOS application adapter.
- [ ] macOS window restoration adapter.

## Phase 6 — Runtime operations

- [ ] Implement owned-process verification.
- [ ] Implement graceful and forced stop.
- [ ] Implement `stop`.
- [ ] Implement `status`.
- [ ] Implement structured event logs.
- [ ] Implement `logs` and `--follow`.
- [ ] Reconcile stale runtime state at startup.

## Phase 7 — Safety and diagnostics

- [ ] Implement `audit`.
- [ ] Implement `trust` and `untrust`.
- [ ] Implement probable-secret detection.
- [ ] Implement secret redaction.
- [ ] Implement Keychain references.
- [ ] Implement permission checks.
- [ ] Implement `doctor`.
- [ ] Implement port conflict handling.
- [ ] Add safe prompts and noninteractive behavior.

## Phase 8 — Plugin protocol

- [ ] Define protocol models.
- [ ] Implement executable discovery.
- [ ] Implement handshake.
- [ ] Implement request timeouts and output limits.
- [ ] Add a reference sample plugin.
- [ ] Document compatibility and security.

## Phase 9 — Hardening

- [ ] Complete unit test suite.
- [ ] Complete integration fixtures.
- [ ] Complete CLI end-to-end tests.
- [ ] Add macOS smoke test instructions.
- [ ] Reach coverage targets.
- [ ] Benchmark large manifests.
- [ ] Review all error messages.
- [ ] Validate Unicode and paths with spaces.
- [ ] Test clean install and uninstall.

## Phase 10 — Release

- [ ] Finalize README examples.
- [ ] Generate shell completion support.
- [ ] Add man-page or command reference generation.
- [ ] Add release workflow.
- [ ] Build and validate wheel and source distribution.
- [ ] Create Homebrew tap instructions.
- [ ] Update changelog for v1.0.0.
- [ ] Tag and publish v1.0.0.
