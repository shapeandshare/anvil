---
title: Data Model — Learning Architecture Differences
type: spec
tags:
  - type/spec
created: '2026-06-28'
updated: '2026-06-28'
---
# Data Model: Learning Architecture Differences

**Feature**: 049 Learning Architecture Differences
**Date**: 2026-06-28

## Overview

This feature adds 1 accordion-style learning page to the existing learning system. No new database entities, ORM models, or persistence layer changes are needed. The "data model" here describes the in-memory data structures used by the existing learning content system.

## Entities

### 1. LearningArcEntry (existing — extended)

Defined inline in `LEARNING_ARC` list in `anvil/api/v1/learning.py`.

| Field | Type | Description |
|-------|------|-------------|
| `key` | string | Unique identifier (e.g., `"architecture-differences"`). Used for route paths and `_arc_context()` lookup. |
| `title` | string | Display title (e.g., `"Architecture Differences"`) |
| `path` | string | Route path (e.g., `"/v1/learn/architecture-differences"`) |
| `desc` | string | Short description shown on the learning index page. HTML-safe. |

**New entry to add (1):**

| Key | Title | Path | Description |
|-----|-------|------|-------------|
| `architecture-differences` | Architecture Differences | `/v1/learn/architecture-differences` | How model architectures differ — tokenization, attention variants, parameter scaling, context length — and what those differences mean for fine-tuning. |

**Insertion point**: After `"finetune-vs-prompt-vs-rag"` entry (line ~191), before `"chunking"` (line ~193) in `LEARNING_ARC`.

### 2. AccordionSection (new — step data variant)

Defined as `ARCHITECTURE_DIFFERENCES_STEPS` array in `anvil/api/v1/learning.py`. Each item is a dict representing one accordion section. Uses the same `key`/`title`/`body` structure as carousel steps but rendered as accordion panels instead of carousel slides.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `key` | string | Yes | Unique section identifier. Used for anchor-ID targeting (e.g., `#tokenization`). |
| `title` | string | Yes | Section heading displayed in the accordion header. |
| `body` | string | Yes | HTML body content. May include inline HTML tags, `<code>`, `<a>` links, `<table>`, `<ul>`. |

**New array (1):**

| Array Name | Sections | Description |
|------------|----------|-------------|
| `ARCHITECTURE_DIFFERENCES_STEPS` | 5 sections | Architecture differences across dimensions. No widgets. |

**Sections (in order):**

| Key | Title | Content Description |
|-----|-------|-------------------|
| `tokenization` | Tokenization Differences | Char-level vs subword vs BPE tokenization; vocabulary size differences; fine-tuning implications |
| `attention` | Attention Variants | Causal attention vs cross-attention; multi-query vs grouped-query vs multi-head; fine-tuning portability |
| `parameters` | Parameter Scaling | Total parameter count breakdown; width (n_embd) vs depth (n_layer); how scaling affects fine-tuning behavior |
| `context` | Context Length | Context window size differences; RoPE extrapolation; position encoding and fine-tuning data length |
| `allow-list` | Architecture Allow-List | Concrete runnable architectures (v1: LlamaForCausalLM); accepted format (safetensors); why the boundary exists; GGUF as deferred/planned |

### 3. Cross-Link Targets (anchor IDs)

The module supports inbound anchor-ID links from the catalog eligibility flags (041).

| Anchor ID | Target Section | Purpose |
|-----------|---------------|---------|
| `#allow-list` | allow-list section | Primary entry point from 041 "not eligible / unknown architecture" flags |

## Relationships

```
LEARNING_ARC (list)
  └── entry: "architecture-differences"
        └── maps to: ARCHITECTURE_DIFFERENCES_STEPS (via route handler)
        └── linked from: 041 catalog eligibility flags → #allow-list anchor

041 Catalog (external)
  └── eligibility flags
        └── link to: /v1/learn/architecture-differences#allow-list
```

The `_arc_context()` function derives prev/next navigation from the `LEARNING_ARC` list order. The 049 entry sits between the 048 fine-tuning concept pages and the general chunking lesson.

## Validation Rules

- Step array must have at least 3 sections (FR-025 covers 4+ dimensions)
- Each section must have a unique `key` within the array
- Section keys use kebab-case (matching existing convention)
- The `allow-list` section key MUST be present (FR-025a anchor target)
- Route path `/v1/learn/architecture-differences` must match the key

## No Database Changes

This feature does not require:
- New ORM models
- New database tables
- Alembic migrations
- New SQLAlchemy repositories