# State Management

## State Categories

### Definition state

Stored in YAML manifests. This is the desired setup.

### Runtime state

Stored in SQLite. This includes launch IDs, resource statuses, PIDs, external IDs, and timestamps.

### Ephemeral state

Held in memory during capture and launch, such as graph queues, readiness timers, and streaming logs.

### User configuration

Stored in a user configuration file using platform-standard directories.

## State Machine

Resource run states:

```text
pending -> validating -> starting -> running -> ready
                       -> skipped
                       -> failed
ready -> stopping -> stopped
```

A blocked dependent uses `blocked` and records the failed dependency.

Launch states:

```text
starting -> running -> stopped
         -> partial
         -> failed
```

## Consistency Rules

- Persist launch record before starting resources.
- Persist a resource run before invoking its adapter.
- Update state after each meaningful transition.
- Use transactions for related state changes.
- On startup, reconcile stale `starting` and `running` records against the operating system.
- Never assume a persisted PID still represents the same process; verify executable and start time.

## Configuration Loading

Use immutable validated settings objects. Merge layers in documented precedence order.

## Event Flow

Services emit structured internal events. Renderers and persistence subscribe through explicit interfaces; the domain does not depend on terminal output.

## Idempotency

A launch checks whether each resource already satisfies its desired state. It then:

- reuses a matching resource;
- starts a missing resource;
- reports a conflict;
- or restarts only when the manifest policy allows it.
