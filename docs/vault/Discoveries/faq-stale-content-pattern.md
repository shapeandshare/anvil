---
title: FAQ Stale Content Pattern
type: discovery
status: draft
source: agent
related:
  - '[[Sessions/2026-06-19-faq-stale-content-fix]]'
  - '[[Sessions/2026-06-20-faq-round-2-stale-content-fix]]'
code-refs:
  - anvil/api/templates/archetypes/faq.html
  - anvil/api/v1/learning.py
  - anvil/api/templates/archetypes/glossary.html
session: 2026-06-20-faq-round-2-stale-content-fix
created: '2026-06-19'
updated: '2026-06-20'
summary: >-
  Self-contradiction, stale hardcoded values, dead self-referential Glossary
  link, stale hardcoded lesson count, rotten module path, missing cloud compute,
  and misleading "zero dependencies" language in FAQ — content not kept in sync
  with architecture changes.
tags:
  - type/discovery
  - domain/content
  - status/draft
aliases:
  - FAQ Stale Content Pattern
  - faq-gpu-contradiction
  - faq-stale-param-count
  - faq-stale-lesson-count
  - faq-rotten-module-path
  - faq-missing-cloud-compute
  - faq-misleading-zero-deps
---
The FAQ page at `/v1/learn/faq` (`anvil/api/templates/archetypes/faq.html`) has been caught out of sync with the project state repeatedly. Each round of fixes reveals a new category of staleness:

### Round 1 (2026-06-19)

1. **GPU contradiction**: "Why is it so slow?" claimed the engine is "pure Python with no GPU acceleration" — but "Can I train on GPU, or only CPU?" (two items above) correctly described a dual CPU/GPU backend. The "slow" answer was written before the GPU backend existed and was never updated.

2. **Stale parameter count**: Only the "How is this related to ChatGPT?" FAQ used the correct `4,192+ parameters (depending on architecture config)` form. Two other items ("Can I make it generate better names?" and "What if I change the dataset?") still said the old `4,192 parameters`.

3. **Dead self-referential Glossary link**: The "Is there a glossary of terms?" FAQ answer had `<a href="/v1/learn/faq">Glossary</a>` — pointing to the FAQ page itself. No `/v1/learn/glossary` route existed.

### Round 2 (2026-06-20)

4. **Stale hardcoded lesson count**: The FAQ's "Why does it say '8 interactive lessons'?" answer still said "8" even though `LEARNING_ARC` had grown to 14 interactive walkthroughs plus FAQ and Glossary (16 total entries). The count was a hardcoded number that drifted silently as content was added over multiple sessions (theme engine, graph, architecture, data-flow, export, cloud-compute, glossary).

5. **Rotten module path**: The same answer referenced `LEARNING_ARC` in `anvil/api/v1/router.py`, but the router was decomposed into `pages.py` and `learning.py` during the DDD services restructure (012-ddd-services-restructure). The file path in the FAQ rotted silently — no import error because it's documentation text, not code.

6. **Missing cloud compute**: The "Can I train on GPU, or only CPU?" answer described two backends (CPU + GPU), but the project now has three (CPU + GPU + Modal/cloud). The cloud compute feature had been live for multiple sessions but the FAQ was never updated to mention it.

7. **Misleading "zero dependencies" claim**: The CPU backend answer said "pure Python (zero dependencies)" and "requires no additional packages." While the core engine (`anvil/core/`) is stdlib-only, the project as a whole depends on FastAPI, SQLAlchemy, Jinja2, etc. PyTorch is an optional dep (`[gpu]` extra), but the phrasing implied the entire project had no dependencies. Fixed to say "stdlib only, no framework."

## Root Cause

The FAQ is a flat HTML template with no data-driven generation. Items are hand-authored and drift independently when:
- Architecture changes (GPU backend, cloud compute, DDD decomposition)
- Content grows (LEARNING_ARC adding entries)
- Module structure changes (router.py → learning.py)

There is no cross-reference check, no content audit process, and no automated verification to catch stale answers. Unlike code (which has tests, type checks, and linters), FAQ text has zero guardrails.

## Prevention

- Consider generating the FAQ from structured data (YAML/JSON) with shared parameter descriptions, so a single source of truth propagates to all items.
- Add a routine that cross-references `LEARNING_ARC` length against any hardcoded counts in the FAQ.
- Check all module path references in FAQ text against the actual filesystem.
- Add a link-checker for all `<a href>` references in learning content templates to catch dead/self-referential links.
- During any PR that adds content to `LEARNING_ARC`, file an issue to review the FAQ for stale counts and paths.

## Fixes Applied (Round 1)

- "Why is it so slow?" — rephrased to say "The CPU backend is pure Python" and cross-reference the GPU option.
- "Can I make it generate better names?" — `4,192 parameters` → `4,192+ parameters (depending on architecture config)`.
- "What if I change the dataset?" — same param count fix.
- Created `/v1/learn/glossary` route with 47 glossary terms (`anvil/api/v1/learning.py`), a dedicated template (`archetypes/glossary.html`), and an entry in `LEARNING_ARC`.
- Fixed the broken Glossary `<a href>` in `faq.html` to point to `/v1/learn/glossary`.

## Fixes Applied (Round 2)

- "Why does it say '8 interactive lessons'?" — updated to "14 interactive walkthroughs plus FAQ and Glossary", generalized "recent additions" to include graph, architecture, cloud compute. Fixed filename to `anvil/api/v1/learning.py`.
- "Can I train on GPU, or only CPU?" — updated to "All three... three training backends" adding Cloud/Modal, reworded "pure Python (zero dependencies)" to "stdlib only, no framework."
- "Why is it so slow?" — reworded "pure Python" to "stdlib only, no framework."

## See Also

- [[Discoveries/Discoveries|Discoveries]]
