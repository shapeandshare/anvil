---
title: "Session: Learning Hub Track-Based IA Redesign"
type: session-log
tags:
  - type/session-log
  - domain/content
  - domain/ui
  - status/draft
created: '2026-07-03'
updated: '2026-07-03'
aliases:
  - learning-hub-track-redesign-2026-07-03
status: draft
source: agent
---

# Session: Learning Hub Track-Based IA Redesign

**Date**: 2026-07-03
**Trigger**: User reported the learning section was "too long to be useful" with too many topics. Requested a complete rethink of how learning materials are presented.

## Summary

Used Sisyphus orchestration to map the full learning content system (an `explore` background agent mapped 28 topics, 24 step lists, 3 template archetypes, 17 interactive widgets, and ~3,300 lines in `learning.py`), then proposed two redesign directions. User selected Option A (track-based hub) with an emphasis on inviting depth — users should be able to "go as deep as they want" and see which lessons have interactive components.

### Output

1. **`anvil/api/v1/learning.py`** (169 lines added)
   - Added `LearningTrack` enum (6 tracks)
   - Added `track` field to all 35 entries across LEARNING_ARC, LEARNING_ARC_ADDITIONAL, OPS_ARC
   - Added `_TOPIC_STEPS` lookup dict, `_TRACK_LABELS`, `_topic_meta()`, `_grouped_arc()`
   - Updated `learn_index()` route handler — now uses `_grouped_arc()` instead of old three-list split

2. **`anvil/api/templates/archetypes/learn-index.html`** (rewritten, 294 lines)
   - Replaced single-column numbered list with a grouped hub: filter input, 6 track sections, responsive card grid
   - Each card shows: title, description, widget badge (⚡ Interactive), step count badge
   - Client-side JS filter hides/shows cards and collapses empty tracks

### Verification

- 288/288 tests pass
- Lint clean (black, ruff, isort, pylint, mypy)
- Vault audit: pending (manual `make vault-audit`)

### ADR

- [[Decisions/ADR-046-learning-hub-track-ia|ADR-046: Learning Hub Track-Based Information Architecture]]

## Key Discoveries

1. **The old `LEARNING_ARC_LESSONS` derivation was a hack**: it filtered out entries appearing in ADDITIONAL and OPS, but FAQ/glossary/runtime-config appeared in both LEARNING_ARC and LEARNING_ARC_ADDITIONAL — the `_EXCLUDED_KEYS` dedup was fragile. The track field replaces this entirely.
2. **17 widgets exist but were invisible on the index**: topics like tokenization, attention, and training-loop have rich interactive components; users had no way to identify hands-on lessons from the index.
3. **Step counts range from 5 to 12**: providing "N steps" on the card gives users a quick sense of depth before clicking.