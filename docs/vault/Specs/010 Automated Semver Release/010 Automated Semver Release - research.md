---
title: 010 Automated Semver Release - research
type: research
tags:
  - type/spec
spec-refs:
  - docs/vault/Specs/010 Automated Semver Release/
related:
  - '[[010 Automated Semver Release]]'
created: ~
updated: ~
---
# Research: Automated Semantic Versioning & Release Patterns

**Created**: 2026-06-14  
**Source**: Reference implementations in `~/Workbench/Repositories/` and official tool documentation

## 1. Commitizen Configuration

### Decision
Use **pyproject.toml-based `[tool.commitizen]`** (PEP 621 style), matching Python ecosystem conventions.

### Rationale
- The anvil project already uses `pyproject.toml` for all tooling config (ruff, black, isort, mypy, pytest, coverage)
- PEP 621 `version_provider = "pep621"` reads version directly from `[project].version` — no duplication
- Avoids introducing a separate `.cz.toml` file (reduces config surface area)

### Reference
- `~/Workbench/Repositories/concourse/pyproject.toml` — `[tool.commitizen]` with `version_provider = "pep621"`
- `~/Workbench/Repositories/mlx-lm-server/pyproject.toml` — Same pattern, with `tag_format = "v$version"`
- `~/Workbench/Repositories/oldgrowth/.cz.toml` — Separate `.cz.toml` (Godot project — different ecosystem)

### Key Config Values

```toml
[tool.commitizen]
name = "cz_conventional_commits"
version_scheme = "semver"
tag_format = "v$version"
version_provider = "pep621"
update_changelog_on_bump = true
changelog_incremental = true
changelog_file = "CHANGELOG.md"
```

## 2. Release Workflow Pattern

### Decision
Use the **auto-merge PR pattern** (not direct push) for getting version bumps back to main.

### Rationale
- Direct push to main fails if branch protection is enabled (common in mature repos)
- Direct push re-triggers the push-based release workflow (infinite loop)
- Auto-merge PR satisfies branch protection rules (CI checks run on the PR)
- `[skip ci]` in the bump commit message prevents the auto-merge from re-triggering
- Pattern proven in `oldgrowth/release.yml` and `oldgrowth/auto-bump.yml`

### Workflow Flow
```
PR merged to main (squash, conventional title)
  → Release workflow triggers (push to main)
  → Job 1: Check if version changed vs parent commit
  → Job 2: If changed:
      1. Determine bump type from conventional commit (fix→patch, feat→minor, BREAKING→major)
      2. Run `cz bump --changelog --increment {MAJOR|MINOR|PATCH}`
      3. Create a branch with the bump commit ([skip ci])
      4. Open PR via `gh pr create` (using BUMP_PAT)
      5. Auto-merge via `gh pr merge --auto --squash`
      6. Create tag `vX.Y.Z`
      7. Create GitHub Release via `gh release create` with changelog extraction
  → Job 2: If not changed (chore/docs/etc.):
      - Log warning, skip release
```

### Key Implementation Details

**Version extraction from pyproject.toml:**
```bash
grep '^version =' pyproject.toml | sed 's/version = "\(.*\)"/\1/'
```

**Version comparison with parent commit:**
```bash
git show HEAD^:pyproject.toml | grep '^version =' | sed 's/version = "\(.*\)"/\1/' || echo "none"
```

**Conventional commit type detection from merge message:**
```bash
MERGE_MSG=$(git log -1 --format=%B)
if echo "$MERGE_MSG" | grep -qi "BREAKING CHANGE"; then
  INCREMENT="MAJOR"
elif echo "$MERGE_MSG" | grep -q "^feat"; then
  INCREMENT="MINOR"
elif echo "$MERGE_MSG" | grep -q "^fix"; then
  INCREMENT="PATCH"
else
  INCREMENT="NONE"  # no version bump
fi
```

**Changelog extraction for release notes:**
```bash
awk "/^## \[${VERSION}\]/,/^## \[/" CHANGELOG.md | grep -v "^## \["
```

**PR description fetch:**
```bash
gh pr list --state merged --head "$BRANCH" --json body --jq '.[0].body'
```

**Release creation:**
```bash
gh release create "v${VERSION}" --title "v${VERSION}" --notes-file release-notes.md
```

## 3. Token Strategy

### Decision
- **`GITHUB_TOKEN`** (built-in): checkout, tag push, `gh release create`
- **`BUMP_PAT`** (fine-grained PAT): `gh pr create`, `gh pr merge` (PRs opened by GITHUB_TOKEN don't trigger CI checks)

### BUMP_PAT Required Permissions
- Contents: write
- Pull requests: write
- Workflows: write

### Rationale
GitHub has a known limitation: PRs opened by the built-in `GITHUB_TOKEN` do not trigger CI checks, making them unmergeable under branch protection rules. A fine-grained PAT bypasses this because it acts as a real user.

### Reference
- `oldgrowth/release.yml` — Uses BUMP_PAT for PR creation/auto-merge (lines 323–372)
- `oldgrowth/auto-bump.yml` — Same pattern (lines 86–148)

## 4. Auto-Bump Safety-Net Pattern

### Decision
Add a separate auto-bump workflow as a safety-net for edge cases (direct pushes, workflow suppression).

### Rationale
- Catches code pushed to main without a version bump
- Handles edge cases where the release workflow is suppressed (merge commits touching `.github/workflows/`)
- Proven in `oldgrowth/auto-bump.yml`

### Trigger
```yaml
on:
  push:
    branches: [main]
    paths:
      - 'anvil/**'
      - '!CHANGELOG.md'
      - '!.github/**'
```

### Behavior
1. Check if version in `pyproject.toml` changed vs parent commit
2. If not changed → open a patch-bump PR
3. PR created via BUMP_PAT (so CI triggers on the PR)
4. Auto-merge the PR

## 5. Infinite Loop Prevention

### Decision
Use `[skip ci]` in bump commit messages to prevent the auto-merged bump commit from re-triggering the release workflow.

### Rationale
Without `[skip ci]`, the bump commit's push to main triggers the `push` event again, creating an infinite loop. GitHub Actions honors `[skip ci]` in commit messages.

### Reference
Standard GitHub Actions convention — no special configuration needed beyond including `[skip ci]` in the commit message body.

## 6. Alternatives Considered

| Alternative | Rejected Because |
|-------------|-----------------|
| **Direct push** | Fails under branch protection; creates infinite loop without `[skip ci]` (and `[skip ci]` combined with direct push is fragile) |
| **Pre-merge bump convention** | Requires developers to manually bump versions in every PR — error-prone, inconsistent |
| **semantic-release tool** | Node.js dependency in a Python project; more complex than commitizen for Python |
| **Manual tagging** | Defeats the purpose of automation; error-prone |