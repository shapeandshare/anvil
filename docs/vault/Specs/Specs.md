---
title: Specs
type: moc
tags:
  - type/moc
  - domain/vault
created: 2026-06-21
updated: 2026-06-21
aliases:
  - Specs
---

# Specs

Specification notes that track the status, key decisions, and implementation traceability of anvil feature specs. Each note mirrors a spec authored under `specs/` (the spec-kit workflow) and surfaces it inside the knowledge graph so specs link to the `Systems/` and `Code/` notes that implement them.

Start here to see what has been specified, what is in progress, and what shipped. The authoritative spec artifacts (`spec.md`, `plan.md`, `tasks.md`) live under `specs/`; these notes are the graph-resident index over them.

## Notes

- [[Specs/001 Bootstrap LLM Workbench/001 Bootstrap LLM Workbench|001 Bootstrap LLM Workbench]]
- [[Specs/002 Directory Corpus Ingestion/002 Directory Corpus Ingestion|002 Directory Corpus Ingestion]]
- [[Specs/003 Model Registry Tracking/003 Model Registry Tracking|003 Model Registry Tracking]]
- [[Specs/004 Frontend Refactor/004 Frontend Refactor|004 Frontend Refactor]]
- [[Specs/005 Dataset Curation/005 Dataset Curation|005 Dataset Curation]]
- [[Specs/006 MLflow Experiment Tracking/006 MLflow Experiment Tracking|006 MLflow Experiment Tracking]]
- [[Specs/007 Learning Content Enrichment/007 Learning Content Enrichment|007 Learning Content Enrichment]]
- [[Specs/008 Llama Engine Evolution/008 Llama Engine Evolution|008 Llama Engine Evolution]]
- [[Specs/009 Bootstrap Datasets/009 Bootstrap Datasets|009 Bootstrap Datasets]]
- [[Specs/010 Automated Semver Release/010 Automated Semver Release|010 Automated Semver Release]]
- [[Specs/011 Auto DB Schema/011 Auto DB Schema|011 Auto DB Schema]]
- [[Specs/012 Pip Installable Package/012 Pip Installable Package|012 Pip Installable Package]]
- [[Specs/013 Responsible Data Governance/013 Responsible Data Governance|013 Responsible Data Governance]]
- [[Specs/014 DX Harness Hardening/014 DX Harness Hardening|014 DX Harness Hardening]]
- [[Specs/015 Demo Data Bootstrap/015 Demo Data Bootstrap|015 Demo Data Bootstrap]]
- [[Specs/016 SaaS Architecture/016 SaaS Architecture|016 SaaS Architecture]]
- [[Specs/017 Graph Health Subsumption/017 Graph Health Subsumption|017 Graph Health Subsumption]]
- [[Specs/018 Theme Engine/018 Theme Engine|018 Theme Engine]]
- [[Specs/019 LakeFS Content Repo/019 LakeFS Content Repo|019 LakeFS Content Repo]]
- [[Specs/020 OWASP Remediation/020 OWASP Remediation|020 OWASP Remediation]]
- [[Specs/021 API E2E Suite/021 API E2E Suite|021 API E2E Suite]]
- [[Specs/022 Playwright UI Smoke/022 Playwright UI Smoke|022 Playwright UI Smoke]]
- [[Specs/023 Header API Versioning/023 Header API Versioning|023 Header API Versioning]]
- [[Specs/024 Unified Interface Local TLS/024 Unified Interface Local TLS|024 Unified Interface Local TLS]]
- [[Specs/025 UX Rules Integration/025 UX Rules Integration|025 UX Rules Integration]]

## Conventions

- One note per spec, named `NNN Spec Name.md` (matches the `specs/NNN-slug/` directory).
- Carries `type/spec` and a `spec-refs:` field pointing at the `specs/` artifact directory.
- Links forward to the `Systems/` or `Code/` note(s) that implement the spec.

## Related MOCs

- [[Systems/Systems|Systems]] — implemented subsystems that fulfill specs
- [[Code/Code|Code]] — code-architecture notes referenced by specs
- [[Design/Design|Design]] — conceptual rationale behind specs
