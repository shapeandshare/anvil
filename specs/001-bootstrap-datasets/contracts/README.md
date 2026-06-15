# Contracts Overview

This feature introduces no new external API contracts. All interfaces are internal:

| Contract | File | Purpose |
|----------|------|---------|
| DemoBootstrapService | `anvil/services/demo_bootstrap.py` | Core orchestration logic |
| CLI: `bootstrap-datasets` | `anvil.cli:bootstrap_datasets_main` | User-facing command |
| Training Fallback | `anvil/services/training.py:_load_docs()` | Modified to use demo corpus |
| Inference Demo Model | `anvil/services/inference.py` | Modified to load from DB |