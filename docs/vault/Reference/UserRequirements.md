---
title: User Requirements (Project Charter)
type: reference
tags:
  - type/reference
  - domain/architecture
  - domain/governance
created: 2026-06-21
updated: 2026-06-21
aliases:
  - user-requirements
  - project-charter
  - bootstrap-requirements
---

# User Requirements (Project Charter)

The canonical project requirements specification lives at **`docs/user-requirements.md`** — this is a vault pointer note to make it discoverable within the wiki-link graph.

## What It Is

A consolidated requirements document capturing the original user intent from the `/speckit.specify` and `/speckit.clarify` sessions for the `001-bootstrap-llm-workbench` feature. It defines the project's founding constraints across 10 sections:

- **Architecture & Patterns** — layered architecture (Repository → Service → God Class → Routes/CLI), ACID transactions, implicit namespace packages
- **Web UI** — Jinja2 SSR, SSE streaming, LAN accessibility, retro whimsical aesthetic
- **Tech Stack** — FastAPI, SQLAlchemy async, Pydantic v2, MLflow, Alembic, `FileStore` abstraction
- **Code Style** — PEP 420, relative imports, strict typing, one class per file
- **Testing & Quality** — TDD mandatory, 100% coverage, e2e system tests
- **Versioning & Governance** — SemVer via conventional commits, ADRs for all architecture decisions
- **Build & Distribution** — pip-installable wheel, optional extras, lock files
- **Platform** — macOS ARM primary, Linux secondary, no Windows
- **Operations & Resilience** — process supervisor, auto-migration, health checks
- **Project Management** — agentic implementation assumptions, vault enrichment discipline

## How to Use

- When evaluating whether a new feature or pattern contradicts original requirements, check this document first
- When writing an ADR, cite the relevant section here as context
- When the original intent is unclear, this is the authoritative source

## Related
- [[Reference/ArchitectureOverview|Architecture Overview]]

- [[Sessions/2026-06-10-spec-crafting|Spec Crafting Session]] — the session that produced this document
- [[Reference/Glossary|Glossary]] — key terms defined in the requirements
- [[Reference/DualBackend|Dual Backend Architecture]] — evolved from the storage abstraction requirement