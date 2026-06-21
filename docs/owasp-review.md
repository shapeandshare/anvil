# OWASP Top 10 Security Review

**Living task-tracking report.** Last updated: 2026-06-21
**Target**: `/Users/joshburt/.local/share/opencode/worktree/5354809a525912e5a56a6d4a6e81ccf9f89efdf3/curious-rocket/`
**Scope**: Python/FastAPI backend (anvil/api/, anvil/services/, anvil/db/, anvil/supervisor/), Jinja2 templates, static JS/CSS, Dockerfile, CI/CD workflows, CLI, config
**Reviewer**: Sisyphus (agent)

---

## Scan History

_A chronological log of every scan run. Newest first._

| Scan Date | New Findings | Resolved | Regressed | Total Open | Coverage |
|-----------|-------------|----------|-----------|------------|----------|
| 2026-06-21 | +36 | 0 | 0 | 36 | ~22,000 lines across 200+ files |

---

## Progress Summary

| Metric | Value |
|--------|-------|
| Total findings (all time) | **36** |
| Currently open | **35** |
| In progress | **0** |
| Fixed / resolved | **0** |
| Wontfix / False positive | **1** |
| Resolved rate | **0%** |

### Open Findings by Severity

| Severity | Count |
|----------|-------|
| CRITICAL | 3 |
| HIGH | 12 |
| MEDIUM | 12 |
| LOW | 7 |
| INFO | 1 |

### Trend Since Last Review

- New findings added: +36
- Findings resolved: 0
- Findings regressed: 0

> ⚠️ **Top 3 Risks**:
> 1. **No authentication on any endpoint** (A07-001) — ALL API endpoints, including service management (restart, stop, kill-port), are accessible to anyone who can reach the server. Server binds to `0.0.0.0` by design (LAN access).
> 2. **MLflow `--allowed-hosts "*"`** (A05-001) — MLflow tracking server accepts requests from any host. In network-accessible deployments, this enables cross-origin attacks against the tracking server.
> 3. **18+ endpoints accept raw `dict` bodies without typed validation** (A04-001) — Training start, inference, corpus creation, and more accept unstructured JSON with no Pydantic schema validation.

---

## Flat Finding Register (All Categories)

| ID | Cat | Sev | Status | File:Line | Title | First Seen | Last Confirmed | Resolved |
|----|-----|-----|--------|-----------|-------|------------|----------------|----------|
| A01-001 | A01 | CRITICAL | open | `anvil/api/v1/health_ops.py:203` | No auth on POST /services/restart-all | 2026-06-21 | 2026-06-21 | — |
| A01-002 | A01 | CRITICAL | open | `anvil/api/v1/health_ops.py:252-364` | 5 service-management endpoints with no auth (start/stop/restart/kill-port) | 2026-06-21 | 2026-06-21 | — |
| A01-003 | A01 | HIGH | open | `anvil/api/v1/inference.py:53-343` | 9 model inference endpoints with no auth (loads models, exposes weights) | 2026-06-21 | 2026-06-21 | — |
| A01-004 | A01 | HIGH | open | `anvil/api/v1/datasets.py:144-1152` | IDOR on ALL dataset endpoints (no ownership checks) | 2026-06-21 | 2026-06-21 | — |
| A01-005 | A01 | HIGH | open | `anvil/api/v1/training.py:645` | No ownership check on GET /training/stream/{run_id} (SSE stream) | 2026-06-21 | 2026-06-21 | — |
| A01-006 | A01 | MEDIUM | open | `anvil/api/v1/corpora.py:656` | Path traversal risk in corpus file reads | 2026-06-21 | 2026-06-21 | — |
| A01-007 | A01 | MEDIUM | open | `anvil/api/app.py:161-198` | No CORS middleware configured (server binds to 0.0.0.0) | 2026-06-21 | 2026-06-21 | — |
| A02-001 | A02 | INFO | wontfix | `anvil/core/engine.py:448` | `random.choices()` for LLM token sampling (non-security context — appropriate) | 2026-06-21 | 2026-06-21 | — |
| A03-001 | A03 | LOW | open | `anvil/services/content/local_versioned_content_store.py:214` | User-controlled `path` in staging area file construction | 2026-06-21 | 2026-06-21 | — |
| A03-002 | A03 | LOW | open | `anvil/storage/local.py:55` | No path containment check after `Path.resolve()` | 2026-06-21 | 2026-06-21 | — |
| A04-001 | A04 | CRITICAL | open | `anvil/api/v1/training.py:47` | POST /training/start accepts raw `dict` config (no validation) | 2026-06-21 | 2026-06-21 | — |
| A04-002 | A04 | HIGH | open | Multiple v1/ route files | 18+ endpoints accept `body: dict` instead of typed Pydantic models | 2026-06-21 | 2026-06-21 | — |
| A04-003 | A04 | HIGH | open | `anvil/api/v1/schemas.py:28-268` | Pydantic models missing `max_length`, `pattern`, and range constraints on string/number fields | 2026-06-21 | 2026-06-21 | — |
| A04-004 | A04 | HIGH | open | `anvil/api/app.py:161-165` | No rate limiting middleware configured | 2026-06-21 | 2026-06-21 | — |
| A04-005 | A04 | MEDIUM | open | `anvil/api/app.py:161-198` | No security headers (CSP, HSTS, X-Frame-Options, X-Content-Type-Options) | 2026-06-21 | 2026-06-21 | — |
| A04-006 | A04 | HIGH | open | `anvil/api/v1/datasets.py:260` | No file size limit on POST /datasets/upload | 2026-06-21 | 2026-06-21 | — |
| A04-007 | A04 | HIGH | open | `anvil/api/v1/content.py:420` | No file size limit on POST /content/sessions/{id}/stage | 2026-06-21 | 2026-06-21 | — |
| A04-008 | A04 | HIGH | open | `anvil/api/v1/datasets.py:1082` | User-controlled regex without ReDoS protection in regex_replace | 2026-06-21 | 2026-06-21 | — |
| A04-009 | A04 | MEDIUM | open | `anvil/api/v1/content.py:1085-1094` | TOCTOU race condition in lock acquisition | 2026-06-21 | 2026-06-21 | — |
| A04-010 | A04 | MEDIUM | open | `anvil/api/v1/training.py:46` | Training start has no idempotency key | 2026-06-21 | 2026-06-21 | — |
| A05-001 | A05 | HIGH | open | `anvil/supervisor/services.py:142-143` | MLflow `--allowed-hosts "*"` — accepts requests from any host | 2026-06-21 | 2026-06-21 | — |
| A05-002 | A05 | MEDIUM | open | `anvil/api/v1/health_ops.py:86` | Version disclosure in /v1/health response | 2026-06-21 | 2026-06-21 | — |
| A05-003 | A05 | MEDIUM | open | `anvil/api/v1/corpora.py:137` (×9 files) | `str(exc)` in HTTPException details leaks internal information | 2026-06-21 | 2026-06-21 | — |
| A05-004 | A05 | MEDIUM | open | `Dockerfile:11,30` | Python base image not digest-pinned | 2026-06-21 | 2026-06-21 | — |
| A05-005 | A05 | LOW | open | `anvil/api/app.py:198` | StaticFiles mounted without explicit `html=False` | 2026-06-21 | 2026-06-21 | — |
| A06-001 | A06 | MEDIUM | open | `.github/workflows/ci.yml:125` | SonarCloud action pinned to `@master` (floating tag) | 2026-06-21 | 2026-06-21 | — |
| A06-002 | A06 | LOW | open | `pyproject.toml:54` | `torch>=2.0` — no upper bound on optional GPU dep | 2026-06-21 | 2026-06-21 | — |
| A07-001 | A07 | CRITICAL | open | `anvil/` entire API | **No authentication on ANY endpoint** — zero auth middleware, no users model | 2026-06-21 | 2026-06-21 | — |
| A07-002 | A07 | HIGH | open | `anvil/services/content/authz.py:39-60` | AuthzContext is a no-op stub (reserved for future SaaS) | 2026-06-21 | 2026-06-21 | — |
| A08-001 | A08 | MEDIUM | open | `.github/workflows/release.yml:125` | CI/CD uses SonarSource action from `@master` (floating tag, supply chain risk) | 2026-06-21 | 2026-06-21 | — |
| A09-001 | A09 | MEDIUM | open | `anvil/cli.py:162-166` | `logging.basicConfig(level=logging.INFO)` set only in CLI — not in API lifespan | 2026-06-21 | 2026-06-21 | — |
| A09-002 | A09 | MEDIUM | open | `anvil/api/app.py:77` (×5 locations) | Silent `except: pass` on startup failures (license seeding, demo bootstrap) | 2026-06-21 | 2026-06-21 | — |
| A09-003 | A09 | LOW | open | `anvil/cli.py:403` | `print()` used in CLI training path (acceptable for CLI tool) | 2026-06-21 | 2026-06-21 | — |
| A09-004 | A09 | LOW | open | `anvil/services/inference/demo_model_provider.py:268` | `print()` in warm-up path | 2026-06-21 | 2026-06-21 | — |
| A10-001 | A10 | INFO | open | `anvil/config.py:155` | MLflow URI is user-configurable via env var; no host allowlist for outbound tracking | 2026-06-21 | 2026-06-21 | — |

---

## Detailed Finding Register

### A01 — Broken Access Control

| ID | Severity | Status | File | Title | First Seen | Last Confirmed | Resolved |
|----|----------|--------|------|-------|------------|----------------|----------|
| A01-001 | CRITICAL | open | `anvil/api/v1/health_ops.py:203` | No auth on POST /services/restart-all | 2026-06-21 | 2026-06-21 | — |
| A01-002 | CRITICAL | open | `anvil/api/v1/health_ops.py:252-364` | 5 service-management endpoints with no auth | 2026-06-21 | 2026-06-21 | — |
| A01-003 | HIGH | open | `anvil/api/v1/inference.py:53-343` | 9 model inference endpoints with no auth | 2026-06-21 | 2026-06-21 | — |
| A01-004 | HIGH | open | `anvil/api/v1/datasets.py:144-1152` | IDOR on ALL dataset endpoints | 2026-06-21 | 2026-06-21 | — |
| A01-005 | HIGH | open | `anvil/api/v1/training.py:645` | No ownership check on SSE training stream | 2026-06-21 | 2026-06-21 | — |
| A01-006 | MEDIUM | open | `anvil/api/v1/corpora.py:656` | Path traversal risk in corpus file reads | 2026-06-21 | 2026-06-21 | — |
| A01-007 | MEDIUM | open | `anvil/api/app.py:161-198` | No CORS middleware | 2026-06-21 | 2026-06-21 | — |

#### A01-001: No auth on POST /v1/services/restart-all
- **Severity**: CRITICAL
- **Status**: open
- **File**: `anvil/api/v1/health_ops.py:203-L227`
- **First seen**: 2026-06-21
- **Last confirmed**: 2026-06-21
- **Pattern**:
  ```python
  @router.post("/services/restart-all")
  async def restart_all_services(request: Request):
      mlflow = getattr(request.app.state, "mlflow", None)
      if mlflow is not None:
          if mlflow.is_running:
              mlflow.stop()
          mlflow.start()
  ```
- **Risk**: Unauthenticated restart of MLflow tracking server. Attacker can disrupt experiment tracking.
- **Recommendation**: Restrict to localhost in production or add authentication middleware.

#### A01-002: 5 service-management endpoints with no auth
- **Severity**: CRITICAL
- **Status**: open
- **File**: `anvil/api/v1/health_ops.py:252-364`
- **First seen**: 2026-06-21
- **Last confirmed**: 2026-06-21
- **Endpoints**: `POST /services/{name}/start`, `POST /services/{name}/stop`, `POST /services/{name}/restart`, `POST /services/{name}/kill-port`, `POST /services/logs/{name}/clear`
- **Risk**: Complete control over service lifecycle — stop/start MLflow, kill processes via SIGKILL.
- **Recommendation**: Add authentication to all service management endpoints.

#### A01-003: 9 model inference endpoints with no auth
- **Severity**: HIGH
- **Status**: open
- **File**: `anvil/api/v1/inference.py:53-343`
- **First seen**: 2026-06-21
- **Last confirmed**: 2026-06-21
- **Endpoints**: tokenize, embeddings, attention, sampling-distribution, forward-graph, backward-graph, autograd-example, loss-breakdown, model-params
- **Risk**: Unauthenticated model inference. `model-params` exposes model weights and architecture.
- **Recommendation**: Add `Depends(get_workbench)` at minimum to inference routes.

#### A01-004: IDOR on ALL dataset endpoints
- **Severity**: HIGH
- **Status**: open
- **File**: `anvil/api/v1/datasets.py:144-1152`
- **First seen**: 2026-06-21
- **Last confirmed**: 2026-06-21
- **Pattern**:
  ```python
  @router.get("/datasets/{id}")
  async def get_dataset(id: int, workbench: AnvilWorkbench = Depends(get_workbench)):
      d = await workbench.datasets.get_dataset(id)  # No owner filter
  ```
- **Risk**: Any user can read/update/delete ANY dataset by ID. No ownership scoping.
- **Recommendation**: Add ownership-scoped repository methods.

#### A01-005: No ownership check on SSE training stream
- **Severity**: HIGH
- **Status**: open
- **File**: `anvil/api/v1/training.py:645-698`
- **First seen**: 2026-06-21
- **Last confirmed**: 2026-06-21
- **Pattern**: `GET /training/stream/{run_id}` streams any training run's SSE events by run ID.
- **Risk**: An attacker can subscribe to any training run's progress stream.
- **Recommendation**: Add ownership verification before returning the SSE queue.

#### A01-006: Path traversal risk in corpus file reads
- **Severity**: MEDIUM
- **Status**: open
- **File**: `anvil/api/v1/corpora.py:656`
- **First seen**: 2026-06-21
- **Last confirmed**: 2026-06-21
- **Pattern**:
  ```python
  full_path = corpus.root_path.rstrip("/") + "/" + file_path.lstrip("/")
  ```
- **Risk**: If corpus root_path points to a directory with symlinks outside expected dirs, combined with user-controlled `file_path`, path traversal is possible.
- **Recommendation**: Canonicalize with `Path.resolve()` and verify result is within root.

#### A01-007: No CORS middleware configured
- **Severity**: MEDIUM
- **Status**: open
- **File**: `anvil/api/app.py:161-198`
- **First seen**: 2026-06-21
- **Last confirmed**: 2026-06-21
- **Pattern**: Server binds to `0.0.0.0` with no CORS middleware.
- **Risk**: Any origin can call the API from a browser on the same LAN.
- **Recommendation**: Add explicit CORS middleware with allowlist.

---

### A02 — Cryptographic Failures

| ID | Severity | Status | File | Title | First Seen | Last Confirmed | Resolved |
|----|----------|--------|------|-------|------------|----------------|----------|
| A02-001 | INFO | wontfix | `anvil/core/engine.py:448` | `random.choices()` for LLM token sampling | 2026-06-21 | 2026-06-21 | — |

#### A02-001: `random.choices()` for LLM token sampling
- **Severity**: INFO
- **Status**: wontfix — intentionally uses `random.choices()` for model inference sampling (non-security context). LLM creative output does not require cryptographic randomness. Using `secrets` module would degrade sampling performance without security benefit.
- **File**: `anvil/core/engine.py:448`
- **First seen**: 2026-06-21
- **Last confirmed**: 2026-06-21
- **Pattern**:
  ```python
  token_id = random.choices(range(vocab_size), weights=[p.data for p in probs])
  ```
- **Risk**: None — this is LLM token sampling for creative output generation, not a security context.
- **Recommendation**: Accept as-is.

**Additional A02 context**: No hardcoded secrets found. SHA-256 used appropriately for content-addressed storage and audit chains. No MD5/SHA1 for security purposes. No JWT/HMAC implemented (whole application is unauthenticated). HTTP used for localhost-only connections (MLflow sidecar). No encryption at rest — appropriate for single-user local tool.

---

### A03 — Injection

| ID | Severity | Status | File | Title | First Seen | Last Confirmed | Resolved |
|----|----------|--------|------|-------|------------|----------------|----------|
| A03-001 | LOW | open | `anvil/services/content/local_versioned_content_store.py:214` | User-controlled path in staging file construction | 2026-06-21 | 2026-06-21 | — |
| A03-002 | LOW | open | `anvil/storage/local.py:55` | No path containment check after resolve | 2026-06-21 | 2026-06-21 | — |

#### A03-001: User-controlled path in staging file construction
- **Severity**: LOW
- **Status**: open
- **File**: `anvil/services/content/local_versioned_content_store.py:214`
- **First seen**: 2026-06-21
- **Last confirmed**: 2026-06-21
- **Pattern**:
  ```python
  staging_ref_path = staging_area / path  # path is user-controlled from API
  ```
- **Risk**: Limited — `staging_key` is a UUID, and blob storage is content-addressed by hash. An attacker could write staging references outside the intended staging area but cannot read arbitrary files.
- **Recommendation**: Add containment check after resolve.

#### A03-002: No path containment check after resolve
- **Severity**: LOW
- **Status**: open
- **File**: `anvil/storage/local.py:55`
- **First seen**: 2026-06-21
- **Last confirmed**: 2026-06-21
- **Pattern**:
  ```python
  full = (self.base_path / path).resolve()  # no check: starts with base_path?
  ```
- **Risk**: Low — `path` typically comes from internal code or DB, not directly from user input at this layer.
- **Recommendation**: Add `is_relative_to` or `startswith` check.

**Additional A03 context**: No SQL injection (all queries use SQLAlchemy ORM). No command injection (all subprocess calls use list args, no `shell=True`). No SSTI (`render_template_string` not used). No `eval()`/`exec()`/unsafe deserialization (no pickle, yaml.safe_load used consistently).

---

### A04 — Insecure Design

| ID | Severity | Status | File | Title | First Seen | Last Confirmed | Resolved |
|----|----------|--------|------|-------|------------|----------------|----------|
| A04-001 | CRITICAL | open | `anvil/api/v1/training.py:46` | Raw `dict` config for training start | 2026-06-21 | 2026-06-21 | — |
| A04-002 | HIGH | open | Multiple v1/ route files | 18+ endpoints accept raw `dict` bodies | 2026-06-21 | 2026-06-21 | — |
| A04-003 | HIGH | open | `anvil/api/v1/schemas.py` | Pydantic models missing field constraints | 2026-06-21 | 2026-06-21 | — |
| A04-004 | HIGH | open | `anvil/api/app.py` | No rate limiting middleware | 2026-06-21 | 2026-06-21 | — |
| A04-005 | MEDIUM | open | `anvil/api/app.py` | No security headers (CSP, HSTS, etc.) | 2026-06-21 | 2026-06-21 | — |
| A04-006 | HIGH | open | `anvil/api/v1/datasets.py:260` | No file size limit on /datasets/upload | 2026-06-21 | 2026-06-21 | — |
| A04-007 | HIGH | open | `anvil/api/v1/content.py:420` | No file size limit on /content/stage | 2026-06-21 | 2026-06-21 | — |
| A04-008 | HIGH | open | `anvil/api/v1/datasets.py:1082` | User-controlled regex without ReDoS protection | 2026-06-21 | 2026-06-21 | — |
| A04-009 | MEDIUM | open | `anvil/api/v1/content.py:1085-1094` | TOCTOU race in lock acquisition | 2026-06-21 | 2026-06-21 | — |
| A04-010 | MEDIUM | open | `anvil/api/v1/training.py:46` | Training start lacks idempotency key | 2026-06-21 | 2026-06-21 | — |

#### A04-001: Raw `dict` config for training start
- **Severity**: CRITICAL
- **Status**: open
- **File**: `anvil/api/v1/training.py:46-47`
- **First seen**: 2026-06-21
- **Last confirmed**: 2026-06-21
- **Pattern**:
  ```python
  @router.post("/training/start")
  async def start_training(config: dict):
      n_embd = config.get("n_embd", 16)
      # ... used directly to launch compute workload
  ```
- **Risk**: No schema validation on training configuration. Client can send arbitrary values for compute backend, device, dataset_id, corpus_id, etc. Could trigger unauthorized GPU workloads.
- **Recommendation**: Define a Pydantic `TrainConfig` model with validated fields and constraints.

#### A04-008: User-controlled regex without ReDoS protection
- **Severity**: HIGH
- **Status**: open
- **File**: `anvil/api/v1/datasets.py:1082`
- **First seen**: 2026-06-21
- **Last confirmed**: 2026-06-21
- **Pattern**:
  ```python
  result = await curation_svc.regex_replace(
      body.pattern, body.replacement, body.case_sensitive
  )
  ```
  Where `body.pattern: str` has no `max_length` and is compiled directly with `re.compile(pattern, flags)`.
- **Risk**: Regex DoS via catastrophic backtracking patterns like `(a+)+$` or `([a-zA-Z]+)*$`.
- **Recommendation**: Add regex timeout via `re.compile(pattern, flags, timeout=...)` (Python 3.11+), and/or validate pattern complexity client-side.

#### A04-009: TOCTOU race condition in lock acquisition
- **Severity**: MEDIUM
- **Status**: open
- **File**: `anvil/api/v1/content.py:1085-1094`
- **First seen**: 2026-06-21
- **Last confirmed**: 2026-06-21
- **Pattern**:
  ```python
  existing = await workbench.content_locks.list_active()
  for lock in existing:
      if lock.scope == body.scope:
          raise HTTPException(status_code=409, ...)
  new_lock = await workbench.content_locks.acquire(body.scope, body.holder)
  ```
- **Risk**: Between the `list_active` check and `acquire`, another request could acquire the same lock.
- **Recommendation**: Use atomic check-and-insert at the database level.

---

### A05 — Security Misconfiguration

| ID | Severity | Status | File | Title | First Seen | Last Confirmed | Resolved |
|----|----------|--------|------|-------|------------|----------------|----------|
| A05-001 | HIGH | open | `anvil/supervisor/services.py:142-143` | MLflow `--allowed-hosts "*"` | 2026-06-21 | 2026-06-21 | — |
| A05-002 | MEDIUM | open | `anvil/api/v1/health_ops.py:86` | Version disclosure in health endpoint | 2026-06-21 | 2026-06-21 | — |
| A05-003 | MEDIUM | open | `anvil/api/v1/corpora.py:137` (×9 files) | `str(exc)` leaks internal details in HTTPException | 2026-06-21 | 2026-06-21 | — |
| A05-004 | MEDIUM | open | `Dockerfile:11,30` | Python base image not digest-pinned | 2026-06-21 | 2026-06-21 | — |
| A05-005 | LOW | open | `anvil/api/app.py:198` | StaticFiles without explicit `html=False` | 2026-06-21 | 2026-06-21 | — |

#### A05-001: MLflow `--allowed-hosts "*"`
- **Severity**: HIGH
- **Status**: open
- **File**: `anvil/supervisor/services.py:142-143`
- **First seen**: 2026-06-21
- **Last confirmed**: 2026-06-21
- **Pattern**:
  ```python
  subprocess.Popen([
      mlflow_bin, "server",
      "--host", "0.0.0.0",
      "--allowed-hosts", "*",
      ...
  ])
  ```
- **Risk**: MLflow tracking server accepts requests from any host. In network-accessible deployments, an attacker can interact with the MLflow API from arbitrary origins. MLflow's default is more restrictive — this explicitly opens it up.
- **Recommendation**: Replace `*` with explicit host values (e.g., `["localhost", "127.0.0.1"]`), or derive from `ANVIL_MLFLOW_URI`.

#### A05-003: `str(exc)` leaks internal details
- **Severity**: MEDIUM
- **Status**: open
- **File**: `anvil/api/v1/corpora.py:137` (and content.py, datasets.py)
- **First seen**: 2026-06-21
- **Last confirmed**: 2026-06-21
- **Pattern**:
  ```python
  raise HTTPException(status_code=422, detail=str(exc)) from exc
  ```
- **Risk**: `str(exc)` can include absolute filesystem paths, internal variable names, DB constraint names, third-party library error messages — all leaked to API clients.
- **Recommendation**: Replace with sanitized user-facing message. Log the original exception server-side.

---

### A06 — Vulnerable & Outdated Components

| ID | Severity | Status | File | Title | First Seen | Last Confirmed | Resolved |
|----|----------|--------|------|-------|------------|----------------|----------|
| A06-001 | MEDIUM | open | `.github/workflows/ci.yml:125` | SonarCloud action pinned to `@master` (floating tag) | 2026-06-21 | 2026-06-21 | — |
| A06-002 | LOW | open | `pyproject.toml:54` | `torch>=2.0` — no upper bound on optional GPU dep | 2026-06-21 | 2026-06-21 | — |

#### A06-001: SonarCloud action pinned to floating `@master` tag
- **Severity**: MEDIUM
- **Status**: open
- **File**: `.github/workflows/ci.yml:125`
- **First seen**: 2026-06-21
- **Last confirmed**: 2026-06-21
- **Pattern**: `uses: SonarSource/sonarcloud-github-action@master` — floating tag, not a SHA digest.
- **Risk**: `@master` tag can be force-pushed to, enabling supply chain attacks.
- **Recommendation**: Pin to a specific SHA256 digest.

#### A06-002: `torch` dependency has no upper bound
- **Severity**: LOW
- **Status**: open
- **File**: `pyproject.toml:54`
- **First seen**: 2026-06-21
- **Last confirmed**: 2026-06-21
- **Pattern**: `"torch>=2.0"` in `[project.optional-dependencies] gpu`
- **Risk**: A future torch 3.0+ could contain breaking changes. Low risk since it's an optional GPU extra.
- **Recommendation**: Add upper bound: `"torch>=2.0,<3"`.

---

### A07 — Identification & Authentication Failures

| ID | Severity | Status | File | Title | First Seen | Last Confirmed | Resolved |
|----|----------|--------|------|-------|------------|----------------|----------|
| A07-001 | CRITICAL | open | `anvil/` entire API | No authentication on ANY endpoint | 2026-06-21 | 2026-06-21 | — |
| A07-002 | HIGH | open | `anvil/services/content/authz.py:39-60` | AuthzContext is a no-op stub | 2026-06-21 | 2026-06-21 | — |

#### A07-001: No authentication on ANY endpoint
- **Severity**: CRITICAL
- **Status**: open
- **File**: `anvil/` entire API
- **First seen**: 2026-06-21
- **Last confirmed**: 2026-06-21
- **Pattern**:
  - No `HTTPBearer`, `OAuth2PasswordBearer`, `APIKeyHeader` middleware
  - No user model in `anvil/db/models/`
  - No login/register/signin routes
  - No session cookies or JWT tokens
  - `anvil/api/deps.py` only provides `get_db_session` and `get_workbench` (no auth)
  - `anvil/api/app.py` has no auth middleware
- **Risk**: **Every API endpoint is accessible to anyone who can reach the server.** The server binds to `0.0.0.0:8080` for LAN access. This includes service management (restart, stop, kill-port), training execution, dataset CRUD, model registry, and inference.
- **Recommendation**: This is an architectural decision for a local-only tool. Document as "network-level security only" or add authentication middleware. See ADR-030 for the planned SaaS auth model.

#### A07-002: AuthzContext is a no-op stub
- **Severity**: HIGH
- **Status**: open
- **File**: `anvil/services/content/authz.py:39-60`
- **First seen**: 2026-06-21
- **Last confirmed**: 2026-06-21
- **Pattern**:
  ```python
  class AuthzContext:
      """No-op in local single-user mode."""
      def require_management_action(self, ...) -> None:
          pass  # All actions permitted in local mode
  ```
- **Risk**: Reserved for future SaaS RBAC but currently a no-op. In local mode all management actions are permitted.
- **Recommendation**: Ensure SaaS deployment wraps `AuthzContext` with real RBAC checks before exposing MLflow/training endpoints.

---

### A08 — Software & Data Integrity Failures

| ID | Severity | Status | File | Title | First Seen | Last Confirmed | Resolved |
|----|----------|--------|------|-------|------------|----------------|----------|
| A08-001 | MEDIUM | open | `.github/workflows/release.yml:125` | SonarSource action uses floating `@master` tag | 2026-06-21 | 2026-06-21 | — |

#### A08-001: CI/CD uses floating action tag
- **Severity**: MEDIUM
- **Status**: open
- **File**: `.github/workflows/ci.yml:125`, `.github/workflows/release.yml:125`
- **First seen**: 2026-06-21
- **Last confirmed**: 2026-06-21
- **Pattern**: `uses: SonarSource/sonarcloud-github-action@master` — not pinned to SHA.
- **Risk**: Supply chain — a compromise of the `master` branch of that action could inject malicious code into the CI pipeline. Combined with `pull-requests: write` permissions in release.yml, a compromised action could write to repos.
- **Recommendation**: Pin to SHA256 digest: `uses: SonarSource/sonarcloud-github-action@<SHA256>`.

**Additional A08 context**: No unsafe deserialization (`pickle`, unsafe `yaml.load`) found. No open redirects (`RedirectResponse` not used in API routes). Model files use safetensors with content-addressed hashing. No unvalidated URL forwards.

---

### A09 — Security Logging & Monitoring Failures

| ID | Severity | Status | File | Title | First Seen | Last Confirmed | Resolved |
|----|----------|--------|------|-------|------------|----------------|----------|
| A09-001 | MEDIUM | open | `anvil/cli.py:162-166` | Logging configured only in CLI, not in API lifespan | 2026-06-21 | 2026-06-21 | — |
| A09-002 | MEDIUM | open | `anvil/api/app.py:77` (×5) | Silent `except: pass` on startup failures | 2026-06-21 | 2026-06-21 | — |
| A09-003 | LOW | open | `anvil/cli.py:403` | `print()` used in CLI training path | 2026-06-21 | 2026-06-21 | — |
| A09-004 | LOW | open | `anvil/services/inference/demo_model_provider.py:268` | `print()` in warm-up path | 2026-06-21 | 2026-06-21 | — |

#### A09-001: Logging configured only in CLI, not in API
- **Severity**: MEDIUM
- **Status**: open
- **File**: `anvil/cli.py:162-166`
- **First seen**: 2026-06-21
- **Last confirmed**: 2026-06-21
- **Pattern**: `logging.basicConfig(level=logging.INFO, ...)` is only called in the `serve()` CLI function, not in the FastAPI lifespan or anywhere else.
- **Risk**: When running via other entry points (e.g., uvicorn directly), logging may not be configured with the intended format and level.
- **Recommendation**: Move logging configuration to the lifespan handler in `app.py`.

#### A09-002: Silent `except: pass` on startup failures
- **Severity**: MEDIUM
- **Status**: open
- **File**: `anvil/api/app.py:77,93,126-127,147,149`
- **First seen**: 2026-06-21
- **Last confirmed**: 2026-06-21
- **Pattern**:
  ```python
  except Exception:
      pass
  ```
- **Locations**: License seeding (l.77-94), demo bootstrap (l.126-127), demo model warmup (l.147-149)
- **Risk**: Failures in these startup processes are silently swallowed. If license seeding or demo bootstrap fails, there is no indication in logs. The application starts without important data.
- **Recommendation**: Log the exception with `logger.warning()` at minimum. Only `pass` when failure is truly acceptable.

---

### A10 — SSRF (Server-Side Request Forgery)

| ID | Severity | Status | File | Title | First Seen | Last Confirmed | Resolved |
|----|----------|--------|------|-------|------------|----------------|----------|
| A10-001 | INFO | open | `anvil/config.py:155` | MLflow URI is user-configurable; no outbound host allowlist | 2026-06-21 | 2026-06-21 | — |

#### A10-001: MLflow URI is user-configurable
- **Severity**: INFO
- **Status**: open
- **File**: `anvil/config.py:155`
- **First seen**: 2026-06-21
- **Last confirmed**: 2026-06-21
- **Pattern**: `ANVIL_MLFLOW_URI` env var controls where MLflow tracking data is sent.
- **Risk**: An attacker who controls the environment (or env var) could redirect MLflow tracking data to an attacker-controlled server. This is a deliberate configuration option, not an SSRF vector from user input directly.
- **Recommendation**: Acceptable for local-only use. In SaaS deployments, restrict MLflow URI to a known allowlist.

**Additional A10 context**: No user-controlled URL fetches found. `httpx`/`aiohttp` usage is limited to tests (httpx test client) and MLflow client connections to a configurable URI. No cloud metadata endpoints accessed.

---

## Cross-Cutting Observations

1. **Local-first architecture, global-first exposure**: The application is designed as a single-user local development tool but binds to `0.0.0.0` (all interfaces) by default. The README advertises LAN access. This creates a tension between the "no auth needed" assumption and the network exposure. **If exposed to an untrusted network, every finding in this report becomes exploitable immediately.**

2. **SaaS readiness vs. local safety**: The codebase has stubs for auth (`authz.py`), RBAC role definitions (in learning.py docstrings), and cloud compute backends (`modal` extra). These patterns acknowledge that multi-user auth will eventually be needed, but local mode has no enforcement. The risk is that these stubs give a false sense of security.

3. **Hash-chained audit trail is a positive**: `anvil/services/governance/audit_service.py` implements a proper hash-chained audit trail with SHA-256 for tamper evidence. This is a strong positive for governance and integrity.

4. **Consistent use of SQLAlchemy ORM**: All database queries use the ORM with parameterized queries — no raw SQL injection vectors found. This is good practice.

5. **Content-addressed storage for integrity**: Blob storage uses SHA-256 content hashing, providing built-in integrity verification for stored content.

---

## Recommendations (Priority Order)

### Immediate (CRITICAL)
1. **Add authentication middleware** (A07-001): At minimum, add a simple API key or HTTP Basic auth for all routes. For SaaS, implement the planned Cognito/JWT auth from ADR-030.
2. **Restrict MLflow `--allowed-hosts`** (A05-001): Replace `*` with explicit allowlist (`localhost`, `127.0.0.1`). Derive from `ANVIL_MLFLOW_URI` hostname.
3. **Replace all `body: dict` with Pydantic models** (A04-001, A04-002): 18+ endpoints accept unstructured dicts. Define typed Pydantic models with field constraints.

### Short-term (HIGH)
4. **Add rate limiting** (A04-004): Add `slowapi` middleware to prevent DoS and brute force.
5. **Add input size limits** (A04-006, A04-007): Cap file upload size and JSON body size.
6. **Protect service management endpoints** (A01-002): Restrict to localhost or add auth.
7. **Add ReDoS protection** (A04-008): Add regex timeout via `re.compile(pattern, timeout=...)`.
8. **Pin CI/CD action SHAs** (A06-001, A08-001): Replace `@master` tags with SHA256 digests.
9. **Sanitize HTTPException details** (A05-003): Replace `str(exc)` with sanitized messages in corpora.py, content.py, datasets.py.

### Medium-term (MEDIUM)
10. **Pin Docker base image** (A05-004): Use SHA256 digest for `FROM python:3.11-slim`.
11. **Add security headers** (A04-005): Add CSP, HSTS, X-Frame-Options via middleware.
12. **Add idempotency keys** (A04-010): Prevent duplicate training run creation.
13. **Move logging config to lifespan** (A09-001): Ensure logging is configured in all entry points.
14. **Log startup failures** (A09-002): Replace silent `pass` with `logger.warning()`.
15. **Add file upload size limits** (A04-006): Cap at reasonable size.
16. **Fix lock acquisition race condition** (A04-009): Use atomic DB-level check-and-insert.

---

_Generated by `/owasp-review` command | Last full scan: 2026-06-21_
