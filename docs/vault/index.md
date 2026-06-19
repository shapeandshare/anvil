---
title: anvil Vault
type: reference
tags:
  - type/reference
  - domain/vault
created: 2026-06-10
updated: 2026-06-18
aliases:
  - anvil-vault
  - vault-index
---

# anvil Vault

The canonical documentation surface for **anvil** — a pip-installable LLM training workbench. The engine features RoPE, SwiGLU, RMSNorm, and safetensors export.

Open this vault in [Obsidian](https://obsidian.md) for graph navigation.

## Navigation

| Section | Description |
|---------|-------------|
| [[Governance/Constitution|Governance]] | Constitution, policies, principles |
| [[Design/Design|Design]] | Conceptual design and rationale |
| [[Systems/Systems|Systems]] | Implemented subsystems and tooling |
| [[Decisions/ADR-001-architecture-decisions|Decisions]] | Architecture Decision Records |
| [[Reference/ArchitectureOverview|Reference]] | Glossary, architecture guides, topic references |
| [[Discoveries/Discoveries|Discoveries]] | Non-obvious constraints found during sessions |
| [[Sessions/2026-06-10-implementation|Sessions]] | Agent session logs |

### Vault Meta

- [_meta/tags.md](./_meta/tags.md) — Controlled tag vocabulary for vault notes

## Quick Links

| Topic | Docs |
|-------|------|
| **Architecture** | [[Reference/ArchitectureOverview|Architecture & Data Flow]] · [[Reference/DualBackend|CPU vs GPU Bridge]] · [[Reference/Hyperparameters|Hyperparameter Guide]] |
| **Training Pipeline** | [[Reference/TrainingDataFlow|Training Render Loop]] · [[Reference/MlflowIntegration|MLflow Tracking]] · [[Reference/ProgressiveWalkthroughs|train0→train5 Progression]] |
| **MLflow Lineage** | [[Decisions/ADR-016-mlflow-primary-lineage|ADR-016: MLflow as Primary Lineage Source of Truth]] |
| **Model Export** | [[Reference/SafetensorsExport|Safetensors & HF Interop]] |
| **Infrastructure** | [[Decisions/ADR-016-auto-db-migration|ADR-016: Auto DB Schema]] · [[Sessions/2026-06-18-auto-db-schema|Auto DB Schema Session]] |
| **Reference** | [[Reference/Glossary|Glossary]] · [[Reference/OpenQuestions|Open Questions]] |