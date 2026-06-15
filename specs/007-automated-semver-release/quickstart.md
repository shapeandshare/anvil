# Quickstart: Automated Versioning & Release

**Created**: 2026-06-14  \n**Feature**: [spec.md](spec.md)

## For Developers

### Making Commits

```bash
# Interactive commit (recommended)
cz commit

# Manual conventional commit (if you know the format)
git commit -m "feat(api): add endpoint for model comparison"
git commit -m "fix(core): correct attention mask computation"
git commit -m "docs: update API reference"
```

### PR Titles

When opening a PR, the title MUST follow conventional commit format. The title determines the version bump:

| Title | Version Bump | Example |
|-------|-------------|---------|
| `feat: ...` | MINOR (x.Y.0) | `feat: add dataset dashboard` |
| `fix: ...` | PATCH (x.y.Z) | `fix: correct training loss NaN` |
| `feat!: ...` or body has `BREAKING CHANGE` | MAJOR (X.0.0) | `feat!: remove legacy v1 API` |
| `chore:`, `docs:`, `ci:`, etc. | NONE | `ci: update Python version` |

### Local Enforcement

A commit-msg hook will warn if your commit message doesn't follow conventional commit format. You can bypass it for non-PR commits (squash merge is the final gate), but using conventional format consistently helps generate a clean changelog.

### What Happens on Merge

1. You merge your PR to `main` (squash merge)
2. The release workflow detects the version bump type from the PR title
3. A bump PR is automatically created with updated version + changelog
4. The bump PR auto-merges to main
5. A `vX.Y.Z` tag is created
6. A GitHub Release is published

## For Maintainers

### Manual Trigger (Escape Hatch)

If the automated workflow is suppressed (e.g., a merge commit touches `.github/workflows/`):

1. Go to **Actions** → **Release** → **Run workflow** → **main**
2. The workflow reads the version at HEAD and creates a release

### Manual Release (if automated workflow fails)

```bash
# Bump version and update changelog
cz bump --changelog --increment patch   # or minor, or major

# Push tag
git push origin vX.Y.Z

# Create release
gh release create vX.Y.Z \
  --title "vX.Y.Z" \
  --notes "$(awk '/^## \['"vX.Y.Z"'\]/,/^## \[/' CHANGELOG.md | grep -v '^## \[')" \
  --target main
```

### Monitoring

Verify the pipeline is healthy with:

```bash
# Check latest tag
git tag --list 'v*' | tail -3

# Check version matches tag
grep '^version =' pyproject.toml

# Check changelog is populated
head -5 CHANGELOG.md

# Check GitHub Release exists
gh release view "$(git tag --list 'v*' | tail -1)" --json name,body,tagName
```

## For CI

The release workflow requires one secret to be configured:

| Secret | Purpose | Required Permissions |
|--------|---------|---------------------|
| `BUMP_PAT` | Opens bump PRs (GITHUB_TOKEN PRs don't trigger CI) | `Contents: write`, `Pull requests: write`, `Workflows: write` |

Set this in **Settings** → **Secrets and variables** → **Actions**.