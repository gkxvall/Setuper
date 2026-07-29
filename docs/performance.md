# Performance

## Targets

- Common informational commands should feel immediate.
- Capture should stream findings instead of appearing frozen.
- Independent resources should launch concurrently.
- Setuper should add negligible overhead after handing execution to external tools.

## Budgets

- `setuper --help`: under 300 ms target.
- `setuper list`: under 500 ms for 1,000 setup records.
- Manifest parsing: under 100 ms for 1,000 resources.
- Graph construction: linear relative to nodes and edges.
- Database writes: batched where safe.

## Optimization Rules

- Measure before optimizing.
- Avoid scanning the entire filesystem.
- Bound process inspection and network retries.
- Cache immutable adapter capability discovery per command invocation.
- Use concurrency for independent readiness checks.
- Avoid polling faster than necessary.
- Stream subprocess logs rather than retaining unlimited output in memory.

## Resource Limits

Configurable defaults:

- Maximum concurrent launches: 4.
- Maximum retained in-memory log lines per resource: 1,000.
- Readiness poll interval: 250–500 ms with backoff.
- Default resource timeout: 60 seconds.
- Graceful stop timeout: 10 seconds.

## Benchmarks

Add benchmarks for:

- Large manifest validation.
- Dependency graph scheduling.
- SQLite launch-event ingestion.
- Secret redaction.
- Process matching and stale PID validation.

Performance regressions above 20% require investigation before release.
