# Tasks: UX Rules Integration

**Input**: Design documents from `specs/020-ux-rules-integration/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Not requested in spec — verification tasks are integrated into each phase.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4)
- Include exact file paths in descriptions

## Phase 1: Setup

**Purpose**: Create target directories needed by all subsequent placement tasks

- [x] T001 Create `.opencode/skills/` directory structure for skill placement (needed by US2, US4)
- [x] T002 [P] Verify `scripts/ci/` directory exists and is writable (needed by US1, US4)

---

## Phase 2: Foundational

**Purpose**: Place shared artifacts that are prerequisites for multiple user stories — the ruleset (consumed by all stories) and the Makefile include (needed by US1, US4)

**⚠️ CRITICAL**: US1 and US4 cannot be verified without this phase complete

- [x] T003 Place `docs/ux-rules.md` ruleset from `docs/usability/ux-rules.md` (consumed by all skills and scripts). Verify the operating contract section (lines ~15-28) is present after placement — confirms FR-012.
- [x] T004 [P] Create `shared/ux.mk` with `ux-lint` and `ux-review` targets referencing `scripts/ci/ux_lint.py` and `scripts/ci/ux_review.py`
- [x] T005 Add `include shared/ux.mk` to root `Makefile` alongside existing includes
- [x] T006 [P] Create `.opencode/skills/ux-generate/SKILL.md` with YAML frontmatter (`name: ux-generate`, `description: ...`) and body applying S4/S3-as-hard-constraints referencing `docs/ux-rules.md`. Follow the interface contract at `contracts/opencode-skills.md` for exact content spec. Reference the generate-projection design from INTEGRATION §3.

**Checkpoint**: Shared infrastructure ready — all user stories can proceed

---

## Phase 3: User Story 1 — Developer UX Linting (Priority: P1) 🎯 MVP

**Goal**: Developers can run `make ux-lint` locally and get deterministic S4 findings on templates and CSS

**Independent Test**: `echo '{{ x | safe }}' > /tmp/test.html && make ux-lint FILES=/tmp/test.html` produces `[S4] template` + `GATE: FAIL`

- [x] T007 [P] [US1] Place `scripts/ci/ux_lint.py` from `docs/usability/ux_lint.py`
- [x] T008 [US1] Verify `make ux-lint` passes on a clean file (`make ux-lint FILES=docs/ux-rules.md` yields `GATE: PASS`)
- [x] T009 [US1] Verify `make ux-lint` fails on a seeded S4 violation (unsafe `|safe` produces `[S4] template` + `GATE: FAIL`)

**Checkpoint**: `make ux-lint` works and can be used by any developer

---

## Phase 4: User Story 2 — Agent UX Compliance (Priority: P1)

**Goal**: OMO builder agents loading `ux-generate` skill produce UI code that complies with the ruleset by construction

**Independent Test**: `skill` tool lists `ux-generate` at project priority; loading the skill and prompting for a Jinja form yields CSRF token + semantic buttons + no unsafe `|safe`

- [x] T010 [P] [US2] Configure agent context to load `ux-generate` skill when editing UI files (verify in `skill` tool output)
- [x] T011 [US2] Verify `skill` tool lists `ux-generate` at project priority. Also confirm `.opencode/skills/ux-generate/SKILL.md` has valid YAML frontmatter with `name` and `description` fields.
- [x] T012 [US2] Smoke-test: instruct an agent with `ux-generate` loaded to generate a Jinja form — verify CSRF token, `<button>` elements, and associated labels

**Checkpoint**: `ux-generate` skill is discoverable and functional

---

## Phase 5: User Story 3 — Spec Kit Governance (Priority: P2)

**Goal**: `.specify/memory/constitution.md` includes a UI-compliance MUST principle; `/speckit.analyze` flags S4/S3 violations at spec time

**Independent Test**: Create a spec snippet describing unescaped template output; run `/speckit.analyze` and confirm a CRITICAL violation referencing the constitution principle

- [x] T013 [P] [US3] Add UI-compliance MUST principle to `.specify/memory/constitution.md` referencing `docs/ux-rules.md`
- [x] T014 [US3] Run `/speckit.constitution` to propagate the new principle to spec/plan/tasks templates
- [x] T015 [US3] Verify: run `/speckit.analyze` on a spec with a UI violation and confirm CRITICAL flag

**Checkpoint**: UI compliance gates the spec pipeline

---

## Phase 6: User Story 4 — Deep AI UX Review (Priority: P2)

**Goal**: Developers can run `make ux-review` with `UX_API_KEY` set for AI-powered full-ruleset analysis

**Independent Test**: `UX_API_KEY="sk-..." make ux-review FILES=<file-with-S3-violation>` returns findings with severity tags and a `GATE: PASS|FAIL` tally

- [x] T016 [P] [US4] Place `scripts/ci/ux_review.py` from `docs/usability/ux_review.py`
- [x] T017 [P] [US4] Place `.opencode/skills/ux-review/SKILL.md` from `docs/usability/SKILL.md`
- [x] T018 [US4] Verify `skill` tool lists `ux-review` at project priority. Also confirm `.opencode/skills/ux-review/SKILL.md` has valid YAML frontmatter with `name` and `description` fields.
- [x] T019 [US4] Smoke-test: run `make ux-review FILES=docs/ux-rules.md` (requires `UX_API_KEY`) — verify findings output format or graceful skip if key unset

**Checkpoint**: `ux-review` is available for developers with API access

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Final verification that all pieces work together

- [x] T020 Run `make ux-lint` across the entire repo to establish baseline (document any pre-existing findings). Use explicit `FILES` argument (not origin/main diff which may not exist yet). Pre-existing S4 findings need `ux-lint:allow` suppression annotations or documented exclusion.
- [x] T021 Run full verification per quickstart.md steps to confirm all acceptance criteria pass

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS US1 and US4 verification
- **User Story 1 (Phase 3)**: Depends on Foundational (Phase 2) — can proceed independently
- **User Story 2 (Phase 4)**: Depends on Foundational (Phase 2) — can proceed in parallel with US1
- **User Story 3 (Phase 5)**: Depends on Phase 2 (for ruleset path) — can proceed in parallel with US1/US2
- **User Story 4 (Phase 6)**: Depends on Foundational (Phase 2) — can proceed in parallel with US1/US2/US3
- **Polish (Phase 7)**: Depends on all user stories being complete

### User Story Dependencies

- **US1 (P1)**: No dependencies on other user stories
- **US2 (P1)**: No dependencies on other user stories
- **US3 (P2)**: No dependencies on other user stories
- **US4 (P2)**: No dependencies on other user stories

### Parallel Opportunities

- T001 and T002 can run in parallel
- T003, T004, T006 can run in parallel (T005 depends on T004)
- All [P]-marked tasks within user stories can run in parallel
- US1, US2, US3, and US4 are fully independent — can be executed in parallel

---

## Parallel Example: Foundational Phase

```bash
# Launch all independent placement tasks together:
Task: "Place docs/ux-rules.md from docs/usability/ux-rules.md"
Task: "Create shared/ux.mk with ux-lint and ux-review targets"
Task: "Create .opencode/skills/ux-generate/SKILL.md"
```

## Parallel Example: All User Stories

```bash
# Once Foundational is done, all 4 stories can launch in parallel:
Task: "US1: Place scripts/ci/ux_lint.py + verify make ux-lint"
Task: "US2: Verify ux-generate skill loads + smoke test"
Task: "US3: Wire constitution principle + run /speckit.constitution"
Task: "US4: Place scripts/ci/ux_review.py + ux-review skill + verify"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: User Story 1 (linting gate)
4. **STOP and VALIDATE**: `make ux-lint` works deterministically
5. MVP is ready — developer linting gate functional

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add US1: Linting gate → Test independently (MVP!)
3. Add US2: Agent compliance → Test independently (skills online)
4. Add US3: Governance → Test independently (spec gating)
5. Add US4: Deep review → Test independently (full stack)

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Developer A: US1 (linter) + US4 (review) — these share Makefile and scripts/ci/
3. Developer B: US2 (ux-generate skill) + US3 (constitution) — independent of scripts/
4. All 4 stories complete and integrate independently