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

## Key Discovery

The FAQ page had a self-contradiction: "Why is it so slow?" said no GPU acceleration, while "Can I train on GPU, or only CPU?" (same page) correctly described dual backends. The parameter count was also inconsistent across items — only the ChatGPT FAQ used the correct `4,192+` form while two others were stuck at the old `4,192`.
