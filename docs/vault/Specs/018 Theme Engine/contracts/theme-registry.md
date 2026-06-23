# Contract: Theme Module & Registry (client-side)

**Purpose**: Define the stable shape every theme module must satisfy and the lifecycle the theme manager guarantees, so a new theme can be added without touching engine code (FR-015, SC-009). Vanilla ES6, no framework, no build step.

## Theme module shape

Each theme is one file: `anvil/api/static/js/themes/<id>.js`. It registers itself with the global registry on load.

```js
// themes/forge.js  (illustrative — names binding, internals refine-able)
ThemeRegistry.register({
  id: 'forge',                       // string, unique, valid data-theme value
  displayName: 'Forge',              // string, shown in picker
  previewHint: 'Loss as cooling metal', // string, lets users tell themes apart (FR-001)
  modes: ['dark'],                   // subset of ['light','dark'] OR ['single']
  cssLayer: '/static/css/themes/forge.css', // string|null (null ⇒ base tokens only)

  // OPTIONAL expressive hook. Absent/null ⇒ purely cosmetic theme (FR-014).
  // Called when this theme becomes active AND signals are available on the page.
  // MUST be idempotent; MUST return a teardown() for clean switching (FR-026).
  mapping(signalBus, effectLevel) {
    // subscribe to NEUTRAL signals; drive CSS vars / canvas; respect effectLevel
    const unsub = signalBus.on('metrics', (m) => { /* ... */ });
    return function teardown() { unsub(); /* cancel rAF, listeners */ };
  },
});
```

### Field contract

| Field | Required | Rule |
|---|---|---|
| `id` | yes | Unique in registry; valid CSS attribute value; becomes `data-theme="<id>"`. |
| `displayName` | yes | Non-empty. |
| `previewHint` | yes | Non-empty short string. |
| `modes` | yes | Either a subset of `['light','dark']`, or exactly `['single']`. If both light+dark, the CSS layer MUST define both. |
| `cssLayer` | yes (nullable) | Path under `/static/css/themes/`, or `null` to use only base `tokens.css`. |
| `mapping` | no | `function(signalBus, effectLevel) → teardown` or absent. |

## Registry API

```js
ThemeRegistry.register(theme)   // idempotent by id; last registration wins with a console.warn on dup
ThemeRegistry.get(id)           // → theme | undefined
ThemeRegistry.list()            // → Theme[] in display order
ThemeRegistry.has(id)           // → bool
ThemeRegistry.defaultId         // → 'default' (constant)
```

**Guarantees**:
- `default` is always present and is the fallback for any unknown id (FR-024).
- Registration order = picker display order.
- Adding a theme = drop a `themes/<id>.js` + `css/themes/<id>.css` and include the script; NO change to manager/registry/SSE code (SC-009).

## Theme Manager lifecycle

`theme-manager.js` owns application and persistence.

```js
ThemeManager.init()                 // read+migrate localStorage, resolve OS mode, apply before-paint already done by FOUC head script
ThemeManager.apply(id, mode?)       // switch theme WITHOUT full reload (FR-003)
ThemeManager.current()              // → { themeId, mode }
ThemeManager.reset()                // → apply('default') (FR-007)
```

### `apply(id, mode)` MUST, in order:
1. Resolve `id` via registry; if unknown ⇒ use `default` and rewrite preference (FR-024).
2. Tear down the previously active theme's `mapping` (if any).
3. Set `data-theme="<id>"` and `data-mode="<mode|single>"` on `<html>`.
4. Ensure the theme's `cssLayer` `<link>` is present (and remove the prior theme's layer); base `tokens.css` always stays loaded.
5. Persist `{themeId:id, mode}` to `localStorage['theme']`.
6. If signals are available on the current page (a live `SSESession`/`signal-bus` exists) and the theme has a `mapping`, bind it to the bus with the current `EffectLevelState` (FR-002 signal layer activates only where signals exist; FR-026 no connection drop).
7. Update picker UI selection + light/dark control state (disabled/explained for `single` themes — FR-023).

### Lifecycle guarantees
- **No full reload** on switch (FR-003); applied within perceptible-instant budget (SC-001).
- **No FOUC**: the inline `<head>` script in `base.html` applies `data-theme`/`data-mode` and injects the active `cssLayer` link before first paint (FR-006, SC-010).
- **Survives client-side nav**: the manager + picker live in the nav bar (outside `<main>`), so `core.js` page swaps don't re-init theme state.
- **Mid-run switch**: rebinds mapping to the existing bus; never closes the EventSource (FR-026).
- **Effect gating**: the active mapping receives `EffectLevelState` and MUST suppress continuous/legibility-degrading effects per Full/Muted/Legible/Paused (FR-016–021).
