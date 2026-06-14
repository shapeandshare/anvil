# Research Findings: Learning Content Enrichment

**Phase**: 0 (Research) | **Date**: 2026-06-13 | **Plan**: [plan.md](plan.md)

## Research Method

Three parallel background agents conducted exhaustive analysis:

1. **Agent 1** — CSS & archetype patterns (`.specify/extensions/git/` + templates + static assets)
2. **Agent 2** — Engine backprop & optimizer state support (`engine.py`, `autograd.py`, `inference.py`, `training.py`)
3. **Agent 3** — Widget framework patterns (`scroll-scene.js`, 5 widget JS files, `concept.html`, `router.py`)

---

## Findings

### 1. Computation Graph Format

**Decision**: Extend existing `forward_graph()` to include `.grad` and `_local_grads`.

**Rationale**: The `Value` class (`microgpt/core/autograd.py`) defines `__slots__ = ("_children", "_local_grads", "data", "grad")`. The existing `InferenceService.forward_graph()` (inference.py:330-401) already traverses `_children` via DFS to build `{nodes, edges}`. Adding two fields per node is ~3 lines of code.

**Current node shape** (in `forward_graph()`):
```python
{"id": str, "op": str, "label": str, "value": float, "depth": int}
```

**Target node shape** (for autograd lesson):
```python
{"id": str, "op": str, "label": str, "value": float, "grad": float,
 "local_grads": [float, ...], "depth": int}
```

**Caveat**: `.grad` is 0 unless `backward()` is called. A separate `backward_graph()` endpoint is needed that runs forward → computes loss → calls `loss.backward()` → then traverses. This prevents breaking the existing forward-only `forward_graph()`.

### 2. Optimizer State Capture

**Decision**: Modify `train()` to expose m/v buffers; add `optimizer_state` SSE event type.

**Rationale**: Adam buffers `m` and `v` are created as `[0.0] * len(model.params)` in `engine.py:233-237` but are local variables — they die when `train()` returns. Three approaches were considered:

| Option | Pros | Cons |
|--------|------|------|
| A: Return m/v from `train()` | Simplest code change | Only captures final state, not trajectory |
| B: Add callback for per-step snapshots | Captures full trajectory | ~20 lines new code; more complex |
| C: Query PyTorch `optim.state_dict()` | Works for GPU path | Only available post-training; torch dependency |

**Chosen**: Option B (callback). Add an `optimizer_state_callback` parameter to `train()`. The `TrainingService.progress_callback` (training.py:95-106) already streams per-step events via SSE — extend it to include an `optimizer_state` event type when callback is provided.

**PyTorch constraint**: The `torch_engine.py` GPU path uses PyTorch's internal Adam. For GPU-trained models, optimizer state can only be queried post-hoc via `optim.state_dict()`. CPU training (the default) will be the primary source for optimizer visualization.

### 3. Widget Framework Pattern

**Decision**: Follow the existing 5-widget pattern exactly.

**Rationale**: All 5 existing widgets (tokenization, embedding, attention, sampling, training-loop) follow an identical pattern:

```javascript
function Widget(container) {
  this.container = container;    // DOM element to render into
  this._data = null;            // cached fetched data
  this._debounceTimer = null;   // 250ms debounce
  this._render();               // build HTML + bind events
}
Widget.prototype._render = function() { /* build DOM, cache refs, bind listeners */ };
Widget.prototype._fetch = function(param) { /* POST to /v1/inference/* */ };
Widget.prototype._renderOutput = function(data) { /* update DOM with data */ };
```

**Registration checklist** (exact same across all 5 existing lessons):
1. Create widget JS file in `static/js/widgets/`
2. Add `<script>` tag + `WIDGET_CLASSES` entry in `concept.html`
3. Define step array in `router.py`
4. Add route handler in `router.py`
5. Add entry to `LEARNING_ARC`

**Key insight**: Widgets are instantiated TWICE per step — once in the right narrative panel (persistent instance cached in `widgetInstances[key]`) and once in the left visual panel (fresh instance each step change).

### 4. Demo Model Fallback

**Decision**: All new lesson widgets call `load_model(None)` to get the demo model.

**Rationale**: The existing `InferenceService.load_model(None)` (inference.py:186-225) lazy-provisions a demo model via `DemoModelProvider`. The demo model is trained on a tiny corpus (11 sentences) with `n_embd=16, n_head=4, n_layer=1`. This ensures all widgets work immediately without requiring the user to train a model.

### 5. Progressive Script Reuse Strategy

**Decision**: Reuse shared helpers from `engine.py` but implement unique per-stage logic.

**Rationale**: Constitution Article II requires each script to "demonstrate the GPT algorithm one component at a time." The scripts should show the incremental build-up. Shared helpers (data loading from `input.txt`, random seeding, loss printing) can be reused. The algorithmic components (linear layers, softmax, attention, multi-head assembly) should be explicitly defined in each script to show what's new.

**Script dependency chain**:
- `train0.py` (bigram counts) — ✅ exists, no changes
- `train1.py` (MLP + manual gradients) — uses `Value` class from autograd.py; implements 2-layer MLP with forward/backward by hand
- `train2.py` (autograd) — ✅ exists, no changes
- `train3.py` (attention) — implements single-head causal attention; uses `linear()`, `softmax()`, `rmsnorm()` from engine.py
- `train4.py` (multi-head GPT) — implements full single-layer GPT with multi-head attention; uses `GPT.forward()` from engine.py
- `train5.py` (Adam) — ✅ exists, delegates to engine.py

## Alternatives Considered

| Topic | Rejected Alternative | Why Rejected |
|-------|---------------------|--------------|
| Computation graph | Separate D3.js or dagre rendering library | Existing canvas-based GraphView class handles rendering; no new JS deps needed |
| Optimizer state | Pre-computed synthetic trajectory (Option A) | User chose Option B (real logged data from training) |
| Widget rendering | React/Vue components | Would break `concept.html` scroll-scene widget lifecycle; existing vanilla JS pattern is proven |
| New lesson pages | Custom page archetype per lesson | Existing `concept.html` + `scroll-scene.js` pattern handles all scroll-driven lessons; only FAQ might need a different layout |
| Progressive scripts | Single `engine.py` with configuration flags | Constitution Article II mandates incremental walkthrough files |

## Unresolved Questions

None. All design decisions are resolved by the spec, constitution, and research findings.
