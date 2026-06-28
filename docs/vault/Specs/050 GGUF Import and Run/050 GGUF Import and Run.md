---
title: 050 GGUF Import and Run
type: spec
tags:
  - type/spec
  - domain/training
  - domain/mlops
spec-refs:
  - docs/vault/Specs/050 GGUF Import and Run/
status: draft
created: '2026-06-28'
updated: '2026-06-28'
aliases:
  - 050 GGUF Import and Run
---

# 050 GGUF Import and Run

**Deferred** GGUF spec (FT-AD-11) of the [[Specs/038 Fine-Tuning Arc/038 Fine-Tuning Arc|Fine-Tuning
Arc]]: import a GGUF model and run inference on it via a GGUF runtime backend (behind a new `[gguf]`
extra). Sequenced after the v1 arc; v1 rejects GGUF until this ships.

## Owned

- **FRs**: FR-001..FR-005 (spec-local)
- **Decisions**: FT-AD-11 (GGUF roadmap); reuses FT-AD-4/FT-AD-5/FT-AD-7

## Dependencies

- [[Specs/040 External Model Registry/040 External Model Registry|040 External Model Registry]] (import)
- [[Specs/042 Model Asset Storage/042 Model Asset Storage|042 Model Asset Storage]] (assets)
- A GGUF runtime (e.g. `llama-cpp-python`) behind a new `[gguf]` extra

## Artifacts

- [[050 GGUF Import and Run - spec|spec]]

## References

- [[Specs/038 Fine-Tuning Arc/038 Fine-Tuning Arc|038 Fine-Tuning Arc]]
- [[Reference/FineTuningArchitectureDecisions|Fine-Tuning Architecture Decisions]]
- [[Specs/Specs|Specs]]
