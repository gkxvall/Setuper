# Terminal UI

## Direction

Setuper is a CLI, so its UI is terminal-first. The interface must remain clear in both rich interactive terminals and plain CI output.

## Visual Rules

- Use color to reinforce meaning, never as the only signal.
- Respect `NO_COLOR` and non-TTY output.
- Use concise headings and stable column order.
- Use icons only when Unicode is supported.
- Never hide failures behind animation.
- Long-running operations show resource-level progress.

## Status Vocabulary

- `READY`
- `RUNNING`
- `REUSED`
- `SKIPPED`
- `BLOCKED`
- `FAILED`
- `STOPPED`
- `UNSUPPORTED`

## Main Screens

### `setuper list`

```text
NAME                 RESOURCES  LAST LAUNCHED        STATUS
ansade-development   6          2026-07-28 22:14     stopped
portfolio            4          2026-07-27 16:02     running
```

### `setuper inspect`

Group findings by category and show capture support.

```text
Applications
  READY  VS Code — ~/Projects/ANSADE-data-portal
  READY  Google Chrome — 8 tabs
  PART   Terminal — 3 windows; commands require confirmation

Services
  READY  Docker Compose — postgres, redis
  READY  Port 3000 — node
```

### `setuper launch`

```text
Launching ansade-development

READY   postgres      TCP 127.0.0.1:5432
READY   frontend      HTTP 200 in 3.2s
READY   editor        opened 1 project
READY   browser       opened 2 tabs

4 ready, 0 reused, 0 skipped, 0 failed
```

## Prompts

Prompts must default to the safe option.

```text
This imported setup contains 4 executable commands.
Review with `setuper audit ansade` before trusting.
Trust and launch now? [y/N]
```

Destructive commands require confirmation unless `--yes` is passed.

## JSON and Plain Modes

- `--json`: no Rich layout, no prompts unless explicitly allowed.
- `--no-color`: disable ANSI colors.
- Piped output automatically uses stable plain text.
