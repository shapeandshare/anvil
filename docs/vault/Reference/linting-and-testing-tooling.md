---
title: 'Linting, Formatting, and Testing Tooling'
type: reference
status: draft
source: agent
tags:
  - type/reference
  - domain/tooling
  - status/draft
aliases:
  - Linting and Testing Tooling
  - Tooling Reference
code-refs:
  - pyproject.toml
  - shared/python.mk
  - shared/testing.mk
  - shared/vault.mk
  - .githooks/pre-commit
  - .githooks/commit-msg
  - .github/workflows/ci.yml
  - Makefile
session: 2026-06-21-linting-testing-hooks-tooling
created: '2026-06-21'
updated: '2026-06-21'
---
# Linting, Formatting, and Testing Tooling

Comprehensive reference for the quality tooling configured in the anvil project. All tools are installed via `uv sync --extra dev` and runnable through `make` targets.

## Quick Start

```bash
make setup          # Install everything (dev deps included)
make setup-hooks    # Install git hooks (pre-commit + commit-msg)
make pr-ready       # Run all checks before pushing/opening a PR
```

## Linting Pipeline (`make lint`)

Runs in order. Fails fast on the first error.

| Step | Tool | Config | What It Checks |
|------|------|--------|----------------|
| 1 | `ruff check .` | `pyproject.toml` [tool.ruff.lint] | Pycodestyle errors (E4/E7/E9), Pyflakes (F), Bugbear (B), comprehensions (C4), pyupgrade (UP), async (ASYNC), ruff-specific (RUF), numpy pydocstyle (D) |
| 2 | `black --check .` | `pyproject.toml` [tool.black] | Line length 88, py311 target, double quotes |
| 3 | `isort --check .` | `pyproject.toml` [tool.isort] | Import ordering (black profile), first-party `anvil` |
| 4 | `pylint anvil/ --disable=R,C` | `pyproject.toml` [tool.pylint] | Additional static analysis (convention refactor warnings disabled) |
| 5 | grep `@dataclass` | inline in Makefile | Disallowed pattern — must use Pydantic `BaseModel` |

## Formatting (`make format`)

Applies auto-fixes in-place.

| Step | Tool | What It Fixes |
|------|------|---------------|
| 1 | `black .` | Code formatting (line breaks, spacing, quotes) |
| 2 | `isort .` | Import ordering |

## Type Checking (`make typecheck`)

| Step | Tool | Config | Notes |
|------|------|--------|-------|
| 1 | `mypy anvil/` | `pyproject.toml` [tool.mypy] | Strict mode. Two modules suppressed for MLflow stub issues. |

## Testing (`make test`)

| Target | What It Runs | Coverage |
|--------|-------------|----------|
| `make test` | Unit tests in two batches (sequential) | `--cov=anvil --cov-branch`, min 23% (`fail_under`) |
| `make test-e2e` | `tests/e2e/` HTTP API tests | No coverage |
| `make test-e2e-seed` | Train demo model (prerequisite for inference E2E) | — |
| `make test-e2e-full` | Seed + full E2E API suite | — |
| `make test-system` | Docker container system tests | — |
| `make test-browser` | Playwright browser smoke tests | — |

## Pre-PR Validation (`make pr-ready`)

```bash
make pr-ready
```

Chains: **format → lint → typecheck**. This is the same sequence the CI `ci.yml` workflow runs (plus the CI also runs `make test` and SonarCloud scan).

The pre-commit hook (`.githooks/pre-commit`) runs `make pr-ready` on every commit. Bypass with `git commit --no-verify`.

## Git Hooks

| Hook | File | What It Enforces | Installed By |
|------|------|------------------|-------------|
| pre-commit | `.githooks/pre-commit` | `make pr-ready` (format → lint → typecheck) | `make setup-hooks` |
| commit-msg | `.githooks/commit-msg` | Conventional Commits format via commitizen | `make setup-hooks` |

## CI Pipeline (`ci.yml`)

Triggered on: every PR (pull_request) and every push to non-main branches.

| Job | Runs | Gate Type |
|-----|------|-----------|
| bump-scope-guard | Classifies change scope (version-only skips heavy gates) | Classification |
| format | `make format` + commits back to PR branch | Auto-fix |
| lint | `make lint` | Required |
| typecheck | `make typecheck` | Required |
| test | `make test` with coverage | Required (23% min) |
| sonar-scan | SonarCloud static analysis + coverage | Required |
| vault-audit | `make vault-audit` | Required |
| browser-smoke | `make test-browser` with Playwright | Non-blocking (`continue-on-error: true`) |

The auto-format job (`format`) runs `make format` and auto-commits formatting fixes back to the PR branch with `[skip ci]`. This only works for same-repo PRs; fork PRs see a `lint` failure instead.

## Configuration Files

| File | Configures |
|------|-----------|
| `pyproject.toml` | ruff, black, isort, pylint, mypy, pytest, coverage, commitizen |
| `shared/python.mk` | `make` targets for format, lint, typecheck, build |
| `shared/testing.mk` | `make` targets for test, test-e2e, test-e2e-full |
| `shared/vault.mk` | `make` targets for vault-audit, adr-check, guarded-imports-check |
| `.githooks/pre-commit` | Pre-commit check script |
| `.githooks/commit-msg` | Commit message validation script |
| `.github/workflows/ci.yml` | CI workflow definition |

## Tool Versions

All version-pinned in `pyproject.toml [project.optional-dependencies] dev`:

| Tool | Version Constraint |
|------|-------------------|
| ruff | `>=0.5,<1` |
| black | `>=24.0,<25` |
| isort | `>=5.13,<6` |
| pylint | `>=3.2,<4` |
| mypy | `>=1.10,<2` |
| pytest | `>=8.0,<9` |
| pytest-cov | `>=5.0,<6` |
| commitizen | `>=3.0,<4` |

## See Also

- [[Reference/ArchitectureOverview|Architecture Overview]]
