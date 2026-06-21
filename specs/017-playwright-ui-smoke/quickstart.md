# Quickstart: Playwright UI Smoke Harness

## Prerequisites

- `make setup` completed (Python venv + dependencies installed)
- Docker installed and running (compose lifecycle brings up the app)
- Playwright Chromium (auto-installed by `make test-browser` on first run if missing)

## Running the Smoke Tests

```bash
make test-browser
```

This single command executes the full loop:
1. `uv run playwright install chromium` — auto-install Chromium if missing (idempotent)
2. `docker compose down -v` — reset any previous state
2. `docker compose up -d --build --wait` — build and start the app stack
3. `pytest tests/browser -v --no-cov` — run the smoke test suite
4. `docker compose down -v` — teardown

## Running Individual Tests

```bash
# Run just the navigation smoke test
uv run pytest tests/browser/test_navigation_smoke.py -v --no-cov

# Run with visible browser (debugging)
uv run pytest tests/browser/test_navigation_smoke.py -v --no-cov --headed

# Run with slow motion (observing interactions)
uv run pytest tests/browser/test_navigation_smoke.py -v --no-cov --headed --slowmo 500
```

## What Gets Tested

| Test | What It Verifies |
|------|------------------|
| `test_navigation_smoke` | All 8 primary pages load without console errors; nav links work |
| `test_dataset_upload_wiring` | Upload form submits to backend; dataset appears in list |
| `test_training_sse_wiring` | Training start button → live chart receives ≥1 data point |
| `test_experiment_listing_wiring` | Completed run shows in experiment list with final loss |
| `test_inference_wiring` | Model selected → prompt submitted → non-empty output rendered |

## CI Integration

The browser smoke tests run in a **Linux-only** GitHub Actions job that is **non-blocking for v1** (`continue-on-error: true`) — it reports a status signal without blocking merge to `main`. This mirrors the existing heavy `tests/system` suite, which is deliberately kept out of the blocking CI path. The job may be promoted to a blocking gate after a sustained zero-flake record (≥10 consecutive CI runs), as recorded in the ADR. The job:

1. Checks out the repository
2. Sets up uv
3. Runs `make setup`
4. Installs Playwright browsers: `uv run playwright install --with-deps chromium`
5. Runs `make test-browser`

## What NOT To Do

- Do NOT add `pytest-playwright` to runtime dependencies
- Do NOT run browser tests as part of `make test` (they are excluded via `--ignore`)
- Do NOT add visual/pixel snapshot regression tests (out of scope)
- Do NOT add fixed `time.sleep()` calls — always use Playwright auto-waiting
- Do NOT promote the job to blocking until it is proven flake-free — a flaky blocking gate stalls all merges

## Troubleshooting

| Problem | Likely Cause | Fix |
|---------|-------------|-----|
| `ModuleNotFoundError: playwright` | Playwright not installed | `uv sync` (installs `pytest-playwright` dev dep) |
| `Browser not found` | Chromium not installed | `uv run playwright install chromium` |
| Tests fail with timeout | App not ready or port conflict | Check `docker compose ps`; ensure port 8080 is free |
| Tests fail on CI with browser errors | Missing Linux deps | Use `playwright install --with-deps chromium` |
| `make test` collects browser tests | `--ignore` missing from pyproject.toml | Verify `addopts` includes `--ignore=tests/browser` |