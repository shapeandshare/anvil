---
title: 'Session: 005-mlflow-experiment-tracking Implementation'
type: session-log
tags:
  - type/session-log
  - domain/tracking
  - domain/mlops
created: '2026-06-14'
updated: '2026-06-14'
aliases:
  - 005-mlflow-experiment-tracking-implementation
source: agent
---
# Session: 005-mlflow-experiment-tracking Implementation

**Date**: 2026-06-14
**Branch**: 005-mlflow-experiment-tracking

## Summary
Complete implementation of MLflow experiment & data lifecycle tracking feature.
Phases 1-10 executed across 9 parallel/sequential implementation agents.

## Key Deliverables
- MLflow 3.x bump (`>=3.1,<4`, resolved 3.13.0)
- Single canonical HTTP tracking-server URI via `get_config()["mlflow_uri"]`
- `TrackingService` — single MLflow seam (lifecycle, lineage, metrics, artifacts, registry, genai)
- `MlflowInputResolver` — dataset/corpus lineage with content-derived digests
- `MlflowCapabilities` — genai/server-backed detection
- `MPSMetricsCollector` + `MPSSamplerThread` — Apple Silicon GPU utilization via ioreg/IOKit (no sudo)
- Managed evaluation datasets (`mlflow.genai.datasets`, first-class under 3.x, OSS SQLite-backed)
- Source-keyed model registry (`dataset-<id>`/`corpus-<id>`/`default-source`)
- Experiment lifecycle: `running`->`finished`/`failed`; orphan reconciliation on startup
- CLI parity: `anvil train --dataset` tracks identically to web

## Corrections Applied
- MPS utilization via `ioreg` (not psutil/torch.mps which are memory-only)
- `mlflow.genai.datasets` confirmed on self-hosted SQLite (not Databricks-only)
- Registry dual-write clarified: MLflow auto-registers; local registry manual-only

## Test Count
291 tests (41 pre-existing + 250 new tests across all phases)

## Known Pre-Existing Issue
Coverage is at ~60% (was 56.24% on main before this branch). `fail_under=100` was already failing on main; this feature improved coverage but did not fix the pre-existing deficit in unrelated modules (supervisor, corpus_loader, dataset_curation, etc.).

## Related

- [[Specs/006 MLflow Experiment Tracking/006 MLflow Experiment Tracking|006 MLflow Experiment Tracking]] — feature specification
- [[Decisions/ADR-004-mlflow-3x-and-canonical-uri|ADR-004: MLflow 3.x and Canonical URI]] — architecture decision record
- [[Decisions/ADR-005-source-keyed-registry-consolidation|ADR-005: Source-Keyed Registry Consolidation]] — architecture decision record
- [[Reference/MlflowIntegration|MLflow Tracking]] — MLflow integration overview