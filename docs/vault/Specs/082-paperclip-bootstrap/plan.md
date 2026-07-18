# Implementation Plan: Bootstrap Anvil into Paperclip

**Branch**: `063-paperclip-bootstrap` | **Date**: 2026-07-05 | **Spec**: [`spec.md`](spec.md)
**Input**: Feature specification from `docs/vault/Specs/082-paperclip-bootstrap/spec.md`

## Summary

Create a seed script (`anvil-seed.sh`) and companion staffing plan that bootstrap the Anvil project as a Paperclip company — following the established conjure pattern. The script creates the company, goals, projects, agents (opencode_local adapter), and seed tickets, all with heartbeats disabled by default. The staffing plan documents agent roles, budgets, escalation paths, and reserved powers.

## Technical Context

**Language/Version**: Bash (POSIX shell — matching `conjure-seed.sh` pattern)  
**Primary Dependencies**: Paperclip CLI (`npx paperclipai`), OpenCode (opencode_local adapter), cURL (health check)  
**Storage**: N/A — Paperclip handles its own embedded Postgres state  
**Testing**: Manual verification — run seed script, validate via `npx paperclipai company list / agent list / issue list`  
**Target Platform**: macOS (Paperclip runs on macOS/Linux; anvil repo co-located)  
**Project Type**: Operations — Paperclip company bootstrap and agent provisioning  
**Performance Goals**: Seed script completes in < 60 seconds  
**Constraints**: Paperclip must be running at `http://127.0.0.1:3100`; OpenRouter key must be configured for OpenCode  
**Scale/Scope**: Single Anvil company within existing Paperclip instance (coexists with Conjure company)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Articles that apply to this feature (operations/DevOps — not code):**

- **Article IX — Pit of Success**: The seed script defaults must produce a working Anvil company without manual configuration. Paperclip health check before operations. Graceful exit with clear error if Paperclip is not running.
- **Article XI — Simplicity First (Boring Technology)**: Uses the exact same pattern as conjure-seed.sh — proven, battle-tested. No novel approach, no speculative generality.

**Articles that do not apply (justification):**
- Articles I (core deps), II (educational), III (reproducibility), IV (TDD — no code written for anvil itself), V (async), VI (__init__.py), VII (layers), VIII (UI polish), X (DDD) — these govern the anvil Python package. This feature is operational bootstrap infrastructure, not anvil source code.

**Simplicity First gate (Article XI — hard MUST)**:

- [x] **Simplest viable** (§11.1) — Direct copy of conjure-seed.sh pattern with anvil-specific values. No new infrastructure.
- [x] **Boring over novel** (§11.2) — Uses the proven `opencode_local` adapter, same Paperclip CLI commands, same model strings as conjure.
- [x] **YAGNI** (§11.3) — Creates only what the spec requires: company, goals, projects, agents, seed tickets. No speculative agent hires or projects.
- [x] **Reuse first** (§11.4) — Reuses conjure-seed.sh's exact JSON payload structure, health check pattern, idempotency logic, and env var configuration.
- [x] **Testable** (§11.6) — Seed script is verifiable: run it, then inspect via `npx paperclipai CLI` commands. Manual verification is appropriate for a one-time bootstrap operation.

> No deviations from simplest viable — Complexity Tracking table is empty.

**Post-design re-check (Phase 1 complete)**: ✅ All gates remain green.
- research.md resolves all unknowns. No NEEDS CLARIFICATION items remain.
- data-model.md, contracts/, quickstart.md conform to spec requirements.
- Complexity Tracking table remains empty — no unjustified complexity introduced.
- The design produces a seed script + staffing plan following the exact conjure pattern (boring, proven). No novel technology, no speculative generality.

## Project Structure

### Artifacts (this feature)

```text
docs/vault/Specs/082-paperclip-bootstrap/
├── spec.md              # Feature specification (already created)
├── plan.md              # This file (implementation plan)
├── research.md          # Phase 0: Research findings
├── data-model.md        # Phase 1: Key entities & relationships
├── quickstart.md        # Phase 1: Quick-start guide for the operator
├── contracts/           # Phase 1: Interface contracts (if applicable)
│   └── paperclip-api.md     # Paperclip CLI contract for the seed script
└── checklists/
    └── requirements.md  # Spec quality checklist
```

### Source Code (repository root)

```text
# Seed script — one file at repo root, matching conjure pattern
docs/anvil-seed.sh       # Bootstrap script (companion to conjure-seed.sh)
docs/STAFFING_PLAN.md    # Agent staffing plan (companion to conjure's STAFFING_PLAN.md)
```

**Structure Decision**: Single seed script at `docs/` (alongside the existing paperclip bootstrap docs pattern from conjure). No Python code — this is an operational script. Staffing plan as a standalone doc for board review.

## Complexity Tracking

> **No violations — this plan follows the simplest viable approach (direct reuse of conjure pattern).**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| *(none)* | — | — |
