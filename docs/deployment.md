# Deployment and Distribution

## Distribution Targets

v1.0.0 should be installable through:

1. PyPI using `pipx install setuper`.
2. A Homebrew tap for macOS.
3. GitHub release artifacts and checksums.

## Packaging

- Use `pyproject.toml`.
- Expose the console script `setuper`.
- Build source distribution and wheel.
- Include schema files and migrations as package data.
- Keep optional browser extension artifacts separately versioned when necessary.

## CI/CD

### Pull request workflow

- Lint.
- Format check.
- Type check.
- Unit and integration tests.
- Build package.

### Main branch workflow

- Run the full suite on supported Python versions.
- Generate coverage.
- Validate documentation links.

### Release workflow

Triggered by an annotated tag such as `v1.0.0`:

1. Verify clean main branch.
2. Run all checks.
3. Build artifacts.
4. Generate checksums and SBOM if practical.
5. Publish GitHub release.
6. Publish to PyPI using trusted publishing.
7. Update Homebrew formula.

## Versioning

Use Semantic Versioning.

- Patch: backward-compatible fixes.
- Minor: backward-compatible features.
- Major: breaking CLI, manifest, or plugin changes.

## Release Checklist

- Version updated in one source of truth.
- Changelog updated.
- Migrations tested from previous release.
- Fresh install tested.
- Upgrade tested.
- Browser integration compatibility tested.
- Security audit completed.
- Documentation matches actual commands.
