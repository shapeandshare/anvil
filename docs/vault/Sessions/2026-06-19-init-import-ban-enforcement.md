---
title: 'Session: Enforce __init__.py Import Ban'
type: session-log
tags:
  - type/session-log
  - domain/architecture
  - domain/governance
  - status/draft
created: '2026-06-19'
updated: '2026-06-19'
aliases:
  - 'Session: Enforce __init__.py Import Ban'
  - init-py-import-ban
source: agent
---
# Session: Enforce `__init__.py` Import Ban

**Date**: 2026-06-19
**Trigger**: AGENTS.md rule #6 (Implicit Namespace) was not being followed — internal code was importing from `__init__.py` re-export aggregators instead of the actual definition modules.

## Problem

Rule #6 states: "Never `import` from `__init__.py` within the package itself — it violates the implicit namespace contract and creates brittle wiring."

9 files within `anvil/` were violating this rule, creating invisible dependencies on `__init__.py` re-export chains.

## What was fixed

All 9 violations re-routed to import from the actual definition module:

| File | What changed |
|------|-------------|
| `anvil/db/__init__.py` | `from anvil.db import models` → `import anvil.db.models as models` (self-import) |
| `anvil/api/app.py` | `from anvil.db import models` → `import anvil.db.models` |
| `anvil/api/app.py` | `from anvil import __version__` → `importlib.metadata.version("anvil")` |
| `anvil/api/v1/router.py` | `from anvil import __version__` → `importlib.metadata.version("anvil")` |
| `anvil/services/corpus_loader.py` | `from anvil.services.chunking import ...` → `from anvil.services.chunking.{base,file_chunker,line_chunker,window_chunker} import ...` |
| `anvil/api/v1/datasets.py` | `from anvil.services.chunking import FixedSizeWindowChunker` → `from anvil.services.chunking.window_chunker import ...` |
| `anvil/services/training.py` | `from anvil.services.compute import ...` → `from anvil.services.compute.{result,registry,resolve} import ...` |
| `anvil/services/inference.py` | `from anvil.services.compute import ...` → `from anvil.services.compute.{registry,resolve} import ...` |
| `anvil/cli.py` | `from anvil.services.compute import resolve_backend` → `from anvil.services.compute.resolve import ...` |

## Post-hoc note

The `__init__.py` Ownership Policy (enacted later on 2026-06-19) replaces "No `__init__.py` (Strict)" with bare docstring-only `__init__.py` files at authoritative namespace levels. The import ban enforced in this session **remains valid** — those `__init__.py` files are docstring-only and contain no re-exports, so importing from them would be meaningless. Direct module-path imports remain the correct pattern.

## Not changed

- `tests/` — external to the package, valid consumers of the public API
- `from anvil.config import ...` / `from anvil.gpu import ...` — those are actual `.py` modules, not `__init__.py` re-exports

## Tags

- type/session-log
- domain/architecture
- domain/governance
- status/draft

## Related

- [[Decisions/ADR-021-init-py-ownership-policy|ADR-021: __init__.py Ownership Policy]] — architecture decision record
- [[Decisions/ADR-022-domain-driven-package-decomposition|ADR-022: Domain-Driven Package Decomposition]] — related architecture decision record
- [[Code/Code|Code]] — code architecture notes
