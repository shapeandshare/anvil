# Session: Automated Semantic Versioning & Release

**Date**: 2026-06-14
**Feature**: 007-automated-semver-release

## What was implemented

- **Commitizen integration** (`pyproject.toml`): Added `[tool.commitizen]` config with `cz_conventional_commits`, semver, PEP 621 version provider, incremental changelog. Added `commitizen` to dev optional dependencies.
- **CHANGELOG.md**: Created at repository root with Conventional Commits header template.
- **Git hooks** (`.githooks/commit-msg`): Shell script that runs `cz check --commit-msg-file` to reject non-conventional commit messages with helpful error output. Enabled via `make setup-hooks`.
- **Release workflow** (`.github/workflows/release.yml`): Two-job workflow triggered on push to main. Job 1 detects version changes and determines bump type from conventional commit. Job 2 runs `cz bump`, creates an auto-merge bump PR (with `[skip ci]`), waits for merge, creates git tag and GitHub Release.
- **Auto-bump safety-net** (`.github/workflows/auto-bump.yml`): Separate workflow triggered on `anvil/**` file changes. Detects un-versioned source code pushes and auto-opens a patch-bump PR with changelog entry.
- **Secrets docs** (`docs/secrets.md`): Step-by-step BUMP_PAT creation and configuration guide.
- **Makefile target** (`setup-hooks`): Convenience target to configure `core.hooksPath` for the commit-msg hook.
- **Full Spec Kit artifacts**: spec, plan, research, data model, contracts, quickstart, tasks (31 tasks), and quality checklist — all at `docs/vault/Specs/010 Automated Semver Release/`.

## Key decisions

1. **Auto-merge PR pattern**: Bump commits go through a PR (not direct push) to respect branch protection and avoid re-triggering the release workflow. Pattern adapted from `oldgrowth/.github/workflows/release.yml`.
2. **`[skip ci]` in bump commits**: Prevents infinite workflow loops. Both the release workflow and auto-bump workflow include this in every automated commit.
3. **Pyproject.toml-based commitizen config**: Uses PEP 621 `version_provider` to read version from `[project].version` — no separate `.cz.toml` file. Follows patterns from `concourse/pyproject.toml` and `mlx-lm-server/pyproject.toml`.
4. **BUMP_PAT for PR creation**: Fine-grained PAT required because PRs opened by `GITHUB_TOKEN` don't trigger CI checks under branch protection. Both workflows fail early with diagnostic messages if `BUMP_PAT` is missing.
5. **Safety-net auto-bump (P3)**: Lower priority but prevents version drift from edge cases (direct pushes, workflow suppression). Pattern adapted from `oldgrowth/.github/workflows/auto-bump.yml`.
6. **Conventional commit → bump type mapping**: `fix` → PATCH, `feat` → MINOR, `BREAKING CHANGE` or `!` → MAJOR, `chore/docs/ci/test/etc.` → NONE (no bump, changelog only).

## Reference patterns used

- `~/Workbench/Repositories/oldgrowth/.cz.toml` — Commitizen TOML config structure
- `~/Workbench/Repositories/oldgrowth/.github/workflows/release.yml` — Version detection, changelog extraction, `gh release create` pattern
- `~/Workbench/Repositories/oldgrowth/.github/workflows/auto-bump.yml` — Safety-net auto-bump with changelog insertion
- `~/Workbench/Repositories/oldgrowth/CHANGELOG.md` — Conventional Commits changelog format
- `~/Workbench/Repositories/concourse/pyproject.toml` — Python `[tool.commitizen]` PEP 621 integration

## Files changed

- `pyproject.toml` (commitizen config + dev dep)
- `CHANGELOG.md` (new — header template)
- `.githooks/commit-msg` (new — commit enforcement hook)
- `Makefile` (added `setup-hooks` target)
- `.github/workflows/release.yml` (new — 427 lines)
- `.github/workflows/auto-bump.yml` (new — 147 lines)
- `docs/secrets.md` (new — BUMP_PAT guide)
- `AGENTS.md` (updated — new technologies)
- `docs/vault/Specs/010 Automated Semver Release/` (20 artifacts across 7 phases)