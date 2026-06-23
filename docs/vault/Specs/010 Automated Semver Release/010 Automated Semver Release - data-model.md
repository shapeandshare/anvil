---
title: 010 Automated Semver Release - data-model
type: data-model
tags:
  - type/spec
spec-refs:
  - docs/vault/Specs/010 Automated Semver Release/
related:
  - '[[010 Automated Semver Release]]'
created: ~
updated: ~
---
# Data Model: Automated Semantic Versioning & Release

**Created**: 2026-06-14  
**Source**: [spec.md](spec.md) entities section and [research.md](research.md)

## Entity Relationship Diagram (Conceptual)

```
pyproject.toml (version)
      │
      │ reads/writes
      ▼
┌─────────────┐     bump creates      ┌──────────────┐
│  Version     │ ──────────────────▶   │  Git Tag     │
│  (X.Y.Z)    │                       │  (vX.Y.Z)    │
└─────────────┘                       └──────┬───────┘
      │                                      │
      │ writes to (via cz bump)              │ triggers
      ▼                                      ▼
┌─────────────┐                       ┌──────────────┐
│ CHANGELOG   │                       │  GitHub      │
│ .md         │ ◀──── includes ─────▶ │  Release     │
│ (entry per   │                       │  (vX.Y.Z)    │
│  version)   │                       └──────────────┘
└─────────────┘
      ▲                                      ▲
      │ includes PR body                     │ uses release
      │                                      │ notes from
┌─────────────┐                              │
│ PR Metadata │ ─────────────────────────────┘
│ (title +    │
│  body)      │
└─────────────┘
```

## Entities

### 1. Version String

| Attribute | Type | Description |
|-----------|------|-------------|
| `major` | integer | Breaking changes (MAJOR bump) |
| `minor` | integer | New features (MINOR bump) |
| `patch` | integer | Bug fixes (PATCH bump) |
| `source` | string | File: `pyproject.toml`, field: `[project].version` |
| `format` | string | `"X.Y.Z"` (semver, no leading `v`) |

**Validation Rules:**
- MUST follow semver 2.0.0 (`MAJOR.MINOR.PATCH`)
- MUST be stored in `pyproject.toml` under `[project].version` (PEP 621)
- Pre-release labels (e.g., `-alpha.1`) NOT supported for this feature (out of scope)
- BUILD metadata (e.g., `+build.123`) NOT supported for this feature (out of scope)

**State Transitions:**
```
X.Y.Z → (bump patch) → X.Y.(Z+1)
X.Y.Z → (bump minor) → X.(Y+1).0
X.Y.Z → (bump major) → (X+1).0.0
```

### 2. Git Tag

| Attribute | Type | Description |
|-----------|------|-------------|
| `name` | string | Format: `vX.Y.Z` (e.g., `v0.2.0`) |
| `commit_sha` | string | The commit this tag points to |
| `type` | string | Lightweight tag (no annotation) |
| `created_by` | string | Release workflow (via `git tag`) |

**Validation Rules:**
- MUST be prefixed with `v` (e.g., `v0.2.0`, not `0.2.0`)
- MUST match the version in `pyproject.toml` at the tagged commit
- MUST be a lightweight tag (no `-a` flag)
- MUST be unique per version (collisions cause workflow failure)

### 3. CHANGELOG.md Entry

| Attribute | Type | Description |
|-----------|------|-------------|
| `version` | string | `vX.Y.Z` in header (`## [vX.Y.Z]`) |
| `date` | date | Release date in `YYYY-MM-DD` format |
| `sections` | list | Sections: `feat`, `fix`, `perf`, `refactor`, `chore`, `docs`, `ci`, `test`, `style`, `build` |
| `entries` | list | Bullet points per section, derived from merge commit messages |
| `file` | string | `CHANGELOG.md` at repository root |

**Format Convention:**
```markdown
## vX.Y.Z (YYYY-MM-DD)

### Feat

- **scope**: description of feature

### Fix

- **scope**: description of fix
```

**Validation Rules:**
- Newest entry MUST be at the top (reverse chronological)
- Each version section MUST be separated by `---`
- Sections with no entries SHOULD be omitted (not left empty)
- `changelog_incremental = true` in commitizen config — appends new entries without rewriting

### 4. GitHub Release

| Attribute | Type | Description |
|-----------|------|-------------|
| `tag_name` | string | `vX.Y.Z` — matches git tag |
| `name` | string | `vX.Y.Z` — release title |
| `body` | markdown | Release notes (changelog entry + PR description) |
| `draft` | boolean | `false` — published immediately |
| `prerelease` | boolean | `false` for this feature |
| `target_commitish` | string | `main` branch |

**Validation Rules:**
- MUST be created by the release workflow, not manually
- MUST reference an existing git tag
- Release notes MUST include the changelog entry for this version
- Release notes MUST include the PR description body (if non-empty)

### 5. PR Metadata

| Attribute | Type | Source |
|-----------|------|--------|
| `title` | string | PR title (becomes squash-merge commit message) |
| `body` | markdown | PR description (included in release notes) |
| `base_branch` | string | `main` |
| `merge_commit_sha` | string | The merge commit on main |

**Validation Rules:**
- PR title MUST follow conventional commit format (`type(scope): description`)
- PR body is optional but, if present, SHOULD be included in release notes
- Retrieved via `gh pr list --state merged --head <branch>` after merge

## State Machine: Release Workflow

```
┌──────────────┐
│ PR merged    │
│ to main      │
└──────┬───────┘
       │ push event
       ▼
┌──────────────┐     version changed?     ┌──────────────┐
│ Version      │ ──────── no ──────────▶  │ Skip Release │
│ Check        │                          │ (log warning)│
└──────┬───────┘                          └──────────────┘
       │ yes
       ▼
┌──────────────┐
│ Determine    │
│ Bump Type    │
│ (conventional│
│  commit)     │
└──────┬───────┘
       │
       ▼
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ cz bump      │────▶│ Create Bump  │────▶│ Auto-Merge   │
│ --changelog  │     │ PR ([skip    │     │ PR (squash)  │
│              │     │  ci])        │     │              │
└──────────────┘     └──────────────┘     └──────┬───────┘
                                                 │
                                                 ▼
                                        ┌──────────────┐
                                        │ git tag      │
                                        │ vX.Y.Z       │
                                        └──────┬───────┘
                                               │
                                               ▼
                                        ┌──────────────┐
                                        │ gh release   │
                                        │ create       │
                                        └──────────────┘
```

## Configuration Files

| File | Format | Purpose | New/Modified |
|------|--------|---------|-------------|
| `pyproject.toml` | TOML | Version source + commitizen config + dev dependency | Modified |
| `CHANGELOG.md` | Markdown | Release changelog | New |
| `.github/workflows/release.yml` | YAML | Automated release on merge to main | New |
| `.github/workflows/auto-bump.yml` | YAML | Safety-net auto-bump | New |