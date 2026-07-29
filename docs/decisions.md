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

## ADR-009 — Manifest IDs are optional at parse time

**Status:** Accepted

**Decision:** Schema-v1 manifests accept an omitted `id`. Setup creation and import
workflows assign a stable UUID before persistence.

**Reason:** The manifest API lists `id`, while the canonical example omits it.
Parsing the example must remain valid without generating nondeterministic data
during validation.

**Consequence:** A parsed manifest may have no ID, but repositories must reject or
assign one before recording the setup in SQLite.

## ADR-010 — Project-local manifest filename

**Status:** Accepted

**Decision:** `setuper init [PATH]` creates `PATH/.setuper.yaml`.

**Reason:** The CLI contract defines project initialization but not its filename.
A hidden, repository-local YAML file is discoverable without competing with
common project files.

**Consequence:** Initialization refuses to overwrite any existing file or
symlink at that path.

## ADR-011 — Editor selection and validation

**Status:** Accepted

**Decision:** `setuper edit` selects `$VISUAL`, then `$EDITOR`, and falls back to
macOS `open -W -t`. It edits a private copy, validates it, and atomically replaces
the stored manifest only when its name and ID are unchanged.

**Reason:** Environment-based editor selection is conventional and supports
argument-bearing commands without shell execution. A validated copy protects the
source of truth from partial or invalid editor writes.

**Consequence:** Renaming is reserved for `setuper rename`; users on non-macOS
systems must configure `$VISUAL` or `$EDITOR`.

## ADR-012 — Managed clone storage

**Status:** Accepted

**Decision:** Cloned setups receive a new UUID and are stored as
`<data-directory>/setups/<uuid>.yaml`.

**Reason:** The clone command accepts a setup name rather than a destination
path. UUID filenames keep names with spaces and Unicode safe and prevent names
from influencing filesystem traversal.

**Consequence:** Clones are registered as local setups but receive no copied
trust approval.

## ADR-013 — Non-destructive export

**Status:** Accepted

**Decision:** Export writes only validated manifest YAML and refuses to overwrite
an existing file or symlink.

**Reason:** SQLite runtime metadata and local trust approvals are machine-local.
Refusing replacement prevents an output typo from destroying an existing file.

**Consequence:** Users must choose a new destination path for every export.
