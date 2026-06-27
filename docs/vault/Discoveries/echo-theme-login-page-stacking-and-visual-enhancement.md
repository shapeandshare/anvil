---
title: Echo Theme — Login Page Stacking & Visual Enhancement
type: discovery
status: draft
source: agent
aliases:
  - Echo Theme — Login Page Stacking & Visual Enhancement
related:
  - Reference/theme-creation-guide
code-refs:
  - anvil/api/static/css/themes/echo.css
  - anvil/api/static/css/login.css
session: 2026-06-26-echo-theme-login-stacking
created: '2026-06-26'
updated: '2026-06-26'
tags:
  - type/discovery
  - domain/ui
  - status/draft
---
## Summary

The echo theme's primary visual effect — a pulsing sonar ring via `.app-main::after` at `z-index: 41` — rendered on top of the login card on the login page because its fixed-position pseudo-element had a higher z-index than the `.login-page` container (`z-index: 2`). Unlike grid and hyperspace themes (hidden entirely on login via `display: none`), the echo ring benefits from being visible behind the login card with adjusted styling.

## The Discovery

### Echo theme ring overlaps login card by default

The echo CSS theme (`anvil/api/static/css/themes/echo.css`) defines a centered fixed-position ring:

```css
[data-skin="echo"] .app-main::after {
  position: fixed;
  left: 50%; top: 50%;
  z-index: 41;  /* above .login-page at z-index 2 */
  ...
}
```

This makes the pulsing sonar ring render on top of the login card — a visual overlap issue identical to grid and hyperspace, but those themes hide their effects entirely (`display: none`).

### Login-page z-index override preserves the effect

Rather than hiding the echo ring on the login page (which loses the theme's character), lowering `z-index` to `0` keeps it visible and animating behind the card. The login page's `.login-page` container at `z-index: 2` sits above it in the stacking context, so the ring is visible as a backdrop effect behind the login card.

### Login-page visual enhancement

On the login page (where no training session is active), `--ping` stays at `0`, making the ring very faint (2px border at 5% opacity, 20% element opacity). Three properties are overridden on login:
- `z-index: 0` — behind the login card
- `border-width: 6px` — thicker ring for visibility
- `box-shadow: 0 0 70px 30px rgba(74, 200, 230, 0.15)` — diffuse cyan glow that spreads as the ring expands

## References

- `anvil/api/static/css/themes/echo.css` — Echo ring at `.app-main::after`
- `anvil/api/static/css/login.css` — Login page override block (lines 127-131)
- [[Reference/theme-creation-guide]]
