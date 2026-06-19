---
title: Content Enrichment Session
type: session
tags:
  - type/session-log
  - domain/content
created: 2026-06-15
updated: 2026-06-15
---

# Content Enrichment Session

**Date**: 2026-06-15

## Summary

Systematic enrichment of learning content and reference documentation across two dimensions: vault reference docs and interactive walkthroughs.

## What Was Created

### Vault Reference Docs (6 new)

| Doc | Content |
|-----|---------|
| [[Reference/ArchitectureOverview]] | Full system architecture diagram, layer discipline rules, end-to-end data flow for training and inference, learning walkthrough flow |
| [[Reference/SafetensorsExport]] | Export pipeline diagram, tensor name mapping table (anvil→HF), config generation, tokenizer export, MLflow pyfunc model, loading guide |
| [[Reference/DualBackend]] | CPU vs GPU comparison table, weight bridge function, architecture parity checklist, device resolution, usage scenarios |
| [[Reference/Hyperparameters]] | Per-parameter effect analysis, interaction guide, parameter count formula, quick reference table, tuning recommendations |
| [[Reference/ProgressiveWalkthroughs]] | train0→train5 progression with code examples, concept introduction per script, pedagogical design philosophy |
| [[Reference/MlflowIntegration]] | System architecture, tracking data inventory, registry flow, lifecycle management, external server support, data flow diagram |

### Walkthrough Enrichments

- **TOKENIZATION_STEPS**: Added "Tokenizer vs Vocabulary" step explaining the two classes
- **ATTENTION_STEPS**: Added "KV Cache Mechanics" step explaining cache behavior and RoPE rotation timing
- **TRAINING_LOOP_STEPS**: Added "CPU vs GPU Training" step explaining dual backend
- **PARAMS_STEPS**: Added "Safetensors Export Names" step with tensor name mapping
- **ADAM_STEPS**: Added "Weight Decay (AdamW)" step explaining absence of weight decay
- **LEARNING_ARC**: Added "Data Flow" and "Model Export" entries

### New Walkthroughs (2)

| Route | Steps | Description |
|-------|-------|-------------|
| `/v1/learn/data-flow` | 5 steps | Browser→Service→Engine→SSE→Persistence flow |
| `/v1/learn/export` | 5 steps | Why export, tensor mapping, config gen, tokenizer, MLflow pyfunc |

### Cross-References Updated

- `index.md` — quick links table to all new docs
- `TrainingDataFlow.md` — links to ArchitectureOverview, DualBackend, Hyperparameters
- `Glossary.md` — added Safetensors, RoPE, SwiGLU, Dual Backend, GPU Bridge terms

## What Was Already Covered (verified)

- Tokenization walkthrough ✓ (was already complete with 5 steps)
- Autograd/Value graph walkthrough ✓ (was already complete with 5 steps)
- Training internals walkthrough ✓ (TRAINING_LOOP_STEPS covered well)
- TrainingDataFlow reference ✓ (existing doc was thorough)

## Critical Review Findings (Round 2 — Application Audit)

A follow-up critical review of the application learning surface (templates, widgets, services) found and fixed **four real bugs**, three of which were pre-existing stale GPT-2 artifacts and one introduced by the enrichment work:

1. **`graph.html` computation graph (stale GPT-2)** — The forward-pass explorer still showed WPE position embedding, LayerNorm, and ReLU MLP. Rewrote all 8 `STEP_INFO` entries + node IDs/edges to match the actual Llama `LlamaModel.forward()` (RMSNorm, RoPE, SwiGLU, residuals, final norm).

2. **`training.html` parameter estimator (stale GPT-2 formula)** — The live "Architecture / Parameters" card computed counts with `wpe = block_size * n_embd` (phantom — Llama has no learned position params) and a ReLU-style `4*n_embd` MLP term. Replaced with the correct Llama formula: `wte + lm_head + rms_final + n_layer*(4*n_embd² + 3*intermediate*n_embd + 2*n_embd)` where `intermediate = int(8*n_embd/3)`. Verified default config now yields the correct **3,952** params.

3. **`inference.py` autograd op-labeling (stale ReLU)** — `assign_op()` in both `forward_graph` and `backward_graph` labeled all single-child unary nodes `"relu"`. The engine uses **SiLU**, not ReLU. Relabeled catch-all to `"silu"` and updated the `autograd.js` legend + draw color maps to match.

4. **Adam vs AdamW (factual inconsistency, surfaced by enrichment)** — The new ADAM_STEPS "Weight Decay" walkthrough correctly noted the optimizer is plain Adam (no weight decay), but the pre-existing Glossary and TrainingDataFlow.md both called it "AdamW". Corrected Glossary, TrainingDataFlow (3 spots + ASCII diagrams), and Hyperparameters cross-ref to accurately say **Adam (not AdamW)**, matching `engine.py:438-443` which has no weight-decay term.

5. **Widget-less walkthrough layout bug (introduced by enrichment)** — The two new walkthroughs (DATA_FLOW_STEPS, EXPORT_STEPS) have zero widgets, which made `concept.html` render an empty bordered `.concept-widget-area` box (orphaned `border-top` + padding). Added `{% if steps | selectattr('widget') | list %}` guard so the widget area only renders when at least one step has a widget. This also cleans up ATTENTION_STEPS' trailing widget-less steps.

### Application Content Updates
- `learn-index.html` — lesson count made dynamic (`{{ arc|length }}`) instead of hardcoded "Eight"; intro mentions Llama, data flow, export
- `faq.html` — added 7 new Q&A: architecture, export, GPU/CPU, data flow, MLflow, dynamic lesson count, progressive examples, glossary

## Files Changed

- `anvil/api/v1/router.py` — enriched 5 walkthroughs + added 2 new ones
- `docs/vault/index.md` — updated quick links
- `docs/vault/Reference/Glossary.md` — added 5 new terms
- `docs/vault/Reference/TrainingDataFlow.md` — cross-reference links
- `docs/vault/Reference/*.md` — 6 new reference docs