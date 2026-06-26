---
title: "Session: 015-theme-engine Implementation"
type: session-log
tags:
- type/session-log
- domain/ui
- domain/training
- domain/architecture
created: 2026-06-20
updated: 2026-06-20
aliases:
- Session: 015-theme-engine
source: agent
---

# Session: 015-theme-engine Implementation

**Date**: 2026-06-20
**Branch**: 015-theme-engine

## Summary

Full Spec Kit flow for behavioral theme engine feature: specify → clarify → plan → tasks → analyze (×2 with all findings addressed) → implement. Delivered the complete theme-selection and neutral-signal-instrumentation system across all planned phases. Shipped as PR #86, merged to main.

## Key Deliverables

- **Theme engine** (vanilla JS, no build step): registry, manager (apply/persist/legacy-migration/FOUC/multi-tab/picker), effect-level resolver, signal bus. Backward-compatible `data-theme`(mode)+`data-skin`(theme-id) attribute model.
- **Four themes**: default (unchanged), forge (dark, ember/warm), oldgrowth (single-mode CRT, mono), aurora (dual-mode). Self-contained CSS layers + JS modules.
- **Neutral signal instrumentation** (TDD, 15 tests): `CoreStepObservation`→`Pydantic StepMetrics`; widened `metrics` (grad_norm, exact tokens_per_sec via `ThroughputTracker`); new `divergence` event (halts NaN runs via `DivergenceError`, reconciled status) and `milestone` cadence marker; engines/protocol/backends/service/route/sse.js wired.
- **Expressive mappings**: forge (loss→cooling-metal, throughput→glow, quench/divergence states), oldgrowth (client-derived disturbance from grad_norm+loss volatility, scanline overlay), aurora (loss→calm, throughput→flow). All gated by effect level.

## Related

- [[Specs/018 Theme Engine/018 Theme Engine|018 Theme Engine]] — feature specification
- [[Decisions/ADR-031-behavioral-theme-engine|ADR-031: Behavioral Theme Engine]] — architecture decision record
- [[Design/Design|Design]] — UI design system including theme engine
- [[Reference/theme-creation-guide|Theme Creation Guide]] — theme authoring reference
- **Accessibility**: centralized reduced-motion/effects/visibility gating, picker toggles, reduced-motion resets in every theme layer.
- **Spec artifacts**: `docs/vault/Specs/018 Theme Engine/` (spec, plan, research, data-model, 3 contracts, tasks, checklist) + **ADR-031**.

## Key Discoveries

1. **Engines are unbatched and variable-length**: `core/torch_engine.py` and `core/engine.py` process one document per step with `n = min(block_size, len(tokens)-1)` tokens. There is NO `batch_size` anywhere. This invalidated the initial `tokens_per_sec = steps_per_sec × batch_size × context_len` formula — corrected to a rolling sum of per-step `tokens` via `ThroughputTracker`.

2. **No gradient clipping exists**: The single `grad_norm` after `backward()` is un-clipped — no pre/post-clip ambiguity.

3. **No NaN guard in engines**: Both engines happily train through NaN loss. Divergence detection must raise an exception from the callback to halt the run, mirroring the existing `StopRequested` pattern.

4. **No periodic checkpointing**: The "quench" beat in Forge maps to a neutral `milestone` marker (no artifact write), not a real model checkpoint.

5. **Pre-existing mypy baseline**: The repo has ~508 `mypy --strict` errors at HEAD (torch-unstubbed calls, missing type annotations in old modules). The gate is not actually green.

## Architecture Decisions (recorded in ADR-031)

- Tri-branch attribute model (`data-theme` for mode, `data-skin` for theme id) for zero-risk backward compatibility with `tokens.css` and `components.css`.
- Keyword-extras callback `progress_callback(step, loss, *, tokens=..., grad_norm=...)` over structured object — keeps 6 call sites valid unchanged while adding new signals.
- stdlib `NamedTuple` at the `core/` boundary; Pydantic `BaseModel` only in the service layer (Constitution Article I compliance).

## Remaining Work (audit/verification, needs browser)

- WCAG AA audit ✓ (computed from CSS tokens — all pass; one 4.09:1 warning on aurora light accent, OK for UI components)
- Vault audit, quickstart proof, SC QA matrix, e2e system test via CI
