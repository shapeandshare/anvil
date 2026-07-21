---
title: 'ADR-050: Navigation CTA Elements Rendered as <button>, Overriding ux-rules.md S4'
type: decision
tags:
  - type/decision
  - domain/ui
  - domain/governance
created: '2026-07-21'
updated: '2026-07-21'
source: agent
code-refs:
  - docs/ux-rules.md
  - anvil/api/templates/archetypes/models.html
  - anvil/api/templates/archetypes/model_detail.html
  - anvil/api/templates/teach.html
  - anvil/api/templates/datasets.html
  - anvil/api/templates/operations.html
  - anvil/api/templates/config.html
  - anvil/api/templates/data_add.html
  - anvil/api/templates/data_sources.html
  - anvil/api/templates/dataset_curation.html
  - anvil/api/templates/archetypes/training.html
  - anvil/api/templates/archetypes/playground.html
  - anvil/api/templates/archetypes/experiment.html
  - anvil/api/templates/archetypes/content_library.html
aliases: 'ADR-050: Navigation CTA Elements Rendered as button, Overriding ux-rules.md S4'
---
# ADR-050: Navigation CTA Elements Rendered as `<button>`, Overriding `ux-rules.md` S4

## Status

Accepted

## Context

User feedback (collected via the in-app annotation tool, 3 separate reports) flagged 15 elements as "wrong button type — its not ios and has a live hyperlink": the "Learn More →" / "Learn Why →" banner CTAs across 13 templates, and the Models-table "View" / "Inference" action links.

All of these elements are semantically navigation (they carry a real destination URL) and were correctly implemented per `docs/ux-rules.md` as `<a href="...">` styled with `.btn` classes:

- `[S4]` `(lint)`: *"Actions use `<button>`; navigation uses `<a>`."*
- `[S2]`: *"Links are real `<a>` (support Cmd/Ctrl-click, middle-click)."*

The reporter's complaint is about the **hyperlink affordance leaking through the button-shaped visual treatment** — hovering shows the destination URL in the browser status bar, right-click offers "Open in new tab" / "Copy link", and the element is a real anchor despite reading visually as an iOS filled button. This breaks the illusion of a native app interface, which is this project's stated design goal (ADR-006: iOS Design Overhaul).

The user was presented with the S4/S2 tradeoff explicitly and chose to override it for these specific elements, accepting the loss of Cmd/Ctrl-click and middle-click support in exchange for a consistent button affordance.

### A costly implementation mistake

The first implementation pass converted `<a href="...">` to `<button type="button" onclick="window.location.href='...'">`. This project's CSP header (`anvil/api/app.py`, `security_headers_middleware`) is `script-src 'self' 'nonce-{nonce}'` with **no `'unsafe-inline'`** for any page outside `/docs`, `/redoc`, `/openapi.json`. Per the CSP spec, a nonce on `script-src` governs `<script>` elements only — it does **not** enable inline event-handler attributes (`onclick=`, `onerror=`, etc.). Every converted button was therefore silently non-functional: clicking did nothing, with a CSP violation logged to the console.

This exact failure mode was already documented in this vault (see `[[Discoveries/csp-nonce-does-not-cover-inline-onclick-handlers]]`) from an earlier incident on `operations.html`. The mistake was caught by running the real Playwright browser suite against a live server rather than trusting static syntax checks (`node --check`, `ux_lint.py`) — neither tool understands CSP-vs-`onclick` interaction. The fix was reverted to the established codebase pattern: `addEventListener` wired in the page's nonce-protected `<script>` block, using either a static `staticBtnMap`-style dispatch table (per-page, single CTA) or a delegated click handler with `data-nav-url` attributes (dynamically-rendered rows, e.g. the models table and `model_detail.html`'s Inference/Continue Training buttons).

## Decision

1. **Scope of the override**: ONLY the 15 originally-flagged elements (13 "Learn More"/"Learn Why" banner CTAs + 2 models-table action links) plus, for consistency, `model_detail.html`'s "Inference"/"Continue Training" buttons (same visual pattern, same page family) are converted from `<a href="...">` to `<button type="button">`. No other navigation `<a>` in the codebase is affected — external links (`target="_blank"`, e.g. "View on HF ↗", "Open in MLflow →"), prev/next lesson navigation, and general "Back to X" links remain `<a>` per `ux-rules.md` S4/S2, since they were not part of the feedback and converting them would be unjustified scope creep (Constitution Article XI, Simplicity First).
2. **Navigation MUST be implemented via `addEventListener`, never inline `onclick=`.** This project's CSP forbids inline event-handler attributes on every authenticated page. Two established sub-patterns apply, matching existing codebase convention (`operations.html`):
   - **Static single CTA** (one button per page, static destination): give the `<button>` an `id`; wire a `.addEventListener('click', ...)` call in the page's nonce-protected script block, either standalone or via a `staticBtnMap`-style dispatch table.
   - **Dynamically-rendered rows** (server/JS-rendered per-item action buttons, e.g. table rows): render `data-nav-url="..."` (not `href`) on the button; use a single delegated `click` listener on the parent container that reads `data-nav-url` and does `window.location.href = ...`.
3. **The mechanical `ux_lint.py` gate does not, and will not, catch this class of bug.** It has no notion of CSP header configuration and cannot statically prove an `onclick=` attribute is dead code. Verification for any new/changed CSP-relevant interactive element MUST include a real browser click-through (Playwright, against a running server) — static syntax/lint checks are necessary but insufficient.

## Consequences

### Easier

- CTA buttons now read consistently as iOS filled buttons with no residual hyperlink affordance (no status-bar URL preview, no "Open in new tab" context menu item) — directly resolves the reported feedback.
- The existing `addEventListener`/`data-nav-url` delegation pattern (already used by `operations.html`, `models.html`'s `eval-btn`) is now the single consistent idiom for all button-styled navigation across the app.

### Harder

- These 16 elements no longer support Cmd/Ctrl-click or middle-click to open in a new tab — an explicit, accepted, and narrowly-scoped regression in browser-native behavior, not present for any other link in the app.
- `ux-review` (the AI deep-pass checker) will flag these elements as S4/S2 violations on every run, since it has no mechanism to know this override was deliberate. This is intentional — the finding remains a visible, per-file record of the exception rather than a silent allowlist. A future enhancement could add file-scoped `ux-lint:allow` annotations (already supported by `ux_lint.py`'s suppression syntax) if the AI-review noise becomes a maintenance burden.
- Any future navigation CTA added to this codebase must default back to `<a href>` per `ux-rules.md` S4/S2 unless it matches the exact "button-styled CTA with reported hyperlink-affordance complaint" pattern this ADR documents — this is a narrow, feedback-driven exception, not a new house style.

## Dependencies

- Amends the "UI compliance (MUST)" constraint in `.specify/memory/constitution.md` (Additional Constraints section) — adds a narrow, ADR-recorded exception mechanism to the previously-absolute "never dilute the rule" clause. Constitution version bumped 1.8.0 → 1.9.0.

## Compliance

- `make ux-lint` passes (S4:0) on all touched templates — the mechanical gate does not check semantic `<a>`-vs-`<button>` element choice, only the `<div>`/`<span>`-click-handler subset.
- Real Playwright browser tests (`tests/browser/test_navigation_smoke.py::TestLearnMoreButtons`, `tests/browser/test_models_eval_modal.py`, plus an ad-hoc verification script for `model_detail.html`) confirm: element is a `<button>` tag, click navigates to the correct destination, zero console errors (including zero CSP violations).
- `tests/browser/test_training_sse_wiring.py::test_wizard_steps_and_tabs_render` (pre-existing) was updated to assert on the button `id` instead of the now-removed `a[href*="training-loop"]` selector.

## See Also

- [[Decisions/ADR-006-ios-theme-overhaul|ADR-006: iOS Design Overhaul]]
- [[Decisions/ADR-038-ux-rules-integration|ADR-038: UX Rules Integration]]
- [[Discoveries/csp-nonce-does-not-cover-inline-onclick-handlers|CSP nonce does not cover inline onclick handlers]]
- [[Decisions/README|Decisions]]
