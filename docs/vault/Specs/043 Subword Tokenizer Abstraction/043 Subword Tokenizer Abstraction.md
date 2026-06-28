---
title: 043 Subword Tokenizer Abstraction
type: spec
tags:
  - type/spec
  - domain/core
  - domain/training
spec-refs:
  - docs/vault/Specs/043 Subword Tokenizer Abstraction/
status: draft
created: '2026-06-28'
updated: '2026-06-28'
aliases:
  - 043 Subword Tokenizer Abstraction
---

# 043 Subword Tokenizer Abstraction

Track B core of the [[Specs/038 Fine-Tuning Arc/038 Fine-Tuning Arc|Fine-Tuning Arc]]: the tokenizer
travels with the model. One abstraction holds anvil's char-level vocabulary and HuggingFace subword
tokenizers; encode/decode dispatch from the attached tokenizer. The hard dependency that gates local
PEFT (044).

## Owned

- **FRs**: FR-014, FR-015 (+ FR-014a, FR-015a), FR-031 (tokenizer serializations)
- **Decisions**: FT-AD-3, FT-AD-11 (tokenizer aspect)

## Dependencies

- `anvil/core/tokenizer.py`, `anvil/core/vocabulary.py`
- `transformers`/`tokenizers` (behind `[finetune]` extra) for subword

## Artifacts

- [[043 Subword Tokenizer Abstraction - spec|spec]]

## References

- [[Specs/038 Fine-Tuning Arc/038 Fine-Tuning Arc|038 Fine-Tuning Arc]]
- [[Specs/008 Llama Engine Evolution/008 Llama Engine Evolution|008 Llama Engine Evolution]]
- [[Reference/FineTuningArchitectureDecisions|Fine-Tuning Architecture Decisions]]
- [[Specs/Specs|Specs]]
