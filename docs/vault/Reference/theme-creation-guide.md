---
created: '2026-06-20'
status: reviewed
tags:
  - domain/ui
  - type/reference
title: Theme Creation Guide
updated: '2026-06-20'
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
| hologram | Hologram | loss | single |
| stormfront | Storm Front | grad_norm/loss | light/dark |
| emberdrift | Ember Drift | loss/TPS | single |
| resonance | Resonance | grad_norm/loss (+ audio) | light/dark |
| inkwash | Inkwash | loss | light/dark |
| stainedglass | Stained Glass | loss/milestone | single |
| pulse | Pulse | TPS | light/dark |
| solarflare | Solar Flare | grad_norm | single |
| deepsea | Deep Sea | loss | light/dark |
| static | Static | loss volatility | single |
| vinyl | Vinyl | TPS | light/dark |
| echo | Echo | grad_norm + milestone | single |
| prism | Prism | loss/milestone | light/dark |
| loom | Loom | TPS | light/dark |
| ash | Ash | loss | single |

---
*See also: [[Decisions/ADR-031-behavioral-theme-engine]], [[Reference/theme-picker-grid-keyboard-nav]], [[Sessions/2026-06-20-nine-new-themes]], [[Sessions/2026-06-20-unicorn-theme-and-prism-vibrancy]]*
