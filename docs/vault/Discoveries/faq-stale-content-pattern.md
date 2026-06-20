---
title: FAQ Stale Content Pattern
type: discovery
status: draft
source: agent
related:
  - '[[Sessions/2026-06-19-faq-stale-content-fix]]'
code-refs:
  - anvil/api/templates/archetypes/faq.html
session: 2026-06-19-faq-stale-content-fix
created: '2026-06-19'
updated: '2026-06-19'
summary: >-
  Self-contradiction and stale hardcoded values in FAQ — GPU description and
  parameter count not kept in sync with architecture changes.
tags:
  - type/discovery
  - domain/content
  - status/draft
aliases:
  - FAQ Stale Content Pattern
  - faq-gpu-contradiction
  - faq-stale-param-count
---
The FAQ page at `/v1/learn/faq` (`anvil/api/templates/archetypes/faq.html`) had a self-contradiction and stale hardcoded values:

1. **GPU contradiction**: "Why is it so slow?" claimed the engine is "pure Python with no GPU acceleration" — but "Can I train on GPU, or only CPU?" (two items above) correctly described a dual CPU/GPU backend. The "slow" answer was written before the GPU backend existed and was never updated.

2. **Stale parameter count**: Only the "How is this related to ChatGPT?" FAQ used the correct `4,192+ parameters (depending on architecture config)` form. Two other items ("Can I make it generate better names?" and "What if I change the dataset?") still said the old `4,192 parameters`.

## Root Cause

The FAQ is a flat HTML template with no data-driven generation. Items are hand-authored and drift independently when architecture changes (GPU backend addition, configurable param counts). There is no cross-reference check or content audit process to catch stale answers.

## Prevention

- Consider generating the FAQ from structured data (YAML/JSON) with shared parameter descriptions, so a single source of truth propagates to all items.
- Or add a vault health check that cross-references FAQ content against known architectural facts.
