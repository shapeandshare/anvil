---
title: 048 Learning Fine-Tuning Concepts
type: session-log
tags:
  - type/session-log
  - domain/content
  - domain/ui
created: '2026-06-28'
updated: '2026-06-28'
status: draft
source: agent
aliases: 048 Learning Fine-Tuning Concepts
---

# 048 Learning Fine-Tuning Concepts

**Session**: Full speckit flow (specify → clarify → plan → tasks → analyze → implement) for spec 048, adding three explorable fine-tuning concept pages and an interactive LoRA low-rank decomposition widget.

## Work Done

### Clarification (5 questions)
- Insertion point: after "Model Export" as individual `LEARNING_ARC` entries
- LoRA widget: full interactive JS widget (not static diagram)
- Forward links: "Coming soon" badges for unshipped 039/044
- Decision page format: comparison table with strengths/weaknesses/use-cases
- Page ordering: What fine-tuning is → Warm-start vs PEFT/LoRA → Fine-tune vs prompt vs RAG

### Plan & Tasks
- Created `plan.md`, `research.md`, `data-model.md`, `quickstart.md`, `tasks.md` (22 tasks)
- Critical review caught 5 LOW issues (terminology, testability, coverage) — all remediated
- Verified all code-level claims against actual codebase via explore agents — one line-number imprecision fixed

### Implementation

**Python** (`anvil/api/v1/learning.py`):
- 3 `*_STEPS` arrays: `FINE_TUNING_INTRO_STEPS`, `WARMSTART_VS_LORA_STEPS`, `FINETUNE_VS_PROMPT_VS_RAG_STEPS`
- 3 `LEARNING_ARC` entries inserted after "Model Export" (key `export`)
- 3 route handlers: `fine_tuning_intro_page`, `warmstart_vs_lora_page`, `finetune_vs_prompt_vs_rag_page`

**Widget** (`anvil/api/static/js/widgets/lora.js`):
- Pure-JS truncated SVD via power iteration with deflation — reconstruction error decreases **monotonically** with rank (0.165 → 0.008)
- Low-rank-plus-noise synthetic W so error drops sharply at first 3 ranks then plateaus
- Retina/HiDPI `devicePixelRatio` canvas handling
- Purely client-side, no API calls

**Template** (`anvil/api/templates/archetypes/concept.html`):
- Registered `lora.js` script include and `lora: window.LoraWidget` in `WIDGET_CLASSES`

**CSS** (`anvil/api/static/css/components.css`):
- `.lora-controls`, `.lora-panels`, `.lora-panel`, `.lora-canvas`, `.lora-info` — widget layout
- `.coming-soon-badge` — forward-link badge for unshipped capabilities
- `.learn-comparison-table` — comparison table styling

**Tests** (`tests/e2e/api/test_pages.py`):
- `test_learn_fine_tuning_intro` — asserts 200, title, coming-soon-badge
- `test_learn_warmstart_vs_lora` — asserts 200, title, `data-widget="lora"`, `lora.js` include, coming-soon-badge
- `test_learn_finetune_vs_prompt_vs_rag` — asserts 200, title, comparison-table with Strengths/Weaknesses/Best For

### Spec Artifacts Updated
- `spec.md`: SC-002 widget behavior criteria, FR-024 terminology normalized, acceptance scenarios clarified
- `plan.md`: Article IV (TDD) rationale updated for new e2e tests
- `tasks.md`: T005-T007 step outlines expanded; T008-T010 e2e tests added; line refs corrected
- `feature.json`: Fixed directory path to full name

## Discoveries

- **Widget educational correctness is critical**: The initial LoRA widget taught the *inverse* concept (error increased with rank). A and B were random and independent of W — no SVD. Prevented by extracting and verifying the math numerically using both Python and Node.js against the actual shipped JS.
- **LEARNING_ARC_LESSONS is a blacklist derivation**: New entries auto-appear in the index page as long as their keys aren't in `_ADDITIONAL_KEYS | _OPS_KEYS`. Verified via `frozenset` exclusion at lines 293–297.
- **`concept.html` widget rendering**: `step.widget` in step dicts drives auto-rendered `<div class="concept-widget" data-widget="...">` elements via Jinja2 loop (lines 26–36), then auto-instantiated via `document.querySelectorAll('.concept-widget')` (lines 109–116).
- **No-API widgets are feasible**: `governance.js`, `architecture.js`, `memory-divergence.js` all operate purely client-side with no `fetch`/`apiFetch` calls.
- **Canvas `devicePixelRatio`**: `params.js` and `sampling.js` handle DPR scaling; widgets without it render blurry on Retina.
- **Pre-existing `test_learn_cloud_compute` failure**: "cloud-compute" key exists only in `LEARNING_ARC_ADDITIONAL`, not `LEARNING_ARC`, causing `_arc_context` to return `current_index=-1`. Unrelated to spec 048.

## References
- [[Specs/048 Learning Fine-Tuning Concepts/048 Learning Fine-Tuning Concepts - spec|Feature Spec]]
- [[Specs/048 Learning Fine-Tuning Concepts/plan|Implementation Plan]]