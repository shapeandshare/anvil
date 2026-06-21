---
aliases:
  - GITHUB_TOKEN CI Trigger Restriction
code-refs:
  - .github/workflows/release.yml
  - docs/secrets.md
created: '2026-06-21'
related:
  - '[[Decisions/ADR-008-automated-semver-release]]'
  - '[[Discoveries/release-workflow-git-identity-and-cz-commit]]'
  - '[[Sessions/2026-06-14-automated-semver-release]]'
  - '[[Sessions/2026-06-20-release-workflow-ci-fix]]'
session: '2026-06-21'
source: agent
summary: >-
  GitHub's built-in GITHUB_TOKEN cannot trigger CI checks on PRs it opens under
  branch protection. This forces the PAT approach for auto-merge release
  workflows — a non-obvious platform constraint that must be accounted for in
  any CI/CD design that creates PRs programmatically.
tags:
  - type/discovery
  - domain/infrastructure
  - domain/tooling
  - status/draft
title: GITHUB_TOKEN CI Trigger Restriction
type: discovery
updated: '2026-06-21'
---
GitHub's built-in `GITHUB_TOKEN` — the auto-injected token available in every workflow run — cannot trigger CI checks (status checks, required checks, workflow runs) on Pull Requests that it opens. This is a deliberate platform restriction, not a configuration issue, and it has direct consequences for any automated release pipeline that depends on auto-merge PRs under branch protection.

## The Restriction

When a workflow uses `GITHUB_TOKEN` to create a PR (via `gh pr create` or the API), that PR does **not** fire any CI workflows. From GitHub's perspective, the event is considered an intra-workflow action rather than an external user action, and it does not generate a `pull_request` or `pull_request_target` event. The result: the PR sits with zero status checks, blocked under branch protection rules that require "All Checks to pass."

This is documented by GitHub as "Pushes from GITHUB_TOKEN do not trigger workflows by default" (the `GITHUB_TOKEN` is the only token that triggers the `GITHUB_TOKEN_NO_WORKFLOW` event type instead of `push` or `pull_request`).

## Solution: Fine-Grained PAT

The workaround is a Personal Access Token (PAT) from a real GitHub user account, configured as a repository secret:

- **Fine-grained PAT** (not a classic token) with repository-level scope: Contents (read+write), Pull Requests (read+write), Workflows (read+write).
- Stored as a repository secret (e.g., `BUMP_PAT`) and referenced in workflow steps that create PRs: `token: ${{ secrets.BUMP_PAT }}`.
- A classic token works for the PR-creation API call, but a fine-grained PAT is preferred for narrower scoping.

## Why Not GITHUB_TOKEN in an Open Context

Even outside the anvil project, this restriction affects any automation that:

1. Creates a PR as part of a workflow (version bumps, dependency updates, auto-fixes).
2. Has branch protection requiring CI checks to pass before merging.
3. Uses `GITHUB_TOKEN` as the credential and then cannot understand why the PR is stuck.

The only workarounds are (a) a PAT from a user with CI-triggering privileges, or (b) removing the CI-required branch protection on automated PRs (not recommended).

## How It Manifests in anvil

The `Release` workflow (`.github/workflows/release.yml`) creates an auto-merge bump PR after `cz bump` updates the version and changelog. If `GITHUB_TOKEN` were used here:

- The PR would be created successfully.
- No CI checks would run on it.
- Auto-merge would block under branch protection.
- The tag-and-release step would never proceed (or timeout and tag the pre-bump state).

The fix is `BUMP_PAT` referenced at `docs/secrets.md` with setup instructions. Both the release workflow and the safety-net auto-bump workflow (`auto-bump.yml`) use `secrets.BUMP_PAT` for PR creation.

## Related Patterns

- Dependabot uses its own app identity, not `GITHUB_TOKEN`, which is why Dependabot PRs do trigger CI.
- `actions/create-github-app-token` is an alternative if a dedicated GitHub App is available — it produces an installation token that also triggers CI.

## References

- `.github/workflows/release.yml` — `Create bump PR with auto-merge` step uses `secrets.BUMP_PAT`.
- `.github/workflows/auto-bump.yml` — Same pattern for the safety-net workflow.
- `docs/secrets.md` — Setup guide for `BUMP_PAT`.
- [[Decisions/ADR-008-automated-semver-release]] — ADR that decided the auto-merge PR pattern.
- [[Discoveries/release-workflow-git-identity-and-cz-commit]] — Related discovery about git identity ordering in the release workflow.
