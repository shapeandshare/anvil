---
created: '2026-06-20'
status: reviewed
tags:
  - domain/ui
  - type/reference
title: Theme Creation Guide
type: reference
updated: '2026-06-20'
aliases:
  - Theme Creation Guide
related:
  - '[[Discoveries/canvas-particle-amplitude-vs-frequency-perceived-speed]]'
  - '[[Discoveries/signal-gated-decorations-invisible-at-rest]]'
  - '[[Discoveries/multi-layer-radial-gradient-rain-failure]]'
---
# Theme Creation Guide

The anvil behavioral theme system lets themes respond to live training signals (loss, throughput, gradient norm) with dynamic CSS. Adding a new theme requires exactly **three files** and **no engine changes**.

## The 3-Step Contract

### Step 1: CSS Layer — `anvil/api/static/css/themes/<id>.css`

Override design tokens under `[data-skin="<id>"]`:

- **Token overrides**: `--bg`, `--surface`, `--surface-2`, `--grouped-bg`, `--separator`, `--text`, `--text-secondary`, `--text-tertiary`, `--text-bright`, `--accent`, `--accent-green`, `--accent-red`, `--accent-orange`, `--accent-yellow`, `--accent-purple`, `--accent-cyan`, `--glass-bg`, `--glass-border`
- **Theme-private effect variables** (e.g., `--heat`, `--surge`, `--charge`) with sensible defaults so the theme looks correct at rest
- **Effect pseudo-elements** (`::before`, `::after`) on `.app-main` for ambient visuals (position fixed, pointer-events none, z-index 0–41)
- **Transition/animation** on effect elements using `var(--dur-slow) var(--ease)` and theme-private vars for speed
- **Divergence state** with a `data-skin` scoped selector (e.g. `[data-skin="<id>"][data-<id>-state="diverged"]`)
- **`@media (prefers-reduced-motion: reduce)`** reset scoped to `[data-skin="<id>"] *`
- If dual-mode: a `[data-skin="<id>"][data-theme="light"]` block with light-mode token overrides
- Single-mode themes (`['single']`) define one inherent appearance; light/dark control is inert

### Step 2: JS Module — `anvil/api/static/js/themes/<id>.js`

Register with the global registry using an IIFE:

```javascript
(function () {
  'use strict';

  var L0 = 9.8;          // reference loss
  var MAX_TPS = 600000;  // reference throughput

  function clamp01(x) {
    if (!isFinite(x)) return 0;
    return x < 0 ? 0 : x > 1 ? 1 : x;
  }

  function someMapping(bus, effectLevel) {
    var root = document.documentElement;
    var paused = effectLevel && effectLevel.level === 'paused';
    var unsubs = [];

    function setVar(name, value) {
      root.style.setProperty(name, value);
    }

    // Set initial/at-rest defaults
    setVar('--private-var', '0');

    unsubs.push(bus.on('metrics', function (m) {
      if (!m || paused) return;
      // Map signals to CSS vars
    }));
    unsubs.push(bus.on('divergence', function () {
      root.setAttribute('data-<id>-state', 'diverged');
    }));

    return function teardown() {
      unsubs.forEach(function (u) { u(); });
      root.removeAttribute('data-<id>-state');
      root.style.removeProperty('--private-var');
    };
  }

  window.ThemeRegistry.register({
    id: '<id>',
    displayName: '<Display Name>',
    previewHint: '<short description>',
    modes: ['light', 'dark'],   // or ['single'], ['dark']
    cssLayer: '/static/css/themes/<id>.css',
    mapping: someMapping,       // or null for cosmetic-only themes
  });
})();
```

**Mapping function rules:**
- MUST be idempotent (safe to call multiple times)
- MUST return a `teardown()` that unsubscribes all listeners, cancels timers/rAF, removes data-* attributes, removes private CSS vars
- MUST handle `effectLevel.legible` — suppress degrading effects (chromatic aberration, blur, shake)
- MUST handle `effectLevel.level === 'paused'` — skip processing when tab is hidden
- MUST clamp out-of-range signals via `clamp01()`
- MUST respond to `'divergence'` with a distinct visual state
- SHOULD set initial/default CSS var values immediately

### Step 3: Script Include — `anvil/api/templates/base.html`

Add one line in alphabetical order among the existing theme script tags:

```html
<script src="/static/js/themes/<id>.js"></script>
```

### Also update: `tests/system/test_theme_engine.py`

Add the theme id to the `THEME_IDS` list (alphabetical order). The test automatically generates `THEME_REGISTRATIONS` and `THEME_CSS_LAYERS` from this list.

## Signal-Mapping Patterns

| Driving Signal | CSS var pattern | Reference L0/MAX_TPS |
|---------------|-----------------|----------------------|
| **Loss-led** | `clamp01(1 - m.loss / L0)` where `L0 = 9.8` | Higher loss = less effect |
| **Throughput-led** | `clamp01(m.tokens_per_sec / MAX_TPS)` where `MAX_TPS = 600000` | Higher TPS = more effect |
| **Gradient norm** | `clamp01(m.grad_norm)` | Raw grad_norm, no scaling |
| **Instability** | Rolling stddev of last 8 loss values | Derived from volatility |
| **Milestone** | Subscribe to `bus.on('milestone', fn)` for flash/celebration | Discrete event |
| **Complete** | Subscribe to `bus.on('complete', fn)` for final state | Discrete event |
| **Divergence** | Subscribe to `bus.on('divergence', fn)` for alarm state | Discrete event |

## Color Palette Rules

- WCAG AA contrast (4.5:1 minimum) for primary text in every supported mode
- Light mode: keep backgrounds light (white/off-white), text dark, reduce accent saturation
- Single mode: define one palette under `[data-skin="<id>"]` only (no `[data-theme="light"]` block)
- Use `--glass-bg: rgba(...)` with alpha 0.78–0.88 for nav transparency
- `--glass-border: rgba(<accent-color>, 0.12–0.20)` for nav border

## Available Signal Events

| Event | Payload | Description |
|-------|---------|-------------|
| `'metrics'` | `{ loss, tokens_per_sec, grad_norm? }` | Per-step training metrics |
| `'divergence'` | (no payload) | Loss became NaN/inf; run halted |
| `'milestone'` | (no payload) | Periodic training progress beat |
| `'complete'` | (no payload) | Run completed successfully |

## Theme Categories

- **Cosmetic**: No JS mapping function (`mapping: null`). Pure color scheme. Example: `default`.
- **Loss-led**: Signal drives clarity/convergence. Loss decreases → effect increases. Examples: Tide, Aurora, Glacier.
- **Throughput-led**: Tokens/sec drives intensity. Examples: Mainframe, Reactor, Hyperspace.
- **Instability-led**: Gradient norm drives disruption. Examples: Tectonic, Storm Front.
- **Spectrum/Audio**: Uses the opt-in WebAudio layer. Example: Resonance (only one).

## Presence Tiers — Always-On vs Session-Gated

A theme's `mapping()` runs **only while a training signal bus session is attached**
(the manager short-circuits binding otherwise). So theme visuals fall into three tiers,
and you must put each effect in the right place:

1. **Session-gated (JS)** — sprites/effects that *respond* to `metrics` /
   `milestone` / `complete` / `divergence`. Present only during/around a run. Built in
   the JS module's `mapping()`. May inject DOM (see below).
2. **Always-on (CSS)** — decoration that must exist regardless of run state (e.g. a
   mascot). Must live in the CSS layer — the JS IIFE body should only `register()`.
3. **Always-on (canvas particles)** — the `particleConfig` effect from
   `particle-system.js`. Runs on every page via an idle-signal baseline and intensifies
   once training drives the signal vars. See the Canvas particle layer section below.

For the full rationale see [[Discoveries/theme-presence-tiers-css-vs-session-gated-js]]
and [[Discoveries/particle-canvas-always-on-idle-baseline]].

### Canvas particle effects (a third visual layer)

Beyond CSS pseudo-element ambience and DOM-sprite injection, a theme can opt into the
shared **canvas particle system** by setting `particleConfig: { type: '<effect>' }` in
its `register()` call (e.g. Tide uses `bubble`). The effect itself is a factory
registered in `anvil/api/static/js/theme/particle-system.js` that reads the same private
CSS variable the theme's `mapping()` publishes (Tide's `bubble` reads `--surge`), so the
canvas motion stays in lockstep with the CSS animations driven by that variable. The full
authoring contract — effect skeleton, the `readSignal` idle-baseline behavior, and the
density/speed tuning knobs — is documented in [[Reference/particle-effect-authoring]].

### JS DOM-sprite injection (session-gated tier)

If `mapping()` injects DOM nodes (overlay sprites, particles), it MUST:

- Append a single managed container (e.g. to `document.body`), `pointer-events:none`.
- Use `requestAnimationFrame` for continuous motion and **compact** any node arrays
  each frame (mark-removed-but-never-spliced is an unbounded leak iterated per frame).
- Seed each node's `transform` at spawn (avoid a first-frame flash at `(0,0)`).
- Gate spawning on `effectLevel` (`paused` → none; `legible` → none; `muted` /
  reduced-motion → static, no rAF) — including inside burst/milestone handlers.
- Tear down completely: cancel rAF + timers, unsubscribe, remove every node + the
  container, drop all `data-*` attrs and private CSS vars.

### Always-on CSS mascot (always-on tier)

Render a persistent illustration as a `background-image` data-URI SVG on a dedicated
pseudo-element (`.app-shell::after` is a safe, never-clipped, always-present anchor).
The SVG can self-animate and self-gate reduced-motion internally. Encoding and the
non-harmonic-period autonomous-motion trick are documented in
[[Reference/css-data-uri-animated-svg-sprite]].

### Canvas particle layer (always-on, idle baseline)

`anvil/api/static/js/theme/particle-system.js` provides a `<canvas>` overlay of
registered effects (`rain`, `snow`, `ember`, `aurora`, …). A theme opts in by giving its
registration a `particleConfig: { type: '<effect>', params: {} }`; omitting it (or
`type: 'css'`) means the theme has no canvas particles (the `default` theme falls back to
the CSS `.ambient-particles` sparks, scoped to `[data-skin="default"]`). This is a
**third presence tier**, distinct from the session-gated `mapping()` and from always-on
CSS pseudo-elements:

- The canvas layer is **always on** (every page), not training-gated. The manager
  applies it on theme selection; do not re-apply it on `bindSession` (that rebuilds the
  canvas and causes a "wave").
- Effects scale count/opacity by a theme-private signal var. Because that var is only
  written by the (session-gated) `mapping()`, effects read it through `readSignal(name)`
  / `readSignalChain(primary, fallback)`, which return an **idle baseline**
  (`IDLE_SIGNAL`) only when the var is *unset*. A var set to `"0"` during training still
  wins — so do not collapse this to `parseFloat(...) || 0`. Route only *intensity* vars
  through these helpers, never a hue/rotation var.
- The canvas is `position: fixed; z-index: 0` — behind `.app-main` (which isolates its
  own stacking context) but above the `.app-shell` background. Any static sibling that
  must stay legible above it (the `.nav-bar`) needs its own positive stacking context.
- Seed an effect's *initial* population across the full viewport, not off-screen, so it
  looks steady on first paint instead of filling in as a wave.

Full rationale: [[Discoveries/particle-canvas-always-on-idle-baseline]].

## Existing Themes (27 total as of 2026-06-20)

| ID | Display | Signal | Modes |
|----|---------|--------|-------|
| default | Default | cosmetic | light/dark |
| forge | Forge | loss/TPS | dark |
| oldgrowth | Old Growth | grad_norm + volatility | single |
| aurora | Aurora | loss/TPS | light/dark |
| tide | Tide | loss/TPS | light/dark |
| unicorn | Unicorn | loss/TPS (+ sparkle) | light/dark |
| bloom | Bloom | loss/volatility | light/dark |
| tectonic | Tectonic | grad_norm + volatility | light/dark |
| glacier | Glacier | loss | light/dark |
| reactor | Reactor | TPS/loss | single |
| hyperspace | Hyperspace | TPS/loss | single |
| mainframe | Mainframe | TPS | light/dark |
| grid | Grid | loss | single |
| stormfront | Storm Front | grad_norm/loss | light/dark |
| emberdrift | Ember Drift | loss/TPS | single |
| resonance | Resonance | grad_norm/loss (+ audio) | light/dark |
| inkwash | Inkwash | loss | light/dark |
| arcade | Arcade | loss/milestone | light/dark |
| pulse | Pulse | TPS | light/dark |
| solarflare | Solar Flare | grad_norm | single |
| deepsea | Deep Sea | loss | light/dark |
| static | Static | loss volatility | single |

| echo | Echo | grad_norm + milestone | single |
| prism | Prism | loss/milestone | light/dark |
| loom | Loom | TPS | light/dark |
| ash | Ash | loss | single |

---
*See also: [[Decisions/ADR-031-behavioral-theme-engine]], [[Reference/theme-picker-grid-keyboard-nav]], [[Reference/css-data-uri-animated-svg-sprite]], [[Reference/particle-effect-authoring]], [[Discoveries/theme-presence-tiers-css-vs-session-gated-js]], [[Discoveries/css-perspective-grid-floor-subpixel-flicker]], [[Sessions/2026-06-20-nine-new-themes]], [[Sessions/2026-06-20-unicorn-theme-and-prism-vibrancy]], [[Sessions/2026-06-20-unicorn-mascot-flying-sprites]], [[Sessions/2026-06-20-grid-theme-and-flicker-fix]]*
