---
title: Architecture Decision Records — Index
type: reference
tags:
  - type/reference
  - domain/architecture
  - domain/governance
created: '2026-06-10'
updated: '2026-06-24'
---
# Architecture Decision Records — Index

This index lists all ADRs in this repository. ADRs document significant architecture decisions, their rationale, and alternatives considered.

<!-- This index is manually maintained. Run `make vault-audit` to verify. -->

| ID | Title | Status | Date |
|----|-------|--------|------|
| ADR-001 | Architecture Decisions | — | — |
| ADR-002 | Sync Core / Async Bridge | — | — |
| ADR-003 | Pit of Success | — | — |
| ADR-004 | MLflow 3.x and Canonical URI | — | — |
| ADR-005 | Source-Keyed Registry Consolidation | — | — |
| ADR-006 | iOS Theme Overhaul | — | — |
| ADR-007 | Llama Engine Evolution | — | — |
| ADR-008 | Automated SemVer Release | — | — |
| ADR-009 | MLflow PyFunc Model Compliance | — | — |
| ADR-010 | Disable Local MLflow Server | — | — |
| ADR-011 | Name-Based Demo Bootstrap Idempotency | — | — |
| ADR-012 | MLflow Browser URL from Request Host | — | — |
| ADR-013 | Training Config Footgun Guards | — | — |
| ADR-014 | ML Infrastructure Tier Strategy | — | — |
| ADR-015 | Pluggable Compute Backends | — | — |
| ADR-016 | MLflow Primary Lineage | — | — |
| ADR-018 | Packaging Resource Relocation | — | — |
| ADR-019 | Pydantic BaseModel over Dataclass | — | — |
| ADR-020 | One Class Per File | — | — |
| ADR-021 | `__init__.py` Ownership Policy | — | — |
| ADR-022 | Domain-Driven Package Decomposition | — | — |
| ADR-023 | Data Page Tabbed Layout (renumbered from ADR-008) | — | — |
| ADR-024 | Auto DB Migration (renumbered from ADR-016) | — | — |
| ADR-025 | NumPy Docstring Enforcement (renumbered from 010-prefix) | — | — |
| ADR-026 | Coverage Ratcheting Baseline | Draft | 2026-06-19 |
| ADR-027 | TYPE_CHECKING Conditional Allow with Exception Discipline | Draft | 2026-06-19 |
| ADR-028 | CI Merge Gate Enforcement | Draft | 2026-06-19 |
| ADR-029 | ADR Renumbering and Uniqueness Enforcement | Draft | 2026-06-19 |
| ADR-030 | SaaS Architecture -- Three-Mode Operating Model | Proposed | 2026-06-19 |
| ADR-031 | Behavioral Theme Engine and Neutral Signal Instrumentation | Proposed | 2026-06-19 |
| ADR-032 | Greenfield Legacy and Backward-Compatibility Removal | Draft | 2026-06-20 |
| ADR-033 | Content Repository Substrate -- Pure-Python Local, LakeFS for SaaS | Proposed | 2026-06-20 |
| ADR-034 | Vault Health Subsumption into Anvil | Draft | 2026-06-21 |
| ADR-035 | MLflow Reverse Proxy -- Authenticated, Port-Closed Access in Local and SaaS | Proposed | 2026-06-21 |
| ADR-036 | Header-Based API Versioning and URL Path De-Versioning | Proposed | 2026-06-21 |
| ADR-037 | Unified Single-Origin Interface and Working Local TLS | Proposed | 2026-06-21 |
| ADR-038 | UX Rules Integration | Accepted | 2026-06-21 |
| ADR-039 | Client SDK Architecture | Accepted | 2026-06-21 |
| ADR-040 | Full-Deployment Backup & Restore | Accepted | 2026-06-21 |
| ADR-041 | Simplicity First (Boring Technology) | Accepted | 2026-06-22 |

**Status**: Draft → Reviewed → Canonical (human-only). See `_meta/tags.md` for lifecycle.

## ADR Files

- [[Decisions/ADR-001-architecture-decisions|ADR-001-architecture-decisions]] — ADR-001: Bootstrap Implementation Architecture
- [[Decisions/ADR-002-sync-core-async-bridge|ADR-002-sync-core-async-bridge]] — ADR-002: Sync Core Engine with Async SSE Bridge
- [[Decisions/ADR-003-pit-of-success|ADR-003-pit-of-success]] — ADR-003: Pit of Success — Opt-In Optional Capabilities with Silent Fallback
- [[Decisions/ADR-004-mlflow-3x-and-canonical-uri|ADR-004-mlflow-3x-and-canonical-uri]] — ADR-004: MLflow 3.x bump and canonical HTTP-server tracking URI
- [[Decisions/ADR-005-source-keyed-registry-consolidation|ADR-005-source-keyed-registry-consolidation]] — ADR-005: Source-keyed model registry consolidation
- [[Decisions/ADR-006-ios-theme-overhaul|ADR-006-ios-theme-overhaul]] — ADR-006: iOS Design Overhaul
- [[Decisions/ADR-007-llama-engine-evolution|ADR-007-llama-engine-evolution]] — ADR-007: Llama Engine Evolution
- [[Decisions/ADR-008-automated-semver-release|ADR-008-automated-semver-release]] — ADR-008: Automated Semantic Versioning & Release
- [[Decisions/ADR-009-mlflow-pyfunc-model-compliance|ADR-009-mlflow-pyfunc-model-compliance]] — ADR-009: MLflow Pyfunc Model Compliance for Safetensors Export
- [[Decisions/ADR-010-disable-local-mlflow-server|ADR-010-disable-local-mlflow-server]] — ADR-010: Hosted MLflow support — disable local server
- [[Decisions/ADR-011-name-based-demo-bootstrap-idempotency|ADR-011-name-based-demo-bootstrap-idempotency]] — ADR-011: Name-Based Idempotency for Demo Data Bootstrap
- [[Decisions/ADR-012-mlflow-browser-url-from-request-host|ADR-012-mlflow-browser-url-from-request-host]] — ADR-012: Derive MLflow browser URL from HTTP request Host header
- [[Decisions/ADR-013-training-config-footgun-guards|ADR-013-training-config-footgun-guards]] — ADR-013: Training Config Footgun Guards — Multi-Layer Hyperparameter Validation
- [[Decisions/ADR-014-ml-infrastructure-tier-strategy|ADR-014-ml-infrastructure-tier-strategy]] — ADR-014: ML Infrastructure Tier Strategy — Compute & Orchestration Trajectory
- [[Decisions/ADR-015-pluggable-compute-backends|ADR-015-pluggable-compute-backends]] — ADR-015: Pluggable Compute Backend Abstraction
- [[Decisions/ADR-016-mlflow-primary-lineage|ADR-016-mlflow-primary-lineage]] — ADR-016: MLflow as Primary Lineage Source of Truth
- [[Decisions/ADR-018-packaging-resource-relocation|ADR-018-packaging-resource-relocation]] — ADR-018: Package Runtime Resources Inside the Wheel
- [[Decisions/ADR-019-pydantic-basemodel-over-dataclass|ADR-019-pydantic-basemodel-over-dataclass]] — ADR-019: Pydantic BaseModel Over dataclasses.dataclass
- [[Decisions/ADR-020-one-class-per-file|ADR-020-one-class-per-file]] — ADR-020: One Class Per File
- [[Decisions/ADR-021-init-py-ownership-policy|ADR-021-init-py-ownership-policy]] — ADR-021: `__init__.py` Ownership Policy
- [[Decisions/ADR-022-domain-driven-package-decomposition|ADR-022-domain-driven-package-decomposition]] — ADR-022: Domain-Driven Package Decomposition
- [[Decisions/ADR-023-responsible-data-governance|ADR-023-responsible-data-governance]] — ADR-023: Responsible Data Governance — Provenance, Hash-Chained Audit, and Acceptable-Use Gate
- [[Decisions/ADR-024-auto-db-migration|ADR-024-auto-db-migration]] — ADR-016: Auto Database Schema Migration
- [[Decisions/ADR-025-numpy-docstring-enforcement|ADR-025-numpy-docstring-enforcement]] — ADR-010: NumPy-Style Docstring Enforcement
- [[Decisions/ADR-026-coverage-ratcheting-baseline|ADR-026-coverage-ratcheting-baseline]] — ADR-026: Coverage Ratcheting Baseline
- [[Decisions/ADR-027-type-checking-conditional-allow|ADR-027-type-checking-conditional-allow]] — ADR-027: TYPE_CHECKING Conditional Allow with Exception Discipline
- [[Decisions/ADR-028-ci-merge-gate-enforcement|ADR-028-ci-merge-gate-enforcement]] — ADR-028: CI Merge Gate Enforcement
- [[Decisions/ADR-029-adr-renumbering-and-uniqueness|ADR-029-adr-renumbering-and-uniqueness]] — ADR-029: ADR Renumbering and Uniqueness Enforcement
- [[Decisions/ADR-030-saas-architecture|ADR-030-saas-architecture]] — ADR-030: SaaS Architecture — Three-Mode Operating Model
- [[Decisions/ADR-031-behavioral-theme-engine|ADR-031-behavioral-theme-engine]] — ADR-031-behavioral-theme-engine
- [[Decisions/ADR-032-greenfield-legacy-removal|ADR-032-greenfield-legacy-removal]] — ADR-032: Greenfield Legacy and Backward-Compatibility Removal
- [[Decisions/ADR-033-content-repository-substrate|ADR-033-content-repository-substrate]] — ADR-033: Content Repository Substrate — Pure-Python Local, LakeFS for SaaS
- [[Decisions/ADR-034-playwright-ui-smoke-harness|ADR-034-playwright-ui-smoke-harness]] — ADR-034: Playwright UI Smoke Harness
- [[Decisions/ADR-034-vault-health-subsumption|ADR-034-vault-health-subsumption]] — ADR-034: Vault Health Subsumption into Anvil
- [[Decisions/ADR-035-mlflow-reverse-proxy|ADR-035-mlflow-reverse-proxy]] — ADR-035: MLflow Reverse Proxy — Authenticated, Port-Closed Access in Local and SaaS
- [[Decisions/ADR-036-header-based-api-versioning|ADR-036-header-based-api-versioning]] — ADR-036: Header-Based API Versioning and URL Path De-Versioning
- [[Decisions/ADR-037-unified-interface-local-tls|ADR-037-unified-interface-local-tls]] — ADR-037: Unified Single-Origin Interface and Working Local TLS
- [[Decisions/ADR-038-ux-rules-integration|ADR-038-ux-rules-integration]] — ADR-038: UX Rules Integration
- [[Decisions/ADR-039-client-sdk-architecture|ADR-039-client-sdk-architecture]] — ADR-039: Client SDK Architecture
- [[Decisions/ADR-039-specs-to-vault|ADR-039-specs-to-vault]] — ADR-039: Migrate `specs/` Artifacts into `docs/vault/Specs/`
- [[Decisions/ADR-040-deployment-backup-restore|ADR-040-deployment-backup-restore]] — ADR-040: Full-Deployment Backup & Restore
- [[Decisions/ADR-041-simplicity-first-boring-technology|ADR-041-simplicity-first-boring-technology]] — ADR-041: Simplicity First (Boring Technology)
- [[Decisions/ADR-template|ADR-template]]
