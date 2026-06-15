# ADR-008: Automated Semantic Versioning & Release

**Date**: 2026-06-14  
**Status**: Accepted  
**Deciders**: anvil contributors  

## Context

The anvil project had no automated release process. Versions were static at `0.1.0`, there was no changelog, no release tagging, and no CI/CD pipeline for version management. Every release would require manual version bumps, changelog editing, and GitHub Release creation.

## Decision

We adopted a four-component automated semantic versioning system:

### 1. Commitizen Configuration (Python ecosystem native)
Commitizen is configured via `[tool.commitizen]` in `pyproject.toml` using PEP 621 `version_provider` (reads version from `[project].version`). This avoids a separate config file. Config: `cz_conventional_commits` backend, semver scheme, `v$version` tag format, incremental changelog.

### 2. Auto-Merge PR Pattern (not direct push)
Version bump commits are delivered via an auto-merge PR rather than direct push to main. This:
- Respects branch protection rules (CI checks run on the PR)
- Avoids re-triggering the release workflow (bump commit includes `[skip ci]`)
- Uses `BUMP_PAT` (fine-grained PAT) for PR creation because `GITHUB_TOKEN` PRs don't trigger CI under branch protection

### 3. Release Workflow (triggered on merge to main)
On push to main, the workflow:
1. Checks if the version in `pyproject.toml` changed vs parent commit
2. Determines bump level from conventional commit type (`fix`→PATCH, `feat`→MINOR, `BREAKING CHANGE`→MAJOR)
3. Runs `cz bump --changelog` to update version and changelog
4. Creates a bump PR with `[skip ci]` and auto-merges
5. Creates git tag `vX.Y.Z` and GitHub Release with changelog + PR description

### 4. Safety-Net Auto-Bump
A separate workflow detects source code pushed to main without a version bump and auto-opens a patch-bump PR. Triggered only on `anvil/**` paths (excludes CHANGELOG.md and .github/).

## Consequences

- Every PR merged to main with a conventional commit title produces a version bump, changelog entry, tag, and GitHub Release within minutes
- CHANGELOG.md is always up-to-date without manual editing
- A `BUMP_PAT` secret must be configured in GitHub repository settings (documented in `docs/secrets.md`)
- Local commit-msg hook enforces conventional commit format (enabled via `make setup-hooks`)
- No PyPI publishing — out of scope for this feature

## Alternatives considered

- **Direct push for bump commits**: Rejected — fails under branch protection; creates infinite workflow loop without `[skip ci]` which is fragile
- **Pre-merge bump convention** (developers bump versions in every PR): Rejected — error-prone, inconsistent
- **semantic-release tool**: Rejected — Node.js dependency in a Python project
- **Separate .cz.toml file**: Rejected — PEP 621 integration with existing pyproject.toml is cleaner for Python projects
- **Manual tagging**: Rejected — defeats purpose of automation

## Compliance

- `cz bump --dry-run --increment patch` exits 0 (verified)
- `cz check --commit-msg-file` rejects invalid commit messages (verified)
- All YAML workflow files parse as valid YAML (verified)
- Agentic checklist: 15/15 items pass (verified)
- All 31 implementation tasks completed and marked `[X]`