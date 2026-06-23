---
title: 018 Theme Engine - research
type: research
tags:
  - type/spec
spec-refs:
  - docs/vault/Specs/018 Theme Engine/
related:
  - '[[018 Theme Engine]]'
created: ~
updated: ~
---
# Research: Theme Engine (Behavioral Themes)

**Phase 0 output** — resolves all unknowns from the plan's Technical Context. Each section gives a Decision, Rationale, and Alternatives Considered. Decisions favor a backend that emits **neutral signals** and themes that **own their mapping**, with full constitution compliance.

> **Note**: An Oracle architecture consultation was attempted for the signal-instrumentation sub-problem (R1–R6) but the consultation session was unavailable at planning time. The decisions below were derived directly from the verified codebase facts and the constitution; they are recorded here explicitly so they can be reviewed and, if desired, re-validated via `/speckit.analyze` or a later Oracle pass.

---

## R1 — Per-step signal carrier: structured `StepMetrics` value object

**Decision**: Replace the brittle `progress_callback(step: int, loss: float)` with a single structured carrier. The **pure engine (`core/`) emits a plain stdlib `NamedTuple`** of primitives (`step: int`, `loss: float`, `grad_norm: float | None`); the **service layer wraps it into a Pydantic `BaseModel` `StepMetrics`** living in `anvil/services/training/step_metrics.py`. The compute-backend protocol type (`services/compute/protocol.py`) carries the stdlib tuple from engine → backend, and the service closure constructs the `BaseModel` before serialization.

**Rationale**:
- `grad_norm` is only knowable *inside* the training loop after `backward()`; it cannot be derived downstream. So the carrier MUST widen at the engine boundary.
- A single structured object is future-proof and avoids kwargs creep. The constitution requires Pydantic `BaseModel` for structured data.
- **Article I conflict resolved**: a Pydantic model in `core/` would add a third-party dependency to the zero-dep engine. Splitting the carrier — stdlib `NamedTuple` at the `core/` boundary, `BaseModel` at the service layer — keeps `core/` pure while satisfying the BaseModel rule where structured data actually crosses the service/API boundary.
- Per Article X §10.9, the signature change is a single structural commit with zero behavioral delta to training math.

**Alternatives considered**:
| Alternative | Rejected because |
|---|---|
| Optional kwargs `progress_callback(step, loss, *, grad_norm=None, tokens=None)` | Violates "structured data = BaseModel"; grows unbounded as signals are added; weaker typing. |
| Pydantic `BaseModel` directly in `core/` | Violates Article I (zero-dep core engine). |
| Compute everything outside the engine | Impossible for `grad_norm` (needs in-loop gradient access). |
| Separate side-channel callback for extra signals | Doubles the thread→asyncio marshalling surface; harder to keep ordered with the main metrics stream. |

---

## R2 — `grad_norm` in the pure stdlib engine

**Decision**: Compute `grad_norm` in the **torch engine** (`core/torch_engine.py`). **Sampling point (verified):** after `loss.backward()` (`:493`) and before the next iteration's `optim.zero_grad()`, as `sqrt(Σ p.grad.norm()²)` over `model.parameters()`. **No gradient clipping exists anywhere** in the codebase (grep-confirmed), so there is a single, un-clipped norm — no pre/post-clip ambiguity. In the **pure stdlib engine** (`core/engine.py`), emit `grad_norm = None` for v1 (graceful absence) unless a short, well-commented global-norm loop is added without obscuring the educational path. Themes MUST degrade gracefully when `grad_norm is None`.

**Rationale**:
- Article II prioritizes educational clarity in `core/`; bolting a norm accumulator into the hand-written autograd risks noise. Optional/`None` keeps the teaching path clean.
- **Per-step sampling is acceptable** (no need to throttle): the torch loop already calls `loss.item()` every step (`:497`), forcing a device→host sync each step, and the loop is a slow per-token Python loop — an extra norm reduction is negligible relative to existing cost.
- Article III (determinism) safe: `grad_norm` is a read-only reduction over existing grads; it touches neither RNG (`torch.manual_seed(42)` at `:449`) nor iteration order.
- Article IX (pit of success): a stdlib run simply lacks the instability-derived "disturbance" precision; Old Growth still functions from loss volatility alone (see R6). No crash, no block.

**Alternatives considered**: Mandatory grad_norm in both engines (rejected — Article II clarity cost in the teaching engine); never computing grad_norm (rejected — Old Growth's core mapping wants instability, and torch makes it nearly free); sampling every N steps (rejected as unnecessary — the loop already syncs per step).

---

## R3 — Divergence / NaN: dedicated SSE event

**Decision**: Detect divergence in the **service closure** (`services/training/training.py`) via `math.isnan(loss) or math.isinf(loss)` (and optionally a `grad_norm` explosion threshold), surface it as a **new named SSE event `divergence`** `{step, reason}` (NOT a boolean on `metrics`), and **halt the run by raising `DivergenceError`** from the progress closure. Add `divergence` to the SSE route's terminal break set and reconcile persisted run status to a terminal `diverged` state.

**Rationale (verified against code)**:
- **The engines do NOT break on NaN** (`core/torch_engine.py:469-501`, `core/engine.py:401-431` have no `isnan` guard). Merely emitting an event would leave training spinning in the background thread. The codebase already provides the correct halt mechanism: the progress closure **raises `StopRequested`** (`training.py:280-281`) which propagates through `backend.run` and is caught at `:357`. `DivergenceError` mirrors this exactly — raise → engine loop unwinds → the `complete` block (`:370`) is skipped.
- **The SSE route only breaks on `("complete","error")`** (`api/v1/training.py:614`). A `divergence` event therefore would NOT end the stream unless added to that tuple — so the task explicitly adds it.
- **Run status**: success finalization runs in `on_complete` (`training.py:383`), which is skipped on the exception path; without reconciliation the run's persisted status would dangle. Divergence must set a terminal status through the service/repository (Article VII), not the route.
- The client `SSESession` dispatches by **named event**, so a discrete `divergence` lets themes register a distinct response (FR-012). Neutral signal: backend says "loss is NaN at step N"; themes decide expression.

**Alternatives considered**: a `diverged: bool` field on every `metrics` payload (rejected — bloats the hot path, awkward one-shot); emitting `divergence` WITHOUT halting (rejected — training keeps running, wasting compute and contradicting the "diverged run" contract); detecting in the engine (rejected — presentation/observation concern belongs at the service boundary; keeps `core/` minimal).

---

## R4 — `tokens_per_sec` derivation  *(CORRECTED after code review)*

> **Superseded decision**: an earlier draft proposed `tokens_per_sec = steps_per_sec × batch_size × context_len` in the service closure with no engine change. **Code review invalidated this** — see below.

**Decision**: Carry the **actual tokens processed per step** as a new `tokens: int` field on `CoreStepObservation`, and derive `tokens_per_sec` in the service closure from a **rolling sum of `tokens` ÷ window-elapsed**. This requires a (small) engine change, but it rides the already-planned `progress_callback` → `CoreStepObservation` signature widening, so it adds no new structural cost.

**Rationale (verified against code)**:
- **There is NO `batch_size`** anywhere in config or the engines (grep-confirmed; README hyperparams list none). The proposed formula references a value that does not exist.
- **The engines are unbatched and variable-length**: each step processes one document, and tokens/step `= n = min(block_size, len(tokens)-1)` (`core/torch_engine.py:474`, `core/engine.py:406`) — `n` varies per document. So `context_len` (≈`block_size`) would systematically **overestimate** throughput for shorter documents.
- The only correct, exact value is the engine-reported `n`. Summing `n` over the rolling window ÷ elapsed gives true tokens/sec. Edge cases that would otherwise complicate this (grad accumulation, partial/variable batches) **do not apply** — none exist.

**Alternatives considered**: keep the config-formula (rejected — wrong: no batch_size, variable n); approximate as `steps_per_sec × block_size` with a caveat (rejected — knowingly inaccurate when a correct value is one int away); compute client-side (rejected — client lacks per-step token counts).

---

## R5 — "Quench" beat event scope for v1  *(naming corrected after review)*

**Decision**: For v1, **do not introduce periodic checkpointing** (no model-artifact writes). Map the themes' discrete "quench" response onto two neutral moments: (1) run **completion/export** (already emits `complete`), and (2) a lightweight periodic **`milestone`** `{step}` marker event emitted by the service closure every N steps (no artifact write). The marker is a **delivered** part of the signal surface. Real periodic model checkpointing remains explicitly out of scope.

**Rationale**:
- Spec scope is a theme engine, not a training-durability feature. Adding real periodic checkpoint artifact writes would be a large, orthogonal change to the training loop (Article X §10.9: don't combine).
- **Naming (least-surprise)**: the event was originally named `checkpoint`, but emitting a `checkpoint` event when **no checkpoint artifact is written** would mislead future maintainers. Renamed to **`milestone`** — a neutral periodic-progress beat. Themes still map it to the "quench" flash; the backend stays honest and signal-agnostic.
- A cadence-based neutral marker is trivially emitted from the service closure (which already has `step` and `_num_steps`).

**Alternatives considered**: name it `checkpoint` (rejected — implies a saved artifact that doesn't exist); full periodic checkpointing in scope (rejected — orthogonal, large, risk to training loop); no quench beat at all (rejected — weakens Forge fidelity per FR-027). Final: completion-as-quench is guaranteed AND a neutral `milestone` cadence marker is delivered.

---

## R6 — "Disturbance" derivation: split responsibility

**Decision**: The backend emits only **neutral primitives** (`loss`, `grad_norm`, `divergence` event). The **Old Growth theme module computes its own "disturbance"** client-side from the neutral stream — combining normalized `grad_norm` (when present) with **loss volatility** (rolling standard deviation / spike detection over the loss series it already receives), and pinning to max on a `divergence` event.

**Rationale**:
- Honors "themes own their mapping" (FR-011) and "backend stays signal-agnostic": "disturbance" is a theme-specific interpretation, not a universal signal, so it MUST NOT live server-side.
- Works even when `grad_norm is None` (stdlib runs): volatility alone still drives disturbance (graceful degradation, R2).
- Keeps the SSE payload lean and reusable by other themes that may interpret the same primitives differently.

**Alternatives considered**: server-side `disturbance` field (rejected — bakes one theme's mapping into the neutral backend, violating FR-011 and the neutrality principle).

---

## R7 — Theme registry, persistence, and FOUC for N themes (client architecture)

**Decision**: Generalize the existing binary mechanism into a **client-side theme registry** (`static/js/theme/theme-manager.js`). Each theme is a self-contained module under `static/js/themes/<id>.js` declaring: `id`, `displayName`, `previewHint`, `modes` (`light`/`dark`/`single`), its CSS layer file under `static/css/themes/<id>.css`, and an optional `mapping(signalBus)` expressive hook. Persistence reuses `localStorage` (extend the existing `theme` key to store `{themeId, mode}`; tolerate/migrate the legacy `'dark'|'light'` string). The **FOUC guard** in `base.html`'s inline `<head>` script is extended to read the stored `themeId`, set `data-theme=<id>` (and `data-mode`) before first paint, and inject the theme's CSS-layer `<link>`. A `signal-bus.js` subscribes to the single `SSESession` and re-publishes neutral signals to the active theme's mapping; switching themes mid-run rebinds the mapping to the live bus without dropping the EventSource (FR-026).

**Rationale**:
- Matches verified facts: theme state lives in `localStorage['theme']` + `data-theme` on `<html>`; the nav bar (with the toggle) survives client-side `<main>` swaps; widgets already react to CSS tokens via `getComputedStyle`, so a token-swapping theme layer needs **no per-widget change**.
- Self-contained theme modules + CSS layers deliver FR-015/SC-009 (add a theme without touching the engine).
- The single `SSESession` + `signal-bus` indirection keeps "one connection, many consumers" and satisfies mid-run switching.

**Alternatives considered**: server-side theme registry / context processor (rejected — spec Assumption keeps selection client-local for v1; `app.py` has no context processor today); per-theme separate EventSource (rejected — wasteful, and `adam.js`'s unused second EventSource shows that pattern is already a liability).

---

## R8 — Accessibility & graceful degradation gating

**Decision**: The theme manager centralizes an **effect-level resolver** combining: OS `prefers-reduced-motion`, OS `prefers-reduced-transparency`, an in-app reduced-effects/maximum-legibility toggle, audio opt-in (default off), and `document.visibilityState` (throttle/pause when hidden). Themes query this resolver to decide whether to run continuous effects, and CSS layers include `@media (prefers-reduced-motion: reduce)` resets mirroring the existing global reset in `tokens.css`. Primary content/controls are always rendered from base, legible tokens regardless of theme.

**Rationale**: Satisfies FR-016–FR-021 and the `004` accessibility commitment; reuses the existing reduced-motion/reduced-transparency CSS patterns already in `tokens.css`.

**Alternatives considered**: per-theme ad-hoc a11y handling (rejected — inconsistent, easy to regress; centralizing guarantees SC-005/SC-006 across all themes).

---

## Summary of Architecture Decisions

| Area | Decision | Impact |
|---|---|---|
| Signal carrier (R1) | stdlib tuple in `core/` → Pydantic `StepMetrics` in service layer | Article I preserved; one structural commit |
| grad_norm (R2) | torch-engine exact, sampled post-`backward()` (no clipping → single norm); stdlib `None` + graceful fallback; per-step sampling fine | Educational core stays clean; determinism safe |
| Divergence (R3) | service-side `isnan/isinf` → `divergence` event **+ raise `DivergenceError` to halt** + add to route break set + reconcile run status | Distinct discrete-event response; run actually stops |
| tokens_per_sec (R4) | **CORRECTED** — carry per-step `tokens=n` on `CoreStepObservation`; rolling Σ tokens ÷ elapsed (no `batch_size` exists; n is variable) | Exact; rides the planned signature change |
| Quench beat (R5) | completion-as-quench + delivered neutral **`milestone`** marker (renamed from `checkpoint`); no real periodic checkpointing | Scope contained; honest naming |
| Disturbance (R6) | computed **client-side** in Old Growth theme from neutral primitives | Backend stays signal-agnostic; FR-011 honored |
| Client architecture (R7) | registry + self-contained theme modules + extended FOUC guard + single signal bus | FR-015/SC-009; no per-widget change |
| Accessibility (R8) | centralized effect-level resolver + CSS reduced-motion resets | FR-016–021; `004` decision preserved |
| ADR | Record "behavioral theme engine + neutral signal instrumentation" in `docs/vault/Decisions/` | Constitution Additional Constraints |

**All Technical Context unknowns resolved. No NEEDS CLARIFICATION remain. Ready for Phase 1.**
