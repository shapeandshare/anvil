---
title: Debris Effect Strict-Mode Undeclared Variable (shake)
type: discovery
aliases:
  - Debris Effect Strict-Mode Undeclared Variable (shake)
  - Strict-Mode Undeclared shake Variable
tags:
  - type/discovery
  - domain/ui
  - status/draft
created: '2026-06-26'
updated: '2026-06-26'
source: agent
code-refs:
  - anvil/api/static/js/theme/particle-system.js
related:
  - '[[Discoveries/particle-effect-strict-mode-undeclared-glow]]'
status: draft
---

# Debris Effect Strict-Mode Undeclared Variable (`shake`)

**Discovered**: 2026-06-26, when switching to the Tectonic theme produced `Uncaught ReferenceError: shake is not defined` in the browser console, from the `debris` particle effect.

## The problem: undeclared variable in strict mode

The `debris` particle effect (driven by `--tremor`, used by the **Tectonic** theme) assigns to a variable `shake` on every particle update loop:

```js
shake = Math.sin(ts * 0.005 + q.ph) * sig * 4;
```

The outer IIFE and all effect closures run under `'use strict'` (line 7 of `particle-system.js`). In strict mode, assigning to an undeclared variable throws a `ReferenceError` — the variable **must** be declared with `var`, `let`, or `const` first.

The effect variable declaration on line 1536 was:

```js
var i, q, tc, glow;
```

`shake` was simply omitted from this list. Every other variable used in the `update()` body (`i`, `q`, `tc`, `glow`) was declared — `shake` was the only missing one.

## Why it wasn't caught earlier

- The `debris` effect is only active when the **Tectonic** theme is selected (it's registered under `particleConfig: { type: 'debris' }` in `tectonic.js`).
- The Tectonic theme was likely tested less frequently than the default theme.
- There is no JS linter or strict-mode checker in CI that catches undeclared variable assignment.

## The fix

Added `shake` to the `var` declaration:

```js
var i, q, tc, glow, shake;
```

## Precaution

A grep for `= Math.sin` or standalone assignments that might be undeclared across the file found no other similar cases beyond `glow` (already fixed) and `shake` (now fixed). Each effect's `var` declaration list was reviewed — all other effects declare their local variables correctly.

This is the second occurrence of the same bug class. Both the `energy` (`glow`) and `debris` (`shake`) effects suffered from the same pattern: a variable was introduced during development but never added to the `var` declaration, working silently in non-strict mode but throwing in strict mode.

## See Also

- [[Discoveries/particle-effect-strict-mode-undeclared-glow]] — The same bug class in the `energy` effect (`glow` variable)
- [[Discoveries/Discoveries|Discoveries]]
