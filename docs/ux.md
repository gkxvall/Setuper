# User Experience

## First-Run Experience

Running `setuper` without arguments should show a concise introduction and examples. Running `setuper doctor` should identify missing permissions and integrations.

Recommended first-run flow:

```bash
setuper doctor
setuper inspect
setuper save my-workspace --dry-run
setuper save my-workspace
setuper show my-workspace
setuper launch my-workspace
```

## Experience Principles

- Make the safe path the easiest path.
- Explain limitations honestly.
- Preserve user control over commands and secrets.
- Never silently kill unrelated processes.
- Give actionable errors with the exact command to fix the issue.
- Prefer recoverable partial results over all-or-nothing behavior.

## Capture UX

`save` should:

1. Detect supported resources.
2. Show unsupported or sensitive findings.
3. Ask for confirmation for terminal commands and sensitive metadata.
4. Generate a readable manifest.
5. Open an optional review step.

The user must understand that Setuper reconstructs a setup rather than freezing process memory.

## Launch UX

Before executing, Setuper should clearly report:

- Missing applications.
- Missing directories.
- Dirty Git repositories.
- Untrusted commands.
- Port conflicts.
- Required permissions.
- Resources that cannot be restored.

When possible, errors should provide choices such as reuse, stop, change port, skip, or cancel.

## Failure Recovery

A failed resource should show:

- What failed.
- Why it failed.
- Which dependents were blocked.
- Relevant log command.
- A suggested corrective action.

Example:

```text
FAILED frontend — port 3000 is used by PID 9214
Run `setuper launch ansade --profile alternate-ports`
or stop the conflicting process and retry.
```

## Accessibility

- Do not rely only on color.
- Support plain text.
- Avoid excessive animation.
- Keep output compatible with screen readers where practical.
- Use predictable labels and ordering.
