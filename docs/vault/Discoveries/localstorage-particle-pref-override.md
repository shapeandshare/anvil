---
aliases:
  - localStorage Particle Pref Override — Silent Effect Hijack
code-refs:
  - anvil/api/static/js/theme/particle-system.js
  - anvil/api/static/js/theme/theme-manager.js
created: '2026-06-23'
related:
  - '[[Discoveries/particle-canvas-always-on-idle-baseline]]'
  - '[[Sessions/2026-06-23-particle-system-toggle-and-localstorage-fix]]'
session: 2026-06-23-particle-system-toggle-and-localstorage-fix
source: agent
summary: >-
  The getEffectiveConfig() function allowed localStorage.theme:particle to
  override every theme's particleConfig with a single forced effect. A stored
  effect name (e.g. 'spin') would run on all themes, on top of each theme's own
  particles. The pref is now strictly on/off.
tags:
  - type/discovery
  - domain/ui
  - status/draft
title: localStorage Particle Pref Override — Silent Effect Hijack
type: discovery
updated: '2026-06-23'
---
The `getEffectiveConfig()` function in `particle-system.js` had a fallback path where
`localStorage.getItem('theme:particle')` could override a theme's own `particleConfig`.
If a user (or the system) ever stored a registered effect name in this key, that effect
would run on **every** theme unconditionally — on top of each theme's intended particles.

## The vulnerable path (removed)

```javascript
function getEffectiveConfig(themeConfig) {
    var pref = readPref();  // localStorage.getItem('theme:particle')
    if (pref === 'none') return { type: 'none', params: {} };
    if (pref && effects[pref]) return { type: pref, params: {} };  // ← DANGER
    return themeConfig || { type: 'css', params: {} };
}
```

The third line checked whether the stored pref matched any registered effect name
(e.g. `'spin'`, `'rain'`, `'snow'`). If it did, that effect was forced on all themes
regardless of each theme's `particleConfig`. The intended use appeared to be a user
preference system, but the absence of any UI to set this pref meant it could only be
set manually (DevTools, or a now-removed particle dropdown).

## The fix

The pref is now strictly on/off:
- `'none'` → particles disabled
- Any other value (or unset) → falls through to the theme's own `particleConfig`

```javascript
function getEffectiveConfig(themeConfig) {
    var pref = readPref();
    if (pref === 'none') return { type: 'none', params: {} };
    return themeConfig || { type: 'css', params: {} };
}
```

## Why this matters

This was a silent footgun. A developer testing a particle effect by writing directly
to localStorage could accidentally leave the override in place, causing:

1. A particle effect that belongs to one theme (e.g. `rain` for Stormfront) to run
   on every theme.
2. Conflicting visual layers — the forced effect's canvas on top of the theme's own
   canvas (both at `z-index: 0`).
3. Hard-to-diagnose bug reports ("why is rain showing on my Matrix theme?").

The fix makes the pref's behavior obvious: it only controls whether particles run,
not *which* particles run.

## References
- [[Discoveries/Discoveries|Discoveries]]

- `anvil/api/static/js/theme/particle-system.js` — `getEffectiveConfig`, `readPref`, `writePref`
- `anvil/api/static/js/theme/theme-manager.js` — "Show particles" toggle wiring
- [[Sessions/2026-06-23-particle-system-toggle-and-localstorage-fix]]
- [[Discoveries/particle-canvas-always-on-idle-baseline]]
