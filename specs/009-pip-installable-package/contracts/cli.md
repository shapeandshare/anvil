# Contract: Console Scripts (post-install CLI surface)

**Feature**: `009-pip-installable-package`

Every console script declared in `[project.scripts]` MUST be importable and runnable after a clean wheel install (FR-005, FR-007, SC-004). Verified by invoking each inside the running container via `docker compose exec`.

## Entry points after this feature

| Command | Target function | Post-install smoke check | Expected |
|---|---|---|---|
| `anvil` | `anvil.cli:serve` | started as container CMD | web serves on 8080; `/v1/health` healthy |
| `anvil-train` | `anvil.cli:train` | `anvil-train --help` (and a short run optional) | exits 0; help prints |
| `anvil-corpus` | `anvil.cli:corpus_main` | `anvil-corpus list` | exits 0; lists demo corpus |
| `anvil-stop` | `anvil.cli:stop` | `anvil-stop` (not asserted in container teardown) | exits 0 |
| `anvil-bootstrap-datasets` | `anvil.cli:bootstrap_datasets_main` | `anvil-bootstrap-datasets --dry-run` | exits 0; reports bundled demo found |
| `anvil-db` | `anvil.cli:db_main` | `anvil-db current` | exits 0; prints a revision (not `<base>` after first run) |

## Removed

| Command | Reason |
|---|---|
| `anvil-migrate-registry` | Phantom — `anvil.cli:migrate_registry` does not exist; invoking it errors. REMOVED from `[project.scripts]` (Decision 8). |

## Requirements

- R-CLI1: No entry point may reference a non-existent function (FR-007).
- R-CLI2: `anvil-corpus list` and `anvil-bootstrap-datasets --dry-run` MUST resolve the bundled demo content from the installed package (not CWD) (FR-003a).
- R-CLI3: `anvil-db current` MUST resolve the bundled migrations from the installed package and report the HEAD revision after first-run migration (FR-003, FR-010).

## Acceptance checks

| ID | Check | Maps to |
|----|-------|---------|
| CLI-1 | Each remaining script exits 0 on its smoke check inside the container | FR-007, SC-004 |
| CLI-2 | `anvil-migrate-registry` is gone (not callable) | FR-007 |
| CLI-3 | CLI checks succeed without any anvil source tree present | FR-005, FR-007 |
