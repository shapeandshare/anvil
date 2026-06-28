---
title: 054 Fine-Tuned Model Evaluation
type: spec
tags:
  - type/spec
  - domain/training
  - domain/mlops
spec-refs:
  - docs/vault/Specs/054 Fine-Tuned Model Evaluation/
status: draft
created: '2026-06-28'
updated: '2026-06-28'
aliases:
  - 054 Fine-Tuned Model Evaluation
---

# 054 Fine-Tuned Model Evaluation

Evaluation slice of the [[Specs/038 Fine-Tuning Arc/038 Fine-Tuning Arc|Fine-Tuning Arc]]: compare a
fine-tuned model to its base — side-by-side samples + metric delta — reusing the eval service. Answers
"did fine-tuning help?" for warm-start and adapter models alike.

## Owned

- **FRs**: FR-035 (+ spec-local FR-001..FR-003)
- **Decisions**: reuses FT-AD-7, FT-AD-10

## Dependencies

- Existing eval service (`anvil/api/v1/eval.py` and eval service)
- [[Specs/045 Adapter Inference Export/045 Adapter Inference Export|045 Adapter Inference Export]] (base+adapter inference)
- [[Specs/043 Subword Tokenizer Abstraction/043 Subword Tokenizer Abstraction|043 Subword Tokenizer Abstraction]] (tokenizer dispatch)

## Artifacts

- [[054 Fine-Tuned Model Evaluation - spec|spec]]

## References

- [[Specs/038 Fine-Tuning Arc/038 Fine-Tuning Arc|038 Fine-Tuning Arc]]
- [[Reference/FineTuningArchitectureDecisions|Fine-Tuning Architecture Decisions]]
- [[Specs/Specs|Specs]]
