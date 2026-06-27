---
aliases:
  - CSP Blocks Dynamic Style Injection
code-refs:
  - anvil/api/static/js/themes/aurora.js
  - anvil/api/static/css/themes/aurora.css
created: '2026-06-26'
domain: ui
related:
  - Discoveries/css-ambient-glow-via-color-mix
  - Reference/theme-creation-guide
session: 2026-06-26-aurora-starfield
source: agent
summary: >-
  Dynamically injected <style> nodes are blocked by CSP nonce restrictions; real
  DOM elements with inline style.cssText bypass this.
tags:
  - type/discovery
  - domain/ui
  - status/draft
title: CSP Blocks Dynamic <style> Injection — Use Real DOM Elements Instead
type: discovery
updated: '2026-06-26'
---
# CSP Blocks Dynamic `<style>` Injection — Use Real DOM Elements Instead

**Framing sentence**: Content Security Policy nonces applied to `<head>` elements block dynamically injected `<style>` nodes; inline styles on real DOM elements (`element.style.cssText`) bypass this restriction entirely.

## The Problem

Adding a CSS starfield background via a dynamically created `<style>` element appended to `<head>` produced no visible effect:

```js
var s = document.createElement('style');
s.textContent = '.app-shell::before { ... }';
document.head.appendChild(s);
// → Nothing rendered. CSP blocked the injected rule.
```

The server applies a strict CSP that requires a `nonce` attribute on `<style>` and `<link>` elements. Static `<link>` stylesheets loaded in the HTML template work because they include the nonce from `request.state.csp_nonce`. Dynamically created `<style>` nodes lack this nonce and are silently dropped.

This same restriction applies to all four CSS-based approaches tried before switching to DOM elements:

1. `box-shadow` on a `::before` pseudo-element via CSS file
2. `radial-gradient` multi-layer `background-image` on `.app-shell` via CSS file
3. `radial-gradient` multi-layer `background` on `.app-shell::before` via CSS file
4. Injected `<style>` rule for `::before` via dynamic `<style>` element

## The Fix

Replace the `<style>` element approach with a real `<div>` DOM element carrying inline styles via `element.style.cssText`:

```js
var el = document.createElement('div');
el.id = 'aurora-starfield';
el.style.cssText =
  'position:fixed;top:0;left:0;width:100%;height:100%;' +
  'z-index:0;pointer-events:none;' +
  'background:radial-gradient(...),radial-gradient(...),...;';
document.body.appendChild(el);
```

`element.style.cssText` sets inline styles on the element itself, which is unaffected by CSP `style-src` restrictions. The `<div>` renders immediately without requiring a nonce.

A secondary issue was the theme manager script loading order: `theme-manager.js` loads and executes *before* any theme files (`default.js`, `aurora.js`, etc.). Theme registration (`window.ThemeRegistry.register(...)`) stores configs but the `mapping` callback may never be invoked for the active theme. The starfield injection was moved from inside the `auroraMapping` callback to the IIFE body, executing immediately when `aurora.js` loads.

## Verification

- Open aurora theme → stars appear as 2.5–1 px white dots on dark `--bg: #05070d` background
- Switch to another theme → stars removed via teardown (`document.getElementById('aurora-starfield').remove()`)
- Light mode uses muted gray-blue stars at lower opacity
- The element layers at `z-index: 0` in the root stacking context, behind `.app-shell` (z-index: 2), visible through transparent background areas

## File Locations

- `anvil/api/static/js/themes/aurora.js` — DOM element injection in IIFE body (lines 12–75)
- `anvil/api/static/css/themes/aurora.css` — reverted to original (no starfield CSS)

## References

- [[Discoveries/Discoveries]]
- [[Reference/theme-creation-guide]]
- [[Reference/particle-effect-authoring]]
