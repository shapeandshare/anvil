# Quickstart: Vault Health Subsumption

**Date**: 2026-06-19 | **Feature**: [spec.md](spec.md)

## What This Feature Delivers

After subsumption, developers interact with vault health tools through the standard `anvil-vault` CLI:

```bash
# Run full vault audit (mechanical + graph health)
anvil-vault audit

# Run mechanical audit only (skip graph health)
anvil-vault audit --skip-graph-health

# Auto-fix fixable issues
anvil-vault audit --apply

# Preview auto-fixes (no changes)
anvil-vault audit --diff

# CI validators
anvil-vault check-adrs
anvil-vault check-guarded-imports
anvil-vault check-bump-scope

# Programmatic use (Python)
from anvil.services.vault import VaultHealthService, GraphHealthService

svc = VaultHealthService(vault_dir="docs/vault")
report = await svc.run_audit()
print(report.errors)  # typed Finding objects
```

## For CI Pipeline Maintainers

Update `shared/vault.mk` to delegate to the new CLI:

```makefile
# Before:
vault-audit:
    $(PYTHON) scripts/ci/vault_audit.py $(VAULT_DIR)

# After:
vault-audit:
    anvil-vault audit --vault-dir $(VAULT_DIR)
```

The legacy `scripts/ci/vault_audit.py` is retained as a thin wrapper during transition for backward compatibility.

## Installation

```bash
# Install with graph health support
pip install "anvil[vault-health]"

# Install without graph health (mechanical audit only)
pip install anvil
```

## Migration Checklist

1. ✅ New `anvil/services/vault/` domain sub-package created
2. ✅ Types migrated to Pydantic BaseModel
3. ✅ One class per file decomposition
4. ✅ NumPy docstrings on all public symbols
5. ✅ mypy --strict passes
6. ✅ CLI entry points in `pyproject.toml`
7. ✅ `shared/vault.mk` updated
8. ✅ Thin wrappers in `scripts/ci/` (transition only)
9. ✅ `networkx` moved to `[project.optional-dependencies] vault-health`
10. ✅ Tests for all new service classes
11. ✅ Vault enriched with session log + ADR