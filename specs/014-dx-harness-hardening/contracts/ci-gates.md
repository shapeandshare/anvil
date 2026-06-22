# Contract: CI Gate Suite

This contract defines the automated enforcement interface (GitHub Actions + branch protection). It is verifiable by triggering deliberate-failure and happy-path pull requests.

## Workflow trigger contract

| Property | Value |
|---|---|
| Workflow | `.github/workflows/ci.yml` |
| Triggers | `pull_request` (all PRs into `main`); `push` to branches other than `main` |
| Runner | `ubuntu-latest`, Python 3.11 via `uv` |
| Concurrency | Cancel-in-progress per ref allowed (latest commit wins) |

## Required jobs / gates

Each job runs the **same command a developer runs locally** (parity requirement FR-005).

| Job | Command | Pass condition |
|---|---|---|
| `lint` | `make lint` | ruff + black --check + isort --check + pylint all exit 0 |
| `typecheck` | `make typecheck` | `mypy --strict` exits 0 |
| `test` | `make test` | pytest exits 0 **and** coverage ≥ `fail_under` |
| `vault-audit` | `make vault-audit` | 0 errors (frontmatter, wikilinks, vocabulary, ADR-uniqueness) |
| `guarded-imports` | `python scripts/ci/check_guarded_imports.py` | 0 guarded symbols used in runtime code |
| `bump-scope-guard` | `python scripts/ci/check_bump_scope.py` | classifies PR as version-only-bump or full (always passes; gates the exemption) |

## Behavioral contract

1. **Block on failure** (FR-003): if any required job fails, the PR check status is `failure` and branch protection prevents merge into `main`.
2. **Pre-merge** (FR-002): jobs run on the PR head before merge, not only post-merge.
3. **Actionable output** (FR-004): a failing job's logs name the specific gate and the offending file(s)/rule(s).
4. **Fail-closed** (FR-006): if the workflow cannot complete (infra error, cancelled, timeout), the check is not `success`, so merge stays blocked. No path sets `success` without the gates running.
5. **Bump exemption** (FR-006a):
   - `bump-scope-guard` computes `changed_files`.
   - If `changed_files ⊆ {pyproject.toml version line, CHANGELOG.md}` → heavy gates (`lint`/`typecheck`/`test`) may be marked skipped/neutral for that PR; the guard itself remains a required, passing check.
   - Otherwise → all heavy gates are required and run, regardless of PR author (human/agent/bot).
   - The exemption MUST NOT pass any PR containing a source/test diff.

## Acceptance tests (verification)

| # | Given | When | Then |
|---|---|---|---|
| C1 | A PR introducing a lint error | CI runs | `lint` fails; merge blocked; log names the rule/file |
| C2 | A PR introducing a `mypy` error | CI runs | `typecheck` fails; merge blocked |
| C3 | A PR dropping coverage below `fail_under` | CI runs | `test` fails on coverage; merge blocked |
| C4 | A PR with a broken wikilink in a vault note | CI runs | `vault-audit` fails; merge blocked |
| C5 | A PR adding a guarded import used in runtime code | CI runs | `guarded-imports` fails; merge blocked |
| C6 | A clean PR (all gates green) | CI runs | all checks `success`; merge allowed |
| C7 | A bot PR touching only version + changelog | CI runs | `bump-scope-guard` passes; heavy gates skipped; merge allowed |
| C8 | A PR touching version + changelog **and** a source file | CI runs | full gate suite required and runs |
| C9 | Workflow infra failure / timeout | CI runs | check is not `success`; merge stays blocked |
