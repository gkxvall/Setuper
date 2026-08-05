# v1.0.0 Task Plan

Codex must complete tasks in order. Each checkbox should produce one or more smallest-possible commits. After every atomic commit, push the current branch.

## Phase 0 — Repository foundation

- [x] Initialize Git repository if needed.
- [x] Add Python `src/` package layout.
- [x] Add `pyproject.toml`.
- [x] Add license, README, changelog, contributing, code of conduct, and security policy.
- [x] Add Ruff, Mypy, Pytest, Coverage, and pre-commit configuration.
- [x] Add CI workflow.
- [x] Add a minimal root CLI and version command.

## Phase 1 — Domain and persistence

- [x] Define domain enums and typed errors.
- [x] Define manifest Pydantic models.
- [x] Implement YAML load, validate, and atomic save.
- [x] Implement platform-standard paths.
- [x] Add SQLite connection and migration runner.
- [x] Add initial database schema.
- [x] Add setup repository and launch repository.
- [x] Add manifest hashing and trust approvals.

## Phase 2 — Setup commands

- [x] Implement `init`.
- [x] Implement `list`.
- [x] Implement `show`.
- [x] Implement `edit`.
- [x] Implement `clone`.
- [x] Implement `rename`.
- [x] Implement `delete`.
- [x] Implement `import` and `export`.
- [x] Add JSON output for supported commands.

## Phase 3 — Capture system

- [x] Define adapter interfaces and registry.
- [x] Implement process detection.
- [x] Implement listening-port detection.
- [x] Implement Git detection.
- [x] Implement Docker detection.
- [x] Implement Docker Compose detection.
- [x] Implement VS Code detection.
- [x] Implement Cursor detection.
- [x] Implement basic macOS app detection.
- [x] Implement window geometry capture.
- [x] Implement browser integration protocol.
- [x] Implement `inspect`.
- [x] Implement `save` with dry-run.
- [x] Implement `update`.
- [x] Implement `diff`.

## Phase 4 — Launch engine

- [x] Implement variable resolution.
- [x] Implement profile merging.
- [x] Implement dependency graph and cycle errors.
- [x] Implement subprocess supervisor.
- [x] Implement TCP readiness check.
- [x] Implement HTTP readiness check.
- [x] Implement command readiness check.
- [x] Implement retry and timeout policies.
- [x] Implement bounded-concurrency scheduler.
- [x] Implement resource state persistence.
- [x] Implement dry-run launch plan.
- [x] Implement `launch`.

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
