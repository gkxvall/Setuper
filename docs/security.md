# Security

## Threat Model

A setup manifest may execute commands, open applications, access files, start containers, and reference secrets. Imported manifests must therefore be treated like executable code.

## Trust Model

- Local captured setups may be reviewed before trust.
- Imported and cloned project setups are untrusted by default.
- Trust is bound to the exact manifest SHA-256 hash.
- Any manifest modification invalidates previous approval.
- `setuper audit` displays commands, hooks, file paths, network checks, secret references, and plugins.

## Command Execution

- Prefer argument arrays over shell strings.
- Shell execution requires explicit `shell: true` and a trust warning.
- Never concatenate untrusted values into shell commands.
- Environment inheritance uses an allowlist or explicit policy.
- Working directories must be validated.

## Secrets

Supported references:

- environment variable;
- macOS Keychain through `keyring`;
- approved `.env` file path.

Rules:

- Never capture secret values automatically.
- Never store secrets in SQLite or logs.
- Redact known values and common credential patterns.
- Warn when a manifest contains a probable literal secret.

## Process Safety

- Stop only owned and verified processes by default.
- Verify PID, executable, and process start time before signaling.
- Do not run Setuper as root.
- Reject paths that unexpectedly resolve outside an approved project root when policy requires confinement.

## Plugin Safety

- Plugins execute out of process.
- Plugin executable path and version appear in audit output.
- Untrusted plugins require explicit approval.
- Apply timeouts and output-size limits.
- Reject malformed protocol responses.

## Browser Privacy

- Capture URLs and grouping metadata only when the user grants permission.
- Do not capture cookies, form content, browsing history outside selected windows, or authentication tokens.
- Clearly show the extension permissions.

## Reporting

Create `SECURITY.md` at repository root with a private vulnerability reporting method before public release.
