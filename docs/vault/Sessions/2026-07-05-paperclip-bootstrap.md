---
title: Paperclip Bootstrap
type: session-log
tags:
  - type/session-log
  - domain/operations
  - domain/infrastructure
aliases:
  - Paperclip Bootstrap Session
source: spec/065
created: 2026-07-05
updated: 2026-07-05
---

# Paperclip Bootstrap

**Date**: 2026-07-05
**Feature**: `specs/065-paperclip-bootstrap`

## Summary

Bootstrapped the anvil project as a Paperclip company, following the established conjure pattern. Created a seed script and staffing plan, then verified everything live against the running Paperclip instance.

## What Was Done

1. **Specification** (`/speckit.specify`): Created `spec.md` defining the bootstrap requirements — seed script, staffing plan, agent structure, goals, projects, budget.

2. **Planning** (`/speckit.plan`): Generated `plan.md`, `research.md`, `data-model.md`, `contracts/paperclip-api.md`, `quickstart.md`. All NEEDS CLARIFICATION resolved by referencing the conjure pattern.

3. **Tasks** (`/speckit.tasks`): Generated 29 tasks across 6 phases.

4. **Analysis** (`/speckit.analyze`): Cross-artifact consistency check — 100% FR coverage, 0 critical issues, 2 MEDIUM items (SC-001 timing gap, FR-011 defaults not in spec).

5. **Implementation** (`/speckit.implement`): All 29 tasks completed.

## Deliverables

| File | Purpose |
|------|---------|
| `docs/anvil-seed.sh` | Paperclip seed script — creates Anvil company, goals, projects, agents, tickets |
| `docs/STAFFING_PLAN.md` | Staffing plan — 3 agents, budgets, charters, sequencing, kill criteria |

## Key Decisions

- **Agent structure**: CEO ($20/mo) + Platform Engineer ($30/mo) + UX Engineer ($25/mo). Anvil's maturity (0.13.0, CI/CD, 60+ specs) justified splitting Platform from UX instead of conjure's monolithic Engineer + QA pattern.
- **Projects**: 4 — Core Engine & Training, Web UI & Design System, API & Data Services, Operations & Infrastructure.
- **Goals**: 1 mission goal ("reliable LLM workbench") + 2 team goals (core engine, web UI).
- **Budget**: $75/mo company hard cap, matching conjure.
- **Adapter**: opencode_local with DeepSeek V4 Flash primary + GPT-4o-mini budget lane.

## Verification

All checks passed against running Paperclip instance (v2026.626.0):
- Company "Anvil" created with correct mission
- $75/mo budget set (7500 cents)
- 3 goals, 4 projects, 3 agents, 4 seed tickets
- Heartbeats disabled by default
- Idempotency check works (re-run detects existing company)
- Seed script syntax clean (`bash -n`), executable (`chmod +x`)

## Artifacts

- Spec: `specs/065-paperclip-bootstrap/`
- Seed script: `docs/anvil-seed.sh`
- Staffing plan: `docs/STAFFING_PLAN.md`