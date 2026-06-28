---
title: 051 GGUF Export
type: spec
tags:
  - type/spec
  - domain/training
  - domain/mlops
spec-refs:
  - docs/vault/Specs/051 GGUF Export/
status: draft
created: '2026-06-28'
updated: '2026-06-28'
aliases:
  - 051 GGUF Export
---

# 051 GGUF Export

**Deferred** GGUF spec (FT-AD-11) of the [[Specs/038 Fine-Tuning Arc/038 Fine-Tuning Arc|Fine-Tuning
Arc]]: export anvil and merged fine-tuned models to GGUF at a chosen quantization for use in the
llama.cpp ecosystem. Consumes 045's merge/export. Sequenced after the v1 arc.

## Owned

- **FRs**: FR-001..FR-004 (spec-local)
- **Decisions**: FT-AD-11 (GGUF roadmap)

## Dependencies

- [[Specs/045 Adapter Inference Export/045 Adapter Inference Export|045 Adapter Inference Export]] (merge/export)
- [[Specs/042 Model Asset Storage/042 Model Asset Storage|042 Model Asset Storage]] (asset storage)
- GGUF conversion tooling behind the `[gguf]` extra

## Artifacts

- [[051 GGUF Export - spec|spec]]

## References

- [[Specs/038 Fine-Tuning Arc/038 Fine-Tuning Arc|038 Fine-Tuning Arc]]
- [[Reference/FineTuningArchitectureDecisions|Fine-Tuning Architecture Decisions]]
- [[Specs/Specs|Specs]]
