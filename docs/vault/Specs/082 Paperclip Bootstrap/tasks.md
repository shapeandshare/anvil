# Tasks: Bootstrap Anvil into Paperclip

**Input**: Design documents from `docs/vault/Specs/082 Paperclip Bootstrap/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅, quickstart.md ✅

**Tests**: Not applicable for this feature — deliverables are operational scripts and documentation, not anvil source code. Verification is manual: run seed script against Paperclip, inspect via CLI.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Seed script**: `docs/anvil-seed.sh` (bash)
- **Staffing plan**: `docs/STAFFING_PLAN.md` (markdown)
- All deliverables at repository root under `docs/`

---

## Phase 1: Setup (Reference Load)

**Purpose**: Load the conjure reference files that serve as the template for anvil's bootstrap.

- [x] T001 Read `docs/learn-paperclip-with-conjure.md` from conjure repo at `/Users/joshburt/Workbench/Repositories/conjure` — understand the Paperclip mental model, model strings, adapter config, budget lane pattern
- [x] T002 Read `docs/conjure-seed.sh` from conjure repo — study the exact CLI command syntax, JSON payload shapes, idempotency pattern, env var defaults, and CHEAP_PROFILE construction
- [x] T003 Read `STAFFING_PLAN.md` from conjure repo — understand the staffing plan template structure (sections: What Changed, Current State, Proposed Team, Charters, Reserved Powers, Sequencing, Success/Kill Criteria)

---

## Phase 2: Foundational (Design Decisions)

**Purpose**: Confirm the design decisions that both deliverables depend on.

- [x] T004 Determine the absolute path to the anvil repository for `WORKDIR` default (see research.md RQ-2)
- [x] T005 Confirm the model strings available in `opencode models` output match research.md defaults (DeepSeek V4 Flash + GPT-4o-mini)

---

## Phase 3: User Story 1 - Seed script bootstraps the Anvil company (Priority: P1) 🎯 MVP

**Goal**: A single `anvil-seed.sh` script that creates the complete Anvil company in Paperclip — company, goals, projects, agents, and seed tickets.

**Independent Test**: Run `bash docs/anvil-seed.sh`, then verify via `npx paperclipai company list`, `npx paperclipai agent list -C <companyId>`, `npx paperclipai issue list -C <companyId>`.

- [x] T006 [P] [US1] Write Paperclip health check + env var defaults (MODEL, SMALL_MODEL, WORKDIR, PC) at the top of `docs/anvil-seed.sh` — match conjure pattern
- [x] T007 [P] [US1] Write JSON extraction helper (`json()`) and `set -euo pipefail` in `docs/anvil-seed.sh`
- [x] T008 [P] [US1] Write company creation block (idempotency check + create + budget set) in `docs/anvil-seed.sh` — company name "Anvil", mission from spec FR-002, budget $75/mo
- [x] T009 [P] [US1] Write goal creation block (1 mission goal + 2 team goals) in `docs/anvil-seed.sh` — mission "Anvil v1: reliable LLM workbench from scratch", team: "Core engine & training pipeline is reliable" + "Web UI is polished"
- [x] T010 [P] [US1] Write project creation block (4 projects) in `docs/anvil-seed.sh` — Core Engine & Training, Web UI & Design System, API & Data Services, Operations & Infrastructure
- [x] T011 [P] [US1] Write agent creation block (3 agents: CEO $20/mo, Platform Engineer $30/mo, UX Engineer $25/mo) in `docs/anvil-seed.sh` — opencode_local adapter, model profiles, heartbeats disabled
- [x] T012 [US1] Write seed ticket creation block (4 tickets) in `docs/anvil-seed.sh` — one per project, assigned to appropriate agent, appropriate priority
- [x] T013 [US1] Write done message (URL, next steps) at end of `docs/anvil-seed.sh`
- [x] T014 [US1] Verify `docs/anvil-seed.sh` is executable (`chmod +x`) and has no syntax errors (`bash -n docs/anvil-seed.sh`)

**Checkpoint**: At this point, User Story 1 should be fully functional. Run `bash docs/anvil-seed.sh` against a running Paperclip instance and verify the Anvil company appears at http://localhost:3100.

---

## Phase 4: User Story 2 - Agents begin working (Priority: P2)

**Goal**: A `docs/STAFFING_PLAN.md` that documents the agent structure — roles, budgets, charters, escalation paths, reserved powers, and sequencing. This mirrors conjure's STAFFING_PLAN.md v2 structure.

**Independent Test**: Read the staffing plan and verify it covers all three agents with: role, title, budget, capabilities, charter guardrails, escalation paths, and reserved powers. Verify company budget cap matches seed script ($75/mo).

- [x] T015 [P] [US2] Write staffing plan header (title, author, status, date), "What Changed" section (conjure pattern adapted for anvil), and "Current State" section (anvil project maturity stats: TDD, 8 domains, 0.13.0 release maturity) in `docs/STAFFING_PLAN.md`
- [x] T016 [P] [US2] Write "Proposed Team Structure" section (3 agents: CEO, Platform Engineer, UX Engineer) with org-chart ASCII tree, decomposition table (work shape → owner → rationale), and roles not created + why in `docs/STAFFING_PLAN.md`
- [x] T017 [P] [US2] Write "Charters and Guardrails" section (SOUL/CHARTER/INTENT structure, authority, reserved powers carve-out, behavioral invariants per agent, escalation paths) in `docs/STAFFING_PLAN.md`
- [x] T018 [P] [US2] Write "Reserved Powers" (human-only: constitution amendments, version bumps, merges, hiring, budget changes) and Budget table (CEO $20/mo, Platform Engineer $30/mo, UX Engineer $25/mo, hard cap $75/mo) in `docs/STAFFING_PLAN.md`
- [x] T019 [US2] Write "Sequencing" (Phase 0: fix baseline, Phase 1: spec backlog work), "Success/Kill Criteria" (S1-S4/K1-K4 matching conjure pattern), "Concrete Next Actions" table, and "Risks" section in `docs/STAFFING_PLAN.md`

**Checkpoint**: At this point, User Stories 1 AND 2 should both be complete. The seed script provisions the company, and the staffing plan governs agent operations.

---

## Phase 5: User Story 3 - Operator monitors work and costs (Priority: P3)

**Goal**: Operator verification that the seeded company is functional — agents appear, budget is configured, and the operator knows how to enable and monitor agent work.

**Independent Test**: Run `npx paperclipai agent list -C "$CID"`, `npx paperclipai company list --json`, and open http://localhost:3100 to verify all entities visible.

- [x] T020 [P] [US3] Verify company appears in Paperclip UI at http://localhost:3100 with correct name "Anvil" and mission text
- [x] T021 [P] [US3] Verify all 3 goals appear (1 mission + 2 team) via `npx paperclipai goal list -C "$CID" --json`
- [x] T022 [P] [US3] Verify all 4 projects appear via `npx paperclipai CLI` or Paperclip UI
- [x] T023 [US3] Verify all 3 agents exist with correct adapter type (opencode_local), model, cwd, and heartbeats disabled via `npx paperclipai agent list -C "$CID" --json`
- [x] T024 [US3] Verify 4 seed tickets exist via `npx paperclipai issue list -C "$CID" --json`
- [x] T025 [US3] Verify company budget is set to $75/mo via `npx paperclipai company list --json`
- [x] T026 [US3] Verify re-running seed script detects existing company and skips (idempotency)

**Checkpoint**: All user stories now complete. The Anvil company is fully bootstrapped and verifiable.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories — documentation and updates.

- [x] T027 [P] Update `AGENTS.md` "Active Technologies" section to include Paperclip / bootstrap entries (bash seed script pattern, etc.) — the agent context script already ran in Phase 1, verify AGENTS.md has the new entries
- [x] T028 [P] Write a one-paragraph section in `docs/learn-paperclip-with-anvil.md` (new file) explaining how anvil's Paperclip setup differs from conjure's (more agents, higher project count, mature repo) — or skip if not needed
- [x] T029 Run proof-of-concept: invoke a single heartbeat on one agent, confirm it picks up a ticket, verify transcript appears in Paperclip UI

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — reference reading
- **Foundational (Phase 2)**: Depends on Setup completion
- **User Story 1 (Phase 3)**: Depends on Foundational; no code dependencies (writing a bash script)
- **User Story 2 (Phase 4)**: Can run fully in parallel with US1 — staffing plan is independent of seed script
- **User Story 3 (Phase 5)**: Depends on US1 completion (company must be seeded to verify)
- **Polish (Phase 6)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: No dependencies — standalone seed script
- **User Story 2 (P2)**: No dependencies on other stories — can be written in parallel with US1
- **User Story 3 (P3)**: Depends on US1 completion (requires running seed script to verify)

### Within Each User Story

- US1 tasks T006-T013 marked [P] can be written in parallel (each section of the seed script is independent)
- US1 T014 (verify) depends on all script sections
- US2 tasks T015-T018 marked [P] can be written in parallel (each section of the staffing plan is independent)
- US2 T019 (assembly) depends on all sections
- US3 tasks are sequential verification steps

### Parallel Opportunities

- **US1 and US2**: Fully parallelizable — the seed script and staffing plan are independent files
- **Within US1**: T006-T012 can all run in parallel (sections of the seed script are independent blocks)
- **Within US2**: T015-T018 can run in parallel (sections of the staffing plan are independent)
- **Within US3**: T020-T022 can run in parallel (independent verification checks)

---

## Parallel Example: User Story 1

```bash
# Launch all seed script sections in parallel:
Task: "Write health check + env vars in docs/anvil-seed.sh"
Task: "Write JSON helper in docs/anvil-seed.sh"
Task: "Write company creation block in docs/anvil-seed.sh"
Task: "Write goal creation block in docs/anvil-seed.sh"
Task: "Write project creation block in docs/anvil-seed.sh"
Task: "Write agent creation block in docs/anvil-seed.sh"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (read conjure references)
2. Complete Phase 2: Foundational (confirm paths/models)
3. Complete Phase 3: User Story 1 (anvil-seed.sh)
4. **STOP and VALIDATE**: Run `bash docs/anvil-seed.sh` against running Paperclip
5. Company is seeded — this is the MVP

### Incremental Delivery

1. **MVP**: US1 → seed script runs, Anvil company is live in Paperclip
2. **+ Governance**: US2 → staffing plan documents agent charters and operating model
3. **+ Verification**: US3 → operator confirms everything works end to end
4. Each story adds value without breaking previous stories

### Parallel Strategy (2 developers)

- **Developer A**: US1 — write `docs/anvil-seed.sh`
- **Developer B**: US2 — write `docs/STAFFING_PLAN.md`
- **Both converge**: US3 — operator verifies
- This works because the seed script and staffing plan touch different files with zero overlap.

---

## Notes

- [P] tasks = different files or independent sections, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- US1 verification requires a running Paperclip instance (`npx paperclipai run`)
- US2 verification is document review (no runtime required)
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently