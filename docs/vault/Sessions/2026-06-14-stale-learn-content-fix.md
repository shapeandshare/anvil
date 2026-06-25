---
title: 'Session: Fix Stale Learning Content After GPT→Llama Migration'
type: session-log
tags:
  - type/session-log
  - domain/core
created: '2026-06-14'
updated: '2026-06-14'
aliases:
  - 2026-06-14-stale-learn-content-fix
source: agent
---
# Session: Fix Stale Learning Content After GPT→Llama Migration

**Date**: 2026-06-14
**Type**: Session Log
**Tags**: [type/session, domain/content]

## Summary

Investigated and fixed 3 stale lesson sections in the interactive learning courses (`router.py`) that still described GPT-2 architecture after the Llama migration. The progressive code examples (`examples/train*.py`) were already correct, but the inline lesson text was never updated.

## Changes

**File**: `anvil/api/v1/router.py` (3 sections, 5 edits)

| Lesson | Step | Change |
|--------|------|--------|
| Embeddings | "Position Matters" | WPE → RoPE explanation |
| Embeddings | "Type and Explore" | "position offset" → "position via RoPE inside attention" |
| Attention | "How Attention is Computed" | Added RoPE mention before dot product |
| Parameters | "Position Embeddings (WPE)" | Replaced entire entry with "RoPE (Position Encoding)" |
| Parameters | "MLP and Output Head" | fc1/fc2 → SwiGLU gate/up/down |

## Vault Enrichment

- **New discovery note**: [[Reference/stale-learning-content-llama-migration]] — documents root cause and prevention for future migrations

## Related

- [[Sessions/2026-06-14-gpt-to-llama-completion]] — missed the lesson content in its audit
- [[Sessions/2026-06-13-learning-content-enrichment]] — added lesson steps but didn't cross-check architecture
- [[Decisions/ADR-007-llama-engine-evolution]] — the original architecture migration