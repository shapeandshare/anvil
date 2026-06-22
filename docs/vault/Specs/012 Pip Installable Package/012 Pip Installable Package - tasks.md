---
title: 012 Pip Installable Package - tasks
type: tasks
tags:
  - type/spec
spec-refs:
  - docs/vault/Specs/012 Pip Installable Package/
related:
  - '[[012 Pip Installable Package]]'
created: ~
updated: ~
---
# Tasks: Pip-Installable Package

**Input**: Design documents from `/docs/vault/Specs/012 Pip Installable Package/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: INCLUDED — the project Constitution (Article IV) mandates TDD with 100% unit coverage, and the feature's acceptance gate (FR-012/US4) is a system-test suite. Unit tests are written before the Python refactors; system tests are User Story 4.

**Organization**: Tasks are grouped by user story. NOTE: unlike typical independent stories, the four P1 stories here form a **sequential delivery pipeline** (build artifact → install clean → bring online → system-test). Each builds on the prior. The shared packaging refactor that makes the wheel self-contained is in Phase 2 (Foundational) because every story depends on it.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1–US4 (maps to spec.md user stories)
- File paths are repo-root-relative.

## Path Conventions

Single project. Package code under `anvil/`; tests under `tests/`; build/ops files at repo root.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Scaffolding and tooling needed before refactor work.

- [ ] T001 Create package resource directories `anvil/_resources/` and `anvil/data/` (placeholder `.gitkeep` removed once content moved) so relocated resources have a home per plan.md Project Structure.
- [ ] T002 [P] Add a `build` target to `shared/python.mk` (or `Makefile`) that runs `python -m build --wheel --outdir dist .` (allow `uv build` fallback); ensure `make clean` already removes `dist/` (it does).
- [ ] T003 [P] Scaffold `tests/system/` with an empty `tests/system/__init__.py`-free dir (implicit namespace per Constitution Art. VI) and a `tests/system/conftest.py` placeholder exposing a `base_url` fixture (`http://localhost:8080`).
- [ ] T004 [P] Add `pytest` system marker config note in `pyproject.toml` `[tool.pytest.ini_options]` so `tests/system` can be excluded from the coverage-gated `make test` run (system tests run via `make test-system`, not under `--cov`).

**Checkpoint**: Directories + build/test scaffolding exist.

---

## Phase 2: Foundational (Blocking Prerequisites — the packaging refactor)

**Purpose**: Make the package self-contained. This is the root-cause fix that EVERY user story depends on (the wheel cannot bundle or resolve resources without it). Follows TDD: failing unit tests first, then relocation + resolution code.

**⚠️ CRITICAL**: No user story can be validated until this phase is complete.

### Tests first (must FAIL before implementation)

- [ ] T005 [P] Write failing unit test `tests/unit/db/test_migration_paths.py` asserting `MigrationService` resolves `alembic.ini` and `script_location` from the installed package via `importlib.resources` (not repo root / not CWD), and that the resolved migrations dir contains the version files incl. the merge head.
- [ ] T006 [P] Write failing unit test `tests/unit/services/test_demo_bootstrap_paths.py` asserting `demo_bootstrap` resolves the demo directory from the installed package (`importlib.resources.files("anvil")/"data"/"demo"`), independent of CWD.

### Relocate resources into the package

- [ ] T007 Move Alembic config into the package: `git mv alembic.ini anvil/_resources/alembic.ini`.
- [ ] T008 Move migrations into the package: `git mv migrations anvil/_resources/migrations` (keeps `env.py`, `script.py.mako`, `scripts/`, `versions/*`). Do NOT add `__init__.py` (Constitution Art. VI; research Decision 2).
- [ ] T009 Move demo/seed data into the package: `git mv data/demo anvil/data/demo`.

### Fix runtime path resolution (make tests T005/T006 pass)

- [ ] T010 Edit `anvil/db/migration.py`: replace `ALEMBIC_INI = Path(__file__).resolve().parent.parent.parent / "alembic.ini"` with `importlib.resources`-based resolution of `anvil/_resources/alembic.ini`; in `_build_config`, override `script_location` to the absolute path of `anvil/_resources/migrations` (research Decision 2). Use `importlib.resources.as_file` for zip-safe access.
- [ ] T011 Edit `anvil/services/demo_bootstrap.py`: replace module-level `DEMO_DIR = Path("data/demo")` with a lazily-resolved package-relative path via `importlib.resources` (research Decision 3); keep directory-walking logic intact and ensure it remains monkeypatch-friendly for tests.
- [ ] T012 Verify `anvil/_resources/migrations/env.py` still imports `from anvil.db.base import Base` and that `fileConfig(config.config_file_name)` resolves with the bundled `alembic.ini` (no code change expected; confirm + adjust if path assumptions break).

### Packaging declaration & cleanup

- [ ] T013 Edit `pyproject.toml`: add `[tool.setuptools.package-data]` for `anvil` covering `_resources/alembic.ini`, `_resources/migrations/*.py|*.mako`, `_resources/migrations/scripts/*.py`, `_resources/migrations/versions/*.py`, `data/demo/**/*.txt|*.md`, `api/static/**/*`, `api/templates/**/*` (contracts/packaging.md).
- [ ] T014 Edit `pyproject.toml` `[project.scripts]`: REMOVE the phantom `anvil-migrate-registry = "anvil.cli:migrate_registry"` line (Decision 8, contracts/cli.md).
- [ ] T015 Edit `pyproject.toml`: update `[tool.ruff] per-file-ignores` key `"migrations/**"` → `"anvil/_resources/migrations/**"` and `[tool.coverage.run] omit` `"migrations/*"` → `"anvil/_resources/migrations/*"` so paths track the relocation.
- [ ] T016 Update `.dockerignore`: remove the now-obsolete `!data/demo/` negation and any `migrations/`/`alembic.ini` assumptions (resources now live inside `anvil/`); keep excluding `data/*` runtime artifacts, `logs/`, `mlruns/`, `.git/`.
- [ ] T017 Sweep for stragglers: grep the repo (excluding `specs/`) for remaining CWD-relative references to `"data/demo"`, `script_location = migrations`, or repo-root `alembic.ini`, and fix any in `Makefile`/`shared/*.mk`/scripts/tests (e.g., `make setup` bootstrap, existing tests asserting old paths).
- [ ] T018 Update any existing unit/e2e tests that assumed repo-root `migrations/`, `alembic.ini`, or `data/demo/` locations so `make test` stays green at 100% coverage.

**Checkpoint**: T005/T006 pass; `make test` green; resources live inside `anvil/`; phantom entry point gone. The package is now self-contained at the source level.

---

## Phase 3: User Story 1 — Build a self-contained installable artifact (Priority: P1) 🎯 MVP

**Goal**: A single `make build` produces one wheel that bundles all code + non-code resources and declares all base deps.

**Independent Test**: Run the build, inspect the `.whl`, confirm resources + dependency metadata present — no source checkout needed afterward.

- [ ] T019 [P] [US1] Write packaging assertion test `tests/system/test_wheel_contents.py` — **artifact-inspection only**: it opens the built `.whl` with `zipfile` and inspects `dist-info/METADATA`; it does NOT import or exercise `anvil` source, so it carries no unit-coverage obligation and correctly lives under the coverage-excluded `tests/system/` (see T004). Build/locate `dist/anvil-*.whl`, assert presence of `anvil/_resources/alembic.ini`, all `anvil/_resources/migrations/versions/*.py` (incl. `12a4027155f0_merge_*`), `anvil/data/demo/**`, `anvil/api/static/**`, `anvil/api/templates/**`; assert `dist-info/METADATA` lists base deps and `Requires-Python: >=3.11`; assert torch NOT a base requirement (contracts/packaging.md PKG-2..PKG-5).
- [ ] T020 [US1] Run `make build`; produce `dist/anvil-<version>.whl` with no errors (FR-001, SC-001); fix packaging config until T019 passes.
- [ ] T021 [US1] Validate a clean `pip install dist/anvil-*.whl` in a throwaway venv: confirm install succeeds, `python -c "import anvil; print(anvil.__version__)"` works, and `pip list | grep -i torch` is empty (FR-002, FR-014, SC-002, SC-009).

**Checkpoint**: A correct, lean, self-contained wheel exists and is verified.

---

## Phase 4: User Story 2 — Install into a clean, isolated environment (Priority: P1)

**Goal**: A multi-stage Dockerfile installs the wheel into a source-free `python:3.11-slim`; console scripts work.

**Independent Test**: Build the image; confirm runtime stage has no anvil source and all console scripts are present/runnable.

**Depends on**: US1 (a wheel must exist to install).

- [ ] T022 [US2] Rewrite root `Dockerfile` as multi-stage per contracts/dockerfile.md: `builder` stage builds the wheel (`python -m build --wheel`); `runtime` stage (`python:3.11-slim`, non-root user, `WORKDIR /workspace`) `COPY --from=builder /dist/*.whl` and `pip install` the wheel ONLY (no source COPY); `EXPOSE 8080 5001`; `CMD ["anvil"]`.
- [ ] T023 [US2] Build the image (`docker build -t anvil:local .`) and verify the runtime stage contains the installed package but NO source tree (`docker run --rm anvil:local sh -c 'ls /workspace && ! test -d /app/anvil'` or equivalent), and that `anvil`, `anvil-db`, `anvil-corpus`, `anvil-bootstrap-datasets`, `anvil-train`, `anvil-stop` are all on PATH (DOCK-1, FR-005, FR-007).
- [ ] T024 [P] [US2] Verify fail-fast: building/installing against a Python <3.11 base produces a clear `requires-python` error (document the check; DOCK-3, FR-006).

**Checkpoint**: The wheel installs cleanly and runs in an isolated, source-free container.

---

## Phase 5: User Story 3 — Bring the installed package online locally (Priority: P1)

**Goal**: `docker compose up` starts the installed anvil (in-process MLflow), reachable locally, with first-run auto-init.

**Independent Test**: `docker compose up -d --build --wait` reports healthy; `http://localhost:8080/` serves a page; DB + demo bootstrap happen automatically on first run.

**Depends on**: US2 (image must build).

- [ ] T025 [US3] Create root `compose.yaml` per contracts/compose.md: single `anvil` service built from the Dockerfile `runtime` target, ports `8080:8080` + `5001:5001`, a named volume `anvil-workspace` mounted at `/workspace`, `working_dir: /workspace`, and a `healthcheck` polling `/v1/health` via Python stdlib (no `version:` key).
- [ ] T026 [P] [US3] Add Makefile targets: `compose-up` (`docker compose up -d --build --wait`), `compose-down` (`docker compose down`), and `compose-reset` (`docker compose down -v`).
- [ ] T027 [US3] Verify online behavior: `make compose-up` → service healthy; `GET /v1/health` returns `status: healthy`; first launch auto-creates+migrates the DB (`anvil-db current` ≠ `<base>`) and auto-bootstraps demo content (CMP-1..CMP-4, FR-005, FR-010, FR-003a, SC-004); confirm state persists across `docker compose restart` and a fresh `down -v`+`up` re-runs first-run init.
- [ ] T027a [US3] Verify the non-writable-workspace error path (FR-011, edge case "Read-only / non-writable runtime workspace"): run the container with the workspace mounted read-only (e.g., `docker run --read-only` or a `:ro` volume) and confirm anvil surfaces a **clear, actionable error** (cannot create `data/`/`logs/`/`mlruns/`) rather than an obscure stack trace or silent hang. If current behavior is unclear, add a minimal guarded check + message at startup in the appropriate service/config layer (with a unit test if code is added).
- [ ] T027b [US3] Verify the port-in-use message (FR edge case "Port already in use"): start the stack, then attempt a second bind on 8080/5001 and confirm the failure message is clear and points to changing `ANVIL_PORT` (existing `anvil.cli` behavior — document/assert, no new code expected).

**Checkpoint**: The installed package runs as a usable, reachable application in a reproducible local stack, with clear errors on workspace/port failure modes.

---

## Phase 6: User Story 4 — Validate the running instance with system tests (Priority: P1) 🎯 Acceptance Gate

**Goal**: A focused pytest+httpx suite asserts the deployed instance is a functional end product; one pass/fail signal.

**Independent Test**: With the stack online, `make test-system` runs and returns a single pass/fail against the live container.

**Depends on**: US3 (stack must come online).

- [ ] T028 [US4] Implement `tests/system/conftest.py`: an `httpx.Client` fixture bound to `base_url`, plus a helper to run `docker compose exec -T anvil <cmd>` and capture exit code/output (for CLI assertions).
- [ ] T029 [US4] Implement HTTP assertions in `tests/system/test_installed_runtime.py` per contracts/system-tests.md ST-H1, ST-P1..ST-P8, ST-A1, ST-D1: `/v1/health` healthy + version matches `anvil.__version__`; each primary page (`/`, `/v1/training-page`, `/v1/datasets-page`, `/v1/experiments-page`, `/v1/models-page`, `/v1/inference-page`, `/v1/operations-page`, `/v1/learn`) → 200; `/v1/corpora` shows bundled demo present. For SC-006 ("100% of primary pages render with correct styling"), parse each fetched page for at least one referenced `/static/...` URL and assert it returns 200 with a non-error content-type — i.e., assert assets resolve **per page**, not just one global asset.
- [ ] T030 [US4] Implement CLI assertions in `tests/system/test_installed_runtime.py` per ST-C1..ST-C5: via `compose exec`, assert exit 0 for `anvil-db current` (non-`<base>`), `anvil-corpus list` (demo corpus), `anvil-bootstrap-datasets --dry-run`, `anvil-train --help`, and `anvil-stop` (idempotent — exit 0 even when nothing running). This covers SC-007 "100% of documented CLI tools". Do NOT invoke `anvil-migrate-registry` (removed).
- [ ] T031 [US4] Add Makefile `test-system` target: `docker compose down -v` → `docker compose up -d --build --wait` → `pytest tests/system -v` → capture status → `docker compose down -v` → exit status (SYS-1, SYS-3, FR-013, Q4/FR-011a). The mandatory `--build` guarantees the image reflects the current wheel (covers the "stale container image" edge case — rebuild always wins over cache for changed source).
- [ ] T032 [US4] Run `make test-system` end-to-end; confirm a single PASS and that each failure mode reports the broken aspect (install/page/asset/DB/CLI) distinctly (SYS-2, SC-008, SC-010).

**Checkpoint**: Build → image → online → system-tests-pass loop is green. The feature's acceptance gate is satisfied.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, governance, and final quality gates.

- [ ] T033 [P] Write an ADR in `docs/vault/Decisions/` recording the resource-relocation decision (migrations/alembic.ini/demo moved into `anvil/`, `importlib.resources` resolution, package-data) with rationale and rejected alternatives (Constitution: ADR required; plan Complexity Tracking).
- [ ] T034 [P] Update `README.md`: document the pip-install + container validation path (`make build`, `make compose-up`, `make test-system`) as a supported way to run anvil (FR-015); note `anvil-migrate-registry` removal and that `anvil-db` handles schema ops.
- [ ] T035 [P] (Optional) Add an `anvil --version` flag in `anvil/cli.py` (top-level arg parse in `serve`/a small dispatcher) reporting `anvil.__version__`; add a unit test (research Decision 9, FR-015). Skip if deemed unnecessary.
- [ ] T036 Run full quality gates: `make lint`, `make typecheck` (mypy --strict), `make test` (100% coverage) — all must pass with the relocated paths (Constitution Workflow gates).
- [ ] T037 Run `quickstart.md` end-to-end as the final acceptance walkthrough; fix any drift between docs and reality.
- [ ] T038 [P] Update `docs/vault/Sessions/` with a session log and ensure wikilinks resolve; run `make vault-audit` (0 errors) per AGENTS.md.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Depends on Setup — **BLOCKS all user stories** (the wheel cannot be self-contained without it).
- **User Stories (Phases 3–6)**: This feature's stories are a **sequential pipeline**, not independent:
  - US1 (build) depends on Foundational.
  - US2 (install) depends on US1 (needs a wheel).
  - US3 (online) depends on US2 (needs an image).
  - US4 (system tests) depends on US3 (needs a running stack).
- **Polish (Phase 7)**: Depends on US1–US4 complete.

### Within Phase 2 (Foundational)

- Tests T005, T006 written FIRST (must fail).
- Relocation T007–T009 before resolution edits T010–T012.
- T010 makes T005 pass; T011 makes T006 pass.
- Packaging/cleanup T013–T018 after relocation.

### Parallel Opportunities

- Setup: T002, T003, T004 in parallel (different files).
- Foundational: T005 ‖ T006 (different test files). T007 ‖ T008 ‖ T009 (independent `git mv`s) — but run before the edits that depend on them. T010 ‖ T011 (different source files) once moves are done.
- US1: T019 can be written in parallel with finishing Foundational (it only runs after T020 builds).
- US2: T024 (fail-fast check) ‖ T023 verification.
- US3: T026 (Makefile) ‖ T025 (compose file).
- Polish: T033, T034, T035, T038 in parallel (different files).

---

## Parallel Example: Phase 2 Foundational (TDD)

```bash
# 1. Write both failing path-resolution tests together:
Task: "tests/unit/db/test_migration_paths.py — assert importlib.resources resolution"
Task: "tests/unit/services/test_demo_bootstrap_paths.py — assert package-relative demo dir"

# 2. Relocate resources (independent moves):
Task: "git mv alembic.ini anvil/_resources/alembic.ini"
Task: "git mv migrations anvil/_resources/migrations"
Task: "git mv data/demo anvil/data/demo"

# 3. Fix resolution (different files, parallel):
Task: "Edit anvil/db/migration.py — importlib.resources for alembic.ini + script_location"
Task: "Edit anvil/services/demo_bootstrap.py — package-relative DEMO dir"
```

---

## Implementation Strategy

### MVP scope

The true MVP is the **full pipeline through US4**, because "pip installable, validated" is only proven once system tests pass against the container. However, value lands incrementally:

1. **Phase 1 + 2 (Foundational)** → package is self-contained at source level (`make test` green). Biggest risk retired.
2. **US1** → a correct, lean wheel exists and is inspected (demoable: "here is the artifact, it contains everything").
3. **US2** → wheel installs cleanly in a source-free container.
4. **US3** → it runs and is reachable locally.
5. **US4** → automated proof it's a functional end product. ← **acceptance gate / release-ready.**

### Incremental Delivery

Complete Setup + Foundational first (this is where the real engineering risk lives), then walk US1→US4 in order, validating at each checkpoint. Stop-and-validate after US1 (artifact correct) and after US4 (gate green).

### Notes

- [P] = different files, no dependencies.
- The four stories are intentionally sequential (packaging pipeline) — do not attempt to parallelize US1–US4 across people without accepting integration churn.
- TDD: T005/T006 (and T019) must fail before their implementation tasks.
- Do NOT invoke the removed `anvil-migrate-registry` anywhere.
- Commit after each task or logical group (only when the user requests commits).
- Keep `anvil/core/` untouched (Constitution Art. I).
