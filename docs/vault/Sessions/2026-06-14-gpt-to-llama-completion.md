---
title: 'Session: GPT→Llama Migration Completion'
type: session-log
tags:
  - type/session-log
  - domain/core
created: '2026-06-14'
updated: '2026-06-14'
aliases:
  - 2026-06-14-gpt-to-llama-completion
source: agent
---
# Session: GPT→Llama Migration Completion

**Date**: 2026-06-14  
**Type**: Session Log  
**Tags**: [type/session, domain/core, domain/governance]

## Summary

Audited and completed the GPT→Llama architecture migration — the class rename `GPT` → `LlamaModel` was never fully done during ADR-007. Updated all code references, docstrings, and active documentation to reflect the Llama architecture.

## Changes

### Code: Class Rename (14 files, 75 edits via LSP rename)

- **`anvil/core/engine.py`**: `class GPT` → `class LlamaModel`
- **`anvil/core/torch_engine.py`**: `class TorchGPT` → `class TorchLlamaModel`
- All import statements, type hints, and instantiations across services, API routes, tests, and examples updated automatically

### Code: User-Facing Strings

- `anvil/cli.py` + `tests/e2e/test_cli_training_tracked.py`: argparse `"Train GPT model"` → `"Train Llama model"`
- `anvil/services/inference.py`: `"what's GPT? it's a demo!"` → `"what's this? it's a demo!"`
- `examples/train5.py`: docstring and print message updated

### Active Documentation

| Document | Key Changes |
|----------|-------------|
| **README.md** | "Train GPT from scratch" → "Train from scratch"; "full GPT" → "full transformer" |
| **`.specify/memory/constitution.md`** | Article II: "GPT algorithm" → "Llama transformer architecture" |
| **Glossary.md** | "GPT training engine" → "Llama training engine"; `MicroGPTWorkbench` → `AnvilWorkbench`; weight names to Llama convention; `wpe` removed from State Dict entry |
| **TrainingDataFlow.md** | Full forward pass diagram rewritten — previously described GPT-2 (wpe, ReLU MLP, embedding-level norm). Now correctly describes Llama (RoPE, SwiGLU, learned RMSNorm scales, rms_final before lm_head). |
| **testing-guide.md** | Code examples (`GPT(...)` → `LlamaModel(...)`), test descriptions, walkthrough labels updated |
| **hero.html** | "train GPT from scratch" → "train from scratch"; "bigrams to full GPT" → "bigrams to full transformer" |
| **learn-index.html** | "character-level GPT model" → "character-level LLM" |
| **faq.html** | "microgpt" → "anvil" in user-facing text |

### Intentional GPT References Left (6 total)

- `anvil/core/engine.py` (L251-253): `"Old GPT-2 format detected"` error message — backward compatibility detection
- `anvil/services/inference.py` (L68): Comment about old format retrain
- `tests/unit/core/test_engine.py` (L224, 248, 322): Tests verifying old GPT-2 format rejection

## Vault Notes Updated

- [[Reference/Glossary]] — GPT→Llama, MicroGPTWorkbench→AnvilWorkbench, weight names
- [[Reference/TrainingDataFlow]] — Forward pass algorithm diagram rewritten

## Related

- [[Decisions/ADR-007-llama-engine-evolution]] — the original ADR for the architecture change
