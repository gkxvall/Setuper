# Contributing to Setuper

Thank you for helping build Setuper. The project is developed in small,
reviewable changes against the specifications under [`docs/`](docs/).

## Before you start

1. Read the [product specification](docs/specs.md), [architecture](docs/architecture.md),
   [security rules](docs/security.md), and [coding standards](docs/coding-standards.md).
2. Check the ordered [task plan](docs/tasks.md).
3. Discuss changes that alter the CLI, manifest schema, plugin protocol, security
   model, or architecture before implementing them.

## Development environment

Use Python 3.12 or 3.13.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --editable '.[dev]'
```

## Making a change

- Keep domain code independent of the CLI, infrastructure, and concrete adapters.
- Use typed interfaces and inject system-facing dependencies.
- Never use `shell=True` with untrusted input or include secrets in fixtures,
  logs, manifests, commits, or issue reports.
- Add focused tests with each behavior change.
- Update documentation when public behavior or architecture changes.
- Keep commits to the smallest coherent change and use Conventional Commit
  messages such as `feat(manifest): validate resource identifiers`.

## Required checks

Run the narrowest relevant tests first, followed by:

```bash
ruff check .
ruff format --check .
mypy src
pytest -q
```

Review the final diff for accidental files, credentials, unsafe subprocess use,
and unrelated changes before committing.

Report vulnerabilities privately according to the
[security policy](SECURITY.md), never in a public issue.

## Pull requests

Explain the user-visible outcome, the tests run, and any honest platform
limitations. A pull request is ready only when required checks pass and its
commits remain independently understandable.
