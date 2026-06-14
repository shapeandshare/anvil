# microgpt-workbench Constitution (Spec Kit mirror)

> **Authoritative source**: the root [`CONSTITUTION.md`](../../CONSTITUTION.md) (v1.1.0). This file mirrors it for Spec Kit tooling (`/speckit.analyze` etc.). If the two ever diverge, the root `CONSTITUTION.md` wins; update it first, then re-sync this mirror.

## Core Principles

### Article I — Zero-Dependency Core
The core training engine (`microgpt/core/`) MUST have zero third-party Python dependencies (stdlib only). All additional functionality (web server, database, **experiment tracking**, **GPU**) MUST be opt-in layers.

### Article II — Educational Clarity
Code MUST prioritize readability/educational value over performance. Comments explain WHY, not just WHAT.

### Article III — Seeded Reproducibility
All training runs MUST be deterministic given the same seed and configuration; random state seeded explicitly; every experiment logs its configuration for exact reproduction.

### Article IV — TDD Mandatory
Tests MUST be written before implementation (Red-Green-Refactor). **Unit test coverage MUST be 100% across all layers.** End-to-end system tests MUST exist and pass.

### Article V — Async-First
Web, database, and service layers MUST be async. The core training engine is the only synchronous exception; blocking/CPU-bound calls dispatched off the event loop.

### Article VI — Implicit Namespace
PEP 420 implicit namespaces. `__init__.py` ONLY where a public API surface is exported — never for internal wiring or side-effect imports.

### Article VII — Layered Architecture
Repository pattern for all data access; business logic in Services; services exposed through the God Class (`MicroGPTWorkbench`); routes/CLI/tests call the God Class. No DB primitives leak beyond the Repository layer.

### Article VIII — Whimsy Without Compromise
The UI MUST be delightful, but whimsy MUST NEVER undermine correctness, completeness, or robustness.

### Article IX — Pit of Success
All optional capabilities (GPU, external services, advanced features) MUST work without manual configuration on capable hardware. The default do-nothing path SHALL always produce a working system. When an enabled capability is unavailable at runtime, the system SHALL **silently fall back** to the equivalent base capability — **never crash, never error, never block**. No `raise`/error response MAY be emitted solely because an optional capability's runtime dependency is absent. (Install: GPU extras auto-detected; Config: GPU opt-in via env/flag/UI; Runtime: CPU is the implicit default; explicit `make setup-gpu` forces extras.)

## Additional Constraints

- Schema changes via reversible Alembic migrations (`make db-revision`); data backfills accompany any vocabulary change.
- No type-error suppression; `mypy --strict` passes.
- Lean dependencies; new deps justified in an ADR/plan; optional/heavy deps (e.g. GPU) go in `[project.optional-dependencies]`.
- Significant decisions recorded as ADRs in `docs/vault/Decisions/`; vault enriched per session.

## Development Workflow & Quality Gates

- Spec Kit flow (`specify → clarify → plan → tasks → analyze → implement`) for non-trivial features.
- Merge gates: `make lint`, `make typecheck` (strict), `make test` (100% coverage). All MUST pass.
- Commit only when explicitly requested.

## Governance

The root `CONSTITUTION.md` supersedes all other practices; amendments require an ADR, approval, and a version bump. `/speckit.analyze` treats violations of any MUST/NON-NEGOTIABLE article (incl. Article IX) as CRITICAL findings that block `/speckit.implement` until resolved.

**Version**: 1.1.0 (mirrors root) | **Ratified**: 2026-06-10 | **Last Amended**: 2026-06-13
