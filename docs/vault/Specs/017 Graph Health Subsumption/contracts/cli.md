# CLI Contract: `anvil-vault`

**Date**: 2026-06-19 | **Feature**: [spec.md](../spec.md)

## Entry Point

Console script registered in `pyproject.toml`:

```toml
[project.scripts]
anvil-vault = "anvil.services.vault.cli:main"
```

## Subcommands

### `anvil-vault audit`

Replicates `scripts/ci/vault_audit.py`.

```
anvil-vault audit [--vault-dir PATH] [--apply] [--diff] [--skip-graph-health]
```

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--vault-dir` | `str` | `"docs/vault"` | Path to Obsidian vault directory |
| `--apply` | flag | `False` | Apply safe auto-fixes in-place |
| `--diff` | flag | `False` | Show proposed fixes (no changes) |
| `--skip-graph-health` | flag | `False` | Skip networkx graph analysis |

**Exit codes**: 0 = clean/warnings only, 1 = ERROR found

**Behavior**:
- Without `--apply` or `--diff`: report only, no file modifications
- `--apply` and `--diff` are mutually exclusive
- When `networkx` unavailable and `--skip-graph-health` not set: print notice, run mechanical audit only

### `anvil-vault check-adrs`

Replicates `scripts/ci/check_adr_unique.py`.

```
anvil-vault check-adrs [--decisions-dir PATH]
```

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--decisions-dir` | `str` | `"docs/vault/Decisions"` | Path to ADR decisions directory |

**Exit codes**: 0 = all ADRs valid and unique, 1 = duplicates or naming issues

### `anvil-vault check-guarded-imports`

Replicates `scripts/ci/check_guarded_imports.py`.

```
anvil-vault check-guarded-imports [--source-dir PATH]
```

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--source-dir` | `str` | `"anvil"` | Root directory of Python source to scan |

**Exit codes**: 0 = no violations, 1 = guarded imports used in runtime code

### `anvil-vault check-bump-scope`

Replicates `scripts/ci/check_bump_scope.py`.

```
anvil-vault check-bump-scope [--repo-root PATH]
```

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--repo-root` | `str` | `"."` | Git repository root path |

**Exit codes**: Always 0 (classifier, not enforcer). Prints `BUMP_SCOPE=version-only|full` to stdout.

## Output Contract

All subcommands write to stdout for CLI consumption and stderr for diagnostics. Exit code is the sole success/failure signal for CI integration.

Structured output (JSON) is NOT required — subcommands use human-readable text output matching legacy format, as CI consumes exit codes and simple text patterns (`BUMP_SCOPE=`).