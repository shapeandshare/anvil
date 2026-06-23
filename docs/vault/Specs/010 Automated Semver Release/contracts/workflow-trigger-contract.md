# Contract: Workflow Trigger & Release Contract

**Purpose**: Define the contract between GitHub events, workflow triggers, and the release pipeline behavior.

**Applies to**: `release.yml` and `auto-bump.yml` in `.github/workflows/`

## Event-to-Workflow Mapping

| Event | Workflow | Trigger Condition | Purpose |
|-------|----------|-------------------|---------|
| `push` to `main` | `release.yml` | Always (no path filter) | Detect version change, auto-release |
| `workflow_dispatch` | `release.yml` | Manual via Actions UI | Escape hatch for suppressed workflows |
| `push` to `main` (`anvil/**`) | `auto-bump.yml` | Source code changes only (excludes CHANGELOG.md, .github/) | Safety-net: auto-open patch bump PR |
| `workflow_dispatch` | `auto-bump.yml` | Manual via Actions UI | Escape hatch for suppressed workflows |

## Token Permissions

| Token | Scope | Used For |
|-------|-------|----------|
| `GITHUB_TOKEN` (built-in) | `contents: write` | `actions/checkout`, `git push` (tag), `gh release create` |
| `GITHUB_TOKEN` (built-in) | `pull-requests: write` | (reserved, not used for PRs due to CI restriction) |
| `BUMP_PAT` (secret) | `contents: write` | `gh pr create` — opens the bump/auto-bump PR |
| `BUMP_PAT` (secret) | `pull-requests: write` | `gh pr merge --auto --squash` — auto-merges bump PR |
| `BUMP_PAT` (secret) | `workflows: write` | Ensures PRs created by the workflow trigger CI checks |

## Concurrency

| Workflow | Concurrency Group | Behavior |
|----------|-------------------|----------|
| `release.yml` | `release` | Queue, no cancellation (`cancel-in-progress: false`) |
| `auto-bump.yml` | `auto-bump` | Queue, no cancellation (`cancel-in-progress: false`) |

## Security Constraints

1. **No direct push to main for bump commits**: Bump commits MUST go through a PR (auto-merge) to satisfy branch protection
2. **`[skip ci]` in bump commit messages**: Prevents the merged bump PR from re-triggering the release workflow
3. **BUMP_PAT preflight check**: Workflow MUST check `BUMP_PAT` is set before attempting `gh pr create`, with a clear error message if missing
4. **Tag collision guard**: Workflow MUST check if tag already exists before creating it; if exists, fail with clear diagnostic

## Error Classification

| Error | Severity | Action |
|-------|----------|--------|
| BUMP_PAT missing | CRITICAL | Abort with diagnostic message |
| Tag already exists | CRITICAL | Abort with resolution instructions |
| `cz` not installed | CRITICAL | Abort with install instructions |
| PR description fetch fails | NON-CRITICAL | Log warning, continue without PR body |
| Changelog format unexpected | NON-CRITICAL | Log warning, continue |
| Second workflow triggers within 60s | WARNING | Abort with "possible loop detected" message |

## Merge Strategy

All auto-merge PRs use **squash merge** to keep a clean linear history on main. The squash-merge commit message includes `[skip ci]` at the end.