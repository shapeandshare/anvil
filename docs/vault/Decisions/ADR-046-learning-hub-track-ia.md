---
title: "ADR-046: Learning Hub Track-Based Information Architecture"
type: decision
tags:
  - type/decision
  - domain/content
  - domain/ui
created: '2026-07-03'
updated: '2026-07-03'
aliases:
  - Learning Hub Track-Based IA
source: agent
code-refs:
  - anvil/api/v1/learning.py
  - anvil/api/templates/archetypes/learn-index.html
---

# ADR-046: Learning Hub Track-Based Information Architecture

## Status

Accepted

## Context

The Learning Hub index page (`/v1/learn`) rendered all topics as a single flat numbered `<ol>` constrained to a 640px column. As the content grew to 28 topics plus FAQ and glossary, this approach stopped scaling:

- No grouping or categorization beyond three ad-hoc sections (Lessons / Additional / Operations) that had overlapping entries (FAQ, glossary, runtime-config appeared in both Lessons and Additional)
- No metadata for grouping — the data model was only `{key, title, path, desc}` with no `category`, `track`, `difficulty`, or `tag` field
- No search, filter, or progressive disclosure — all items always in the DOM, equal visual weight
- The numbered list (1→21) implied a linear progression, but the content actually spans ~5 distinct domains: core model internals, training mechanics, fine-tuning, data management, and operations/reference
- Rich per-lesson metadata (step counts 5–10, 17 interactive widgets) existed in the step definitions but was invisible on the index — nothing helped users decide which topic to explore

## Decision

Adopt a **track-based information architecture** for the learning hub:

1. **Add a `LearningTrack` enum** (StrEnum) with six tracks: FOUNDATIONS, TRAINING_MECHANICS, FINE_TUNING, DATA_EXPERIMENTS, OPERATIONS, REFERENCE
2. **Add a `track` field** to every entry in `LEARNING_ARC`, `LEARNING_ARC_ADDITIONAL`, and `OPS_ARC`
3. **Derive topic metadata** (step_count, has_widget, widget names) from the existing `*_STEPS` lists via a `_topic_meta()` helper
4. **Rewrite `learn-index.html`** as a grouped hub:
   - Header with total count + filter input
   - Track sections with title + description + card grid
   - Compact cards: title, description, widget badge (⚡ Interactive), step count badge
   - Client-side JS filter by title/description/keyword
5. **Simplify the route handler**: `learn_index()` now calls `_grouped_arc()` and passes `{"groups": ...}` instead of the old three-list split (`lessons`, `additional`, `ops`)

### Track assignments

| Track | Topics |
|-------|--------|
| **Foundations** | data-fundamentals, tokenization, embeddings, parameters |
| **How Training Works** | autograd, attention, loss, sampling, adam, training-loop, architecture, graph, export |
| **Fine-Tuning** | fine-tuning-intro, warmstart-vs-lora, finetune-vs-prompt-vs-rag, architecture-differences |
| **Data & Experiments** | chunking, content-versioning, experiment-tracking, governance, memory-divergence |
| **Operations** | runtime-config, cloud-compute, backup, configuration, service-management |
| **Reference** | FAQ, glossary |

### Track descriptions

Each track gets a human-readable label and a one-line description rendered directly on the hub:

- **Foundations**: "Core building blocks — how data becomes numbers the model can compute with."
- **How Training Works**: "From autograd and attention to the full training loop and model export — the engine internals."
- **Fine-Tuning**: "Adapting pre-trained models with new data — full warm-start vs. parameter-efficient methods like LoRA."
- **Data & Experiments**: "Chunking, versioning, tracking, and governance — the data and experiment management layer."
- **Operations**: "Runtime config, service management, backups, and cloud compute."
- **Reference**: "FAQ and glossary for quick lookup."

## Consequences

### Positive

- **Scales with content growth**: tracks can accommodate new topics without making the index feel longer — users only see the relevant track
- **Discoverability**: the filter input lets users find topics by keyword; widget and step badges help identify hands-on topics
- **Backward compatible**: all existing route handlers, lesson pages (`concept.html`), and widget integrations are untouched
- **Lightweight**: only 2 files changed (~360 lines net), no new dependencies, no JS framework

### Negative

- **Track assignments are hardcoded**: adding/changing tracks requires editing `learning.py`; not configurable without a code change
- **No per-user progress tracking**: the hub doesn't show which lessons a user has completed (out of scope for this pass)

## Compliance

- All entries in `LEARNING_ARC` MUST have a `track` field of type `LearningTrack`
- The `learn-index` template MUST render all topics grouped by track
- 288 existing tests must pass; lint must be clean

## See Also

- [[Decisions/ADR-041-simplicity-first-boring-technology|ADR-041: Simplicity First (Boring Technology)]]
- [[Sessions/2026-07-03-learning-hub-track-redesign|Session: Learning Hub Track Redesign]]