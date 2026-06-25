---
title: Particle Effect Strict-Mode Undeclared Variable (glow)
type: discovery
aliases:
  - Particle Effect Strict-Mode Undeclared Variable (glow)
  - Strict-Mode Undeclared glow Variable
tags:
  - type/discovery
  - domain/ui
  - status/draft
created: '2026-06-21'
updated: '2026-06-21'
source: agent
aliases:
  - Undeclared glow variable
  - Particle Effect Strict-Mode glow
code-refs:
  - anvil/api/static/js/theme/particle-system.js
related:
  - '[[Discoveries/global-particle-speed-via-sim-step-cadence]]'
---
# Particle Effect Strict-Mode Undeclared Variable (`glow`)

**Discovered**: 2026-06-21, when a browser console error `Uncaught ReferenceError: glow is not defined` was reported from the Reactor theme's particle effect.

## The problem: undeclared variable in strict mode

The `energy` particle effect (driven by `--throughput`, used by the **Reactor** theme) assigns to a variable `glow` on every particle update loop:

```js
glow = q.o * (0.1 + sig * 0.9);
```

The outer IIFE and all effect closures run under `'use strict'` (line 7 of `particle-system.js`). In strict mode, assigning to an undeclared variable throws a `ReferenceError` — the variable **must** be declared with `var`, `let`, or `const` first.

The sibling effect variable declaration on line 1119 was:

```js
var i, q, tc, cx, cy, x, y;
```

`glow` was simply omitted from this list. Every other variable used in the `update()` body (`i`, `q`, `tc`, `cx`, `cy`, `x`, `y`) was declared — `glow` was the only missing one.

## Why it wasn't caught earlier

- The `biolum` effect (Deep Sea theme) uses an identical `glow` pattern and had the declaration correct: `var i, q, tc, glow;`.
- The `energy` effect was likely authored with `glow` as an afterthought — the local variable pattern was copied from `biolum` but `glow` was dropped from the declaration list.
- There is no JS linter or strict-mode checker in CI that catches undeclared variable assignment.

## The fix

Added `glow` to the `var` declaration:

```js
var i, q, tc, cx, cy, x, y, glow;
```

## Precaution

A grep for `glow =` across the file found two occurrences:
- **Line 709** (`biolum` effect) — already had `var glow` declared at line 694 ✅
- **Line 1134** (`energy` effect) — was missing, now fixed ✅

No other effects use `glow`.

## See Also

- [[Discoveries/Discoveries|Discoveries]]
