# ADR-008: Automated Semantic Versioning & Release

**Date**: 2026-06-14  
**Status**: Accepted  
**Updated**: 2026-07-18  

**Deciders**: anvil contributors  

## Context

The anvil project had no automated release process. Versions were static at `0.1.0`, there was no changelog, no release tagging, and no CI/CD pipeline for version management. Every release would require manual version bumps, changelog editing, and GitHub Release creation.

## Decision

We adopted an automated semantic versioning system built on commitizen:

### 1. Commitizen Configuration (Python ecosystem native)
Commitizen is configured via `[tool.commitizen]` in `pyproject.toml` using PEP 621 `version_provider` (reads version from `[project].version`). This avoids a separate config file. Config: `cz_conventional_commits` backend, semver scheme, `v$version` tag format, incremental changelog. `commitizen >=4,<5` is a dev dependency.

### 2. Auto-Merge PR Pattern (not direct push)
Version bump commits are delivered via an auto-merge PR rather than direct push to main. This:
- Respects branch protection rules (CI checks run on the PR)
- The workflow path filter (`anvil/**` excluding `CHANGELOG.md` and `.github/`) prevents the bump commit from re-triggering the release workflow
- Uses `BUMP_PAT` (fine-grained PAT) for PR creation because `GITHUB_TOKEN` PRs don't trigger CI under branch protection

### 3. Release Workflow (triggered on merge to main)
Triggered by pushes to main with changes under `anvil/**`:

1. **Detect** — `anvil-vault detect-increment` classifies the merge commit:
   - `AUTO` — conventional commit detected; let commitizen determine MAJOR/MINOR/PATCH
   - `PATCH` — forced for `workflow_dispatch` manual triggers
   - `SKIP` — version was already manually bumped; skip bump step but still tag/release
   - `NONE` — no relevant conventional commit; skip release entirely
2. **Bump** — `cz bump --changelog --yes` updates `pyproject.toml`, generates changelog from parsed commits, creates a git commit
3. **Tag delete** — the local tag created by `cz bump` is deleted (the tag will be re-created on `main` after the PR merges)
4. **PR** — a bump PR is created on `ci/bump-v<version>` with auto-merge
5. **Release** — after the bump PR merges: git tag `vX.Y.Z` + GitHub Release with changelog-derived notes

## Implementation Evolution

The original implementation (2026-06-14) used custom Python modules (`bump_version.py`, `build_notes.py`, `detect_increment.py`, `version_utils.py`, `check_version.py`) that duplicated commitizen's functionality. The version classification was done by a custom `classify_increment()` function, and changelog entries were boilerplate strings.

On 2026-07-18, the custom code was removed in favor of direct commitizen usage:
- **Bump**: `cz bump --changelog --yes` replaces `anvil-vault bump --increment <type>`
- **Classification**: The `detect-increment` shim outputs `AUTO` for any conventional commit; commitizen determines MAJOR/MINOR/PATCH from commit history
- **Changelog**: Commitizen generates entries from parsed commit messages instead of boilerplate
- **Tag management**: `cz bump` creates a local tag which is deleted before the bump PR; re-created on `main` after merge
- **Removed modules**: `bump_version.py`, `build_notes.py`, `version_utils.py`, `check_version.py`, and their thin-wrapper scripts in `scripts/ci/` and `scripts/release/`

## Consequences

- Every PR merged to main with a conventional commit title produces a version bump, changelog entry, tag, and GitHub Release within minutes
- CHANGELOG.md contains structured, meaningful entries generated from parsed conventional commits
- A `BUMP_PAT` secret must be configured in GitHub repository settings
- No PyPI publishing — out of scope for this feature

## Alternatives considered

- **Direct push for bump commits**: Rejected — fails under branch protection
- **Pre-merge bump convention**: Rejected — error-prone, inconsistent
- **semantic-release tool**: Rejected — Node.js dependency in a Python project
- **Custom Python version management**: Originally implemented, later replaced by direct commitizen (duplicated functionality)
- **Manual tagging**: Rejected — defeats purpose of automation
- **Commitizen auto-tag on bump branch**: The local tag created by `cz bump` is deleted and re-created after the bump PR merges, so the tag points at the canonical `main` commit

## See Also

- [[Decisions/README|Decisions]]
