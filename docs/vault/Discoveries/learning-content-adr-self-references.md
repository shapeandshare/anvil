---
aliases:
  - learning-content-adr-self-references
code-refs:
  - anvil/api/v1/learning.py
  - anvil/api/templates/archetypes/faq.html
created: '2026-06-23'
related:
  - docs/vault/Reference/stale-learning-content-llama-migration.md
  - docs/vault/Sessions/2026-06-14-stale-learn-content-fix.md
session: '2026-06-23'
source: agent
status: draft
summary: >-
  User-facing learning material contained inline ADR/FR citations and internal
  file paths — all removed in favor of plain-language descriptions.
tags:
  - type/discovery
  - domain/content
  - status/draft
title: Learning Content Contained Internal ADR/FR References
type: discovery
updated: '2026-06-23'
---
During a review of the user-facing learning material, five ADR citations, one FR spec reference, and three internal file paths were found embedded in lesson bodies, glossary definitions, and FAQ answers intended for end users learning about LLM concepts.

The lesson steps in `anvil/api/v1/learning.py` referenced ADR-033, ADR-016, ADR-009, ADR-023, and FR-021 inline — none of which help a user understand content-addressed storage, MLflow lineage, or weight replication. The FAQ at `anvil/api/templates/archetypes/faq.html` cited ADR-007 in the architecture answer and pointed users to `docs/vault/Reference/Glossary.md`, the vault, and an internal code file path. The glossary entries for "Vault" and "Constitution" in `learning.py` exposed `docs/vault/` and `.specify/memory/constitution.md` file paths.

All 11 instances were removed and replaced with plain-language descriptions. The ADR citations appear to be AI-generation artifacts — an agent likely pulled them from nearby source-code comments when writing lesson text, not realizing they are process artifacts irrelevant to learners.

## Pattern to Watch

Any time learning content or user-facing docs are auto-generated, the generation context should be constrained to exclude internal project metadata (ADR numbers, spec FR numbers, vault file paths, `__init__` or import conventions). The glossary boundary is also unclear: some entries describe ML concepts (Value, KV Cache, RoPE) while others describe project-internal tooling (ADR, Vault, Constitution). Consider whether the latter belong in a developer onboarding doc rather than the user-facing glossary.

## References

- `anvil/api/v1/learning.py` — lesson body strings at lines ~1240, ~1292, ~1376, ~1380, ~1408; glossary entries at ~1778, ~1782
- `anvil/api/templates/archetypes/faq.html` — FAQ answers at lines ~86, ~188, ~207, ~224
