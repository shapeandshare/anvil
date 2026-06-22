# CLI Contract: bootstrap-datasets Command

## Entry Point

```toml
# pyproject.toml
[project.scripts]
anvil-bootstrap-datasets = "anvil.cli:bootstrap_datasets_main"
```

## CLI Interface

```
anvil bootstrap-datasets [--dry-run] [--verbose]
```

### Arguments

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `--dry-run` | flag | `False` | Scan and report what would be imported without making changes |
| `--verbose` | flag | `False` | Print detailed per-file progress |

### Exit Codes
- `0`: All demo data imported successfully (or dry-run completed)
- `1`: Partial failure (some items failed, some succeeded)
- `2`: Fatal error (data/demo/ missing, DB connection failed)

### Output

```
$ anvil bootstrap-datasets
Bootstrapping demo data from data/demo/...
  ✓ Created corpus 'Demo - small/names' (1 files, 2 chunks)
  ✓ Created corpus 'Demo - small/hello-world' (3 files, 3 chunks)
  ✓ Created dataset 'Demo - small/presidents' (42 samples)
  ✓ Created corpus 'Demo - medium/alice' (2 files, 8 chunks)
  ✓ Created dataset 'Demo - medium/math-facts' (28 samples)
  ✓ Created corpus 'Demo - large/earnest' (3 files, 15 chunks)

Summary: 4 corpora created, 2 datasets created, 0 skipped, 0 errors
Done in 1.2s
```

```
$ anvil bootstrap-datasets  # Second run (idempotent)
Bootstrapping demo data from data/demo/...
  ✓ Corpus 'Demo - small/names' already exists, skipping
  ✓ Corpus 'Demo - small/hello-world' already exists, skipping
  ✓ Dataset 'Demo - small/presidents' already exists, skipping
  ✓ Corpus 'Demo - medium/alice' already exists, skipping
  ✓ Dataset 'Demo - medium/math-facts' already exists, skipping
  ✓ Corpus 'Demo - large/earnest' already exists, skipping

Summary: 0 corpora created, 0 datasets created, 6 skipped, 0 errors
Done in 0.3s
```

## Integration Points

- `make setup` should call `anvil bootstrap-datasets` after DB initialization
- The web UI should have a "Bootstrap Demo Data" button on the datasets page
- App startup (`app.py` lifespan) should attempt bootstrap if no demo data exists (silent, best-effort)