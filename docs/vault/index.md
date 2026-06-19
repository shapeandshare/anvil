---
title: anvil Vault
---

# anvil Vault

The canonical documentation surface for **anvil** — a pip-installable LLM training workbench. The engine features RoPE, SwiGLU, RMSNorm, and safetensors export.

Open this vault in [Obsidian](https://obsidian.md) for graph navigation.

## Navigation

| Section | Description |
|---------|-------------|
| [[Governance]] | Constitution, policies, principles |
| [[Decisions]] | Architecture Decision Records |
| [[Reference]] | Glossary, architecture guides, topic references |
| [[Sessions]] | Agent session logs |

## Quick Links

| Topic | Docs |
|-------|------|
| **Architecture** | [[Reference/ArchitectureOverview|Architecture & Data Flow]] · [[Reference/DualBackend|CPU vs GPU Bridge]] · [[Reference/Hyperparameters|Hyperparameter Guide]] |
| **Training Pipeline** | [[Reference/TrainingDataFlow|Training Render Loop]] · [[Reference/MlflowIntegration|MLflow Tracking]] · [[Reference/ProgressiveWalkthroughs|train0→train5 Progression]] |
| **MLflow Lineage** | [[Decisions/ADR-016-mlflow-primary-lineage|ADR-016: MLflow as Primary Lineage Source of Truth]] |
| **Model Export** | [[Reference/SafetensorsExport|Safetensors & HF Interop]] |
| **Reference** | [[Reference/Glossary|Glossary]] · [[Reference/OpenQuestions|Open Questions]] |