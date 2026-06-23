---
title: 014 DX Harness Hardening - data-model
type: data-model
tags:
  - type/spec
spec-refs:
  - docs/vault/Specs/014 DX Harness Hardening/
related:
  - '[[014 DX Harness Hardening]]'
created: ~
updated: ~
---
# Data Model: Developer & Agent Experience Hardening

This feature is process/enforcement/documentation-oriented; it introduces **no database entities** and no runtime persistence. The "entities" below are conceptual artifacts the feature operates on. Each lists its attributes, relationships, validation rules (from the spec's functional requirements), and lifecycle.

---

## 1. Quality Gate

A declared, automatable check a change must pass.

| Attribute | Description |
|---|---|
| `name` | Gate identifier (`lint`, `typecheck`, `test`, `coverage`, `vault-audit`, `guarded-imports`, `adr-uniqueness`, `bump-scope-guard`) |
| `command` | The local command that runs it (a `make` target or `scripts/ci/*` script) |
| `blocking` | Whether failure blocks merge into the protected main line (all gates: true) |
| `result` | `pass` \| `fail` |
| `failure_detail` | Actionable message naming the specific failure (FR-004) |

- **Relationships**: Runs against a *Change Proposal*; governs merge into the *Protected Main Line*.
- **Validation rules**: FR-001 (the suite covers lint/type/test/coverage/vault-audit); FR-003 (failure blocks merge); FR-005 (same command locally and in CI); FR-006 (unavailable ⇒ fail-closed).
- **Lifecycle**: `queued → running → (pass | fail)`. A `fail` is terminal for that change until a new commit re-triggers the gate.

## 2. Change Proposal

A proposed change (pull request) seeking to merge into the protected main line.

| Attribute | Description |
|---|---|
| `author_kind` | `human` \| `agent` \| `bot` |
| `changed_files` | The set of paths the change touches |
| `is_version_only_bump` | True iff `changed_files ⊆ {pyproject version line, CHANGELOG.md}` |
| `gate_results` | Map of Quality Gate → result |
| `mergeable` | True only if all required gates pass |

- **Validation rules**: FR-002 (gates run on every proposal pre-merge); FR-006a (version-only bumps may skip heavy gates but must pass the `bump-scope-guard`; any source diff ⇒ full suite regardless of `author_kind`).
- **State transitions**: `open → checks_running → (blocked | mergeable) → merged`. `blocked` returns to `checks_running` on a new commit.

## 3. Governance Document

An authoritative rules document.

| Attribute | Description |
|---|---|
| `path` | `.specify/memory/constitution.md`, `AGENTS.md`, `CONTRIBUTING.md` |
| `version` | Present for the constitution (semver, e.g., 1.6.0 → bumped) |
| `rules` | The set of declared rules |

- **Relationships**: Rules are cross-referenced across documents; each rule maps to either code compliance or a Decision Record amendment.
- **Validation rules**: FR-007 (no contradictions across documents); FR-008 (every rule is honored by code or amended); FR-016 (agent guide holds durable rules only — no per-change history); FR-021 (single consistent `TYPE_CHECKING` policy).
- **Lifecycle**: Amended only via a Decision Record + version bump (FR-012).

## 4. Decision Record (ADR)

A dated, versioned record of an architecture/governance decision.

| Attribute | Description |
|---|---|
| `id` | Unique identifier, format `ADR-0NN` (NN unique across all ADRs) |
| `title` | Short decision title |
| `status` | `draft → reviewed → canonical` (canonical is human-only) |
| `date` | Decision date |
| `rationale` | Why the decision was made |

- **Validation rules**: FR-011 (unique `id`; existing collisions 008/010/016 renumbered with redirects, no broken links); FR-012 (every governance amendment has an ADR).
- **Lifecycle**: created `draft`; renumber operation preserves inbound links via redirect/alias stubs; uniqueness enforced by the `adr-uniqueness` gate.
- **New ADRs this feature**: coverage-ratcheting-baseline; type-checking-conditional-allow; ci-merge-gate-enforcement; adr-renumbering-and-uniqueness; (optional) mypy-suppression-narrowing.

## 5. Onboarding Guide

Human-and-agent-facing documentation reachable from the repo root.

| Attribute | Description |
|---|---|
| `architecture_doc` | `ARCHITECTURE.md` — layering model, data flow, "how to add a service" |
| `contributor_guide` | `CONTRIBUTING.md` — code map, mandatory rules, local gate commands |
| `adr_index` | `docs/vault/Decisions/README.md` — human-readable list of decisions |

- **Validation rules**: FR-013 (single authoritative architecture doc); FR-014 (contributor orientation); FR-015 (tooling-free ADR index); FR-017 (docs match actual code/access patterns).
- **Lifecycle**: ADR index kept current by `make vault-audit`; architecture doc updated when the structural refactors (P4) land so it matches reality.

## 6. Guarded-Import Exception

A `TYPE_CHECKING`-guarded import permitted only under the exception discipline.

| Attribute | Description |
|---|---|
| `module` | File containing the guard |
| `symbol` | The type-only imported name |
| `cycle_reason` | One-line comment naming the runtime cycle being broken |
| `annotation_only` | True iff `symbol` is used only in annotations (machine-checked) |

- **Validation rules**: FR-022 — requires `from __future__ import annotations`; a genuine unavoidable runtime cycle; annotation-only usage; an explanatory comment.
- **Permitted instances**: `anvil/db/models/corpus.py`, `anvil/db/models/corpus_file.py`.
- **Disqualified**: `anvil/services/inference/inference.py` (no cycle ⇒ refactor to normal import).

## 7. Protected Main Line

The default integration branch.

| Attribute | Description |
|---|---|
| `branch` | `main` |
| `required_checks` | The CI gate suite + `bump-scope-guard` |
| `merge_policy` | Only changes with all required checks passing may merge |

- **Validation rules**: FR-003, FR-006 (fail-closed). Bot bypass is not permitted (clarify Q5).
