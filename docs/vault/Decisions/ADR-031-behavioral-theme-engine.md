---
title: Behavioral Theme Engine and Neutral Signal Instrumentation
type: decision
tags:
- type/decision
- domain/ui
- domain/training
- status/draft
created: 2026-06-19
updated: 2026-06-19
aliases:
- Behavioral Theme Engine
source: agent
---

# Behavioral Theme Engine and Neutral Signal Instrumentation

## Status

proposed

## Context

The anvil web UI supported exactly two appearances (dark/light) selected by a
single toggle that swapped color tokens. Feature `015-theme-engine` requires
*behavioral* themes — named presentation systems that change palette,
typography, motion, layered effects, and the **semantic mapping between live
training state and what the user sees** (e.g. "Forge" rendering loss as cooling
metal, "Old Growth" rendering training instability as CRT degradation). The two
provided demo files (`anvil_dashboard_demo.html`, `oldgrowth_tui_crt_demo.html`)
define the behavioral intent. This must layer on top of — never regress — the
clean iOS-modern accessible default established in `004-frontend-refactor`
(which deliberately removed an earlier mandatory ANSI/CRT aesthetic).

## Decision

1. **Registry-driven, N-theme client engine** (vanilla ES6, no build step):
   `theme-registry.js` (self-registering theme modules), `theme-manager.js`
   (apply / persist / FOUC / lifecycle / multi-tab), `effect-level.js`
   (accessibility/visibility gating), `signal-bus.js` (single `SSESession` →
   neutral signals → active theme). Each theme is a self-contained module +
   CSS layer, so adding a theme needs no engine change (FR-015).

2. **Attribute model (backward-compatible)**: `data-theme` continues to carry
   the **mode** (`light`/`dark`) exactly as today — preserving `tokens.css`
   `[data-theme="light"]` and all existing `components.css` overrides untouched
   (guarantees SC-007 default parity). A **new** `data-skin` attribute carries
   the **theme id**; theme CSS layers key off `[data-skin="<id>"]`. This refines
   the planning contract's "`data-theme=<id>`" naming for zero-risk backward
   compatibility.

3. **Backend emits NEUTRAL signals; themes own their mapping.** The per-step
   carrier `progress_callback(step, loss)` is widened ONCE to a structured
   `CoreStepObservation(step, loss, tokens, grad_norm?)` (stdlib `NamedTuple` in
   `core/` to honor Article I; wrapped into a Pydantic `StepMetrics` at the
   service layer). The SSE `metrics` event gains `grad_norm` + `tokens_per_sec`
   (derived from a rolling sum of per-step `tokens` — the engines are unbatched
   and variable-length, so a `batch×ctx` formula is invalid). New neutral events:
   `divergence` (non-finite loss → raises `DivergenceError` to halt the run,
   mirroring `StopRequested`, and reconciles run status) and a periodic
   `milestone` marker (no artifact write). The "disturbance" instability metric
   is derived **client-side** in the Old Growth theme, never emitted by the
   backend.

4. **Accessibility is non-negotiable and centralized.** A single effect-level
   resolver combines OS reduced-motion / reduced-transparency, an in-app
   reduced-effects toggle, audio opt-in (off by default), and tab visibility.
   Expressive effects degrade before impairing interactivity; primary content
   meets WCAG AA in every theme/mode.

## Consequences

- **Easier**: adding themes (drop a JS module + CSS layer); systemic restyle via
  token edits; widgets are already token-reactive so they re-theme for free.
- **Harder / risk**: the one-time callback-signature widening touches the
  protocol, both engines, both backends, and the service closure (a single
  structural commit, zero behavioral delta to training math).
- **Behavior change for all users**: divergence (NaN/inf) now halts the run and
  marks it diverged, instead of training uselessly to completion — intentional,
  theme-independent (FR-030).
- The default experience is visually byte-identical for non-adopters (SC-007).

## Compliance

- Article I: `core/` stays stdlib-only (`CoreStepObservation` is a `NamedTuple`;
  Pydantic lives in the service layer).
- Article III: `grad_norm` is a read-only reduction; no RNG/order impact.
- Article IV: TDD for the backend slice (`tests/services/training/test_step_metrics.py`,
  `tests/api/test_training_sse_signals.py`) + an e2e system test
  (`tests/system/test_theme_engine.py`) for the JS engine.
- Article V/VII: threading unchanged; run-status reconciled through the service.
- Verified by `make lint`, `make typecheck`, `make test`, and the SC-001…SC-012
  QA matrix in `specs/015-theme-engine/quickstart.md`.
