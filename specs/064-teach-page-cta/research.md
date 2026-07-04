# Research: Teach Page Onboarding & CTA Remediation

**Phase**: Phase 0 — Outline & Research  
**Date**: 2026-07-03  
**Status**: Complete — no NEEDS CLARIFICATION identified

## Overview

This feature is entirely frontend UX work on an existing, well-understood codebase. No technical unknowns require resolution. The research below covers pattern confirmation and design system compliance checks.

## Pattern Research

### Pattern: Empty-State Guidance Card

| Aspect | Finding |
|--------|---------|
| **Decision** | Centered `section-card` in the main column with icon, welcome message, numbered steps, and "Create Session" button |
| **Rationale** | Matches the existing `section-card` pattern used throughout all archetype pages (`playground.html`, `learn-index.html`, `training.html`). No new containers or layout patterns needed. |
| **Alternatives considered** | Tooltip/pointer from sidebar (too indirect); modal/popover (overly disruptive); blank page with sidebar-only CTA (current broken state) |
| **Codebase references** | `playground.html` line 33 — `section-card` with `--stagger-i`; `learn-index.html` line 11 — intro paragraph with `page-intro` class |

### Pattern: Post-Training CTA

| Aspect | Finding |
|--------|---------|
| **Decision** | A button inserted into the `training-complete` div after SSE `complete` event, calling `inspectRound()` with pre-filled experiment ID |
| **Rationale** | The SSE handler already manipulates the DOM (`training-complete` display, `training-status-text`). Adding a button there is the simplest extension — no new event wiring needed. |
| **Alternatives considered** | Separate CTA panel (over-engineered for a single button); auto-navigate to inspect (takes agency away from user) |
| **Codebase references** | `teach.html` line 361-368 — existing `complete` event handler; `playground.html` line 75 — Generate button pattern |

### Pattern: Progressive Disclosure (Compare Panel)

| Aspect | Finding |
|--------|---------|
| **Decision** | Hide Compare panel via JS on page load; show it when `loadSessionDetails()` detects 2+ rounds |
| **Rationale** | The Compare panel is an independent panel (not inside a conditional block). The simplest approach is JS visibility control matching the existing pattern used for `active-session-panel`, `round-panel`, `inspect-panel`. |
| **Alternatives considered** | Server-side conditional render (requires backend change — violates frontend-only scope); always-shown with placeholder (less clean UX) |
| **Codebase references** | `teach.html` lines 52, 63, 102 — existing `display:none` conditional pattern for panels |

### Pattern: Did You Know? Banner

| Aspect | Finding |
|--------|---------|
| **Decision** | Extend the `didyouknow_banner` Jinja2 block in `teach.html`, matching `playground.html` and `learn-index.html` |
| **Rationale** | `base.html` defines `{% block didyouknow_banner %}{% endblock %}` — the teach page simply doesn't override it. Adding the block override gives zero-effort parity with other pages. |
| **Alternatives considered** | Inline HTML at end of content (duplicates the existing block pattern — violates Reuse First) |
| **Codebase references** | `base.html` — `didyouknow_banner` block; `playground.html` lines 484-492 — block override with JS-driven content; `learn-index.html` lines 143-152 — same pattern |

### Pattern: Staggered Entrance Animations

| Aspect | Finding |
|--------|---------|
| **Decision** | Add `--stagger-i: N` inline styles to each `section-card` div, matching the existing archetype pattern |
| **Rationale** | The `--stagger-i` custom property is already supported by `base.css` or `archetypes.css` (used throughout). It's a one-line addition per card. |
| **Alternatives considered** | Custom CSS animations (creates a second animation system — violates Reuse First) |
| **Codebase references** | `playground.html` lines 33, 82, 112 — `--stagger-i: 0`, `--stagger-i: 1`, `--stagger-i: 2` |

## Design System Compliance

All changes must conform to:

| Document | Key Constraints |
|----------|----------------|
| `DESIGN.md` | iOS modern design language, `--surface`/`--accent` tokens, `--font-body`/`--font-mono`, 44px touch targets, `--radius` card corners |
| `tokens.css` | Referenced via CSS custom properties only — no raw hex values outside token.css |
| `archetypes.css` | `.btn`, `.btn-primary`, `.section-card`, `.section-card__header`, `.section-card__title` — existing component classes to use |
| `docs/ux-rules.md` | S4: no `<div onClick>`, no `outline:none`, no `|safe` on user data; S3: form labels required, `aria-live` for streaming, empty state handling |

## Conclusion

No NEEDS CLARIFICATION remain. All patterns are confirmed via codebase references. Implementation is straightforward modification of a single file using existing, well-established patterns.