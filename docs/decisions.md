# Architecture Decision Record

This file contains compact ADRs. New significant decisions must append a numbered entry rather than rewriting history.

## ADR-001 — Python as the implementation language

**Status:** Accepted

**Decision:** Build v1.0.0 in Python 3.12+.

**Reason:** Fast iteration, mature system and automation libraries, straightforward CLI development, and easier adapter experimentation.

**Consequence:** Distribution must be tested carefully. Use `pipx`, PyPI, and Homebrew to reduce environment conflicts.

## ADR-002 — macOS-first release

**Status:** Accepted

**Decision:** Official v1.0.0 support targets macOS.

**Reason:** Desktop capture APIs differ significantly by platform. A narrow first platform enables a reliable release.

**Consequence:** Platform interfaces must still prevent macOS logic from entering the domain layer.

## ADR-003 — YAML manifests plus SQLite state

**Status:** Accepted

**Decision:** Store desired setups in YAML and operational metadata in SQLite.

**Reason:** Users need readable, editable, versionable definitions while runtime history requires structured transactional storage.

## ADR-004 — Adapter architecture

**Status:** Accepted

**Decision:** All application and resource integrations implement adapter contracts.

**Reason:** Capture and launch behavior varies by tool and platform.

## ADR-005 — Reconstruct intent instead of freezing state

**Status:** Accepted

**Decision:** Setuper records semantic commands, projects, services, and readiness rather than promising exact process restoration.

**Reason:** Arbitrary memory, sockets, and transactions cannot be portably restored.

## ADR-006 — Imported setups are executable and untrusted

**Status:** Accepted

**Decision:** Trust approvals are bound to a manifest hash.

**Reason:** A manifest may execute commands and access sensitive resources.

## ADR-007 — Plugins run out of process

**Status:** Accepted

**Decision:** External plugins communicate through versioned JSON Lines.

**Reason:** Avoid loading untrusted code directly into the Setuper process and allow plugins in multiple languages.

## ADR-008 — Atomic Git workflow

**Status:** Accepted

**Decision:** Every smallest coherent code change is tested, committed, and pushed independently.

**Reason:** Fine-grained history makes Codex work reviewable, reversible, and auditable.

**Constraint:** Commits must remain meaningful; no empty or artificial micro-commits.
