## Summary
Changed the default theme from OS-preference-respecting to always-dark. Previously, users with `prefers-color-scheme: light` would see the light theme on first visit. Now all users see dark mode by default, regardless of OS setting. The toggle still persists via `localStorage`, so users who switch to light keep their preference across visits.

## Files changed
- `anvil/api/templates/base.html` — inline flash-of-content guard: fallback changed from `window.matchMedia('(prefers-color-scheme:dark)').matches ? 'dark' : 'light'` to `'dark'`
- `anvil/api/static/js/core.js` — `initTheme()`: same fallback change

## Key decisions
- Dark mode is now the unconditional default. OS preference is no longer consulted.
- User toggle is still persisted in `localStorage` — light-mode users' choice survives page reloads.
- CSS `:root` block (dark values) was already the default — no CSS changes needed.

## Rationale
The CSS tokens already declared dark as the `:root` default (see `tokens.css` line 2 comment: "Dark Mode — Default"), but the JS was overriding it to light on light-OS machines. This change aligns the runtime behavior with the CSS intent.