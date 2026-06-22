---
title: 014 DX Harness Hardening - research
type: research
tags:
  - type/spec
spec-refs:
  - docs/vault/Specs/014 DX Harness Hardening/
related:
  - '[[014 DX Harness Hardening]]'
created: ~
updated: ~
---
# Phase 0 Research: Developer & Agent Experience Hardening

All five spec-level ambiguities were resolved during `/speckit.clarify` (see `spec.md` → Clarifications). This document records the remaining technical/approach decisions for implementation. No `NEEDS CLARIFICATION` markers remain.

---

## R1 — CI platform & gate orchestration

- **Decision**: Add a single GitHub Actions workflow (`.github/workflows/ci.yml`) triggered on `pull_request` and on `push` to non-`main` branches. It runs the existing `make` gate targets in order: `make lint` → `make typecheck` → `make test` (with coverage) → `make vault-audit`. Enable branch protection on `main` requiring this workflow's check.
- **Rationale**: The gates already exist as local `make`/`shared/*.mk` targets; CI must run the *same* commands to guarantee local/automation parity (FR-005). GitHub Actions is already the project's CI (`auto-bump.yml`, `release.yml`), so no new platform is introduced. Branch protection is the mechanism that makes gates *blocking* (FR-003) and fail-closed (FR-006).
- **Alternatives considered**:
  - *Pre-commit hooks only* — rejected: local-only, bypassable, not authoritative for merge.
  - *A bespoke gate runner* — rejected: duplicates `make` targets and breaks parity.
  - *Re-implementing gates inline in YAML* — rejected: drift risk; YAML must call the same `make` targets devs run.

## R2 — Coverage baseline & ratchet mechanism

- **Decision**: Measure current coverage during implementation (`make test`), set `[tool.coverage.report] fail_under` in `pyproject.toml` to that measured integer (floor), and enforce it in CI. Treat `fail_under` as the ratchet: it may only increase. Record the policy and the chosen starting number in an ADR; amend Constitution Article IV to a phased/aspirational goal.
- **Rationale**: A true, satisfiable threshold makes the gate honest today (FR-009) and prevents regression (FR-010). `pytest-cov`'s `fail_under` already provides the enforcement primitive — no new tooling.
- **Alternatives considered**:
  - *Per-diff (patch) coverage* — rejected for v1: adds tooling (e.g., diff-cover) and complexity; the simple global floor meets the requirement. May be added later as the ratchet matures.
  - *Immediate 100%* — rejected per clarify Q1 (blocks all merges).

## R3 — Required checks vs. existing release automation

- **Decision**: Add a fast guard job (`bump-scope-guard`) that inspects the PR's changed files; if the change touches only `pyproject.toml` version line + `CHANGELOG.md` (no source/test diff), the heavy gate suite is skipped for that PR but the guard itself is a required check. Any PR with a source/test change runs the full suite regardless of author (human/agent/bot). Reconcile `auto-bump.yml`/`release.yml` so bot bump PRs satisfy the guard (their `[skip ci]` commits already touch only version + changelog).
- **Rationale**: Implements FR-006a — keeps automated semver releases flowing without creating a source-change bypass. The guard is cheap (file-list inspection) so it does not slow releases.
- **Alternatives considered**:
  - *Full gates on bump PRs* (clarify option B) — rejected per Q5: needlessly slows releases; bump PRs carry no source risk.
  - *Bot bypass of branch protection* (clarify option C) — rejected: a standing bypass is a loophole and violates fail-closed intent.

## R4 — ADR renumbering & uniqueness enforcement

- **Decision**: Renumber the *later* file in each collision (008, 010, 016) to the next free ADR numbers (current max is ADR-022; assign from 023 upward), update all inbound wikilinks in the same change, and leave a redirect/alias stub at each former filename. Also normalize the off-pattern `010-numpy-docstring-enforcement.md` to the `ADR-0NN-...` naming. Add an ADR-uniqueness check (standalone `scripts/ci/check_adr_unique.py` or folded into `vault_audit.py`) wired into `make vault-audit`.
- **Rationale**: Restores the "one number = one decision" invariant (FR-011) while the vault-audit link-resolution gate guarantees no broken wikilinks. Enforcing uniqueness in the audit prevents recurrence.
- **Alternatives considered**:
  - *Slug-as-identifier* (clarify option B) — rejected per Q4: numbers are the cited identity across the vault; renumbering is cleaner long-term.
  - *Grandfather collisions* (clarify option C) — rejected: leaves the invariant permanently broken.

## R5 — `TYPE_CHECKING` reconciliation & guarded-import audit

- **Decision**: Amend the constitution + `AGENTS.md` to the conditional-allow rule with the 4-point exception discipline (FR-021/FR-022). Keep `anvil/db/models/corpus.py` and `corpus_file.py` guarded imports (add the required one-line cycle comment if absent). Refactor `anvil/services/inference/inference.py` to a plain top-level `from ...core.autograd import Value` and delete the redundant function-local re-import at line ~676. Add `scripts/ci/check_guarded_imports.py` that flags any `TYPE_CHECKING`-guarded symbol referenced in runtime (non-annotation) code.
- **Rationale**: Resolves the most damaging contradiction for agents (Q3). The audit makes condition (c) of the discipline machine-checkable, preventing future `inference.py`-style misuse.
- **Alternatives considered**: Co-location of ORM classes — rejected (violates one-class-per-file); see spec Clarifications. Blanket allow/ban — rejected (see plan Complexity Tracking).

## R6 — `mypy` `ignore_errors` reconciliation (FR-008)

- **Decision**: Evaluate the two module-level overrides (`anvil.services.tracking`, `anvil.services.mlflow_inputs`). For each, either (a) remove the override and fix/annotate the underlying issues, or (b) if they stem from missing third-party (`mlflow`) stubs, narrow the suppression to the specific error codes and record the justification in an ADR. Default preference: narrow + justify, since the errors are MLflow stub gaps, not anvil type defects.
- **Rationale**: FR-008 forbids rules the code knowingly violates; a blanket module `ignore_errors` is exactly that. Narrowing + recording makes the suppression honest and bounded.
- **Alternatives considered**: Leave as-is — rejected (silent contradiction). Full removal without stubs — rejected if it produces unfixable third-party errors.

## R7 — Onboarding documentation structure

- **Decision**: Create `ARCHITECTURE.md` at repo root (layering model Repository→Service→God Class→Routes/CLI, data-flow narrative, "how to add a service/route/endpoint", where ADRs live). Expand `CONTRIBUTING.md` (code map, mandatory rules digest, local gate commands, link to ARCHITECTURE + ADR index). Generate `docs/vault/Decisions/README.md` as a human-readable ADR index (title + status + one-line summary), ideally produced/validated by `make vault-audit`. Trim `AGENTS.md` "Active Technologies"/"Recent Changes" into `CHANGELOG.md`.
- **Rationale**: Satisfies FR-013–FR-017 and SC-007/SC-008/SC-009; keeps the agent guide lean and the human entry points discoverable from the repo root.
- **Alternatives considered**: Putting architecture narrative only in the vault — rejected: not discoverable for humans without Obsidian (FR-015).

## R8 — Structural refactor sequencing (P4)

- **Decision**: Deliver as two independent, behavior-free changes, each its own commit/PR (Constitution §10.9), sequenced *after* the enforcement workstream so the gate suite guards the refactors:
  1. **God class (FR-018)**: expose all services through `AnvilWorkbench` as lazy properties; optionally relocate it from `cli.py` to `anvil/workbench.py`; migrate routes/CLI/tests to obtain services via it. Verify: full suite unchanged.
  2. **Router split (FR-019)**: extract route groups (page-rendering, health/ops, learning, per-domain routers) from `anvil/api/v1/router.py` into cohesive one-class/one-concern modules following Article X; `router.py` becomes a thin aggregator. Verify: full suite unchanged, route table identical.
- **Rationale**: Sequencing after CI means the zero-behavioral-delta claim (FR-020, SC-011) is machine-verified by the now-enforced suite. Splitting into two PRs keeps each reviewable and matches §10.9.
- **Alternatives considered**: One big refactor PR — rejected (§10.9, unreviewable). Doing refactors before CI — rejected: no automated safety net for "zero delta".

## Resolved unknowns summary

| Topic | Resolution source |
|---|---|
| Coverage threshold | R2 (clarify Q1) — ratcheting baseline |
| Refactor scope | R8 (clarify Q2) — in scope, two separate behavior-free PRs |
| `TYPE_CHECKING` | R5 (clarify Q3) — conditional allow + discipline |
| ADR collisions | R4 (clarify Q4) — renumber + uniqueness check |
| Release automation | R3 (clarify Q5) — bump-scope guard |
| `mypy` overrides | R6 — narrow + justify under FR-008 |
| Onboarding docs | R7 — ARCHITECTURE.md + CONTRIBUTING + ADR index |
