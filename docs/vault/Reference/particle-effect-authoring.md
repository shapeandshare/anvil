---
created: '2026-06-20'
status: reviewed
tags:
  - domain/ui
  - type/reference
title: Particle Effect Authoring
type: reference
updated: '2026-06-20'
aliases:
  - Particle Effect Authoring
related:
  - '[[Reference/theme-creation-guide]]'
  - '[[Discoveries/css-multi-background-position-parallax]]'
code-refs:
  - anvil/api/static/js/theme/particle-system.js
  - anvil/api/static/js/themes/tide.js
---
# Particle Effect Authoring

The behavioral theme system has a second, often-overlooked visual layer beyond the CSS pseudo-element ambience documented in [[Reference/theme-creation-guide]]: a shared **canvas particle system**. A theme opts into a named particle effect through its `particleConfig`, and the effect is a self-contained factory registered in `anvil/api/static/js/theme/particle-system.js`. This note documents that contract so a new effect can be added without re-deriving it from the source each time.

## The two halves of the contract

A particle effect is one full-viewport `<canvas>` overlay shared by the whole app — there is exactly one canvas, owned by the particle system, inserted as the first child of `.app-shell` at `z-index: 0` (behind `.app-main` content, above the app-shell background). A theme does not own a canvas; it merely *names* the effect it wants.

1. **Theme side** — the theme's JS module (`anvil/api/static/js/themes/<id>.js`) declares `particleConfig: { type: '<effect-name>' }` in its `ThemeRegistry.register({...})` call. `type: 'css'` means "no canvas, use my CSS pseudo-elements"; `type: 'none'` means "no particles at all". Any other string must match a registered effect name.
2. **Effect side** — `particle-system.js` calls `registerEffect('<effect-name>', factory)`. The factory returns an implementation object exposing `start`, `stop`, `update`, and `resize`. The system drives `update` with `(simClock, width, height, ctx)` and clears the canvas before each such call, so an effect only paints; it never clears. Note that `update` is **not** called on every animation frame: the loop gates the simulation on accumulated wall-clock time and passes a scaled `simClock` (not the raw `requestAnimationFrame` timestamp), which is how the global `SPEED_SCALE` slows all effects uniformly — see [[Discoveries/global-particle-speed-via-sim-step-cadence]].

The link between the two is purely the effect-name string. The Tide theme, for example, names `bubble`, and the `bubble` effect is registered alongside the older `spray` effect that Tide previously used. The Bloom theme's `petal` effect drew circles originally, then was reworked into a sakura (cherry blossom) shape using bezier lobes with a central cleft — see the session log for the exact bezier geometry.

## The signal binding (the important part)

Particle effects are *behavioral*: their density and motion track live training signals. But an effect runs on the animation loop, decoupled from the metrics event bus — so it does **not** subscribe to the bus. Instead, the theme's `mapping()` writes a private CSS custom property on `document.documentElement` (e.g. Tide's `mapping` sets `--surge` from `tokens_per_sec` and `--level` from loss), and the effect *reads that same variable each frame* via the particle system's `readSignal('--surge')` helper.

This indirection is deliberate and has one critical consequence documented in the source: `readSignal` returns an **idle baseline of `0.5`** when the variable is unset (no training session attached), and only an explicitly-set value — even `"0"` — overrides it. That is why particle effects are visible immediately at rest rather than waiting for a run to start. There is also `readSignalChain(primary, fallback)` for effects shared across themes that publish the signal under different names (the `ember` effect reads `--ember` or falls back to `--heat`).

The upshot: an effect's "intensity knob" is whatever CSS variable its host theme already publishes. Adding an effect does not require touching the metrics bus, the theme manager, or the registry — only `particle-system.js` (and the one-line `particleConfig` in the host theme).

## Effect implementation shape

Every effect in the file follows the same terse skeleton — a particle array, `w`/`h`, a cached signal value, an `init`/`start`/`stop`/`resize`/`update` set, and a `create()` particle factory. Conventions that are enforced by the codebase and worth matching:

- **Vars declared at the function root.** The project's lint flags block-scoped `var` (`This var should be declared at the root of the enclosing function`). Declare every loop-local in the top `var i, q, tc, ...` line, not inside the loop body.
- **Count scales with the signal.** The universal pattern is `BASE` and `MAX` constants and `tc = Math.round(BASE + sig * (MAX - BASE))`, then grow/shrink the array to `tc` each frame. To make an effect *sparser*, lower both `BASE` and `MAX`; the per-frame array compaction handles the rest.
- **Speed scales with the signal.** Motion terms are written as `base + sig * range` (e.g. a rise speed of `0.18 + sig * 0.42`). To slow a *single* effect down, shrink both the base and the range together rather than only one. To slow **every** effect at once (idle and active alike), do **not** touch per-effect coefficients — change the global `SPEED_SCALE` knob in the animation loop instead (see [[Discoveries/global-particle-speed-via-sim-step-cadence]]). Note that per-frame integration (`q.y += …`) is delta-less, so scaling the `timestamp` alone will not slow it.
- **Recycle off-screen particles** by repositioning rather than allocating (the rise effects respawn a bubble below the viewport once it passes the top). Horizontal wrap (`if x < -10 → x = w + 10`) keeps swaying particles from piling at an edge.
- **One header comment per effect**, two lines: `// ── Name (one-line description) ──` then `// Driven by --signal (...)`. Every effect in the file carries this; it is the only documentation of the JS↔CSS signal binding, so a new effect must follow suit rather than omit it.
- **`env.paused`** (passed into the factory) gates all motion; the system separately handles reduced-motion / legibility by pausing the loop and applying a blur filter on the canvas via `onEffectLevelChange`, so an effect does not need its own reduced-motion branch — it only needs to honour `env.paused` in `update`. The blur (12px) replaces the previous opacity-zero approach, so particles remain visible but motion-diffused when "Reduce effects" is active — see [[Discoveries/glass-diffusion-via-canvas-blur]].

## The Tide "bubble" example

Tide's `bubble` effect is a representative *rising* effect synced to wave motion. Bubbles spawn below the waterline and rise (`y -= s * (...)`), recycling from the bottom once past the top. The defining trick is that the **horizontal sway frequency and amplitude are both derived from `--surge`** — the very same variable that sets the CSS wave-swell animation speed in `anvil/api/static/css/themes/tide.css` (`calc(14s - var(--surge) * 9s)`). Because both the canvas sway and the CSS ripple read one signal, the bubbles sway in tempo with the visible ripples instead of drifting independently. Tuning the population down and the motion down was a matter of lowering the `BASE`/`MAX` pair and shrinking the `base + sig * range` coefficients for both lift and sway — no structural change.

## Catalogued effects

As of this note the registered effects are: `snow`, `rain`, `ember`, `aurora`, `petal` (sakura/cherry-blossom cleft shape with pale pink gradient for the Bloom theme, reads `--open`), `biolum`, `ribbon`, `streak`, `ink`, `thread` (horizontal purple/cyan shuttle, criss-cross with CSS warp), `matrix`, `leaf`, `prism`, `pulse`, `energy`, `flare`, `shard`, `debris`, `spray`, `bubble`, `spin`, `spark`, and `confetti`. `spark` (Forge, reads `--heat`) is a physics-based forging anvil effect: particles spawn from a bottom band and launch in random directions with friction and gravity, drawn as line streaks oriented along their velocity vector — they look like hot metal fragments rather than floating embers. Color shifts from white-hot through yellow-orange to dim red. `matrix` (Mainframe, reads `--activity`) is a **right-angled** falling-code effect: axis-aligned `fillRect` glyphs snapped to a 12px column grid (pixel-rounded for crisp corners) with dimming square trails — explicitly *not* round "snow" dots. Its `pickShape()` rolls a weighted size mix (mostly tall thin bars + small squares, with an occasional ~8% wide block), so glyph width/height vary per particle. Each names the CSS variable it reads in its header comment. `ribbon` (Grid, reads `--focus`) is a light-cycle effect: bright heads race axis-aligned and lay glowing right-angle trails; higher focus adds more/faster riders, and the `derez` divergence state turns them amber. It replaced the former `holopoint`/`glitch` effect when the Hologram theme became the grid-world **Grid** theme. `spray` remains registered but is no longer referenced by any theme (Tide migrated to `bubble`); leaving it registered is harmless and preserves it as a reusable upward-foam effect. `confetti` (Arcade, reads `--neon`) is a mixed-color palette of neon rectangles and strips in hot pink, cyan, yellow, green, and purple — the first effect with a multi-hue fixed palette rather than a single hue family or monochrome range.

## References

- `anvil/api/static/js/theme/particle-system.js` — the effect registry, the shared canvas lifecycle, `readSignal`/`readSignalChain`, and every built-in effect
- `anvil/api/static/js/themes/tide.js` — host theme: publishes `--surge`/`--level` and names the `bubble` effect via `particleConfig`
- `anvil/api/static/css/themes/tide.css` — the CSS wave-swell animation that the `bubble` sway is synced to
- `anvil/api/static/js/themes/grid.js` + `grid.css` — host theme: publishes `--focus`, names the `ribbon` light-cycle effect, and pairs it with a CSS perspective grid floor
- [[Sessions/2026-06-20-grid-theme-and-flicker-fix|Session: Grid Theme + Flicker Fix]] — where `ribbon` replaced `holopoint`/`glitch`
