---
title: Anvil vs Conjure Paperclip Bootstrap Pattern
type: discovery
tags:
  - type/discovery
  - domain/operations
aliases:
  - Paperclip Bootstrap Pattern
source: spec/065
created: 2026-07-05
updated: 2026-07-05
code-refs:
  - docs/anvil-seed.sh
  - docs/STAFFING_PLAN.md
---

# Anvil vs Conjure Paperclip Bootstrap Pattern

## Context

The anvil project was bootstrapped into Paperclip following the same pattern as conjure. Both projects use the same Paperclip instance (same company at `http://127.0.0.1:3100`), opencode_local adapter, and model strings (DeepSeek V4 Flash + GPT-4o-mini).

## Key Differences

| Dimension | Conjure | Anvil | Rationale |
|-----------|---------|-------|-----------|
| **Project maturity** | Pre-implementation (design docs only) | v0.13.0 release (0 deps core, web UI, API, CI/CD) | Anvil is further along → different agent structure |
| **Agent count** | 3 (CEO + Engineer + QA) | 3 (CEO + Platform Engineer + UX Engineer) | Same count, different roles — anvil's mature codebase needs backend/frontend split, not QA |
| **QA role** | Dedicated "Fidelity Reviewer" | Mechanical gates (`make pr-ready`) | Anvil already has automated quality gates, linting, vault audit. No need for agent-driven QA |
| **Projects** | 4 (Shell, Library, Catalog, Fidelity) | 4 (Core Engine, Web UI, API & Data, Operations) | Mapped to anvil's actual architectural layers |
| **Tickets** | Architecture draft + component contract + fidelity checklist | Spec backlog review per project area | Anvil has 60+ existing specs → agents should triage existing work, not create new from scratch |
| **Seed script location** | `docs/conjure-seed.sh` | `docs/anvil-seed.sh` | Same location pattern |

## Lessons Learned

1. **The conjure seed script is a reusable template** — it took ~30 minutes to adapt for anvil (change names, descriptions, agent roles). The CLI contract (company → goals → projects → agents → tickets) is stable across projects.

2. **Project maturity changes agent structure** — for a mature project, split by technical domain (platform vs UX) rather than role (engineer vs QA). Mechanical gates replace human-like QA agents.

3. **The $75/mo budget model scales** — conjure uses the same cap. With 3 agents at $20/$30/$25 = $75, the budget is a hard constraint that forces deliberate enablement of heartbeats.

4. **Bash syntax gotcha**: `$75` inside double quotes with `set -u` fails because bash interprets `$7` as a positional parameter. Use single quotes for echo statements containing dollar amounts.

## References

- Seed script: `docs/anvil-seed.sh`
- Staffing plan: `docs/STAFFING_PLAN.md`
- Conjure seed script: `../conjure/docs/conjure-seed.sh`