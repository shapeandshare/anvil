---
title: 'Session: Install Portability Overhaul'
type: session-log
tags:
  - type/session-log
  - domain/operations
created: '2026-06-14'
updated: '2026-06-14'
aliases:
  - 2026-06-14-install-portability-overhaul
source: agent
---
# Session: Install Portability Overhaul

**Date**: 2026-06-14
**Trigger**: Audit of how well the project covers installation information for a newcomer/agent

## Assessment

The project scored **6/10** on install portability. Strengths included good README quick start, Makefile automation, Constitution Article IX (Pit of Success), and a populated `uv.lock`. Critical gaps:

1. **Hardcoded Python path** — `shared/python.mk` had `PYTHON_MAIN := /opt/homebrew/bin/python3.11` — a machine-specific absolute Homebrew path that would fail on any other machine
2. **Lock file not wired into build** — `uv.lock` existed (1793 lines of pinned deps) but `make setup` used `pip install -e .` which re-resolves every time. An empty `requirements.lock` was misleading.
3. **No system prerequisites documented** — nowhere listed what tools were needed (Python 3.11+, git, make, bash, uv)
4. **No troubleshooting section** — no guidance for common failures
5. **No Dockerfile** — no containerized deployment option

## What was implemented

9 tasks across 7 files:

| Task | File | Change |
|------|------|--------|
| T1 | `shared/python.mk` | Removed hardcoded `PYTHON_MAIN`; switched from pip to `uv sync` using `uv.lock` |
| T2 | `scripts/detect-gpu-platform.sh` | Output changed from `,gpu` (pip extras syntax) to `gpu` (uv `--extra` syntax) |
| T3 | `README.md` | Added **Prerequisites** section (Python, git, make, bash, uv, nvidia-smi) |
| T4 | `requirements.lock` | Deleted (empty, redundant with `uv.lock`) |
| T5 | `README.md` | Added **Troubleshooting** table (7 scenarios) |
| T6 | `Dockerfile` (new) | Python 3.11-slim, uv, make setup, expose 8080/5001 |
| T7 | `Makefile` | Added `make docker` target |
| T8 | `README.md` | Added Windows/WSL2 note |
| T9 | `AGENTS.md` | Updated `make setup` description to "via uv" |

## Key decisions

1. **uv sync over pip**: The existing `uv.lock` was already the lock file of record — switching `make setup` to `uv sync` makes installs reproducible. `uv` handles Python discovery on its own, eliminating the need for `PYTHON_MAIN`.
2. **No Docker Compose**: A single `Dockerfile` suffices for the MVP. If multi-service orchestration (MLflow + web + DB) becomes needed later, docker-compose can be added.
3. **GPU detection script kept simple**: Changed output format only (`,gpu` → `gpu`), didn't change detection logic. The Makefile converts to the right flag format.

## Files changed

- `shared/python.mk` (pip → uv sync, removed PYTHON_MAIN)
- `scripts/detect-gpu-platform.sh` (output format change)
- `README.md` (prerequisites, troubleshooting, windows note, commands update)
- `AGENTS.md` (command description fix)
- `requirements.lock` (deleted)
- `Dockerfile` (new)
- `Makefile` (docker target added)