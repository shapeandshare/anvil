# Tasks: Play → Inference (Rename) + New Chat Page

**Input**: Design documents from `specs/001-inference-chat-split/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/chat-stream.md

**Organization**: Tasks grouped by user story. Each story is independently testable.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- Include exact file paths in descriptions

---

## Phase 1: Setup

**Purpose**: No setup tasks needed — the project is already initialized. All dependencies (FastAPI, Jinja2, SSE, pytest, Playwright) are already installed.

This phase is intentionally empty.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before user story work can begin

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T001 Add `generate_stream()` method to `InferenceService` in `anvil/services/inference/inference.py` — an async generator that yields characters one at a time from the model's autoregressive loop, reusing the existing KV-cache pattern from `LlamaModel.forward()`. Must accept `prompt`, `temperature`, `max_tokens` parameters and yield each newly generated character.

**Checkpoint**: Foundation ready — streaming generation is available

---

## Phase 3: User Story 1 — Rename "Play" to "Inference" (Priority: P1) 🎯 MVP

**Goal**: Rename the navigation label "Play" to "Inference" for the `/v1/inference-page` route. No changes to the playground page itself.

**Independent Test**: Visit any page, verify the nav tab linking to `/v1/inference-page` displays "Inference" not "Play". Navigate to `/v1/inference-page` and verify the page renders identically.

### Implementation for User Story 1

- [x] T002 [US1] Change nav label from "Play" to "Inference" in `anvil/api/templates/base.html` line 69 — change the `<span class="tab-label">Play</span>` text to `"Inference"` for the `/v1/inference-page` link
- [x] T003 [US1] Update navigation smoke test expected text in `tests/browser/test_navigation_smoke.py` — change the expected text for the `/v1/inference-page` route tuple from `"Play"` to `"Inference"`

**Checkpoint**: Nav label is updated. All existing tests pass.

---

## Phase 4: User Story 2 — Chat with a Model (Priority: P1)

**Goal**: Users can send a message to a loaded model and see the response stream back character-by-character. The demo model is pre-selected, multi-turn conversation works, and users can cancel in-progress generation.

**Independent Test**: Visit `/v1/chat-page`, type a message, click Send, and watch the response stream in. Send a follow-up to verify multi-turn works.

### Implementation for User Story 2

- [x] T004 [P] [US2] Add chat SSE streaming endpoint `GET /v1/chat/stream` in `anvil/api/v1/inference.py` — returns `StreamingResponse` with `text/event-stream` media type, `Cache-Control: no-cache`, `X-Accel-Buffering: no`. Emits events: `chunk` (each character), `complete` (generation done), `error` (failure), `heartbeat` (30s timeout). Calls `InferenceService.generate_stream()` via `AnvilWorkbench`. Accepts query params: `model_name`, `temperature`, `prompt`.
- [x] T005 [P] [US2] Create chat page template `anvil/api/templates/archetypes/chat.html` — extends `base.html`, loads `archetypes.css` + `components.css`. Contains: chat message area (scrollable history), text input + send button, temperature slider, cancel button, context usage indicator near model selector. Inline JS IIFE manages conversation state, SSE client, send/cancel, multi-turn context. Demo model MUST be pre-selected when page loads (FR-006). Input MUST enforce 2000-character limit with visible warning (FR-014).
- [x] T006 [P] [US2] Add chat page route `GET /v1/chat-page` in `anvil/api/v1/pages.py` — renders `archetypes/chat.html` with `related_lessons` context. Follows the same pattern as `inference_page()`.
- [x] T007 [P] [US2] Add "Chat" navigation tab in `anvil/api/templates/base.html` — add a new `<a>` tab-item linking to `/v1/chat-page` with appropriate SVG icon, placed after the "Inference" tab. Use a chat bubble icon.
- [x] T008 [P] [US2] Add chat message styles to `anvil/api/static/css/components.css` — styles for `.chat-message`, `.chat-message--user`, `.chat-message--assistant`, `.chat-input-area`, `.chat-send-btn`, `.chat-cancel-btn`, `.chat-context-bar`. Use existing CSS tokens (`var(--accent)`, `var(--surface-2)`, `var(--space-*)`, `var(--border)`).

**Checkpoint**: Chat page renders, messages send and stream, multi-turn works, cancel works.

---

## Phase 5: User Story 3 — Model Selector in Chat (Priority: P2)

**Goal**: Users can choose which model to chat with from a dropdown, switch between models mid-session, and select model versions.

**Independent Test**: Open the model dropdown on the chat page, verify it populates with available models. Select a different model and verify subsequent messages use it.

### Implementation for User Story 3

- [x] T009 [P] [US3] Add model selector dropdown to chat page template `anvil/api/templates/archetypes/chat.html` — populate from `GET /v1/inference/models` using `dom.syncList()` reconciliation pattern (same as playground.html). Show model name and loss. The demo model is already pre-selected by default (handled in T005); this task adds the dropdown for manual selection.
- [x] T010 [P] [US3] Add version selector for multi-version models in `anvil/api/templates/archetypes/chat.html` — show version dropdown when selected model has >1 version. Use `dom.syncList()` pattern from playground.html.
- [x] T011 [US3] Implement model switching logic in JS in `anvil/api/templates/archetypes/chat.html` — when user switches model, preserve conversation history for reference but subsequent messages use the new model. Update model info display. **Depends on T009** (model dropdown) and **T010** (version selector) being complete.

**Checkpoint**: Model selector shows models, switching models works, version picker works for multi-version models.

---

## Phase 6: User Story 4 — Export a Conversation (Priority: P3)

**Goal**: Users can export or copy the current conversation as formatted text before leaving the page.

**Independent Test**: Have a conversation of at least 2 exchanges, click export, verify the output contains all messages in order with role labels.

### Implementation for User Story 4

- [x] T012 [P] [US4] Add export button to chat page template `anvil/api/templates/archetypes/chat.html` — positioned near the conversation header. Only visible when there are messages.
- [x] T013 [US4] Implement export format logic in JS in `anvil/api/templates/archetypes/chat.html` — format as plain text with role labels (`─── User ───\n{text}\n\n─── Assistant ───\n{text}`). Include conversation date. Support both clipboard copy and download as `.txt` file.

**Checkpoint**: Export button appears after messages exist, exporting produces correct formatted conversation.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Tests, quality gates, and verification that all user stories work together

- [x] T014 [P] Add e2e page render test for chat page in `tests/e2e/api/test_pages.py` — `test_chat_page()` verifying `GET /v1/chat-page` returns 200 with expected content
- [x] T015 [P] Add e2e HTTP tests for streaming endpoint in `tests/e2e/api/test_chat.py` — test SSE event stream, verify chunk events contain text, complete event fires, error handling for missing model
- [ ] T016 [P] Add Playwright browser tests in `tests/browser/test_chat_ux.py` — page loads without console errors, model selector populates, send message button works, streaming visual feedback appears, cancel button works, export button works (requires running Docker stack)
- [x] T017 [P] Update navigation smoke test `tests/browser/test_navigation_smoke.py` — add `("/v1/chat-page", selector, "Chat")` to `PAGES` table
- [x] T018 Run full test suite: `make test` — 305 passed, no regressions
- [x] T019 [P] **UX compliance gate**: run `make ux-lint` on all changed UI/template/CSS files — GATE: PASS (clean)
- [ ] T020 [P] **AI UX review** (optional — run with `UX_API_KEY` set): `make ux-review FILES=anvil/api/templates/archetypes/chat.html,anvil/api/static/css/components.css,anvil/api/templates/base.html`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No work needed — project is already initialized
- **Phase 2 (Foundational)**: T001 must complete before any user story work
- **Phase 3 (US1)**: Depends on Phase 2 completion — no dependencies on other stories
- **Phase 4 (US2)**: Depends on Phase 2 completion — no dependencies on other stories
- **Phase 5 (US3)**: Depends on Phase 4 completion (model selector goes in the chat template)
- **Phase 6 (US4)**: Depends on Phase 4 completion (export button goes in the chat template)
- **Phase 7 (Polish)**: Depends on all user story phases being complete

### User Story Dependencies

- **US1 (P1)**: Can start after Phase 2 — independent of other stories
- **US2 (P1)**: Can start after Phase 2 — independent of US1
- **US3 (P2)**: Depends on US2 (chat page template must exist to add model selector)
- **US4 (P3)**: Depends on US2 (chat page template must exist to add export button)

### Within Each User Story

- Services before endpoints
- Endpoints before templates (where applicable)
- Templates before CSS/JS (if modifying the same page)
- Tests before implementation (TDD)

### Parallel Opportunities

- **Phase 3**: T002 (nav HTML) and T003 (test update) — sequential (test comes after nav change)
- **Phase 4**: T004 (SSE endpoint), T005 (template), T006 (route), T007 (nav tab), T008 (CSS) — ALL can run in parallel [P] since they're different files with no interdependencies
- **Phase 5**: T009 (model dropdown) and T010 (version selector) — can run in parallel [P]
- **Phase 6**: T012 (export button) and T013 (export logic) — sequential (button first, then logic)
- **Phase 7**: T014 (e2e page), T015 (e2e streaming), T016 (Playwright), T017 (smoke test), T019 (UX lint), T020 (UX review) — ALL can run in parallel [P]

---

## Parallel Example: User Story 2

```bash
# Launch all Phase 4 tasks in parallel:
Task: "Add chat SSE streaming endpoint GET /v1/chat/stream in anvil/api/v1/inference.py"
Task: "Create chat page template anvil/api/templates/archetypes/chat.html"
Task: "Add chat page route GET /v1/chat-page in anvil/api/v1/pages.py"
Task: "Add Chat navigation tab in anvil/api/templates/base.html"
Task: "Add chat message styles to anvil/api/static/css/components.css"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 2: Foundational (T001)
2. Complete Phase 3: User Story 1 (T002, T003)
3. **STOP and VALIDATE**: Verify nav label change, run existing tests
4. Deploy/demo if ready

### Incremental Delivery

1. Phase 2 + Phase 3 → Foundation ready, nav renamed (tiny MVP!)
2. Add Phase 4 (US2) → Chat page works with demo model (core MVP!)
3. Add Phase 5 (US3) → Model selector added
4. Add Phase 6 (US4) → Export added
5. Each phase adds value without breaking previous phases

### Parallel Team Strategy

1. One developer completes Phase 2 (T001)
2. Once Phase 2 is done:
   - Developer A: Phase 3 (US1 rename) + Phase 4 (US2 chat)
   - Developer B: Phase 5 (US3 model selector) — can start after Phase 4 template exists
   - Developer C: Phase 6 (US4 export) — can start after Phase 4 template exists
3. All phases converge for Phase 7 integration and testing

---

## Notes

- [P] tasks = different files, no dependencies — can run in parallel
- [Story] label = task belongs to a specific user story
- Each user story is independently testable
- Tests must be written before implementation (TDD — Article IV)
- No new runtime dependencies (Article XI — Simplicity First)
- All UI work must comply with `docs/ux-rules.md` (S4/S3 findings block)
- **Auth**: The chat page is behind the same auth layer as all other pages. The `_login` fixture in browser tests handles this automatically. No auth-specific tasks are needed.