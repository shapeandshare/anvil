# Contract: System Tests (acceptance gate)

**Feature**: `009-pip-installable-package`

The focused system-test suite that gates the feature as a functional end product (FR-012, FR-013, SC-008). Runs against the **running container** via `httpx` (HTTP) and `docker compose exec` (CLI). Location: `tests/system/test_installed_runtime.py`.

## Orchestration (Makefile `test-system`)

```
docker compose down -v                      # reset volume → fresh first-run (Q4, FR-011a)
docker compose up -d --build --wait         # build wheel image, start, wait until /v1/health healthy
pytest tests/system -v                       # run assertions below
status=$?
docker compose down -v                      # teardown + reset
exit $status
```

## HTTP assertions (httpx → http://localhost:8080)

| ID | Request | Expected |
|----|---------|----------|
| ST-H1 | `GET /v1/health` | 200; JSON `status == "healthy"`; `version` matches installed `anvil.__version__` |
| ST-P1 | `GET /` | 200; HTML |
| ST-P2 | `GET /v1/training-page` | 200; HTML |
| ST-P3 | `GET /v1/datasets-page` | 200; HTML |
| ST-P4 | `GET /v1/experiments-page` | 200; HTML |
| ST-P5 | `GET /v1/models-page` | 200; HTML |
| ST-P6 | `GET /v1/inference-page` | 200; HTML |
| ST-P7 | `GET /v1/operations-page` | 200; HTML |
| ST-P8 | `GET /v1/learn` | 200; HTML |
| ST-A1 | For EACH primary page (ST-P1..ST-P8): parse the returned HTML for at least one referenced `/static/...` URL and `GET` it | every referenced asset → 200 with a non-error content-type (no missing-asset failure) — **per-page**, satisfying SC-006 100% — FR-003/SC-003/SC-006 |
| ST-D1 | `GET /v1/corpora` (or `/v1/datasets`) | 200; bundled demo content present (≥1 demo corpus) — FR-003a |

> ST-A1 derives assets dynamically from each page's HTML so coverage tracks every primary page, not a single hand-picked asset.

## CLI assertions (docker compose exec anvil ...)

| ID | Command | Expected |
|----|---------|----------|
| ST-C1 | `anvil-db current` | exit 0; prints a non-`<base>` revision (DB migrated on first run) |
| ST-C2 | `anvil-corpus list` | exit 0; lists the demo corpus |
| ST-C3 | `anvil-bootstrap-datasets --dry-run` | exit 0; reports bundled demo discovered |
| ST-C4 | `anvil-train --help` | exit 0; help text prints (entry point importable/runnable) |
| ST-C5 | `anvil-stop` | exit 0; idempotent (succeeds even when nothing is running) |

> ST-C1..ST-C5 cover SC-007 ("100% of documented CLI tools"). `anvil` itself is exercised as the container CMD (web serves). `anvil-migrate-registry` is excluded — removed as phantom.

## Failure-reporting requirement

- ST-R1: On any failure, output MUST identify the failing aspect — install vs. page vs. asset vs. DB vs. CLI (FR-013, SC-008). (pytest test IDs above provide this granularity.)
- ST-R2: The suite MUST NOT invoke `anvil-migrate-registry` (removed/phantom).
- ST-R3: The suite MUST pass against a freshly reset volume (no reliance on prior state) (Q4).

## Acceptance checks

| ID | Check | Maps to |
|----|-------|---------|
| SYS-1 | Full `make test-system` returns single pass/fail | FR-013, SC-008, SC-010 |
| SYS-2 | All ST-H/ST-P/ST-A/ST-D/ST-C assertions pass against the installed container | US4, FR-012, SC-003/004/005/006/007 |
| SYS-3 | Loop (build→image→online→tests) runnable locally from documented commands | SC-010 |
