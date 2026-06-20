---
title: Coverage Ratcheting Baseline
type: decision
tags:
  - type/decision
  - domain/tooling
  - domain/governance
created: 2026-06-19
updated: 2026-06-19
aliases:
  - ADR-026-coverage-ratcheting-baseline
source: agent
code-refs:
  - pyproject.toml
  - .github/workflows/ci.yml
  - .specify/memory/constitution.md
---

# ADR-026: Coverage Ratcheting Baseline

**Status**: Draft  
**Created**: 2026-06-19  
**Supersedes**: Constitution Article IV ("100% coverage")

## Context

The constitution declares "Unit test coverage MUST be 100% across all layers." In practice:
- The measured coverage is ~23% (web/service-heavy; `anvil/core/` coverage is higher).
- `pyproject.toml` set `fail_under = 100`, but this was never enforced in CI — the gate was honor-system only.
- The 100% target is aspirational, not actionable. An impossible gate trains contributors and agents to ignore gates entirely.

## Decision

Replace the "100% coverage" mandate with a **ratcheting baseline**:

1. **Set `fail_under` to the current measured coverage** (23%, floor to integer) in `pyproject.toml`.
2. **Enforce it in CI** via the `test` gate (FR-001). This makes the gate *true today*.
3. **Ratchet upward only**: `fail_under` may only increase. A decrease requires explicit, recorded approval.
4. **Express 100% as a phased/aspirational goal** in governance, not an enforceable requirement.

The mechanism — `pytest-cov`'s existing `fail_under` — requires no new tooling.

## Rationale

- A true, satisfiable gate prevents regression (FR-010) and makes the declared standard match the enforced standard (FR-009).
- The ratchet pattern (monotonically increasing, never decreasing) is a proven engineering practice for quality metrics.
- An aspirational "100%" retained in governance without enforcement trains disregard; an honest 23% with upward pressure builds trust.

## Alternatives considered

- **Immediate 100%** (rejected): blocks all merges today; would require writing ~5,000 lines of tests purely to satisfy a gate before any other work.
- **Per-diff (patch) coverage** (deferred): adds tooling (`diff-cover`) and complexity. May be layered on top of the global ratchet later.
- **Remove the coverage standard entirely** (rejected): abandons the quality goal.

## Status

Amends Constitution Article IV. Implemented by `pyproject.toml` `fail_under = 23` and enforced by `.github/workflows/ci.yml`.