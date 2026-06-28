---
title: 039 Model Warm-Start
type: spec
tags:
  - type/spec
  - domain/training
  - domain/core
spec-refs:
  - docs/vault/Specs/039 Model Warm-Start/
status: draft
created: '2026-06-28'
updated: '2026-06-28'
aliases:
  - 039 Model Warm-Start
---

# 039 Model Warm-Start

Track A of the [[Specs/038 Fine-Tuning Arc/038 Fine-Tuning Arc|Fine-Tuning Arc]]: specialize anvil's
own char-level checkpoints via warm-start (continued training), with run lineage in the registry and
zero new dependencies. Surfaces the engine's existing `train(docs, model=...)` end-to-end and closes
the `torch_engine` `model=` parity gap.

## Owned

- **FRs**: FR-001..FR-004 (+ FR-001a, FR-003a)
- **Decisions**: FT-AD-1 (native side), FT-AD-10

## Dependencies

- Existing training service + SSE pipeline
- [[Specs/003 Model Registry Tracking/003 Model Registry Tracking|003 Model Registry Tracking]] (lineage)
- [[Specs/008 Llama Engine Evolution/008 Llama Engine Evolution|008 Llama Engine Evolution]] (engine/export)

## Artifacts

- [[039 Model Warm-Start - spec|spec]]

## References

- [[Specs/038 Fine-Tuning Arc/038 Fine-Tuning Arc|038 Fine-Tuning Arc]]
- [[Reference/FineTuningArchitectureDecisions|Fine-Tuning Architecture Decisions]]
- [[Specs/Specs|Specs]]
