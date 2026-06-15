# Contract: Commitizen Configuration Format

**Purpose**: Define the `[tool.commitizen]` section in `pyproject.toml` that configures semantic versioning, changelog generation, and tag creation.

**Applies to**: `pyproject.toml`

## Schema

```toml
[tool.commitizen]
name = "cz_conventional_commits"          # MUST — conventional commits backend
version_scheme = "semver"                  # MUST — semantic versioning
tag_format = "v$version"                   # MUST — tags look like v0.2.0
version_provider = "pep621"                # MUST — read version from [project].version
update_changelog_on_bump = true            # MUST — auto-update CHANGELOG.md
changelog_incremental = true               # MUST — append, don't overwrite
changelog_file = "CHANGELOG.md"            # MUST — path to changelog file
```

## Dependency

```toml
[project.optional-dependencies]
dev = [
    "commitizen>=3.0,<4",
    # ... existing dev deps
]
```

## Validation

```bash
# Verify config loads
cz version
# Should output something like: commitizen 3.x.y

# Verify dry-run bump works
cz bump --dry-run --increment patch
# Should show: new version: X.Y.(Z+1)

# Verify commit message format checking
cz check --rev-range HEAD~1..HEAD
# Exit 0 if valid conventional commit, non-zero if not
```

## Reference

- `~/Workbench/Repositories/concourse/pyproject.toml` — PEP 621 version_provider pattern