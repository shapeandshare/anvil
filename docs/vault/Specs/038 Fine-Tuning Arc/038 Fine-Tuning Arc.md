---
title: 038 Fine-Tuning Arc
type: spec
tags:
  - type/spec
  - domain/training
  - domain/learning
spec-refs:
  - docs/vault/Specs/038 Fine-Tuning Arc/
status: draft
created: '2026-06-28'
updated: '2026-06-28'
aliases:
  - 038 Fine-Tuning Arc
---

# 038 Fine-Tuning Arc

Umbrella spec for anvil's fine-tuning body of work — the next rung of the learning ladder after
training from scratch. It frames two tracks behind one compute seam: **native warm-start** (continue
training anvil's own char-level models) and **external PEFT** (LoRA/QLoRA on HuggingFace TinyLlama-class
models), runnable locally and offloadable to SaaS.

> [!NOTE] Umbrella spec — decomposed into per-feature specs 039–049
> This umbrella owns the cross-cutting requirements and invariant. Delivery happens in the
> independently shippable child specs below. The binding architecture decisions live in a shared
> reference. (The umbrella is being authored first; child specs follow.)

## Summary

anvil teaches how language models work by training a small char-level model from scratch. The
Fine-Tuning Arc extends that with specializing existing models — warm-starting anvil's own checkpoints
and parameter-efficiently fine-tuning real pretrained models — while preserving the dependency-free
base install and the unchanged from-scratch experience (the Fine-Tuning Invariant).

## Child Specs

- [[Specs/039 Model Warm-Start/039 Model Warm-Start|039 Model Warm-Start]] — specialize an anvil checkpoint (Track A)
- [[Specs/040 External Model Registry/040 External Model Registry|040 External Model Registry]] — source-agnostic model import
- [[Specs/041 HuggingFace Model Browser/041 HuggingFace Model Browser|041 HuggingFace Model Browser]] — in-app HF view, TinyLlama-class catalog
- [[Specs/042 Model Asset Storage/042 Model Asset Storage|042 Model Asset Storage]] — download + track assets; LakeFS under SaaS
- [[Specs/043 Subword Tokenizer Abstraction/043 Subword Tokenizer Abstraction|043 Subword Tokenizer Abstraction]] — tokenizer travels with the model
- [[Specs/044 Local LoRA Fine-Tuning/044 Local LoRA Fine-Tuning|044 Local LoRA Fine-Tuning]] — local PEFT for small models
- [[Specs/045 Adapter Inference Export/045 Adapter Inference Export|045 Adapter Inference Export]] — run/merge/export fine-tuned models
- [[Specs/046 Fine-Tune Compute Routing/046 Fine-Tune Compute Routing|046 Fine-Tune Compute Routing]] — local↔SaaS routing
- [[Specs/047 SaaS Fine-Tuning Pipeline/047 SaaS Fine-Tuning Pipeline|047 SaaS Fine-Tuning Pipeline]] — Batch GPU fine-tunes on the existing SaaS pipeline
- [[Specs/048 Learning Fine-Tuning Concepts/048 Learning Fine-Tuning Concepts|048 Learning Fine-Tuning Concepts]] — warm-start vs PEFT, fine-tune vs prompt vs RAG
- [[Specs/049 Learning Architecture Differences/049 Learning Architecture Differences|049 Learning Architecture Differences]] — how architectures differ and why it matters
- [[Specs/053 Fine-Tuning Dataset Preparation/053 Fine-Tuning Dataset Preparation|053 Fine-Tuning Dataset Preparation]] — SFT/chat-template/preference data (enables 044)
- [[Specs/054 Fine-Tuned Model Evaluation/054 Fine-Tuned Model Evaluation|054 Fine-Tuned Model Evaluation]] — compare fine-tuned vs base
- [[Specs/055 Interactive Teaching Loop/055 Interactive Teaching Loop|055 Interactive Teaching Loop]] — iterative, checkpoint-chained teaching

## Deferred Child Specs (GGUF — later priority)

GGUF is a committed but deferred first-class type (FT-AD-11); v1 rejects it on import. Split into three
independently shippable specs:

- [[Specs/050 GGUF Import and Run/050 GGUF Import and Run|050 GGUF Import & Run]] — load + run inference on GGUF
- [[Specs/051 GGUF Export/051 GGUF Export|051 GGUF Export]] — export anvil/merged models to GGUF
- [[Specs/052 GGUF Fine-Tuning/052 GGUF Fine-Tuning|052 GGUF Fine-Tuning]] — train/fine-tune GGUF models

## Shared Decisions

- [[Reference/FineTuningArchitectureDecisions|Fine-Tuning Architecture Decisions (FT-AD-1..11)]]

## Related Existing Work

- [[Reference/SaaSArchitectureDecisions|SaaS Architecture Decisions]] — AD-1 (Batch compute), AD-4 (job_events), AD-17 (LakeFS)
- [[Specs/032 SaaS Training Pipeline/032 SaaS Training Pipeline|032 SaaS Training Pipeline]]
- [[Specs/028 SaaS Abstraction Framework/028 SaaS Abstraction Framework|028 SaaS Abstraction Framework]]
- [[Specs/019 LakeFS Content Repo/019 LakeFS Content Repo|019 LakeFS Content Repo]]
- [[Specs/003 Model Registry Tracking/003 Model Registry Tracking|003 Model Registry Tracking]]
- [[Specs/008 Llama Engine Evolution/008 Llama Engine Evolution|008 Llama Engine Evolution]]

## Artifacts

- [[038 Fine-Tuning Arc - spec|spec]]
- [[038 Fine-Tuning Arc - shippable-features|shippable-features]]

## References

- [[Specs/Specs|Specs]]
