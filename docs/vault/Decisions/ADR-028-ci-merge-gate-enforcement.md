---
title: CI Merge Gate Enforcement
type: decision
tags:
  - type/decision
  - domain/tooling
  - domain/infrastructure
created: 2026-06-19
updated: 2026-06-19
aliases:
  - ADR-028-ci-merge-gate-enforcement
source: agent
code-refs:
  - .github/workflows/ci.yml
  - scripts/ci/check_bump_scope.py
  - scripts/ci/check_adr_unique.py
  - shared/vault.mk
---

# ADR-028: CI Merge Gate Enforcement

**Status**: Draft  
**Created**: 2026-06-19

## Context

The constitution, contributor guide, and agent guide all state that merge gates (`make lint`, `make typecheck`, `make test` with 100% coverage, `make vault-audit`) "MUST pass" before merging. In practice, no automated enforcement existed — there was no CI workflow that ran on pull requests, no required checks in branch protection, and no mechanism preventing a failing change from being merged.

For an agent-first codebase, this gap is uniquely damaging: agents treat declared rules as ground truth, so an unenforced rule produces confident-but-wrong work.

## Decision

Wire the existing local `make` gates into a **required, fail-closed GitHub Actions workflow** with the following design:

1. **Trigger**: Every pull request into `main` and every push to non-`main` branches (FR-002).
2. **Gates**: The workflow runs `make lint`, `make typecheck`, `make test`, and `make vault-audit` — the same commands developers run locally (FR-005).
3. **Bump-scope guard**: A fast file-classification job (`scripts/ci/check_bump_scope.py`) determines whether a PR touches source code or only version/changelog files. Version-only bump PRs skip the heavy gates but must still pass the guard itself (FR-006a).
4. **Fail-closed**: If any required gate fails or the workflow infrastructure errors, the check is not `success`, and branch protection prevents merge (FR-003, FR-006).
5. **Actionable output**: Failing jobs log the specific gate and the offending file/rule (FR-004).
6. **Additional enforcements**: ADR-uniqueness and guarded-imports checks are wired into the gate suite as optional/additional jobs.

Branch protection on `main` requires the overall CI workflow to pass. The bump-scope guard ensures release automation continues without being materially slowed.

## Rationale

- Reuses existing tooling — no new infrastructure. The `make` targets already exist in `shared/*.mk`.
- Local/automation parity (same commands, same results) eliminates "passes locally, fails in CI" — the most common CI trust problem.
- The bump-scope exemption is narrow and machine-verified, not a blanket bot bypass.

## Alternatives considered

- **Pre-commit hooks only** (rejected): bypassable; no authoritative merge-blocking.
- **Bot bypass** (rejected): a standing bypass violates fail-closed intent.
- **Full gates on bump PRs** (rejected): needlessly slows automated releases with no source-change risk.

## Status

Implemented by `.github/workflows/ci.yml` and enforced by branch protection settings on `main`.