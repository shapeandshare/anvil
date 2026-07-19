# Context — 075 Raise Coverage Threshold (Ratcheting)

> Cross-references: `../066-codebase-remediation/data-inventory.md` §10. Constitution Article IV.

## Current State (verified)

`pyproject.toml:203`:
```toml
[tool.coverage.report]
fail_under = 23
```
Test config (`pyproject.toml:192-196`):
```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
addopts = "-v --cov=anvil --cov-report=term-missing --ignore=tests/system --ignore=tests/browser"
```

Docs claim actual coverage ~41% (AGENTS.md, ARCHITECTURE.md), but this was **NOT verified** during spec creation (no venv in that environment).

## CRITICAL: Measure First

Do NOT guess. Run:
```bash
make setup     # if .venv missing
make test      # reports TOTAL coverage line at the end
```
Read the `TOTAL ... NN%` line. Set `fail_under` to `floor(NN)`.

## Constitution Constraint (Article IV)

- `fail_under` is a RATCHET: may only increase. Lowering requires explicit recorded approval.
- The threshold should equal the current measured level (or slightly below to allow noise margin — but the Constitution says "current measured level").

## Interaction With Other Specs

- Specs 066-074 and 076-080 ADD tests (TDD). They should RAISE coverage. Run this spec (075) LAST, after other specs land, so the ratchet captures the improved coverage.
- Alternatively: bump to current (~41) now, then bump again after the suite lands.

## Gotchas

- Coverage excludes migrations and system/browser tests (already configured in `[tool.coverage.run] omit`).
- If coverage legitimately drops due to dead-code removal (e.g., removing `get_config` shim in spec 083), the numerator shrinks — account for this; don't penalize simplification.
- Document the ratcheting policy in CONTRIBUTING.md (FR-005).
