---
title: 018 Theme Engine - quickstart
type: quickstart
tags:
  - type/spec
spec-refs:
  - docs/vault/Specs/018 Theme Engine/
related:
  - '[[018 Theme Engine]]'
created: ~
updated: ~
---
# Quickstart: Theme Engine

Two walkthroughs: (1) how a **user** selects and uses a behavioral theme; (2) how a **developer** adds a brand-new theme end-to-end — which is also the executable proof of FR-015 / SC-009 ("add a theme without touching the system").

---

## 1. User walkthrough — select & use a behavioral theme

1. Start anvil: `make run`, open `http://localhost:8080`.
2. In the nav bar, open the **theme picker** (replaces the old binary sun/moon toggle; the toggle is preserved as the light/dark control within a theme).
3. Pick **Forge**. The whole app re-presents instantly (no reload): warm palette, ember accents.
4. Go to the training dashboard and start a run. As loss falls, the loss curve cools (white-hot → steel-blue) and the sample output **resolves from noise**; throughput drives the forge-core glow and sparks.
5. Trigger a divergence (or run an unstable config): the sample **shatters back to noise** and the UI shifts to an alarm color.
6. Switch to **Old Growth** mid-run — the connection is NOT dropped; the CRT theme begins expressing the live **disturbance** (instability) immediately.
7. Navigate to a non-live page (e.g. Datasets): the theme's *look* applies, but no fabricated data effects play (it shows the at-rest identity).
8. Enable OS "Reduce Motion": continuous effects stop; text stays fully legible. Toggle in-app **maximum legibility**: glyph corruption/overlays are suppressed.
9. Click **Default** in the picker: the clean iOS-modern experience returns and persists across reload (no flash).

**Expected**: FR-001/002/003/004/006/007, FR-013, FR-016–019, FR-026 all observable in this flow.

---

## 2. Developer walkthrough — add a new behavioral theme ("Aurora") end-to-end

This proves SC-009: adding a theme requires **only** new files + one script include — no edits to `theme-manager.js`, `signal-bus.js`, `sse.js`, or any backend code.

### Step 1 — Create the CSS layer
`anvil/api/static/css/themes/aurora.css`:
```css
[data-theme="aurora"] {
  --bg: #05070d; --surface: #0b1020; --accent: #6ea8ff;
  --accent-green: #57e0c2; --font-display: var(--font-body);
  --flow: 0;            /* theme-private: driven by tokens_per_sec */
  --calm: 1;            /* theme-private: 1 − normalized loss */
}
@media (prefers-reduced-motion: reduce) {
  [data-theme="aurora"] * { animation: none !important; transition: none !important; }
}
```
(Must pass WCAG AA — contract `theme-tokens.md` T2.)

### Step 2 — Create the theme module
`anvil/api/static/js/themes/aurora.js`:
```js
ThemeRegistry.register({
  id: 'aurora',
  displayName: 'Aurora',
  previewHint: 'Loss as northern lights',
  modes: ['dark'],
  cssLayer: '/static/css/themes/aurora.css',
  mapping(signalBus, effectLevel) {
    const root = document.documentElement.style;
    const off = signalBus.on('metrics', (m) => {
      if (effectLevel.legible) return;                 // suppress under max-legibility
      const calm = m.loss != null ? clamp01(1 - m.loss / 9.8) : 1;
      root.setProperty('--calm', calm.toFixed(3));
      if (m.tokens_per_sec != null)
        root.setProperty('--flow', clamp01(m.tokens_per_sec / 700000).toFixed(3));
    });
    const offDiv = signalBus.on('divergence', () => root.setProperty('--calm', '0'));
    return () => { off(); offDiv(); };
  },
});
```

### Step 3 — Include the two files
Add to `base.html`'s theme asset block (the only edit, and it's data, not logic):
```html
<script src="/static/js/themes/aurora.js"></script>
```
(The CSS layer is loaded on demand by the manager when the theme is selected.)

### Step 4 — Verify
1. `make run`, reload. **Aurora** appears in the picker with its preview hint.
2. Select it; start a run; confirm `--calm`/`--flow` track loss/throughput.
3. Confirm reduced-motion + max-legibility suppress effects; default still pristine.
4. Confirm **no edits** were needed to `theme-manager.js`, `signal-bus.js`, `sse.js`, or backend.

**Expected**: SC-009 satisfied — a theme added with one CSS file, one JS module, one `<script>` include.

---

## 3. Backend signal slice — verify instrumentation (TDD)

```bash
# Red → Green for the widened signal surface (contract: signal-stream.md)
make test            # runs tests/api/test_training_sse_signals.py + tests/services/training/test_step_metrics.py
make typecheck       # mypy --strict: StepMetrics fully typed, grad_norm/tokens_per_sec float|None
make lint
```

**Expected**:
- `metrics` SSE payload includes `grad_norm` and `tokens_per_sec` (nullable); existing keys unchanged.
- Feeding `loss=NaN` emits a `divergence` event (`reason=loss_nan`) and no `complete`.
- A pure-stdlib-engine run emits `grad_norm: null` without error.
- Coverage ratchet (`fail_under`) not lowered.

---

## 4. Done criteria (maps to Success Criteria)

- [ ] ≥4 themes in the picker: Default, Forge, Old Growth, +1 new (SC-002, FR-028).
- [ ] Theme switch < 200ms, no reload, persists across reload, no FOUC (SC-001, SC-010).
- [ ] Each expressive theme shows distinct low/mid/high signal states (SC-003) and distinct discrete-event responses (SC-004).
- [ ] Reduced-motion → no continuous animation anywhere; max-legibility → AA contrast everywhere (SC-005, SC-006).
- [ ] Default unchanged for non-adopters (SC-007).
- [ ] No error/broken/frozen UI on unknown theme, missing/NaN signal (SC-008).
- [ ] New theme added without touching the engine (SC-009).
- [ ] Heaviest theme on live dashboard: no input lag/stutter; effects pause when tab hidden (SC-011, FR-031).
- [ ] Non-finite-loss run stops and shows diverged/failed within one update cycle, every theme (SC-012, FR-030).
