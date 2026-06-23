---
title: 010 Automated Semver Release
type: spec
tags:
  - type/spec
  - domain/tooling
spec-refs:
  - docs/vault/Specs/010 Automated Semver Release/
status: draft
created: '2026-06-14'
updated: '2026-06-22'
aliases:
  - 010 Automated Semver Release
---

# 010 Automated Semver Release

## Summary

- Q: How should the version bump commit get back to main without infinite loops or branch protection failures? → A: Auto-merge PR pattern — workflow creates a PR with the bump commit, auto-merges via `gh pr merge --auto --squash`, uses `BUMP_PAT` for PR creation, and includes `[skip ci]` in the bump commit message to prevent re-triggering the release workflow.

## Artifacts

- [[010 Automated Semver Release - data-model|data-model]]
- [[010 Automated Semver Release - plan|plan]]
- [[010 Automated Semver Release - quickstart|quickstart]]
- [[010 Automated Semver Release - research|research]]
- [[010 Automated Semver Release - spec|spec]]
- [[010 Automated Semver Release - tasks|tasks]]

## References

- [[Specs/Specs|Specs]]
