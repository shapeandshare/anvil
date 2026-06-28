---
title: >-
  Session: SaaS Spec Decomposition — 016 Umbrella Split into Per-Feature Specs
  028–037
type: session-log
tags:
  - type/session-log
  - domain/architecture
  - domain/infrastructure
  - domain/governance
created: '2026-06-27'
updated: '2026-06-27'
aliases:
  - >-
    Session: SaaS Spec Decomposition — 016 Umbrella Split into Per-Feature Specs
    028–037
  - saas-spec-decomposition
status: draft
source: agent
---

# Session: SaaS Spec Decomposition — 016 Umbrella Split into Per-Feature Specs 028–037

**Date**: 2026-06-27
**Trigger**: Request to break the monolithic SaaS spec (016) into discrete, independently shippable
features, each with a full spec artifact set and explicit local-mode regression gates.

## What was done

### 1. Shippable-feature analysis

Created `docs/vault/Specs/016 SaaS Architecture/016 SaaS Architecture - shippable-features.md`
analyzing the 016 spec into 10 discrete features with dependency order, local-mode risk ratings,
and per-feature Definition of Done including the Local-Mode Regression Gate (LMRG).

Key corrections vs. the reference plan's 14-phase ordering:
- **Docker Compose pulled earlier** (Phase 10 → Feature 2) so every subsequent feature has a fast
  local feedback loop
- **Local-mode verification per-feature** instead of a single late Phase 9 gate
- **S3FileStore folded into the training pipeline** rather than standalone
- **Training pipeline kept as one feature** (Batch + Redis + job_events + SSE + reconciler form a
  single correctness unit)

### 2. Shared architecture decisions reference

Created `docs/vault/Reference/SaaSArchitectureDecisions.md` lifting AD-1..AD-17 from the 016 spec
into a durable shared reference that all 10 child specs link to.

### 3. Ten per-feature specs generated (028–037)

Each with the full artifact set (index note + spec + plan + tasks + research + data-model +
quickstart + contracts/), generated in parallel by sub-agents following a shared template:

| # | Spec | Key FRs | Depends on |
|---|------|---------|------------|
| 028 | SaaS Abstraction Framework | FR-001/011/016, AD-10 | — |
| 029 | SaaS Dev Stack (Docker Compose) | FR-012/013 | 028 |
| 030 | SaaS Authentication (Cognito) | FR-002/018–023, AD-2/3 | 028 |
| 031 | SaaS Multi-Tenancy & RBAC | FR-034–038b, AD-8/14 | 030 |
| 032 | SaaS Training Pipeline | FR-039–048, AD-1/4/5/9/11 | 031 |
| 033 | SaaS CDK Infrastructure | FR-008–010/029/051, AD-6/7 | 028 |
| 034 | SaaS One-Command Deploy | FR-024–031/049/050, AD-3/6/7 | 033, 032 |
| 035 | SaaS CLI Remote & Cluster Mgmt | FR-014/014a-c, AD-15 | 034 |
| 036 | SaaS Observability & MLflow Proxy | FR-052–057, AD-12/13 | 032 |
| 037 | SaaS Resilience & DR | FR-044a/045q/045s/058–061, AD-16 | 033, 036 |

### 4. 016 umbrella spec retired

- Index note marked `status: superseded` with a warning callout and full child-spec index
- All 6 sub-artifacts (`spec.md`, `plan.md`, `tasks.md`, `data-model.md`, `research.md`,
  `quickstart.md`) frontmatter updated: `status: superseded`, tags include `status/superseded`,
  dates filled in, superseded warning added to body
- `shippable-features.md` retained as the bridge/MOC explaining the decomposition

### 5. ADR-030 updated

Code-refs updated to point at the 8 child specs + `SaaSArchitectureDecisions` instead of 016. Status
note added recording the decomposition.

### 6. Specs.md MOC updated

All 10 children added with a "SaaS Decomposition (016 → 028–037)" section.

### 7. Cross-spec wikilink repair

Parallel agents had guessed sibling folder names (e.g. "030 SaaS Auth" instead of "030 SaaS
Authentication"). Fixed 32 broken wikilinks across 6 specs + 037's trailing-backslash artifacts.

## Vault health

Final `make vault-audit`: **0 errors, 0 warnings, 100.0/100** health (553 notes).

## Changes made

| Entity | Action |
|--------|--------|
| `docs/vault/Reference/SaaSArchitectureDecisions.md` | **CREATED** — shared AD-1..AD-17 |
| `docs/vault/Specs/028 SaaS Abstraction Framework/` | **CREATED** — full artifact set |
| `docs/vault/Specs/029 SaaS Dev Stack/` | **CREATED** — full artifact set |
| `docs/vault/Specs/030 SaaS Authentication/` | **CREATED** — full artifact set |
| `docs/vault/Specs/031 SaaS Multi-Tenancy RBAC/` | **CREATED** — full artifact set |
| `docs/vault/Specs/032 SaaS Training Pipeline/` | **CREATED** — full artifact set |
| `docs/vault/Specs/033 SaaS CDK Infrastructure/` | **CREATED** — full artifact set |
| `docs/vault/Specs/034 SaaS One-Command Deploy/` | **CREATED** — full artifact set |
| `docs/vault/Specs/035 SaaS CLI Remote/` | **CREATED** — full artifact set |
| `docs/vault/Specs/036 SaaS Observability MLflow Proxy/` | **CREATED** — full artifact set |
| `docs/vault/Specs/037 SaaS Resilience DR/` | **CREATED** — full artifact set |
| `docs/vault/Specs/016 SaaS Architecture/` | **UPDATED** — all artifacts marked superseded |
| `docs/vault/Decisions/ADR-030-saas-architecture.md` | **UPDATED** — code-refs + decomposition note |
| `docs/vault/Specs/Specs.md` | **UPDATED** — children wired in |
| `docs/vault/Specs/016 SaaS Architecture/016 SaaS Architecture - shippable-features.md` | **UPDATED** — added to 016 artifact index |

## See also

- [[Decisions/ADR-030-saas-architecture|ADR-030]] — originating ADR
- [[Reference/SaaSArchitectureDecisions|SaaS Architecture Decisions]] — shared AD-1..AD-17
- [[Specs/016 SaaS Architecture/016 SaaS Architecture|016 SaaS Architecture]] — superseded umbrella
