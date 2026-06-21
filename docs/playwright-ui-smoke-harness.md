# Playwright UI Smoke Harness Implementation Plan

## Overview

The functional/backend correctness layer is owned by `functional-api-e2e-suite.md` (httpx-driven,
no browser). **This plan covers the one thing a browser uniquely verifies: that the polished UI is
actually *wired* to the working backend** — forms submit to the right endpoints, the SSE training
chart receives live points, runs appear in tables, buttons enable/disable, and primary navigation
works. It is intentionally a **thin smoke layer (≈4–6 tests)**, not a full UI regression suite.

It mirrors the existing `tests/system/` pattern, which already boots the real app in Docker on
`:8080` and runs httpx assertions via `make test-system`. Playwright reuses that exact lifecycle.

**This adds one dev-only dependency (`pytest-playwright`).** Local mode and the runtime/core deps
are untouched. Browser tests run in their own target/CI job — **never** in the fast `make test`
coverage loop.

---

## Ground Truth (verified against the codebase)

- App serves on **`http://localhost:8080`**; `tests/system/conftest.py` already defines
  `BASE_URL = "http://localhost:8080"`, a session-scoped `httpx.Client`, and a `compose_exec`
  helper. The compose lifecycle (`docker compose down -v; up -d --build --wait`) lives in the
  `test-system` target in the root `Makefile`.
- pytest excludes `tests/system` from the default run via
  `addopts = "... --ignore=tests/system"`, and the system suite runs with `--no-cov`. The
  Playwright suite MUST follow the same exclusion/`--no-cov` discipline (it is behavioral, not
  line-coverage).
- Frontend is **vanilla ES6 modules, no build step** (`anvil/api/static/js/**`). Pages are
  Jinja2 templates. Key interactive files: `sse.js` (EventSource), `chart.js` (live loss chart),
  `core.js`, `composer.js`. SSE training stream endpoint: `GET /v1/training/stream/{run_id}`.
- Primary user routes (verified): `/` (dashboard/hero), `/v1/datasets-page`, `/v1/training-page`,
  `/v1/experiments-page`, `/v1/models-page`, `/v1/inference-page`, `/v1/operations-page`,
  `/v1/learn`.
- Existing system tests live in `tests/system/{conftest.py,test_*.py}` and import helpers via
  `from conftest import compose_exec` (flat import, because pytest adds the test dir to `sys.path`).
- CI (`.github/workflows/ci.yml`) runs `make test` in a `test` job on `ubuntu-latest`. System
  tests are currently **NOT** in CI (local-only). The browser job added here is **new** and
  Linux-only (Playwright browsers need Linux deps via `playwright install --with-deps`).

---

## Decision required: ADR before coding

Adding a browser-test toolchain is a "significant architecture decision" → **AGENTS.md Principle 4
requires an ADR**. Author `docs/vault/Decisions/ADR-0NN-playwright-ui-smoke-harness.md` capturing:
- Why Playwright over Selenium/Cypress (async/SSE handling, auto-waiting, Python-native via
  `pytest-playwright`, no JS test toolchain in a Python-first repo).
- Scope boundary: smoke/wiring only; functional correctness stays in the httpx e2e suite.
- Why it lives outside the coverage gate and runs in a separate (Linux-only) CI job.
- Chromium-only for v1 (no cross-browser matrix).

> Number the ADR by checking the highest existing `ADR-0NN` in `docs/vault/Decisions/`.

---

## Scope

### File layout

```
tests/browser/                      # NEW top-level test dir (peer of tests/system)
├── conftest.py                     # base_url, compose lifecycle reuse, page/context fixtures, helpers
├── test_navigation_smoke.py        # all primary pages load + nav works, no console errors
├── test_dataset_upload_wiring.py   # upload a .txt on datasets-page → appears in list
├── test_training_sse_wiring.py     # configure + Start on training-page → live chart receives ≥1 point
├── test_experiment_listing_wiring.py # the run shows up on experiments-page with a final loss
└── test_inference_wiring.py        # playground: pick model, submit prompt → non-empty output rendered
```

> `tests/browser` (not under `tests/system`) keeps it a clean, separately-invokable suite and
> avoids colliding with the existing system conftest. It must ALSO be added to the pytest
> `--ignore` list so the default `make test` never collects it.

### Dependency + config changes

1. **`pyproject.toml`** → add to `[project.optional-dependencies].dev`:
   `"pytest-playwright>=0.5,<1"` (pin within the project's existing style). Do NOT add to runtime
   `dependencies`.
2. **`pyproject.toml`** → extend pytest `addopts` ignore:
   `--ignore=tests/system --ignore=tests/browser`.
3. **`pyproject.toml`** → extend `[tool.coverage.run].omit` with `"tests/browser/*"`.
4. **Makefile** → add a `test-browser` target mirroring `test-system`:
   ```make
   test-browser: ## Browser smoke loop: reset → up → playwright tests → teardown
   	docker compose down -v; \
   	docker compose up -d --build --wait; \
   	uv run pytest tests/browser -v --no-cov; status=$$?; \
   	docker compose down -v; \
   	exit $$status
   ```
   (Confirm whether shared make logic belongs in `shared/testing.mk` vs. the root `Makefile` —
   `test-system` currently lives in the root Makefile, so co-locate `test-browser` there.)
5. **Playwright browser install** — document in the target/README that `uv run playwright install
   chromium` (locally) / `playwright install --with-deps chromium` (CI) is required once.

---

## Implementation Steps

### STEP 1 — ADR + harness scaffold
1. Write the ADR (see "Decision required" above).
2. Add the dependency + config changes (items 1–4 above).
3. Create `tests/browser/conftest.py`:
   - Reuse the compose lifecycle. **Preferred**: a `session`-scoped autouse fixture that brings
     the stack up once and tears it down once (so individual tests don't each pay compose cost),
     OR rely on `make test-browser` to manage compose and have conftest only provide a
     readiness wait against `GET /v1/health`. Pick ONE and document it; do not double-manage.
   - Provide a `base_url` fixture = `http://localhost:8080`.
   - Provide `pytest-playwright`'s `page` fixture config (headless, chromium, sane default
     timeout, e.g. 15s).
   - Add a `assert_no_console_errors(page)` helper that attaches a `page.on("console")` /
     `page.on("pageerror")` listener and fails on uncaught JS errors.

### STEP 2 — Navigation smoke (`test_navigation_smoke.py`)
- For each primary route (`/`, `/v1/datasets-page`, `/v1/training-page`,
  `/v1/experiments-page`, `/v1/models-page`, `/v1/inference-page`, `/v1/operations-page`,
  `/v1/learn`): `page.goto(...)`, assert 200-equivalent (no error page), assert a known landmark
  element is visible, and assert **no console/page errors**.
- Assert the nav bar is present and a couple of nav links navigate correctly.

### STEP 3 — Dataset upload wiring (`test_dataset_upload_wiring.py`)
- Go to `/v1/datasets-page`. Use Playwright's `set_input_files` to upload a tiny `.txt`.
- Submit via the page's real upload control. Assert the new dataset **appears in the on-page
  list/table** (Playwright auto-waits). This proves the form is wired to `POST /v1/datasets/upload`
  and the list refreshes.

### STEP 4 — Training + SSE wiring (`test_training_sse_wiring.py`)  *(the highest-value test)*
- Precondition: a dataset exists (create via the UI in this test, or seed via an API call using
  the httpx client against `:8080` for speed — seeding via API is acceptable here since the
  *subject under test* is the training UI + SSE, not the upload form).
- On `/v1/training-page`: select the dataset, set a tiny config (`n_embd=16, n_layer=1,
  num_steps≈20`, `local-stdlib` backend), click **Start**.
- Assert the **live loss chart receives ≥1 data point** — detect via a DOM/canvas signal the
  frontend exposes (e.g. a metric counter element, a rendered point count, or a visible
  "step N / loss X" readout). **Identify the exact selector by reading
  `anvil/api/templates/archetypes/training.html` + `chart.js` + `sse.js`** — do NOT guess.
- Assert the run reaches a visible terminal/"completed" state in the UI.

### STEP 5 — Experiment listing wiring (`test_experiment_listing_wiring.py`)
- After a completed run, go to `/v1/experiments-page` and assert the run appears in the list with
  a final loss value rendered.

### STEP 6 — Inference wiring (`test_inference_wiring.py`)
- Precondition: a registered model exists (seed via API for speed).
- On `/v1/inference-page`: select the model, type a prompt, submit, assert **non-empty generated
  text is rendered** in the output area.

---

## Acceptance Criteria (Definition of Done)

- [ ] `make test-browser` runs the full loop (compose up → chromium tests → teardown) green
      locally.
- [ ] `make test` is **unchanged** — it does NOT collect `tests/browser` (verify via
      `--ignore`), and coverage gate (`fail_under = 23`) is unaffected.
- [ ] The SSE wiring test (STEP 4) reliably observes a live chart update — the single most
      important assertion in this suite.
- [ ] All smoke tests pass across **3 consecutive `make test-browser` runs** (no flakes); use
      Playwright auto-waiting / `expect` polling, never fixed `sleep`.
- [ ] ADR committed under `docs/vault/Decisions/` and linked from the session log.
- [ ] A new **Linux-only CI job** added to `.github/workflows/ci.yml` (separate from `test`):
      checkout → setup uv → `make setup` → `uv run playwright install --with-deps chromium` →
      `make test-browser`. Wire it into the `gate-status` summarizer's `needs`/loop. This job is
      **BLOCKING** (decided): it is a required gate — NO `continue-on-error`, and it MUST be added
      to the `gate-status` job's `needs:` list and its gate loop so a failure fails the workflow
      (and, via branch protection, blocks merge to `main`). Gate it behind the same
      `if: needs.bump-scope-guard.outputs.scope != 'version-only'` guard as the other heavy gates.
      Because it is blocking, prioritize **zero-flake** stability (auto-waiting, generous timeouts,
      tiny model) — a flaky blocking gate will stall all merges.
- [ ] `make lint` / `make typecheck` pass (tests are exempt from docstring rules via existing
      per-file ignores; confirm `tests/browser` is covered by the `tests/**` ignore globs).

---

## MUST DO

1. Keep it to ≈4–6 smoke tests focused on **wiring**, not exhaustive UI coverage.
2. Reuse the existing compose lifecycle pattern from `tests/system` — do not invent a new server
   bootstrap.
3. Derive ALL selectors by reading the actual templates/JS (`training.html`, `datasets.html`,
   `archetypes/playground.html`, `chart.js`, `sse.js`) — never guess element ids/classes.
4. Use Playwright auto-waiting (`expect(locator).to_be_visible()`, `to_have_text`) — zero fixed
   sleeps.
5. Use the tiny `local-stdlib` model config so the training test finishes in seconds.
6. Write the ADR BEFORE the test code (it's a gating decision per AGENTS.md Principle 4).

## MUST NOT DO

1. Do NOT add Playwright to runtime `dependencies` — dev extra only.
2. Do NOT put browser tests in the `make test` coverage loop or let them affect `fail_under`.
3. Do NOT add visual/pixel snapshot regression for the 27 themes — out of scope, high-maintenance.
4. Do NOT duplicate functional/backend assertions already owned by the httpx e2e suite (don't
   re-verify loss correctness, export validity, etc. — only verify the UI *surfaces* them).
5. Do NOT use fixed `time.sleep()` for SSE/async waits — rely on auto-waiting/polling.
6. Do NOT make the new CI job part of the existing `test` job (keep it isolated + Linux-only).

---

## Vault Enrichment (required per AGENTS.md)

- ADR under `docs/vault/Decisions/ADR-0NN-playwright-ui-smoke-harness.md` (the gating decision).
- Session log under `docs/vault/Sessions/`.
- A Reference/Discovery note documenting the SSE-chart-update assertion technique (how the
  frontend exposes live-point state to a test) — this is reusable and non-obvious.
- Controlled-vocabulary tags from `docs/vault/_meta/tags.md`; run `make vault-audit` → 0 errors.

## Dependencies / Sequencing

- **Independent of `functional-api-e2e-suite.md`** — can run in parallel. (Optionally, the API
  suite's tiny-corpus/seed helpers could be reused for fast UI-test seeding, but do not create a
  hard coupling.)
- Within this plan: STEP 1 (ADR + scaffold) gates STEPS 2–6.

## Out of Scope

- Cross-browser matrix (firefox/webkit), mobile viewports.
- Visual regression / theme gallery screenshots.
- Authentication / SaaS-mode UI flows.
- Accessibility audits (a worthwhile separate plan).
