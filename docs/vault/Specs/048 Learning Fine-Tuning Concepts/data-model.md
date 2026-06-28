---
title: Data Model — Learning Fine-Tuning Concepts
type: spec
tags:
  - type/spec
created: '2026-06-28'
updated: '2026-06-28'
---
# Data Model: Learning Fine-Tuning Concepts

**Feature**: 048 Learning Fine-Tuning Concepts
**Date**: 2026-06-28

## Overview

This feature adds 3 concept pages to the existing learning system. No new database entities, ORM models, or persistence layer changes are needed. The "data model" here describes the in-memory data structures used by the existing learning content system.

## Entities

### 1. LearningArcEntry (existing — extended)

Defined inline in `LEARNING_ARC` list in `anvil/api/v1/learning.py`.

| Field | Type | Description |
|-------|------|-------------|
| `key` | string | Unique identifier (e.g., `"fine-tuning-intro"`). Used for route paths and `_arc_context()` lookup. |
| `title` | string | Display title (e.g., `"What Fine-Tuning Is"`) |
| `path` | string | Route path (e.g., `"/v1/learn/fine-tuning-intro"`) |
| `desc` | string | Short description shown on the learning index page. HTML-safe. |

**New entries to add (3):**

| Key | Title | Path | Description |
|-----|-------|------|-------------|
| `fine-tuning-intro` | What Fine-Tuning Is | `/v1/learn/fine-tuning-intro` | What fine-tuning means in the context of LLMs — continued training of a pre-trained model on new data. |
| `warmstart-vs-lora` | Warm-Start vs PEFT/LoRA | `/v1/learn/warmstart-vs-lora` | How full fine-tuning (warm-start) differs from parameter-efficient approaches like LoRA, and the low-rank intuition behind adapters. |
| `finetune-vs-prompt-vs-rag` | Fine-Tune vs Prompt vs RAG | `/v1/learn/finetune-vs-prompt-vs-rag` | When to fine-tune, when to prompt-engineer, and when to use retrieval-augmented generation — a decision comparison. |

**Insertion point**: After `"export"` entry (line 173), before `"chunking"` (line 175) in `LEARNING_ARC`.

### 2. LessonStepData (existing — new instances)

Defined as `*_STEPS` arrays in `anvil/api/v1/learning.py`. Each array holds step dicts.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `key` | string | Yes | Unique step identifier within the array. Used for hash-based deep linking. |
| `title` | string | Yes | Step heading displayed in the carousel. |
| `body` | string | Yes | HTML body content. May include inline HTML tags, `<code>`, `<a>` links, tables. |
| `widget` | string | No | Widget type key if the step has an interactive visualization. Registered in `WIDGET_CLASSES` map in `concept.html`. |

**New arrays (3):**

| Array Name | Steps | Widget |
|------------|-------|--------|
| `FINE_TUNING_INTRO_STEPS` | 5 steps | None |
| `WARMSTART_VS_LORA_STEPS` | 6 steps | `lora` (new widget) |
| `FINETUNE_VS_PROMPT_VS_RAG_STEPS` | 5 steps | None (comparison table in body) |

### 3. LoRA Widget State

The `lora.js` widget manages client-side state only (no backend API).

| Variable | Type | Description |
|----------|------|-------------|
| `rank` | integer (1-16) | Current LoRA rank, controlled by slider |
| `matrixSize` | integer (default 32) | Size of the synthetic weight matrix |
| `_reducedMotion` | boolean | Respects `prefers-reduced-motion` |
| `_canvas` | HTMLCanvasElement | The visualization canvas |

## Relationships

```
LEARNING_ARC (list)
  ├── entry: "fine-tuning-intro"
  │     └── routes to: FINE_TUNING_INTRO_STEPS
  ├── entry: "warmstart-vs-lora"
  │     ├── routes to: WARMSTART_VS_LORA_STEPS
  │     └── references widget: "lora"
  └── entry: "finetune-vs-prompt-vs-rag"
        └── routes to: FINETUNE_VS_PROMPT_VS_RAG_STEPS
```

The `_arc_context()` function derives prev/next navigation from the `LEARNING_ARC` list order, so the 3 entries naturally form a connected sub-sequence once insertion is correct.

## Validation Rules

- All three step arrays must have at least 4 steps each (FR-024a: "explorable-explanation style")
- Each step must have a unique `key` within its array
- Step keys use kebab-case (matching existing convention)
- The `lora` widget reference in `WARMSTART_VS_LORA_STEPS` must have a corresponding entry in `WIDGET_CLASSES` and a script include in `concept.html` (FR-024c)

## No Database Changes

This feature does not require:
- New ORM models
- New database tables
- Alembic migrations
- New SQLAlchemy repositories