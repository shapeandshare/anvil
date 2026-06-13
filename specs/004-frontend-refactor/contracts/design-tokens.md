# Contract: Design Token System

## Purpose
Centralized design tokens as CSS custom properties. All components reference these only — never raw hex/values. A systemic restyle is a token edit.

## Token Definitions

### Color (Dual Mode)

```css
:root {
  /* Dark mode values (default) */
  --bg:             #0e0f12;
  --surface:        #181a1f;
  --text:           #e8eaed;
  --text-muted:     #8a8c94;
  --border:         #2a2c32;
  --accent:         #3b82f6;    /* Electric blue — "things you can touch" */
  --accent-warn:    #f59e0b;    /* Amber — degraded/warning */
  --accent-error:   #ef4444;    /* Red — error state */
}

[data-theme="light"] {
  --bg:             #fafafa;
  --surface:        #ffffff;
  --text:           #16181d;
  --text-muted:     #6b6d74;
  --border:         #e4e5e7;
  --accent:         #2563eb;    /* Slightly desaturated for light bg legibility */
  --accent-warn:    #d97706;
  --accent-error:   #dc2626;
}

@media (prefers-color-scheme: dark) {
  :root:not([data-theme]) {
    /* OS dark mode — defaults to :root values above */
  }
}
```

### Type

```css
:root {
  --font-display: 'Times New Roman', 'Georgia', serif;  /* Editorial display face */
  --font-body:    -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  --font-mono:    'SF Mono', 'Fira Code', 'Cascadia Code', 'JetBrains Mono', monospace;
}
```

### Spacing (Modular Scale)

```css
:root {
  --space-1:  0.25rem;
  --space-2:  0.5rem;
  --space-3:  0.75rem;
  --space-4:  1rem;
  --space-5:  1.5rem;
  --space-6:  2rem;
  --space-7:  3rem;
  --space-8:  4rem;
  --space-9:  6rem;
  --space-10: 8rem;
  --space-11: 12rem;
  --space-12: 16rem;
}
```

### Motion

```css
:root {
  --ease:       cubic-bezier(0.4, 0, 0.2, 1);
  --dur-fast:   150ms;
  --dur-slow:   400ms;
}
```

### Radii & Borders

```css
:root {
  --radius:        8px;
  --border-width:  1px;
}
```

## Usage Rules

1. **Components reference tokens only** — no raw hex, no hardcoded font stacks, no magic numbers
2. **Mode-specific hex lives ONLY in token definitions** — never in component files
3. **`--accent` is reserved for interactive elements** — buttons, links, active states. Never used for body text or decorative borders
4. **`--font-mono` for all code/data** — tensor values, token IDs, loss numbers, code blocks
5. **`prefers-reduced-motion` disables ALL transitions** — `@media (prefers-reduced-motion) { * { transition: none !important; } }`

## File Organization

```
microgpt/api/static/css/
├── tokens.css       # All :root and [data-theme] token definitions (this file)
├── base.css         # Reset, @font-face, html/body base styles
├── archetypes.css   # Layout styles per archetype
├── components.css   # Reusable component styles (buttons, panels, badges, etc.)
├── utilities.css    # Utility classes (spacing helpers, typography helpers)
└── code.css         # Token/data rendering (mono type, code blocks)
```

## Migration from Legacy

- Remove: `--accent-cyan`, `--accent-yellow`, `--accent-magenta`, `--accent-green`, `--accent-red`
- Rename: `--bg-panel` → `--surface`, `--text-dim` → `--text-muted`, `--bg-element` → removed (use `--surface`)
- Retain: `--radius`, `--t` (becomes `--dur-fast`), existing component selectors (migrated incrementally)