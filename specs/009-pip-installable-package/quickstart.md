# Quickstart: Pip-Installable Package

**Feature**: `009-pip-installable-package` | **Date**: 2026-06-18

The full validation loop a maintainer runs locally to prove anvil is a functional, pip-installable end product. All commands run from the repo root. Requires Docker + Docker Compose.

## TL;DR

```bash
make build          # build the wheel (anvil-<version>.whl in dist/)
make test-system    # build image from wheel, bring up via compose, run system tests, tear down
```

`make test-system` returns a single pass/fail. Green = the installed package is a functional end product.

---

## 1. Build the wheel

```bash
make build
# equivalently: python -m build --wheel --outdir dist .   (or: uv build --wheel)
ls dist/            # → anvil-0.1.0-py3-none-any.whl
```

Verify it bundles the relocated resources:

```bash
python -m zipfile -l dist/anvil-*.whl | grep -E "_resources/(alembic.ini|migrations/versions)|data/demo|api/static|api/templates"
```

Expect: `alembic.ini`, every migration version (incl. the merge head), demo `.txt` files, static assets, templates.

## 2. Verify a clean install (optional, fast feedback)

```bash
python -m venv /tmp/anvil-clean && /tmp/anvil-clean/bin/pip install dist/anvil-*.whl
/tmp/anvil-clean/bin/pip show anvil
# torch must NOT be present:
/tmp/anvil-clean/bin/pip list | grep -i torch || echo "OK: torch not installed (lean base)"
/tmp/anvil-clean/bin/python -c "import anvil; print(anvil.__version__)"
```

## 3. Bring it online in a container (genuine pip install, no source)

```bash
docker compose up -d --build --wait
# wait blocks until /v1/health is healthy
open http://localhost:8080        # macOS; or visit in any browser
```

What happens on first launch (inside the container, from the installed package):
- DB auto-created and migrated to HEAD (`anvil db upgrade heads`).
- In-process MLflow starts on 5001.
- Bundled demo content auto-bootstraps into the DB.

## 4. Run the system tests (acceptance gate)

```bash
make test-system
```

This resets the named volume (`docker compose down -v`), brings the stack up fresh (`up --build --wait`), runs `pytest tests/system`, then tears down. Checks:
- `GET /v1/health` → healthy, version matches.
- Every primary page returns 200 and its assets resolve.
- A `/static/...` asset is served.
- Demo content is present (`/v1/corpora`).
- `anvil-db current`, `anvil-corpus list`, `anvil-bootstrap-datasets --dry-run` exit 0 inside the container.

## 5. Tear down

```bash
docker compose down -v   # stop + remove the workspace volume (fresh next time)
```

---

## Expected results matrix

| Step | Success signal | Spec ref |
|------|----------------|----------|
| Build | one `.whl`, no errors | FR-001, SC-001 |
| Wheel inspect | resources present | FR-003, SC-003 |
| Clean install | installs; no torch | FR-002, FR-014, SC-002, SC-009 |
| Compose up | healthy; workbench reachable | US3, SC-004 |
| First launch | DB migrated + demo bootstrapped automatically | FR-005, FR-010, FR-003a, SC-005 |
| System tests | single PASS | US4, FR-012/013, SC-008, SC-010 |

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| Wheel missing migrations/demo | `package-data` glob wrong | Fix `[tool.setuptools.package-data]` (see contracts/packaging.md) |
| `alembic.ini` not found at runtime | path still CWD-relative | Ensure `migration.py` resolves via `importlib.resources` (research Decision 2) |
| Demo content empty after first run | `DEMO_DIR` still CWD-relative | Ensure `demo_bootstrap.py` resolves via `importlib.resources` (Decision 3) |
| `Address already in use` | 8080/5001 taken | stop other anvil/MLflow, or change published ports in `compose.yaml` |
| Install fails on Python <3.11 | expected | use Python ≥3.11 (FR-006 fail-fast) |
| `anvil-migrate-registry: not found` | expected — it was removed (phantom) | use `anvil-db` for schema ops |
