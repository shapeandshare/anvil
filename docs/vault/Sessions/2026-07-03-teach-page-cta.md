---
title: 2026-07-03-teach-page-cta
type: session-log
aliases:
  - teach-page-cta
tags:
  - type/session-log
  - domain/ui
status: draft
source: agent
created: '2026-07-03'
updated: '2026-07-03'
---

# Session: Teach Page Onboarding & CTA Remediation

## Summary

The teach page (`/v1/teach`) had a dead initial state — all panels were `display:none`, leaving a blank main content area with no call to action. This session added empty-state guidance, flow continuity CTAs, progressive disclosure, and visual polish.

## Changes

### teach.html (anvil/api/templates/teach.html)

1. **Empty-state guidance card (US1)**: Added centered `section-card` with book icon, welcome message, numbered step list (Create → Train → Inspect), and "Create Session" button. Shown when no sessions exist, hidden when a session is created or selected.

2. **Active session action buttons (US2)**: Added "Start New Round" (primary CTA that focuses the round form), "View Rounds" (collapsible round history loaded from `/v1/teach/sessions/{id}/rounds`), and "Delete Session" (with `confirm()` dialog, red styling).

3. **Post-training CTA (US2)**: Added "Inspect This Round →" button in the SSE `complete` event handler that auto-fills the Inspect panel with the completed round's experiment ID and scrolls it into view via `showInspectWithRound()`.

4. **Progressive disclosure (US3)**: Compare panel starts hidden with placeholder text ("Complete at least 2 rounds to compare models side-by-side."). `updateComparePanelVisibility()` gates display on `completedRounds >= 2`, called from `loadSessionDetails()` and the SSE `complete` handler.

5. **Visual polish (US4)**: Added `--stagger-i` entrance animations (0–4) to all section cards, `didyouknow_banner` block override matching playground/learn-index pattern, learning-lesson banner CTA at top of main content, and `btn-accent` gradient class on the sidebar Create Session button.

6. **State tracking**: Added `completedRounds` variable incremented on SSE `complete`, reset on `selectSession()`.

### Tests (tests/browser/test_teach_ux.py)

New Playwright e2e tests (T013–T016): 9 tests covering empty state guidance, flow continuity CTAs, progressive disclosure, and visual polish.

### UX Gate

```text
$ uv run python3 scripts/ci/ux_lint.py anvil/api/templates/teach.html
anvil/api/templates/teach.html ✓
1 files · S4:0 · GATE: PASS
```

## Key Patterns Reused

- `section-card`, `section-card--banner` from `archetypes.css`
- `btn-primary`, `btn-secondary`, `btn-accent` from `archetypes.css`
- `--stagger-i` entrance animation pattern from playground/learn-index
- `didyouknow_banner` block from `base.html`
- `apiFetch()` + existing SSE/session CRUD infrastructure

## Linked Entities

- Spec: `specs/064-teach-page-cta/spec.md`
- Plan: `specs/064-teach-page-cta/plan.md`
- Tasks: `specs/064-teach-page-cta/tasks.md`