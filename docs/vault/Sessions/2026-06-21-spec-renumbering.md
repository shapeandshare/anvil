---
aliases:
  - Spec Renumbering 001–025
created: '2026-06-21'
source: agent
status: draft
tags:
  - type/session-log
  - domain/governance
  - domain/vault
  - domain/tooling
title: Spec Renumbering — Sequential 001–025
type: session-log
updated: '2026-06-21'
---
# Spec Renumbering — Sequential 001–025

**Session**: Full renumbering of all 25 spec directories from a broken duplicate-number scheme to a unique sequential 001–025 ordering, including all cross-references across 66 files (148 references).

## Problem

The `specs/` directory had three numbering issues:

1. **Duplicate numbers** — 6 groups with 14 affected specs sharing the same prefix (`001`, `002`, `005`, `014`, `015`, `017`), making spec numbers useless as identifiers
2. **Numbering gaps** — `003`, `011`, `012` were missing from the sequence
3. **Branch name inconsistencies** — 3 specs used `feature/` prefix in their branch names while peers didn't; 1 spec had a branch mismatch (`001-dataset-curation` directory but `003-dataset-curation` feature branch); 1 spec had a malformed backtick in its Feature Branch line

## Renumbering Map (Chronological)

Order determined by `**Created**:` date in each spec.md, with alphabetical tiebreaker within same day:

| Old | New | Feature |
|-----|-----|---------|
| `001-bootstrap-llm-workbench` | **001** | Bootstrap LLM Workbench |
| `002-directory-corpus-ingestion` | **002** | Directory Corpus Ingestion |
| `002-model-registry-tracking` | **003** | Model Registry Tracking |
| `004-frontend-refactor` | **004** | Frontend Refactor |
| `001-dataset-curation` | **005** | Dataset Curation |
| `005-mlflow-experiment-tracking` | **006** | MLflow Experiment Tracking |
| `005-learning-content-enrichment` | **007** | Learning Content Enrichment |
| `006-llama-engine-evolution` | **008** | Llama Engine Evolution |
| `001-bootstrap-datasets` | **009** | Bootstrap Datasets |
| `007-automated-semver-release` | **010** | Automated SemVer Release |
| `008-auto-db-schema` | **011** | Auto DB Schema |
| `009-pip-installable-package` | **012** | Pip-Installable Package |
| `010-responsible-data-governance` | **013** | Responsible Data Governance |
| `013-dx-harness-hardening` | **014** | DX Harness Hardening |
| `014-demo-data-bootstrap` | **015** | Demo Data Bootstrap |
| `014-saas-architecture` | **016** | SaaS Architecture |
| `015-graph-health-subsumption` | **017** | Graph Health Subsumption |
| `015-theme-engine` | **018** | Theme Engine |
| `016-lakefs-content-repo` | **019** | LakeFS Content Repository |
| `017-owasp-remediation` | **020** | OWASP Remediation |
| `017-api-e2e-suite` | **021** | Whole-API E2E Suite |
| `017-playwright-ui-smoke` | **022** | Playwright UI Smoke |
| `018-header-api-versioning` | **023** | Header-Based API Versioning |
| `019-unified-interface-local-tls` | **024** | Unified Interface + Local TLS |
| `020-ux-rules-integration` | **025** | UX Rules Integration |

## What was changed

### Phase 1 — Directories
- Renamed 22 directories (3 already occupied correct slots)

### Phase 2 — Feature Branch lines (spec.md)
- Updated `**Feature Branch**:` in all 22 renamed specs
- Normalized 3 `feature/` branch prefixes to plain branch names
- Fixed 1 malformed backtick (missing closing `` ` ``)
- Reconciled 1 branch mismatch (`003-dataset-curation` → `005-dataset-curation`)

### Phase 3 — Internal spec cross-references
- Updated stale `specs/OLD_NUMBER/` paths in: plan.md (17), tasks.md (22), checklists (2), quickstart.md (1), spec.md (1 self-ref)

### Phase 4 — Branch lines in plan.md
- Updated `**Branch**:` lines in 17 plan.md files to match new directory names

### Phase 5 — Vault references (docs/vault/)
- **ADRs**: ADR-030, ADR-031, ADR-033, ADR-034, ADR-035, ADR-036, ADR-037 (7 files, 23 references)
- **Session logs**: 9 session logs (18 references) — including old spec paths and backtick-delimited branch name refs
- **Discoveries/Discovery**: 2 files (4 references)
- **Reference**: 3 SaaS diagram/architecture references (14 references)

### Phase 6 — Non-.md files
- **Makefile**: `specs/009-pip-installable-package` → `docs/vault/Specs/012 Pip Installable Package`
- **`.specify/feature.json`**: `specs/020-ux-rules-integration` → `docs/vault/Specs/025 UX Rules Integration`
- **Source code**: `anvil/services/content/__init__.py`, `anvil/services/content/authz.py` (2 files)
- **Tests**: 3 test files referencing spec 016 lakefs-content-repo

### Phase 7 — AGENTS.md
- 10 stale references updated

### Phase 8 — Critical review
- Re-checked all 25 specs for internal consistency (directory name ↔ Feature Branch ↔ plan.md Branch)
- Swept all file types (.md, .py, Makefile, .json, .yml, .toml, .cfg, .sh)
- Found and fixed 6 missed items: 4 `.py` files, 1 `Makefile`, 1 `.specify/feature.json`, 2 vault backtick branch refs

## Final audit

- **25/25 directories**: sequential 001–025, all match directory name
- **25/25 Feature Branch**: all match directory name
- **17 plan.md Branch**: all match directory name
- **66 files updated**: 148 total stale references fixed
- **Zero stale `specs/OLD_NUMBER/`** references remain
- **Zero stale `` `feature/...` ``** branch prefixes remain

## Key decisions

1. **Chronological ordering** — Specs numbered by creation date (oldest = lowest number). Same-day specs ordered alphabetically by feature name. This preserves the development timeline as the primary sort axis.
2. **Branch names normalized** — `feature/` prefix removed from all branch names for consistency. The majority (22/25) already omitted it.
3. **Historical session logs** — Vault session logs that reference old spec paths were updated because they reference spec *directories* (current artifacts), not git branches (historical artifacts). However, branch names in session log frontmatter/titles that refer to actual git branches were preserved — they are factual historical records.

## Related

- [[Specs/Specs|Specs]] — feature specification index (this session was about renumbering it)
- [[Decisions/ADR-029-adr-renumbering-and-uniqueness|ADR-029: ADR Renumbering and Uniqueness]] — related renumbering decision
- [[Systems/Vault Structure|Vault Structure]] — vault directory layout conventions
