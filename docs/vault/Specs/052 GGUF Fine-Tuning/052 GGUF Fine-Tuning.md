---
title: 052 GGUF Fine-Tuning
type: spec
tags:
  - type/spec
  - domain/training
  - domain/core
spec-refs:
  - docs/vault/Specs/052 GGUF Fine-Tuning/
status: draft
created: '2026-06-28'
updated: '2026-06-28'
aliases:
  - 052 GGUF Fine-Tuning
---

# 052 GGUF Fine-Tuning

**Deferred** GGUF spec (FT-AD-11) of the [[Specs/038 Fine-Tuning Arc/038 Fine-Tuning Arc|Fine-Tuning
Arc]]: make GGUF-sourced models first-class for training — convert to a PEFT-trainable form, fine-tune
an adapter (044), optionally re-export to GGUF (051). The most complex GGUF spec; sequenced last.

## Owned

- **FRs**: FR-001..FR-004 (spec-local)
- **Decisions**: FT-AD-11 (GGUF roadmap); reuses FT-AD-1/FT-AD-6/FT-AD-7

## Dependencies

- [[Specs/050 GGUF Import and Run/050 GGUF Import and Run|050 GGUF Import & Run]]
- [[Specs/044 Local LoRA Fine-Tuning/044 Local LoRA Fine-Tuning|044 Local LoRA Fine-Tuning]] (PEFT engine)
- [[Specs/045 Adapter Inference Export/045 Adapter Inference Export|045 Adapter Inference Export]] (adapter results)
- [[Specs/051 GGUF Export/051 GGUF Export|051 GGUF Export]] (re-export)

## Artifacts

- [[052 GGUF Fine-Tuning - spec|spec]]

## References

- [[Specs/038 Fine-Tuning Arc/038 Fine-Tuning Arc|038 Fine-Tuning Arc]]
- [[Reference/FineTuningArchitectureDecisions|Fine-Tuning Architecture Decisions]]
- [[Specs/Specs|Specs]]
