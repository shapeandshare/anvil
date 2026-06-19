# Contributing to anvil

## Development Setup

```bash
make setup   # Creates venv, installs deps, runs migrations
```

## Commands

| Command | Purpose |
|---------|---------|
| `make test` | Run tests (with coverage; must meet `fail_under` in `pyproject.toml`) |
| `make lint` | Run ruff → black --check → isort --check → pylint |
| `make format` | Auto-format with black + isort |
| `make typecheck` | Run mypy (strict) |
| `make vault-audit` | Run vault audit (frontmatter, wikilinks, vocabulary, ADR uniqueness) |
| `make adr-check` | Validate ADR naming conventions and identifier uniqueness |
| `make guarded-imports-check` | Validate TYPE_CHECKING imports are annotation-only |

## Commit Conventions

Follow [Conventional Commits](https://www.conventionalcommits.org/):

- `feat: add dataset upload endpoint`
- `fix: correct SSE reconnection handling`
- `docs: update README with new routes`
- `test: add experiment comparison tests`

## Pull Request Process

1. All gates (`make lint`, `make typecheck`, `make test`, `make vault-audit`) must pass
2. Coverage must meet the ratcheting baseline (`fail_under` in `pyproject.toml`)
3. ADRs must have unique, sequential identifiers (enforced by `make adr-check`)
4. TYPE_CHECKING imports must be annotation-only (enforced by `make guarded-imports-check`)
5. ADR required for significant architecture decisions

### Branch protection

The `main` branch requires the CI workflow to pass before merge. The workflow runs five gates:
- **Bump-scope guard**: classifies PRs as version-only or full-source. Version-only bumps (pyproject version line + CHANGELOG) skip the heavy gates to keep automated releases fast.
- **Lint**, **Type Check**, **Test**, **Vault Audit**: required for every source-code change.

If a gate fails, the CI check shows red, logs the specific failure, and blocks merge. If the CI infrastructure fails (timeout, outage), merge is also blocked (fail-closed). This protects against regression while keeping the automated release pipeline flowing.