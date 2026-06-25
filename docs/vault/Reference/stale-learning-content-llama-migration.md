---
title: Stale Learning Content After GPT→Llama Migration
type: reference
tags:
  - type/reference
  - domain/core
created: '2026-06-14'
updated: '2026-06-14'
---
# Discovery: Stale Learning Content After GPT→Llama Migration

**Date**: 2026-06-14
**Tags**: [domain/core, domain/content, type/discovery]

## Summary

During the GPT→Llama architecture migration (ADR-007), the interactive learning courses at `/v1/learn/*` were **not updated**. The progressive code examples (`examples/train*.py`) were correctly migrated, but the lesson text and parameter descriptions remained GPT-2 era artifacts.

## Stale Content Found

### 1. Embeddings Lesson — WPE reference

**Location**: `anvil/api/v1/router.py`, `EMBEDDING_STEPS`, step "Position Matters"

**Problem**: Described learned position embeddings (WPE matrix) being added to token embeddings. The Llama architecture uses **RoPE** (Rotary Position Embedding), which encodes position by rotating Q/K vectors — no additive WPE.

**Fix**: Replaced with RoPE explanation. The "Type and Explore" step was also updated to clarify the widget shows pure token embeddings before RoPE.

### 2. Parameters Lesson — WPE parameter entry

**Location**: `anvil/api/v1/router.py`, `PARAMS_STEPS`, step "Position Embeddings (WPE)"

**Problem**: Listed WPE as a parameter matrix of shape `block_size x n_embd`. RoPE has no learned position parameters — only precomputed cos/sin tables.

**Fix**: Replaced with "RoPE (Position Encoding)" entry describing precomputed tables and rotation mechanism.

### 3. Parameters Lesson — fc1/fc2 MLP reference

**Location**: `anvil/api/v1/router.py`, `PARAMS_STEPS`, step "MLP and Output Head"

**Problem**: Described ReLU MLP with `fc1 (16 x 64)` and `fc2 (64 x 16)`. The Llama architecture uses **SwiGLU MLP** with `gate`, `up`, `down` projections and `intermediate_size = int(8 * n_embd / 3)`.

**Fix**: Replaced with SwiGLU description matching actual parameter shapes.

### 4. Attention Lesson — RoPE not mentioned

**Location**: `anvil/api/v1/router.py`, `ATTENTION_STEPS`, step "How Attention is Computed"

**Problem**: Described Q/K/V dot product without explaining how position is encoded.

**Fix**: Added "Position is encoded via RoPE: the Query and Key vectors are rotated by an angle proportional to their position before the dot product."

## Root Cause

The learning content enrichment (2026-06-13 session) and the Llama migration (ADR-007) were developed as parallel efforts. The enrichment added RMSNorm and residual connection steps to the attention lesson, but neither pass audited the full lesson text for stale GPT-2 architecture descriptions. The subsequent session log `2026-06-14-gpt-to-llama-completion.md` audited code, docstrings, README, and reference docs — but missed the inline lesson steps in `router.py`.

## Prevention

Any future architecture migration or refactor should include a checklist item: **"Audit inline lesson content in `router.py` for stale descriptions."** The lesson steps (`EMBEDDING_STEPS`, `ATTENTION_STEPS`, `PARAMS_STEPS`, etc.) are string literals co-located with route definitions and are easily overlooked.

## See Also

- [[Reference/ArchitectureOverview|Architecture Overview]]
