# Research: Play → Inference + New Chat Page

## Summary

Research into existing SSE streaming patterns, the inference generation pipeline, Jinja2 template conventions, and Playwright test infrastructure for the anvil project.

---

## SSE Streaming Pattern

**Decision**: Reuse the existing SSE pattern for chat streaming (no new streaming infrastructure needed).

**Rationale**: The project already has a complete SSE streaming implementation — server-side `StreamingResponse` with `asyncio.Queue` buffering, and a client-side `SSESession` class. This same pattern serves the chat streaming use case directly.

**Key Findings**:
- **Server**: `StreamingResponse` with `text/event-stream` media type + `Cache-Control: no-cache` + `X-Accel-Buffering: no` headers (training.py:251-319)
- **Client**: `SSESession` class in `sse.js` (179 lines) with `EventSource` + named event listeners + retry with exponential backoff
- **Event format**: `event: {type}\ndata: {json}\n\n` — use `event: chunk\ndata: {"text": "..."}\n\n` for chat
- **Heartbeat**: 30-second timeout with heartbeat event to keep connection alive
- **Queue pattern**: `asyncio.Queue` with `put_nowait` / `_enqueue_or_drop` (drops on full to prevent memory growth)

**Alternatives Considered**:
- WebSocket — more complex, requires different client/server infrastructure. SSE is simpler and sufficient for one-way streaming.
- Chunked HTTP response — works but SSE provides named events, automatic reconnection, and is already established in the project.
- Long polling — inferior to SSE for streaming use case.

---

## Inference Generation Pipeline

**Decision**: Add a new `generate_stream()` method to `InferenceService` that yields characters incrementally, and wire it to a new SSE endpoint.

**Rationale**: The existing `InferenceService.generate()` (inference.py:1967) is a synchronous method that builds the full output string and returns it. For streaming, we need an async generator that yields each character as it's sampled.

**Key Findings**:
- **Core loop**: `LlamaModel.forward(token_id, pos_id, keys, values)` — KV-cached, single-token forward pass (engine.py:197-310)
- **Sampling**: `_sample_next_token()` applies temperature scaling → top-k/top-p filtering → softmax → random choice
- **Tokenization**: Char-level tokenizer maps characters ↔ IDs; BOS token marks boundaries. Subword tokenizer via `TransformersTokenizerAdapter` for external models.
- **Conversation context**: Build prompt by concatenating turns with role markers, then pass the full string to tokenizer.encode()
- **Existing endpoint**: `POST /v1/inference/sample` (learning.py:3433) generates multiple samples in batch — not suitable for streaming chat

**Streaming approach**:
1. `InferenceService.generate_stream()` becomes an async generator
2. It runs the forward pass loop + sampling, yielding each newly generated character
3. The HTTP endpoint wraps it in `StreamingResponse` with SSE events
4. The client-side `SSESession` handles event reception and appends to the chat output

---

## Jinja2 Template Conventions

**Decision**: Follow the exact same archetype template pattern as `playground.html` and `training.html`.

**Key Patterns**:
- `{% extends "base.html" %}` + `{% block extra_css %}` loading `archetypes.css` + `components.css`
- Content in `{% block content %}` inside `section-card` divs with staggered entrance (`--stagger-i: N`)
- JavaScript in `{% block scripts %}` as a self-contained IIFE `(function() { 'use strict'; ... })();`
- `{% block didyouknow_banner %}` for rotator content
- Model selector uses `dom.syncList()` reconciliation pattern from `dom.js`
- Toast notifications via `toast(msg, type, duration)` function
- CSS tokens: `var(--accent)`, `var(--surface-2)`, `var(--space-*)`, `var(--text-*)`, `var(--border)`
- API calls via `window.apiFetch()` (CSRF-protected wrapper in base.html)

---

## Playwright Test Infrastructure

**Decision**: Create `test_chat_ux.py` following the `test_teach_ux.py` pattern, and add the chat route to `test_navigation_smoke.py`.

**Key Patterns**:
- Fixtures: `base_url` (session-scoped), `assert_no_console_errors` (factory), `seed_client` (httpx for API seeding), `_login` (autouse auth)
- Navigation: `page.goto(f"{base_url}/v1/chat-page")` + `page.wait_for_load_state("networkidle")`
- Exception for SSE pages: `domcontentloaded` instead of `networkidle` (SSE keeps network active)
- Seeding: `model_seed` fixture polls `/v1/inference/models` for demo model availability
- Assertion: `checker = assert_no_console_errors(page)` → `.assert_no_errors()`
- Locators: `page.locator(selector).wait_for(state="visible", timeout=15_000)`
- Parametrized smoke: `PAGES` list of `(route, selector, expected_text)` tuples

---

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Streaming protocol | SSE (existing) | Already in the project, no new deps |
| Chat endpoint | New `/v1/chat/stream` SSE endpoint | Separate from batch `/v1/inference/sample` |
| Generation method | New `generate_stream()` async generator | Reuses KV-cache, yields incrementally |
| Conversation context | Concatenate turns with role markers | Simple, matches how models are trained |
| Template pattern | `archetypes/chat.html` following `playground.html` | Established pattern |
| Client streaming | `SSESession` from `sse.js` | Already exists, add event listener |
| Test pattern | `test_chat_ux.py` + route in `test_navigation_smoke.py` | Follows existing patterns |
| No models available | Informative message, disabled send button | FR-009, Edge Cases |
| Context overflow | Silent truncation + subtle indicator | Per clarification |
| Export format | Plain text with role labels | Minimal, no dependencies |
| Cancel behavior | Partial output preserved with "cancelled" marker | User-friendly |