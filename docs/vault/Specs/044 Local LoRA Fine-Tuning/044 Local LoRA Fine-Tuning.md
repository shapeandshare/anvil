---
title: 044 Local LoRA Fine-Tuning
type: spec
tags:
  - type/spec
  - domain/training
  - domain/core
spec-refs:
  - docs/vault/Specs/044 Local LoRA Fine-Tuning/
status: draft
created: '2026-06-28'
updated: '2026-06-28'
aliases:
  - 044 Local LoRA Fine-Tuning
---

# 044 Local LoRA Fine-Tuning

Track B core of the [[Specs/038 Fine-Tuning Arc/038 Fine-Tuning Arc|Fine-Tuning Arc]]: a
`transformers`+`peft` backend (behind the existing compute protocol and the `[finetune]` extra) that
LoRA/QLoRA-fine-tunes TinyLlama-class models locally, gated to a resource envelope, producing tracked
adapters.

## Owned

- **FRs**: FR-016..FR-019 (+ FR-016a, FR-017a)
- **Decisions**: FT-AD-1 (external side), FT-AD-9

## Dependencies

- [[Specs/042 Model Asset Storage/042 Model Asset Storage|042 Model Asset Storage]] (assets)
- [[Specs/043 Subword Tokenizer Abstraction/043 Subword Tokenizer Abstraction|043 Subword Tokenizer Abstraction]] (tokenizer)
- `anvil/services/compute/` protocol + registry; `torch`/`transformers`/`peft` (`[finetune]`)

## Artifacts

- [[044 Local LoRA Fine-Tuning - spec|spec]]

## References

- [[Specs/038 Fine-Tuning Arc/038 Fine-Tuning Arc|038 Fine-Tuning Arc]]
- [[Reference/FineTuningArchitectureDecisions|Fine-Tuning Architecture Decisions]]
- [[Specs/Specs|Specs]]
