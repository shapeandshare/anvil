# Quickstart: Inference Rename + Chat Page

Implementation order (dependencies flow downward):

## Step 1: Nav Rename (Play → Inference)

**Files**: `anvil/api/templates/base.html`

- Change `"Play"` → `"Inference"` on the nav tab link for `/v1/inference-page` (line 69)
- No other changes to the playground page

**Tests**: Update `test_navigation_smoke.py` expected text for `/v1/inference-page`

---

## Step 2: Streaming Generate Method

**Files**: `anvil/services/inference/inference.py`

- Add `generate_stream(loaded, *, prompt, temperature, max_tokens=200)` — async generator yielding characters
- Reuse existing KV-cache pattern from `forward()` method
- Handle context truncation: if prompt exceeds block_size, drop oldest pairs

**Tests**: `tests/unit/services/inference/test_chat.py` — unit tests for streaming method

---

## Step 3: Chat SSE Endpoint

**Files**: `anvil/api/v1/inference.py` (or new `anvil/api/v1/chat.py`)

- Add `GET /v1/chat/stream` — SSE endpoint calling `generate_stream()`
- Use `StreamingResponse` with `text/event-stream`, `Cache-Control: no-cache`, `X-Accel-Buffering: no`
- Events: `chunk`, `complete`, `error`, `heartbeat` (30s)
- Wire through `AnvilWorkbench` (god class pattern)

**Tests**: `tests/e2e/api/test_chat.py` — HTTP endpoint tests

---

## Step 4: Chat Page Template

**Files**: `anvil/api/templates/archetypes/chat.html`

- New archetype template extending `base.html`
- Model selector populated from `GET /v1/inference/models` (reuse `dom.syncList()`)
- Temperature slider
- Chat message area with scrollable history
- Send button + Enter key handler
- Cancel button during generation
- Export/download button (P3)
- Context usage indicator
- SSE client via `EventSource` (or `SSESession`) for streaming

**CSS**: Add `.chat-message`, `.chat-message--user`, `.chat-message--assistant` styles to `components.css`

---

## Step 5: Chat Page Route

**Files**: `anvil/api/v1/pages.py`

- Add `GET /v1/chat-page` → renders `archetypes/chat.html`
- Pass `related_lessons` context (same as inference page)
- Add nav entry `"Chat"` in `base.html`

---

## Step 6: Demo Model Integration

**Files**: (none — already works)

The existing `DemoModelProvider` auto-provisions on first access. When the Chat page calls `GET /v1/inference/models` and the user selects the demo model, `InferenceService.load_model_by_ref()` resolves it. The streaming endpoint uses the same resolution.

---

## Step 7: Tests

| File | Contents |
|------|----------|
| `tests/browser/test_chat_ux.py` | Playwright: page loads, model selector, send message, cancel, streaming visual feedback |
| `tests/browser/test_navigation_smoke.py` | Add `("/v1/chat-page", selector, "Chat")` to `PAGES` |
| `tests/e2e/api/test_chat.py` | HTTP: streaming endpoint returns SSE events |
| `tests/e2e/test_pages.py` | Add `test_chat_page()` — page render test |
| `tests/unit/services/inference/test_chat.py` | Unit: generate_stream yields expected characters |

---

## Verification

```bash
make test        # Unit + e2e tests pass
make typecheck   # mypy strict passes
make lint        # Ruff + pylint passes
make test-browser # Playwright tests pass
```