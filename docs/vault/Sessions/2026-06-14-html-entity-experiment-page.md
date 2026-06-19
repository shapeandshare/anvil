---
date: '2026-06-14'
title: HTML Entity Rendering Fix in Experiment Page
type: session-log
tags:
- type/session-log
- domain/ui
created: '2026-06-18'
updated: '2026-06-18'
---
# Session: HTML entity rendering in experiment page

**Date**: 2026-06-14
**Type**: Bugfix

## Summary

Fixed raw HTML entity display in the experiment detail page. The Config and Tokenizer status cells were showing `&#10003;` as literal text instead of rendering the checkmark character.

## Root Cause

In `anvil/api/templates/archetypes/experiment.html`, the JavaScript used `.textContent` to set cell values:

```javascript
stConfig.textContent = configFile ? '&#10003;' : '—';
```

`.textContent` sets text literally — it does **not** parse HTML entities. So `&#10003;` was displayed as the raw entity code rather than the intended ✓ character.

## Fix

Replaced the HTML entity with the actual Unicode character:

```javascript
stConfig.textContent = configFile ? '✓' : '—';
```

This is the correct pattern: when using `.textContent` (which is safe and appropriate here), use literal Unicode characters rather than HTML entity references. HTML entities only work when assigned to `.innerHTML`.

## Files Changed

- `anvil/api/templates/archetypes/experiment.html` — lines 173-174

## Prevention

When using `.textContent` to display symbols/characters:
- Use literal Unicode characters (✓, →, ★, etc.)
- HTML entities (`&#10003;`, `&amp;`, `&lt;`) will render as raw text
