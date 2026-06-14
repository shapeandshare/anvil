# anvil Constitution

## Core Principles

### Article I — Zero-Dependency Core

The core training engine (`anvil/core/`) MUST have zero third-party Python dependencies — stdlib only. This ensures the fundamental algorithm is accessible to anyone with Python, without pip install. All additional functionality (web server, database, experiment tracking, GPU) MUST be opt-in layers.

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

All data access MUST follow the Repository pattern. Business logic MUST be in the Service layer. All services MUST be exposed through a single God Class (`AnvilWorkbench`). Routes, CLI, and tests call the God Class. No DB primitives leak beyond the Repository layer.

### Article VIII — iOS-Grade Polish

The UI MUST be polished and responsive — fluid animations, clear visual hierarchy, precise typography, and platform-appropriate interactions. Delight comes from craft and attention to detail: spring-based motion, glass materials (where accessible), consistent spacing, and thoughtful touch targets. The design language MUST follow the system's native aesthetic (iOS on Apple devices, platform-appropriate on others). Polish MUST NEVER undermine correctness, completeness, or robustness.

### Article IX — Pit of Success

All optional capabilities (GPU acceleration, external services, advanced features) MUST work without manual configuration on capable hardware. The default, do-nothing path SHALL always produce a working system. When a user enables an enhanced capability that is unavailable at runtime, the system SHALL silently fall back to the equivalent base capability — never crash, never error, never block. Specifically:

- **Install layer**: GPU dependencies (torch) SHALL be auto-detected on Apple Silicon (MPS) and NVIDIA Linux (nvidia-smi). `make setup` installs GPU extras automatically on capable platforms.
- **Config layer**: GPU acceleration is opt-in via `USE_GPU=true` env var, `--gpu` CLI flag, or web UI toggle.
- **Runtime layer**: CPU is the implicit default device. If GPU is opted in but unavailable (torch missing, no accelerator detected), training SHALL fall back to CPU without raising.
- **Explicit override**: `make setup-gpu` / `make install-gpu` force GPU extras regardless of auto-detection.

## Governance

This constitution supersedes all other practices in this repository. Amendments require documentation in an Architecture Decision Record (ADR), approval, and version bump. All PRs and agent sessions must verify compliance with these articles.

**Version**: 1.2.0 | **Ratified**: 2026-06-10 | **Last Amended**: 2026-06-13