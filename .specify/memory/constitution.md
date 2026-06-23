<!--
SYNC IMPACT REPORT — Constitution Amendment
Version change: 1.7.0 → 1.8.0 (MINOR: new principle added)
Date: 2026-06-22
Modified principles: none renamed or removed
Added sections:
  - Article XI — Simplicity First (Boring Technology)
Removed sections: none
Templates / docs propagated:
  - ✅ .specify/templates/plan-template.md (Constitution Check gate references Article XI)
  - ✅ AGENTS.md (Behavioral Principle 13 + Architecture Rules bullet)
  - ✅ docs/vault/Decisions/ADR-041-simplicity-first-boring-technology.md (new ADR)
  - ✅ docs/vault/Decisions/README.md (ADR index row)
  - ⚠ .specify/templates/spec-template.md (no change — no principle-gate section)
  - ⚠ .specify/templates/tasks-template.md (no change — Polish phase already covers cleanup/refactor)
Follow-up TODOs: none
-->
# anvil Constitution

> **Canonical source** — this is the single authoritative constitution for the project. The root `CONSTITUTION.md` and `docs/vault/Governance/Constitution.md` redirect here. All agents, PRs, and specs must comply with this document.

## Core Principles

### Article I — Zero-Dependency Core

The core training engine (`anvil/core/`) MUST have zero third-party Python dependencies — stdlib only. This ensures the fundamental algorithm is accessible to anyone with Python, without pip install. All additional functionality (web server, database, experiment tracking, GPU) MUST be opt-in layers.

### Article II — Educational Clarity

Code MUST prioritize readability and educational value over performance optimization. The progressive walkthrough files (`train0.py` through `train5.py`) SHALL demonstrate the Llama transformer architecture one component at a time. Comments SHALL explain WHY not just WHAT.

### Article III — Seeded Reproducibility

All training runs MUST be deterministic given the same seed and configuration. Random state MUST be seeded explicitly. Every experiment SHALL log its configuration for exact reproduction.

### Article IV — TDD Mandatory

Tests MUST be written before implementation for every feature (Red-Green-Refactor). Unit test coverage MUST meet a ratcheting baseline: the enforced threshold (set in ``pyproject.toml [tool.coverage.report] fail_under``) is the current measured level and may only increase; lowering it requires explicit, recorded approval. An aspirational goal of improving coverage over time is encouraged. Full end-to-end system tests MUST exist and pass.

### Article V — Async-First

The web server, database layer, and service layer MUST use async Python throughout. FastAPI async handlers, async SQLAlchemy, async FileStore I/O. The core training engine is the only exception (synchronous math).

### Article VI — `__init__.py` Ownership Policy

This is an implicit namespace package codebase. The `anvil/` package root has `anvil/__init__.py` to expose the public API (e.g., `__version__`). For every sub-directory that is a fully-owned Python package level (a directory containing `.py` modules that forms a complete, authoritative part of the `anvil.*` namespace), a **bare `__init__.py`** MUST exist to assert ownership and designate it as a regular package. This means:

- Authoritative levels (fully owned by the `anvil` project) get a bare `__init__.py` — a docstring-only file describing the package's purpose. No re-exports, no imports.
- Data-only directories (`static/`, `templates/`, `data/`, `_resources/`, and similar non-Python-package directories) MUST NOT have `__init__.py`.
- All internal imports MUST continue to use direct module paths: `from .module import X`, not `from . import X` where `X` is a re-export.
- No `__init__.py` may re-export symbols for internal consumption.
- This is enforced at merge review — adding or removing `__init__.py` at a package level requires justification that the level is (or is not) a fully-owned authoritative namespace level.

### Article VII — Layered Architecture

All data access MUST follow the Repository pattern. Business logic MUST be in the Service layer. All services MUST be exposed through a single God Class (`AnvilWorkbench`). Routes, CLI, and tests call the God Class. No DB primitives leak beyond the Repository layer.

### Article VIII — iOS-Grade Polish

The UI MUST be polished and responsive — fluid animations, clear visual hierarchy, precise typography, and platform-appropriate interactions. Delight comes from craft and attention to detail: spring-based motion, glass materials (where accessible), consistent spacing, and thoughtful touch targets. The design language MUST follow the system's native aesthetic (iOS on Apple devices, platform-appropriate on others). Polish MUST NEVER undermine correctness, completeness, or robustness.

### Article IX — Pit of Success

All optional capabilities (GPU acceleration, external services, advanced features) MUST work without manual configuration on capable hardware. The default, do-nothing path SHALL always produce a working system. When a user enables an enhanced capability that is unavailable at runtime, the system SHALL silently fall back to the equivalent base capability — never crash, never error, never block. Specifically:

- **Install layer**: GPU dependencies (torch) SHALL be auto-detected on Apple Silicon (MPS) and NVIDIA Linux (nvidia-smi). `make setup` installs GPU extras automatically on capable platforms.
- **Config layer**: GPU acceleration is opt-in via `USE_GPU=true` env var, `--gpu` CLI flag, or web UI toggle.
- **Runtime layer**: CPU is the implicit default device. If GPU is opted in but unavailable (torch missing, no accelerator detected), training SHALL fall back to CPU without raising.
- **Explicit override**: `make setup-gpu` / `make install-gpu` force GPU extras regardless of auto-detection.

### Article X — Domain-Driven Package Decomposition

Package boundaries SHALL follow domain (bounded context) boundaries. Sub-packaging is governed by cohesion and coupling, not file count alone. This article pairs with the one-class-per-file rule (below) and the `__init__.py` Ownership Policy (Article VI).

- **§10.1 — Domain threshold**: When a package directory contains 12 or more peer `.py` modules, the maintainer MUST evaluate whether the directory mixes multiple domains. If it does, the maintainer SHALL split it into domain-aligned sub-packages.

- **§10.2 — Tight coupling rule**: Result types, exception/error classes, and value objects that are tightly coupled to exactly one service module SHALL co-locate in that service's domain sub-package. They MUST NOT live at the parent package level. This prevents the proliferation of single-class files at the parent level (a direct consequence of pairing one-class-per-file with DDD).

- **§10.3 — Cross-domain shared types**: Types referenced by two or more domains SHALL live in a `_shared/` sub-package within their parent domain. The underscore prefix signals "not a domain, internal infrastructure." At the top-level package boundary (`anvil/` level), shared types MAY live in a `_shared/` directory at the `anvil/` root if they span top-level packages (e.g., a type shared between `services/` and `api/`).

- **§10.4 — Domain naming convention**: Domain sub-packages use plural nouns: `models/`, `repositories/`, `datasets/`, `compute/`, `training/`, `chunking/`. Internal/infrastructure sub-packages use underscore-prefixed names: `_shared/`, `_types/`, `_errors/`. This visually distinguishes domain boundaries from infrastructure grouping.

- **§10.5 — Nesting limit**: Maximum two levels of sub-packaging from any parent package root. A module at `anvil/services/training/backend.py` is acceptable. A module at `anvil/services/training/backend/torch/runner.py` is not — use a longer module name (`torch_backend.py`) rather than deeper nesting.

- **§10.6 — Pairing with Article VI (`__init__.py` Ownership Policy)**: Every domain sub-package is an "authoritative level" under Article VI and MUST have a bare, docstring-only `__init__.py`. The docstring SHALL describe the domain's purpose. Internal sub-packages (`_shared/`, `_types/`, `_errors/`) are also authoritative levels — they get a bare `__init__.py` with a docstring describing the shared/infrastructure purpose.

- **§10.7 — Pairing with one-class-per-file**: DDD determines WHICH sub-package a file belongs to. Each class file is placed in the domain sub-package whose bounded context it serves. A one-result-type file that serves exactly one service module goes into that service's domain sub-package, not into the parent package. This prevents the parent level from accumulating orphan result/error types.

- **§10.8 — Import discipline in a DDD structure**:
  Modules within a domain sub-package use `from .sibling_module import X`.
  Modules in sibling domain sub-packages use `from ..sibling_domain.module import X`.
  Parent-level modules that reference sub-packages use `from .sub_package.module import X`.
  No `__init__.py` re-exports between domains — the relative import rules in Article VI continue unchanged.
  Cross-domain types in `_shared/` are imported as `from .._shared.module import X` (or `from ._shared.module import X` when inside the same parent).

- **§10.9 — Refactoring discipline**: Introducing a domain sub-package is a structural change that SHALL be its own commit/PR. It SHALL NOT be combined with behavioral changes. Imports in consuming modules MUST be updated in the same commit. The diff MUST show only moves and import rewrites — zero behavioral delta.

### Article XI — Simplicity First (Boring Technology)

Every change MUST favor the simplest, most boring solution that fully satisfies the requirement. Proven reliability and obviousness outrank cleverness, novelty, and speculative flexibility. This article is a hard gate at merge review: unjustified complexity, or an unproven approach where a simpler proven one exists, is reject-worthy.

- **§11.1 — Simplest viable solution**: Implementations MUST choose the simplest approach that meets the stated requirement. Complexity is never the default — it MUST be justified by a concrete, present requirement, never by a hypothetical future one.

- **§11.2 — Boring over novel**: Prefer mature, well-understood, widely-used technology and patterns over new, clever, or unproven ones. A novel or experimental dependency, framework, library, or pattern MUST NOT be introduced unless a simpler proven alternative has been evaluated and explicitly rejected in an ADR or the plan's Complexity Tracking table. This pairs with Article I (Zero-Dependency Core) and the "Lean dependencies" constraint.

- **§11.3 — YAGNI (You Aren't Gonna Need It)**: Build only what the current requirement needs. Speculative generality, premature abstraction, configuration knobs without a present consumer, and "future-proofing" for unrequested scenarios are forbidden. Introduce an abstraction when the second concrete use case actually arrives — not before.

- **§11.4 — Reuse before introducing**: Existing libraries, patterns, utilities, and abstractions already present in the codebase MUST be reused before a new one is introduced. Adding a second, parallel way to do something the codebase already does is reject-worthy.

- **§11.5 — Justify every deviation**: Any solution more complex than the simplest viable alternative MUST be recorded in the plan's Complexity Tracking table (`.specify/templates/plan-template.md`) with (a) the simpler alternative considered and (b) the specific reason it was rejected. A change that adds complexity without this record fails the Constitution Check.

- **§11.6 — Untested paths are not done**: An approach that cannot be tested, or has not been tested, MUST NOT be treated as complete or shipped as the chosen solution. A simpler, demonstrably testable approach is always preferred over a complex one whose correctness cannot be shown. This pairs with Article IV (TDD Mandatory).

## Additional Constraints

- Schema changes via reversible Alembic migrations (`make db-revision`); data backfills accompany any vocabulary change.
- No type-error suppression; `mypy --strict` passes. Module-level ``ignore_errors`` overrides MUST be narrowed to specific error codes and justified if they cannot be removed.
- `TYPE_CHECKING`-guarded type-only imports are permitted ONLY to break a genuine runtime circular import that cannot be resolved without violating another constitutional rule (no string-literal forward references, one-class-per-file, `mypy --strict`). Each permitted guarded import MUST satisfy: (a) the module declares ``from __future__ import annotations``; (b) a genuine runtime cycle exists with no rule-compliant alternative; (c) the guarded symbol is referenced only in annotations, never in runtime code; and (d) a one-line comment names the specific cycle. A script (`scripts/ci/check_guarded_imports.py`) enforces condition (c).
- Lean dependencies; new deps justified in an ADR/plan; optional/heavy deps (e.g. GPU) go in `[project.optional-dependencies]`.
- Significant decisions recorded as ADRs in `docs/vault/Decisions/`; vault enriched per session.
- Pydantic `BaseModel` MUST be used for all structured data/value-object classes over `dataclasses.dataclass`. Existing `@dataclass` usages are grandfathered until touched for other reasons, but all NEW code MUST use `BaseModel`.
- **UI compliance (MUST)** — All UI, template, and CSS work MUST comply with `docs/ux-rules.md`. S4/S3 findings block; resolve them, never dilute the rule.
- **One class per file** — Every Python source file MUST contain exactly one class definition. Utility constants, functions, enums, and module-level helpers are permitted in the same file as the primary class only when they are inseparable from that class's interface. Exception and error classes that are tightly coupled may share a file with their primary class. Enforcement is at merge review — any reintroduced multi-class file without explicit exception approval is reject-worthy.

## Development Workflow & Quality Gates

- Spec Kit flow (`specify → clarify → plan → tasks → analyze → implement`) for non-trivial features.
- Merge gates: `make lint`, `make typecheck` (strict), `make test` (coverage at `fail_under` rate), `make vault-audit` (0 errors). All MUST pass in CI on every pull request.
- Commit only when explicitly requested.

## Governance

This constitution supersedes all other practices in this repository. Amendments require documentation in an Architecture Decision Record (ADR), approval, and version bump. All PRs and agent sessions must verify compliance with these articles.

**Version**: 1.8.0 | **Ratified**: 2026-06-10 | **Last Amended**: 2026-06-22
