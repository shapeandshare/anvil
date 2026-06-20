---
title: 'Session: FAQ Round 2 — Stale Content Fix'
type: session-log
tags:
  - type/session-log
  - domain/content
  - domain/architecture
created: '2026-06-20'
updated: '2026-06-20'
aliases:
  - 'Session: FAQ Round 2 — Stale Content Fix'
source: agent
related:
  - '[[Discoveries/faq-stale-content-pattern]]'
code-refs:
  - anvil/api/templates/archetypes/faq.html
  - anvil/api/v1/learning.py
---

# Session: FAQ Round 2 — Stale Content Fix

**Date**: 2026-06-20

## Summary

User reported the FAQ is out of date. Audited the entire FAQ template (`anvil/api/templates/archetypes/faq.html`) against current project state and found 4 new stale items beyond the previous fix round (2026-06-19).

## Changes Made

**File**: `anvil/api/templates/archetypes/faq.html`

1. **"Why does it say '8 interactive lessons' but there are more?"** — The `LEARNING_ARC` now has 16 entries (14 interactive walkthroughs + FAQ + Glossary). The "8" was hardcoded and never updated as content grew. Fixed to "14 interactive walkthroughs plus the FAQ and Glossary." Also generalized the stale "Recent additions include Data Flow and Model Export" to a broader list (graph, architecture, cloud compute).

2. **Stale module path** — Same answer referenced `LEARNING_ARC` in `anvil/api/v1/router.py`, but the router was decomposed into `pages.py` and `learning.py` during 012-ddd-services-restructure. Fixed to `anvil/api/v1/learning.py`.

3. **"Can I train on GPU, or only CPU?"** — Described two backends (CPU + GPU), missing the Cloud/Modal backend. Updated to "All three... three training backends" and described the cloud dispatch flow. Also reworded "pure Python (zero dependencies)... requires no additional packages" to "stdlib only, no framework" — the core engine is stdlib-only but the project has pip dependencies.

4. **"Why is it so slow?"** — Same "zero dependencies" issue. "Pure Python" → "stdlib only, no framework" for consistency.

## What Wasn't Stale

- Parameter count (`4,192+ parameters (depending on architecture config)`) — still accurate and consistent across all three FAQ items that use it.
- GPU bridge, safetensors export, MLflow integration, data flow pipeline — all still accurate.
- Glossary link — correctly points to `/v1/learn/glossary` (fixed in Round 1).

## Key Discoveries

1. **Rotten module paths**: Textual references to source file paths (`anvil/api/v1/router.py`) rot silently when code is moved. Unlike import statements, there's no compiler to catch it.
2. **Hardcoded counts drift**: The "8 interactive lessons" count was correct at some point but drifted as `LEARNING_ARC` grew over multiple sessions. No automated check correlates the count with the actual data structure.
3. **Missing feature coverage**: The cloud compute backend was added but the FAQ's "Can I train on GPU?" answer was never updated — it's not just stale data, it's missing coverage of a major feature.
4. **"Zero dependencies" is misleading**: Even though `anvil/core/` is stdlib-only, the `anvil` pip project has many dependencies. Saying "zero dependencies" in project documentation is confusing.

## Related Discovery

[[Discoveries/faq-stale-content-pattern]] — updated with Round 2 findings.
