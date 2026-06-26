---
title: 'Session: FAQ Stale Content Fix'
type: session-log
tags:
  - type/session-log
  - domain/content
  - domain/architecture
created: '2026-06-19'
updated: '2026-06-19'
aliases:
  - 'Session: FAQ Stale Content Fix'
source: agent
---
# Session: FAQ Stale Content Fix

**Date**: 2026-06-19
**Branch**: opencode/proud-falcon

## Summary

Critical review and correction of three out-of-date FAQ items on the `/v1/learn/faq` page. All three had hardcoded stale parameter counts or contradictions with other content on the same page.

## Changes Made

**File**: `anvil/api/templates/archetypes/faq.html`

1. **"Why is it so slow?"** — Claimed "pure Python with no GPU acceleration" despite the GPU FAQ two items above describing both CPU and GPU backends. Fixed to say "The CPU backend is pure Python" and cross-reference the GPU option.

2. **"Can I make it generate better names?"** — Hardcoded `4,192 parameters` → `4,192+ parameters (depending on architecture config)` to match the ChatGPT FAQ's wording.

3. **"What if I change the dataset?"** — Same stale `4,192 parameters` → same fix.

## Addendum (second pass)

4. **"Is there a glossary of terms?"** — The Glossary link at line 212 pointed to `/v1/learn/faq` (the FAQ page itself). Dead self-referential link. Created `/v1/learn/glossary` route with 47 terms rendered as collapsible entries, added glossary entry to `LEARNING_ARC`, and fixed the FAQ link.

## Key Discoveries

1. **Self-contradiction**: "Why is it so slow?" said no GPU acceleration, while "Can I train on GPU, or only CPU?" (same page) correctly described dual backends.
2. **Stale parameter count**: Only the ChatGPT FAQ used the correct `4,192+` form while two others were stuck at the old `4,192`.
3. **Dead self-referential link**: The Glossary link pointed to the FAQ page itself. No glossary route existed despite the FAQ claiming one was "accessible from the learning page."

## Related

- [[Reference/Glossary|Glossary]] — glossary of terms (created alongside fix)
- [[Design/Design|Design]] — UI design system for content pages
- [[Specs/007 Learning Content Enrichment/007 Learning Content Enrichment|007 Learning Content Enrichment]] — related learning content feature
