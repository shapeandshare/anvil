# microgpt-workbench Constitution

## Core Principles

### Article I — Zero-Dependency Core

The core training engine (`microgpt/core/`) MUST have zero third-party Python dependencies — stdlib only. This ensures the fundamental algorithm is accessible to anyone with Python, without pip install. All additional functionality (web server, database, experiment tracking, GPU) MUST be opt-in layers.

### Article II — Educational Clarity

Code MUST prioritize readability and educational value over performance optimization. The progressive walkthrough files (`train0.py` through `train5.py`) SHALL demonstrate the GPT algorithm one component at a time. Comments SHALL explain WHY not just WHAT.

### Article III — Seeded Reproducibility

All training runs MUST be deterministic given the same seed and configuration. Random state MUST be seeded explicitly. Every experiment SHALL log its configuration for exact reproduction.

### Article IV — TDD Mandatory

Tests MUST be written before implementation for every feature (Red-Green-Refactor). Unit test coverage MUST be 100% across all layers. Full end-to-end system tests MUST exist and pass.

### Article V — Async-First

The web server, database layer, and service layer MUST use async Python throughout. FastAPI async handlers, async SQLAlchemy, async FileStore I/O. The core training engine is the only exception (synchronous math).

### Article VI — Implicit Namespace

All Python packages MUST use implicit namespace packages (PEP 420). `__init__.py` files SHALL exist ONLY in directories that export a public API surface. They MUST NOT be used for internal wiring, side-effect imports, or namespace initialization.

### Article VII — Layered Architecture

All data access MUST follow the Repository pattern. Business logic MUST be in the Service layer. All services MUST be exposed through a single God Class (`MicroGPTWorkbench`). Routes, CLI, and tests call the God Class. No DB primitives leak beyond the Repository layer.

### Article VIII — Whimsy Without Compromise

The UI MUST be delightful — pixel art, ASCII banners, SVG animations, emojis, a unicorn mascot 🦄. Whimsy MUST NEVER undermine correctness, completeness, or robustness.

## Governance

This constitution supersedes all other practices in this repository. Amendments require documentation in an Architecture Decision Record (ADR), approval, and version bump. All PRs and agent sessions must verify compliance with these articles.

**Version**: 1.0.0 | **Ratified**: 2026-06-10 | **Last Amended**: 2026-06-10