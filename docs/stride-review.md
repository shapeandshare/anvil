# STRIDE Threat Model Review

**Living task-tracking report.** Last updated: 2026-10-04
**Scope**: both — full project, local mode and SaaS mode (future)
**DFD reference**: `docs/vault/Reference/SaaSSecurityAndFlowDiagrams.md`
**OWASP cross-reference**: `docs/owasp-review.md`
**Reviewer**: Sisyphus (agent)

---

## Scan History

_A chronological log of every scan run. Newest first._

| Scan Date | New Threats | Resolved | Regressed | Total Open | Scope |
|-----------|-------------|----------|-----------|------------|-------|
| 2026-10-04 | +28 | 0 | 0 | 28 | both (local + SaaS) — full project |

_This section grows with each scan — never prune rows._

---

## Progress Summary

| Metric | Value |
|--------|-------|
| Total threats (all time) | **28** |
| Currently open | **28** |
| In progress | **0** |
| Fixed / resolved | **0** |
| Wontfix / False positive | **0** |
| Resolved rate | **0%** |

### Open Threats by Category

| Category | Open | Critical | High |
|----------|------|----------|------|
| S — Spoofing | 5 | 0 | 3 |
| T — Tampering | 5 | 0 | 3 |
| R — Repudiation | 5 | 0 | 3 |
| I — Information Disclosure | 5 | 0 | 3 |
| D — Denial of Service | 5 | 0 | 3 |
| E — Elevation of Privilege | 3 | 0 | 2 |

### Open Threats by Severity

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 17 |
| MEDIUM | 10 |
| LOW | 1 |
| INFO | 0 |

### Trend Since Last Review

- New threats added: +28
- Threats resolved: −0
- Threats regressed: +0

> ⚠️ **Top 3 Risks**:
> 1. **S-002 / E-001 — Local mode implicit full-trust with no auth boundary** — `anvil/services/content/authz.py:21-42` + `anvil/api/auth.py:201-213`: `AuthzContext.require_management_action()` is a no-op stub; local mode grants implicit full admin to any authenticated session. The auth middleware (API key + session cookie) is the only gate — if bypassed or misconfigured, every destructive operation is open. DFD ref: Part H, H7 local-mode contrast.
> 2. **R-001 — Training, corpus, and model lifecycle events have no audit record with actor identity** — `anvil/api/v1/training.py:186`, `anvil/api/v1/corpora.py:311`, `anvil/api/v1/models.py`: Start/stop training, delete corpus, delete model, delete experiment — none call `workbench.audit.record()`. The AuditService exists and is used in 5 endpoints (datasets, backup, config, governance) but is absent from the highest-value operations. Non-repudiation gap: an actor can deny having started a training run or deleted a model.
> 3. **D-003 — No upload body-size limit on file upload endpoints** — `anvil/api/v1/datasets.py:240`, `anvil/api/v1/content.py:387`, `anvil/api/v1/feedback.py:40`: `UploadFile` endpoints accept arbitrarily large files. No `Content-Length` check, no `max_size` guard. A single request can exhaust disk and memory. The in-process rate limiter (100 req/min/IP) does not bound payload size.

---

## Flat Threat Register (All Categories)

_A single flat table covering every threat across all STRIDE categories. Sortable by status (open first), severity, or date._

| ID | Cat | Sev | Status | Mode | Flow / Component | Title | OWASP xref | First Seen | Last Confirmed | Resolved |
|----|-----|-----|--------|------|-----------------|-------|------------|------------|----------------|----------|
| S-001 | S | HIGH | open | local | Browser→anvil-web: API key login | API key stored in plaintext file with no rotation mechanism | — | 2026-10-04 | 2026-10-04 | — |
| S-002 | S | HIGH | open | local | All routes: auth middleware | Local mode implicit full-trust — AuthzContext is a no-op stub | → A07-002 | 2026-10-04 | 2026-10-04 | — |
| S-003 | S | HIGH | open | local | Browser→anvil-web: SSE stream | SSE training stream has no run-ownership check | → A01-005 | 2026-10-04 | 2026-10-04 | — |
| S-004 | S | MEDIUM | open | local | anvil-web→MLflow: internal call | MLflow service identity not verified (no mTLS, Cloud Map DNS only) | → A05-001 | 2026-10-04 | 2026-10-04 | — |
| S-005 | S | MEDIUM | open | SaaS | Z1→Z3: Cognito callback | OAuth callback PKCE state/code_verifier validation not implemented in current codebase | — | 2026-10-04 | 2026-10-04 | — |
| T-001 | T | HIGH | open | both | Browser→anvil-web: regex replace | User-controlled regex compiled without ReDoS timeout | → A04-008 | 2026-10-04 | 2026-10-04 | — |
| T-002 | T | HIGH | open | local | anvil-web→MLflow: experiment writes | MLflow `--allowed-hosts "*"` allows unauthenticated writes from any host | → A05-001 | 2026-10-04 | 2026-10-04 | — |
| T-003 | T | HIGH | open | local | LocalFileStore→disk: model weights | Model weight files loaded without hash/checksum verification | — | 2026-10-04 | 2026-10-04 | — |
| T-004 | T | MEDIUM | open | local | Browser→anvil-web: training start | `compute_backend` and `device` fields in TrainConfig accept arbitrary strings | — | 2026-10-04 | 2026-10-04 | — |
| T-005 | T | MEDIUM | open | local | anvil-web→SQLite: job events | No DB-level append-only constraint on `job_events` table | — | 2026-10-04 | 2026-10-04 | — |
| R-001 | R | HIGH | open | both | Browser→anvil-web: training lifecycle | Training start/stop has no audit record with actor identity | — | 2026-10-04 | 2026-10-04 | — |
| R-002 | R | HIGH | open | both | Browser→anvil-web: corpus/model delete | Corpus delete, model delete, experiment delete have no audit record | — | 2026-10-04 | 2026-10-04 | — |
| R-003 | R | HIGH | open | both | Browser→anvil-web: all state-changing ops | Audit records that exist use actor="system" not the authenticated user identity | — | 2026-10-04 | 2026-10-04 | — |
| R-004 | R | MEDIUM | open | local | anvil-web→MLflow: run creation | MLflow run creation carries no user/org identity tag | → A10-001 | 2026-10-04 | 2026-10-04 | — |
| R-005 | R | MEDIUM | open | local | anvil-web→disk: log files | Logging not configured in API lifespan — some entry points produce no structured logs | → A09-001 | 2026-10-04 | 2026-10-04 | — |
| I-001 | I | HIGH | open | both | Browser←anvil-web: error responses | `str(exc)` in 36+ HTTPException details leaks internal paths, DB constraint names, library errors | → A05-003 | 2026-10-04 | 2026-10-04 | — |
| I-002 | I | HIGH | open | local | anvil-web→disk: API key file | API key stored in `data/.api_key` (0600) — readable by any process running as the same OS user | — | 2026-10-04 | 2026-10-04 | — |
| I-003 | I | HIGH | open | local | Browser←anvil-web: health/detailed | `GET /v1/health/detailed` returns version, DB schema version, MLflow port, GPU info | → A05-002 | 2026-10-04 | 2026-10-04 | — |
| I-004 | I | MEDIUM | open | local | anvil-web→MLflow: tracking URI | `ANVIL_MLFLOW_URI` is user-configurable with no host allowlist — can redirect tracking data | → A10-001 | 2026-10-04 | 2026-10-04 | — |
| I-005 | I | MEDIUM | open | local | Browser←anvil-web: CORS | CORS is opt-in via `ANVIL_CORS_ORIGINS` — no default allowlist; cross-origin requests blocked by browser but not by server | → A01-007 | 2026-10-04 | 2026-10-04 | — |
| D-001 | D | HIGH | open | both | Browser→anvil-web: training start | No per-user/session training job concurrency limit — unlimited parallel jobs | — | 2026-10-04 | 2026-10-04 | — |
| D-002 | D | HIGH | open | both | Browser→anvil-web: SSE stream | SSE event stream has no max-duration guard — connections held open indefinitely | — | 2026-10-04 | 2026-10-04 | — |
| D-003 | D | HIGH | open | both | Browser→anvil-web: file upload | No body-size limit on UploadFile endpoints (datasets, content, feedback) | → A04-006, A04-007 | 2026-10-04 | 2026-10-04 | — |
| D-004 | D | MEDIUM | open | both | Browser→anvil-web: regex replace | ReDoS via catastrophic backtracking in user-controlled regex | → A04-008 | 2026-10-04 | 2026-10-04 | — |
| D-005 | D | MEDIUM | open | local | In-process: rate limiter | Rate limiter is in-process (dict-based) — reset on restart, not shared across workers | — | 2026-10-04 | 2026-10-04 | — |
| E-001 | E | HIGH | open | local | All routes: AuthzContext | AuthzContext.require_management_action() is a no-op — no RBAC enforcement in local mode | → A07-002 | 2026-10-04 | 2026-10-04 | — |
| E-002 | E | HIGH | open | both | Browser→anvil-web: SSE stream | Any authenticated user can subscribe to any training run's SSE stream by guessing run_id | → A01-005 | 2026-10-04 | 2026-10-04 | — |
| E-003 | E | LOW | open | local | anvil-web→MLflow: proxy | MLflow reverse proxy (`/v1/mlflow-proxy/`) is CSRF-exempt — SPA calls bypass CSRF token check | — | 2026-10-04 | 2026-10-04 | — |

_Sort order: open/in_progress first (by severity desc), then fixed/wontfix (by resolved_date desc)._

---

## Detailed Threat Register

_Per-category context for each threat — scenario, gap, mitigation, and DFD flow._

### S — Spoofing

| ID | Severity | Status | Mode | Flow / Component | Title | First Seen | Last Confirmed | Resolved |
|----|----------|--------|------|-----------------|-------|------------|----------------|----------|
| S-001 | HIGH | open | local | Browser→anvil-web: API key login | API key stored in plaintext file with no rotation mechanism | 2026-10-04 | 2026-10-04 | — |
| S-002 | HIGH | open | local | All routes: auth middleware | Local mode implicit full-trust — AuthzContext is a no-op stub | 2026-10-04 | 2026-10-04 | — |
| S-003 | HIGH | open | local | Browser→anvil-web: SSE stream | SSE training stream has no run-ownership check | 2026-10-04 | 2026-10-04 | — |
| S-004 | MEDIUM | open | local | anvil-web→MLflow: internal call | MLflow service identity not verified (no mTLS, Cloud Map DNS only) | 2026-10-04 | 2026-10-04 | — |
| S-005 | MEDIUM | open | SaaS | Z1→Z3: Cognito callback | OAuth callback PKCE state/code_verifier validation not implemented in current codebase | 2026-10-04 | 2026-10-04 | — |

#### S-001: API key stored in plaintext file with no rotation mechanism
- **Severity**: HIGH
- **Status**: open
- **Mode**: local
- **Flow**: Browser → Z0 (internet/LAN) → anvil-web `/login` endpoint
- **DFD ref**: Part B, B3 Credentials; Part E, E3 Attack Surface Map (authenticated-only)
- **First seen**: 2026-10-04
- **Last confirmed**: 2026-10-04
- **Threat scenario**: An attacker with local filesystem access (or a process running as the same OS user) reads `data/.api_key` (mode 0600) and obtains the full API key. The key has no expiry and no rotation mechanism. Once stolen, it grants full API access indefinitely.
- **Gap**:
  ```python
  # anvil/api/api_key_store.py:144-145
  self._key_path.write_text(self._key, encoding="utf-8")
  self._key_path.chmod(0o600)
  # No rotation, no expiry, no revocation beyond manual file deletion
  ```
- **Mitigation**: Add a key rotation command (`anvil --rotate-api-key`). Consider storing a bcrypt/scrypt hash of the key on disk and comparing against the hash rather than the plaintext. Add a configurable key TTL.
- **OWASP xref**: — (architecture gap — OWASP scan noted no hardcoded secrets; this is a key-lifecycle gap)
- **Notes**: The `ANVIL_API_KEY` env var is popped from `os.environ` after reading (FR-026) — good. The file-persistence path is the gap.

#### S-002: Local mode implicit full-trust — AuthzContext is a no-op stub
- **Severity**: HIGH
- **Status**: open
- **Mode**: local
- **Flow**: All routes → auth middleware → `AuthzContext.require_management_action()`
- **DFD ref**: Part H, H7 local-mode contrast (FR-038b); Part H, H2 RBAC Enforcement Points
- **First seen**: 2026-10-04
- **Last confirmed**: 2026-10-04
- **Threat scenario**: Any authenticated session (valid API key or session cookie) can perform any management action — delete datasets, restart services, stop training runs — because `require_management_action()` is a no-op. There is no role check, no ownership check, no privilege boundary between a "viewer" and an "admin" in local mode.
- **Gap**:
  ```python
  # anvil/services/content/authz.py:39-42
  def require_management_action(self, action: str) -> None:
      """In local single-user mode all management actions are permitted."""
      pass  # All actions permitted in local mode
  ```
- **Mitigation**: Document this as an accepted risk for single-user local mode (wontfix candidate). For SaaS mode, ensure `AuthzContext` is replaced with a real RBAC implementation before any multi-user deployment. Add a mode guard that raises if `ANVIL_MODE=saas` and the stub is still in use.
- **OWASP xref**: → A07-002 (AuthzContext is a no-op stub)
- **Notes**: Part H, H7 explicitly documents local mode as "implicit full access — is_cluster_admin / roles not consulted." This is an accepted architectural decision (ADR-030, AD-14). The threat is real but the risk is accepted for single-user local deployment.

#### S-003: SSE training stream has no run-ownership check
- **Severity**: HIGH
- **Status**: open
- **Mode**: local
- **Flow**: Browser → anvil-web `GET /v1/training/stream/{run_id}` → SSE queue
- **DFD ref**: Part B, B2 DFD L1 (D3→P5→EU); Part E, E3 Attack Surface Map (SSE requires signed token — but this is not implemented)
- **First seen**: 2026-10-04
- **Last confirmed**: 2026-10-04
- **Threat scenario**: Any authenticated user who knows (or guesses) a `run_id` integer can subscribe to that training run's SSE stream and receive live metrics, loss curves, and completion events. Run IDs are sequential integers starting from 1, making enumeration trivial.
- **Gap**:
  ```python
  # anvil/api/v1/training.py:251-269
  @router.get("/training/stream/{run_id}")
  async def stream_training(run_id: int) -> StreamingResponse:
      queue = svc.get_queue(run_id)
      # No check: does the authenticated user own this run?
      if queue is None:
          ...
  ```
- **Mitigation**: Record the authenticated session/user identity when a training run is created. On SSE subscribe, verify the requesting session matches the run's owner. Alternatively, issue a short-lived signed token at job-start time and require it as a query parameter on the SSE endpoint (as described in Part E, E3 and ADR-030 AD-2/FR-020).
- **OWASP xref**: → A01-005 (No ownership check on SSE training stream)
- **Notes**: The architecture spec (Part E, E3) explicitly states "SSE requires signed token" — this control is not yet implemented in the current codebase.

#### S-004: MLflow service identity not verified (no mTLS)
- **Severity**: MEDIUM
- **Status**: open
- **Mode**: local
- **Flow**: anvil-web → MLflow sidecar at `http://127.0.0.1:5001`
- **DFD ref**: Part D, D2 Port/Protocol Matrix (web/batch → MLflow :5000); Part E, E1 Zone 3→Zone 3 crossing
- **First seen**: 2026-10-04
- **Last confirmed**: 2026-10-04
- **Threat scenario**: The anvil-web process connects to MLflow at a configurable URI (`ANVIL_MLFLOW_URI`) with no authentication or TLS. Any process that can bind to the configured port before MLflow starts can impersonate the MLflow server and receive experiment data, or return tampered run metadata.
- **Gap**:
  ```python
  # anvil/config.py: ANVIL_MLFLOW_URI is user-configurable
  # anvil/supervisor/services.py:202-216: MLflow started on 127.0.0.1 (local)
  # No mTLS, no shared secret between anvil-web and MLflow
  ```
- **Mitigation**: For local mode, binding MLflow to `127.0.0.1` (not `0.0.0.0`) limits exposure to localhost. For SaaS mode, use Cloud Map DNS with VPC-internal routing (Part D, D1) and consider adding a shared secret or mTLS between anvil-web and MLflow. Validate the `ANVIL_MLFLOW_URI` against an allowlist.
- **OWASP xref**: → A05-001 (MLflow `--allowed-hosts "*"`)
- **Notes**: In local mode, the risk is low because MLflow binds to `127.0.0.1`. The `--allowed-hosts "*"` setting (A05-001) compounds this by accepting requests from any host header.

#### S-005: OAuth callback PKCE state/code_verifier validation not implemented
- **Severity**: MEDIUM
- **Status**: open
- **Mode**: SaaS
- **Flow**: Browser → Z1 (Cognito) → Z3 (anvil-web `/callback`)
- **DFD ref**: Part A, US1 Sign Up/Log In; Part E, E1 Zone 1→3 crossing; Part E, E2 Boundary Crossings
- **First seen**: 2026-10-04
- **Last confirmed**: 2026-10-04
- **Threat scenario**: The SaaS OAuth callback handler (planned per ADR-030 AD-2) must verify the PKCE `code_verifier` and `state` nonce to prevent CSRF on the OAuth flow. If the callback does not verify `state == session["oauth_state"]`, an attacker can inject their authorization code into a victim's session (login CSRF). The current codebase has no `/callback` route — this is a pre-implementation gap for the SaaS mode.
- **Gap**: No `/callback` route exists in `anvil/api/v1/` or `anvil/api/app.py`. The SaaS auth flow (Cognito OIDC) is planned but not yet implemented. When implemented, it must validate `state` and `code_verifier`.
- **Mitigation**: When implementing the Cognito callback handler: (1) generate a cryptographically random `state` nonce before redirect, store in session; (2) verify `state == session["oauth_state"]` on callback; (3) verify PKCE `code_verifier` matches `code_challenge` sent in the authorization request; (4) reject if either check fails.
- **OWASP xref**: — (pre-implementation gap; no OWASP finding yet)
- **Notes**: ADR-030 AD-2 specifies "app-managed Cognito OIDC/JWT (not ALB-managed)." The US1 flow diagram shows PKCE exchange. This threat is a reminder to implement it correctly.

---

### T — Tampering

| ID | Severity | Status | Mode | Flow / Component | Title | First Seen | Last Confirmed | Resolved |
|----|----------|--------|------|-----------------|-------|------------|----------------|----------|
| T-001 | HIGH | open | both | Browser→anvil-web: regex replace | User-controlled regex compiled without ReDoS timeout | 2026-10-04 | 2026-10-04 | — |
| T-002 | HIGH | open | local | anvil-web→MLflow: experiment writes | MLflow `--allowed-hosts "*"` allows unauthenticated writes from any host | 2026-10-04 | 2026-10-04 | — |
| T-003 | HIGH | open | local | LocalFileStore→disk: model weights | Model weight files loaded without hash/checksum verification | 2026-10-04 | 2026-10-04 | — |
| T-004 | MEDIUM | open | local | Browser→anvil-web: training start | `compute_backend` and `device` fields in TrainConfig accept arbitrary strings | 2026-10-04 | 2026-10-04 | — |
| T-005 | MEDIUM | open | local | anvil-web→SQLite: job events | No DB-level append-only constraint on `job_events` table | 2026-10-04 | 2026-10-04 | — |

#### T-001: User-controlled regex compiled without ReDoS timeout
- **Severity**: HIGH
- **Status**: open
- **Mode**: both
- **Flow**: Browser → anvil-web `POST /v1/datasets/{id}/curate/regex-replace` → `DatasetCuration.regex_replace()`
- **DFD ref**: Part B, B2 DFD L1 (EU→P2→D1); Part E, E3 Attack Surface Map (authenticated-only)
- **First seen**: 2026-10-04
- **Last confirmed**: 2026-10-04
- **Threat scenario**: An authenticated user submits a catastrophically backtracking regex pattern (e.g., `(a+)+$`, `([a-zA-Z]+)*$`) via the regex-replace endpoint. The Python `re` engine enters exponential backtracking, consuming 100% CPU for seconds to minutes, blocking the async event loop and making the server unresponsive to all other requests.
- **Gap**:
  ```python
  # anvil/services/datasets/dataset_curation.py:305
  compiled = re.compile(pattern, flags)
  # No timeout, no complexity limit, no ReDoS protection
  ```
- **Mitigation**: Use `re.compile(pattern, flags)` with a signal-based or thread-based timeout wrapper. Python 3.11+ does not natively support `re.compile(..., timeout=...)`. Options: (1) run regex in a separate thread with `concurrent.futures.ThreadPoolExecutor` and `future.result(timeout=N)`; (2) use the `re2` library (linear-time guarantees); (3) add a pattern complexity heuristic (reject patterns with nested quantifiers).
- **OWASP xref**: → A04-008 (User-controlled regex without ReDoS protection)
- **Notes**: This is both a Tampering threat (data integrity of the dataset operation) and a DoS threat (D-004). The OWASP finding covers the code evidence; this entry adds the DFD context (authenticated data-flow path).

#### T-002: MLflow `--allowed-hosts "*"` allows unauthenticated writes from any host
- **Severity**: HIGH
- **Status**: open
- **Mode**: local
- **Flow**: Any host → MLflow sidecar at `http://127.0.0.1:5001` (or `0.0.0.0:5001` if host config changes)
- **DFD ref**: Part B, B2 DFD L1 (P4→D4); Part E, E1 Zone 3 (MLflow internal); Part F, F1 Egress Paths
- **First seen**: 2026-10-04
- **Last confirmed**: 2026-10-04
- **Threat scenario**: MLflow is started with `--allowed-hosts "*"`, accepting requests from any `Host` header. Any process that can reach the MLflow port can create, modify, or delete experiments and runs without authentication. An attacker on the same LAN (or with SSRF access) can tamper with experiment metadata, inject false metrics, or delete training history.
- **Gap**:
  ```python
  # anvil/supervisor/services.py:214-215
  "--allowed-hosts",
  "*",
  # Should be restricted to localhost or the configured hostname
  ```
- **Mitigation**: Replace `"*"` with `["localhost", "127.0.0.1"]` (or derive from `ANVIL_MLFLOW_URI` hostname). For SaaS mode, restrict to the internal Cloud Map DNS name.
- **OWASP xref**: → A05-001 (MLflow `--allowed-hosts "*"`)
- **Notes**: MLflow's default is more restrictive — this explicitly opens it up. The OWASP finding covers the code evidence; this entry adds the DFD context (Zone 3 internal data store integrity).

#### T-003: Model weight files loaded without hash/checksum verification
- **Severity**: HIGH
- **Status**: open
- **Mode**: local
- **Flow**: anvil-web → `LocalFileStore` → `data/models/` → `safetensors.torch.load_file()`
- **DFD ref**: Part B, B2 DFD L1 (D5 S3 anvil-ml); Part F, F2 Data Exfiltration Controls (S3 object integrity)
- **First seen**: 2026-10-04
- **Last confirmed**: 2026-10-04
- **Threat scenario**: Model weight files (`.safetensors`) are loaded from disk without verifying their integrity against a stored hash. An attacker with write access to `data/models/` can replace a model file with a tampered version (e.g., backdoored weights, adversarial perturbations) that will be loaded silently on the next inference or warm-start request.
- **Gap**:
  ```python
  # anvil/_pyfunc_model.py:61
  state_dict = load_file(str(safetensors_path))
  # No hash verification against a stored manifest
  ```
- **Mitigation**: Store a SHA-256 hash of each model file at export time (in the MLflow artifact manifest or a sidecar `.sha256` file). Verify the hash before loading. The `safetensors` format provides some protection against pickle-based RCE, but not against weight tampering.
- **OWASP xref**: — (architecture gap — OWASP A08 context noted safetensors use; this adds the integrity-verification gap)
- **Notes**: The OWASP scan noted "Model files use safetensors with content-addressed hashing" as a positive. However, the content-addressed hashing is for blob storage (SHA-256 of file content for deduplication), not for integrity verification at load time.

#### T-004: `compute_backend` and `device` fields in TrainConfig accept arbitrary strings
- **Severity**: MEDIUM
- **Status**: open
- **Mode**: local
- **Flow**: Browser → anvil-web `POST /v1/training/start` → `TrainingRunService`
- **DFD ref**: Part B, B2 DFD L1 (EU→P3→P4); Part E, E3 Attack Surface Map
- **First seen**: 2026-10-04
- **Last confirmed**: 2026-10-04
- **Threat scenario**: The `compute_backend` field (e.g., `"auto"`, `"local-stdlib"`, `"local-torch"`, `"modal"`) and `device` field (e.g., `"cpu"`, `"cuda:0"`, `"mps"`) accept arbitrary strings with no enum validation. A malicious or buggy client can submit unexpected values that may trigger unintended code paths in the compute backend selection logic.
- **Gap**:
  ```python
  # anvil/api/v1/training.py:110-114
  compute_backend: str | None = Field(default="auto")
  device: str | None = None
  # No Literal[] or Enum constraint — any string accepted
  ```
- **Mitigation**: Replace `str | None` with `Literal["auto", "local-stdlib", "local-torch", "modal"] | None` for `compute_backend`, and validate `device` against a known pattern (e.g., `^(cpu|cuda:\d+|mps)$`). Use `StrEnum` per AGENTS.md Principle 11.
- **OWASP xref**: — (OWASP A04-003 covers missing constraints on Pydantic models generally; this is a specific instance)
- **Notes**: The `TrainConfig` model has good constraints on numeric fields (ge/le bounds). The string fields are the remaining gap.

#### T-005: No DB-level append-only constraint on `job_events` table
- **Severity**: MEDIUM
- **Status**: open
- **Mode**: local
- **Flow**: anvil-web → SQLite `job_events` table
- **DFD ref**: Part B, B2 DFD L1 (P4→D1); Part C, C1 Schema (job_events append-only)
- **First seen**: 2026-10-04
- **Last confirmed**: 2026-10-04
- **Threat scenario**: The `job_events` table is intended to be append-only (Part B, US2a "append-only, durable"). However, there is no DB-level trigger or constraint preventing UPDATE or DELETE on existing rows. An attacker with DB access (or a bug in the service layer) can modify or delete historical job events, undermining the audit trail and training resilience replay.
- **Gap**: SQLite does not natively support row-level append-only constraints. The application relies on the service layer to never issue UPDATE/DELETE on `job_events`, but this is not enforced at the DB level.
- **Mitigation**: Add a SQLite trigger that raises an error on UPDATE or DELETE of `job_events` rows. Alternatively, use a separate write-once table with a DB user that has only INSERT privileges. For SaaS mode (PostgreSQL), use a row-level security policy or a trigger.
- **OWASP xref**: — (architecture gap — no OWASP equivalent)
- **Notes**: The architecture spec (Part B, US2a) explicitly calls `job_events` "append-only, durable." The current implementation relies on application-level discipline, not DB enforcement.

---

### R — Repudiation

| ID | Severity | Status | Mode | Flow / Component | Title | First Seen | Last Confirmed | Resolved |
|----|----------|--------|------|-----------------|-------|------------|----------------|----------|
| R-001 | HIGH | open | both | Browser→anvil-web: training lifecycle | Training start/stop has no audit record with actor identity | 2026-10-04 | 2026-10-04 | — |
| R-002 | HIGH | open | both | Browser→anvil-web: corpus/model delete | Corpus delete, model delete, experiment delete have no audit record | 2026-10-04 | 2026-10-04 | — |
| R-003 | HIGH | open | both | Browser→anvil-web: all state-changing ops | Audit records that exist use actor="system" not the authenticated user identity | 2026-10-04 | 2026-10-04 | — |
| R-004 | MEDIUM | open | local | anvil-web→MLflow: run creation | MLflow run creation carries no user/org identity tag | 2026-10-04 | 2026-10-04 | — |
| R-005 | MEDIUM | open | local | anvil-web→disk: log files | Logging not configured in API lifespan — some entry points produce no structured logs | 2026-10-04 | 2026-10-04 | — |

#### R-001: Training start/stop has no audit record with actor identity
- **Severity**: HIGH
- **Status**: open
- **Mode**: both
- **Flow**: Browser → anvil-web `POST /v1/training/start`, `POST /v1/training/{run_id}/stop`
- **DFD ref**: Part B, B2 DFD L1 (EU→P3); Part H, H2 RBAC Enforcement Points
- **First seen**: 2026-10-04
- **Last confirmed**: 2026-10-04
- **Threat scenario**: A user starts a training run that consumes significant compute resources (GPU hours, cloud Batch costs in SaaS mode). Later, the user denies having started the run. There is no audit record linking the training start event to the authenticated session/user identity. The `job_events` table records the job lifecycle but not who initiated it.
- **Gap**:
  ```python
  # anvil/api/v1/training.py:186-221
  async def start_training(config: TrainConfig) -> dict[str, Any]:
      run_svc = TrainingRunService(...)
      return await run_svc.start_training_run(svc_config)
      # No: await workbench.audit.record(action=AuditAction.TRAINING_START, actor=<session_user>)
  ```
- **Mitigation**: Call `workbench.audit.record()` at training start and stop, passing the authenticated session identity as `actor`. In local mode, use the API key prefix or a fixed `"local_user"` identifier. In SaaS mode, use the Cognito `sub` claim.
- **OWASP xref**: — (architecture gap — OWASP A09 covers logging failures; this adds the non-repudiation DFD context)
- **Notes**: The `AuditService` exists and is used in 5 endpoints (datasets, backup, config, governance). The training lifecycle is the highest-value gap.

#### R-002: Corpus delete, model delete, experiment delete have no audit record
- **Severity**: HIGH
- **Status**: open
- **Mode**: both
- **Flow**: Browser → anvil-web `DELETE /v1/corpora/{id}`, `DELETE /v1/registry/{id}`, `DELETE /v1/experiments/{id}`
- **DFD ref**: Part B, B2 DFD L1 (EU→P2→D1/D2/D4); Part G, G1 Org Isolation
- **First seen**: 2026-10-04
- **Last confirmed**: 2026-10-04
- **Threat scenario**: A user deletes a corpus, model, or experiment. The deletion is irreversible (no soft-delete). There is no audit record of who deleted what and when. In a multi-user SaaS scenario, this enables repudiation of destructive actions.
- **Gap**:
  ```python
  # anvil/api/v1/corpora.py:311-348
  async def delete_corpus(corpus_id: int, ...) -> dict[str, Any]:
      deleted = await workbench.corpora.delete(corpus_id)
      # Lifecycle tracking via TrackingService (MLflow event_type="delete")
      # But no workbench.audit.record() call with actor identity
  ```
- **Mitigation**: Add `workbench.audit.record()` calls to all delete endpoints, passing the authenticated actor identity. Consider soft-delete (tombstone) for corpora and models to preserve the audit trail even after deletion.
- **OWASP xref**: — (architecture gap)
- **Notes**: The corpus delete does call `TrackingService` with `event_type="delete"`, but this is MLflow experiment tracking (not the hash-chained audit trail) and does not capture the actor identity.

#### R-003: Audit records that exist use actor="system" not the authenticated user identity
- **Severity**: HIGH
- **Status**: open
- **Mode**: both
- **Flow**: All endpoints that call `workbench.audit.record()`
- **DFD ref**: Part H, H2 RBAC Enforcement Points; Part G, G1 Org Isolation
- **First seen**: 2026-10-04
- **Last confirmed**: 2026-10-04
- **Threat scenario**: The 5 endpoints that do call `workbench.audit.record()` (datasets, backup, config, governance) all pass `actor="system"` or `actor="system:takedown"`. This means the audit trail records that "the system" performed the action, not which authenticated user initiated it. In a multi-user scenario, this makes the audit trail useless for non-repudiation.
- **Gap**:
  ```python
  # anvil/api/v1/datasets.py:280
  await workbench.audit.record(
      ...
      actor="system",  # Should be the authenticated user identity
  )
  # anvil/api/v1/backup.py:53
  await wb.audit.record(..., actor="system")
  ```
- **Mitigation**: Pass the authenticated session identity (API key prefix, session ID, or in SaaS mode the Cognito `sub`) as `actor` in all `audit.record()` calls. Add a helper `get_actor_from_request(request)` that extracts the identity from the auth middleware's `request.state`.
- **OWASP xref**: — (architecture gap — OWASP A09 covers logging; this adds the actor-identity gap)
- **Notes**: This is a systemic gap across all existing audit calls, not just a missing call. Even the endpoints that do audit are not capturing the right actor.

#### R-004: MLflow run creation carries no user/org identity tag
- **Severity**: MEDIUM
- **Status**: open
- **Mode**: local
- **Flow**: anvil-web → MLflow `create_run()` → `anvil_mlflow` DB
- **DFD ref**: Part B, B2 DFD L1 (P4→D4); Part G, G1 Layer 6 MLflow experiment tag org_id
- **First seen**: 2026-10-04
- **Last confirmed**: 2026-10-04
- **Threat scenario**: MLflow runs are created without tagging the user identity or org_id. In a multi-user scenario, it is impossible to determine from the MLflow record alone who created a run. The architecture spec (Part G, G1 Layer 6) requires MLflow experiments to be tagged with `org_id` for tenant isolation — this is not yet implemented.
- **Gap**: MLflow `create_run()` calls in `anvil/services/tracking/tracking.py` do not set a `user_id` tag or `org_id` tag on the run.
- **Mitigation**: Add `mlflow.set_tag("user_id", actor)` and `mlflow.set_tag("org_id", org_id)` when creating runs. For SaaS mode, this is required for tenant isolation (Part G, G1 Layer 6).
- **OWASP xref**: → A10-001 (MLflow URI is user-configurable; no outbound host allowlist)
- **Notes**: The architecture spec explicitly requires this for SaaS mode. For local mode, it is a non-repudiation gap.

#### R-005: Logging not configured in API lifespan — some entry points produce no structured logs
- **Severity**: MEDIUM
- **Status**: open
- **Mode**: local
- **Flow**: anvil-web startup → `_setup_logging()` in lifespan
- **DFD ref**: Part B, B2 DFD L1 (all processes)
- **First seen**: 2026-10-04
- **Last confirmed**: 2026-10-04
- **Threat scenario**: `_setup_logging()` is called from the FastAPI lifespan handler. When the app is started via `uvicorn` directly (not via `anvil serve`), logging may not be configured with the intended format and level. Silent startup failures (license seeding, demo bootstrap) are caught and logged at WARNING level, but if logging is not configured, these warnings are lost.
- **Gap**:
  ```python
  # anvil/api/app.py:103-114
  def _setup_logging() -> None:
      logging.basicConfig(level=logging.INFO, format="...", force=True)
  # Called from lifespan — but lifespan is only invoked when the app starts
  # via uvicorn. Direct import of `app` does not trigger lifespan.
  ```
- **Mitigation**: Move `_setup_logging()` to module level in `app.py` so it runs on import, not just on lifespan start. This ensures logging is configured regardless of entry point.
- **OWASP xref**: → A09-001 (Logging configured only in CLI, not in API lifespan — partially addressed)
- **Notes**: The OWASP finding (A09-001) noted logging was only in the CLI. The current code has moved it to the lifespan handler, which is an improvement. The remaining gap is that direct `uvicorn` invocation without the lifespan may not configure logging.

---

### I — Information Disclosure

| ID | Severity | Status | Mode | Flow / Component | Title | First Seen | Last Confirmed | Resolved |
|----|----------|--------|------|-----------------|-------|------------|----------------|----------|
| I-001 | HIGH | open | both | Browser←anvil-web: error responses | `str(exc)` in 36+ HTTPException details leaks internal paths, DB constraint names, library errors | 2026-10-04 | 2026-10-04 | — |
| I-002 | HIGH | open | local | anvil-web→disk: API key file | API key stored in `data/.api_key` (0600) — readable by any process running as the same OS user | 2026-10-04 | 2026-10-04 | — |
| I-003 | HIGH | open | local | Browser←anvil-web: health/detailed | `GET /v1/health/detailed` returns version, DB schema version, MLflow port, GPU info | 2026-10-04 | 2026-10-04 | — |
| I-004 | MEDIUM | open | local | anvil-web→MLflow: tracking URI | `ANVIL_MLFLOW_URI` is user-configurable with no host allowlist — can redirect tracking data | 2026-10-04 | 2026-10-04 | — |
| I-005 | MEDIUM | open | local | Browser←anvil-web: CORS | CORS is opt-in via `ANVIL_CORS_ORIGINS` — no default allowlist; cross-origin requests blocked by browser but not by server | 2026-10-04 | 2026-10-04 | — |

#### I-001: `str(exc)` in 36+ HTTPException details leaks internal information
- **Severity**: HIGH
- **Status**: open
- **Mode**: both
- **Flow**: Browser ← anvil-web: all error responses from `anvil/api/v1/`
- **DFD ref**: Part E, E3 Attack Surface Map (authenticated-only API); Part B, B3 Data Classification
- **First seen**: 2026-10-04
- **Last confirmed**: 2026-10-04
- **Threat scenario**: Exception details passed as `detail=str(exc)` to `HTTPException` can include absolute filesystem paths (e.g., `/home/user/anvil/data/...`), internal variable names, DB constraint names (e.g., `UNIQUE constraint failed: corpora.name`), SQLAlchemy error messages, and third-party library error messages. This information aids an attacker in understanding the internal structure of the application.
- **Gap**:
  ```python
  # anvil/api/v1/backup.py:120
  return JSONResponse(status_code=500, content={"detail": str(exc), "code": type(exc).__name__})
  # anvil/api/v1/content.py:120
  raise HTTPException(status_code=422, detail=str(exc)) from exc
  # ... 34 more instances across v1/ route files
  ```
- **Mitigation**: Replace `detail=str(exc)` with sanitized user-facing messages. Log the original exception server-side with `logger.exception()`. Use a global exception handler in `app.py` that catches unhandled exceptions and returns a generic error message.
- **OWASP xref**: → A05-003 (`str(exc)` leaks internal details in HTTPException)
- **Notes**: The OWASP finding covers the code evidence. This entry adds the DFD context: the leak occurs at the Z0→Z3 boundary (internet-facing API responses).

#### I-002: API key stored in `data/.api_key` (0600) — readable by same OS user
- **Severity**: HIGH
- **Status**: open
- **Mode**: local
- **Flow**: anvil-web startup → `ApiKeyStore._persist()` → `data/.api_key`
- **DFD ref**: Part B, B3 Credentials (most sensitive); Part H, H4 Secrets Access Boundary
- **First seen**: 2026-10-04
- **Last confirmed**: 2026-10-04
- **Threat scenario**: The API key is stored in plaintext at `data/.api_key` with mode 0600. Any process running as the same OS user (e.g., a compromised subprocess, a malicious Python package, a shell script) can read the full API key and use it to authenticate to the anvil API.
- **Gap**:
  ```python
  # anvil/api/api_key_store.py:144-145
  self._key_path.write_text(self._key, encoding="utf-8")
  self._key_path.chmod(0o600)
  # Plaintext storage — any same-user process can read it
  ```
- **Mitigation**: Store a bcrypt/scrypt hash of the key on disk and compare against the hash at validation time. The full key is only ever in memory. Alternatively, use the OS keychain (macOS Keychain, Linux Secret Service) for key storage.
- **OWASP xref**: — (architecture gap — OWASP scan found no hardcoded secrets; this is a key-storage gap)
- **Notes**: The `ANVIL_API_KEY` env var is popped from `os.environ` after reading (good). The file-persistence path is the remaining gap. For a local single-user tool, this risk may be accepted.

#### I-003: `GET /v1/health/detailed` returns sensitive system information
- **Severity**: HIGH
- **Status**: open
- **Mode**: local
- **Flow**: Browser ← anvil-web `GET /v1/health/detailed`
- **DFD ref**: Part E, E3 Attack Surface Map (authenticated-only)
- **First seen**: 2026-10-04
- **Last confirmed**: 2026-10-04
- **Threat scenario**: The detailed health endpoint returns: anvil version, DB schema version, MLflow port number, GPU model and driver version, CPU/memory/disk usage, and DB error messages (including `str(exc)` from DB probing). This information aids an attacker in fingerprinting the deployment and identifying exploitable versions.
- **Gap**:
  ```python
  # anvil/api/v1/health_ops.py:96-154
  return {
      "version": anvil_version,  # exact version
      "database": {"error": db_error},  # str(exc) from DB probe
      "mlflow": {"port": ..., "error": mlflow_error},  # port + str(exc)
      "gpu": {"errors": detect_gpu().errors},  # GPU details
  }
  ```
- **Mitigation**: The endpoint is already auth-gated (requires authentication). Consider further restricting it to admin-role users only. Sanitize error messages (replace `str(exc)` with generic messages). For SaaS mode, this endpoint should only be accessible to cluster admins (Part H, H7).
- **OWASP xref**: → A05-002 (Version disclosure in health endpoint)
- **Notes**: The bare `GET /v1/health` (liveness check) is auth-exempt and returns only `{"status": "healthy"}` — this is correct. The detailed endpoint is auth-gated, which is the right approach. The remaining gap is the richness of information returned.

#### I-004: `ANVIL_MLFLOW_URI` is user-configurable with no host allowlist
- **Severity**: MEDIUM
- **Status**: open
- **Mode**: local
- **Flow**: anvil-web → MLflow client → `ANVIL_MLFLOW_URI`
- **DFD ref**: Part F, F1 Egress Paths; Part B, B3 Data Classification (Operational: transient)
- **First seen**: 2026-10-04
- **Last confirmed**: 2026-10-04
- **Threat scenario**: An attacker who controls the environment (or can set env vars) can redirect `ANVIL_MLFLOW_URI` to an attacker-controlled server. All MLflow tracking data (experiment names, run parameters, metrics, model artifact paths) would be sent to the attacker's server.
- **Gap**:
  ```python
  # anvil/config.py: ANVIL_MLFLOW_URI env var controls MLflow tracking destination
  # No validation against an allowlist of permitted hosts
  ```
- **Mitigation**: For SaaS mode, restrict `ANVIL_MLFLOW_URI` to a known allowlist (e.g., the internal Cloud Map DNS name). For local mode, validate that the URI is localhost or a known safe host.
- **OWASP xref**: → A10-001 (MLflow URI is user-configurable; no outbound host allowlist)
- **Notes**: The OWASP finding covers this. This entry adds the DFD context: the data exfiltration path is via the egress boundary (Part F, F1).

#### I-005: CORS is opt-in — no default allowlist configured
- **Severity**: MEDIUM
- **Status**: open
- **Mode**: local
- **Flow**: Browser → anvil-web: cross-origin requests
- **DFD ref**: Part E, E3 Attack Surface Map; Part D, D2 Port/Protocol Matrix
- **First seen**: 2026-10-04
- **Last confirmed**: 2026-10-04
- **Threat scenario**: CORS middleware is only added if `ANVIL_CORS_ORIGINS` is set. Without it, the browser's same-origin policy blocks cross-origin reads, but the server does not enforce any CORS policy. A malicious page on the same LAN could make credentialed requests to the anvil API if the browser's SOP is bypassed (e.g., via a browser extension or a misconfigured browser).
- **Gap**:
  ```python
  # anvil/api/app.py:485-493
  if _cors_origins_str:
      # CORS middleware only added if env var is set
      app.add_middleware(CORSMiddleware, allow_origins=origins, ...)
  # No default CORS policy — relies entirely on browser SOP
  ```
- **Mitigation**: Add a default CORS policy that denies all cross-origin requests unless `ANVIL_CORS_ORIGINS` is explicitly set. This makes the secure state the default.
- **OWASP xref**: → A01-007 (No CORS middleware configured)
- **Notes**: The OWASP finding (A01-007) noted no CORS middleware. The current code has added opt-in CORS. The remaining gap is that the default (no env var) is no CORS policy rather than a deny-all policy.

---

### D — Denial of Service

| ID | Severity | Status | Mode | Flow / Component | Title | First Seen | Last Confirmed | Resolved |
|----|----------|--------|------|-----------------|-------|------------|----------------|----------|
| D-001 | HIGH | open | both | Browser→anvil-web: training start | No per-user/session training job concurrency limit — unlimited parallel jobs | 2026-10-04 | 2026-10-04 | — |
| D-002 | HIGH | open | both | Browser→anvil-web: SSE stream | SSE event stream has no max-duration guard — connections held open indefinitely | 2026-10-04 | 2026-10-04 | — |
| D-003 | HIGH | open | both | Browser→anvil-web: file upload | No body-size limit on UploadFile endpoints (datasets, content, feedback) | 2026-10-04 | 2026-10-04 | — |
| D-004 | MEDIUM | open | both | Browser→anvil-web: regex replace | ReDoS via catastrophic backtracking in user-controlled regex | 2026-10-04 | 2026-10-04 | — |
| D-005 | MEDIUM | open | local | In-process: rate limiter | Rate limiter is in-process (dict-based) — reset on restart, not shared across workers | 2026-10-04 | 2026-10-04 | — |

#### D-001: No per-user/session training job concurrency limit
- **Severity**: HIGH
- **Status**: open
- **Mode**: both
- **Flow**: Browser → anvil-web `POST /v1/training/start` → `TrainingRunService`
- **DFD ref**: Part B, B2 DFD L1 (EU→P3→P4); Part E, E3 Attack Surface Map
- **First seen**: 2026-10-04
- **Last confirmed**: 2026-10-04
- **Threat scenario**: An authenticated user (or a script) can submit an unlimited number of training jobs in rapid succession. Each job spawns an asyncio task and (for torch backends) loads a model into memory. Submitting 10+ concurrent jobs can exhaust RAM, CPU, and GPU memory, making the server unresponsive to all other requests.
- **Gap**:
  ```python
  # anvil/api/v1/training.py:186-221
  async def start_training(config: TrainConfig) -> dict[str, Any]:
      run_svc = TrainingRunService(...)
      return await run_svc.start_training_run(svc_config)
      # No check: how many active jobs does this session/user already have?
  ```
- **Mitigation**: Add a per-session (or global) concurrency limit on active training jobs. Check `len(_tasks)` before accepting a new job. Return HTTP 429 if the limit is exceeded. For SaaS mode, enforce per-org job quotas via the Batch job queue concurrency limits (Part E, E2 Compute→Data boundary).
- **OWASP xref**: — (architecture gap — OWASP A04-004 covers rate limiting; this adds the job-concurrency DFD context)
- **Notes**: The global rate limiter (100 req/min/IP) does not prevent a single user from submitting 100 training jobs in one minute.

#### D-002: SSE event stream has no max-duration guard
- **Severity**: HIGH
- **Status**: open
- **Mode**: both
- **Flow**: Browser → anvil-web `GET /v1/training/stream/{run_id}` → SSE generator
- **DFD ref**: Part B, B2 DFD L1 (D3→P5→EU); Part E, E3 Attack Surface Map (SSE requires signed token)
- **First seen**: 2026-10-04
- **Last confirmed**: 2026-10-04
- **Threat scenario**: An authenticated client opens an SSE connection to a training stream and holds it open indefinitely. The SSE generator loops with a 30-second timeout per message, yielding heartbeats. A client that never closes the connection holds a server-side asyncio task and an in-memory queue open forever. With enough concurrent connections, this exhausts the server's connection pool and asyncio task budget.
- **Gap**:
  ```python
  # anvil/api/v1/training.py:292-310
  async def event_stream() -> AsyncGenerator[str, None]:
      while True:
          try:
              msg = await asyncio.wait_for(queue.get(), timeout=30)
              yield ...
              if msg["event"] in ("complete", "error", "divergence"):
                  break
          except TimeoutError:
              yield "event: heartbeat\ndata: {}\n\n"
  # No max-duration guard — runs until training completes or client disconnects
  ```
- **Mitigation**: Add a maximum connection duration (e.g., 2 hours) after which the SSE generator yields a `timeout` event and closes. Track connection count per session and enforce a per-session SSE connection limit.
- **OWASP xref**: — (architecture gap — OWASP A04-004 covers rate limiting; this adds the SSE-specific DoS vector)
- **Notes**: The `_orphan_queue_release` timeout (120s) in `TrainingRunService._cleanup` releases the queue after training completes, but does not close the SSE connection if the client is still connected.

#### D-003: No body-size limit on UploadFile endpoints
- **Severity**: HIGH
- **Status**: open
- **Mode**: both
- **Flow**: Browser → anvil-web `POST /v1/datasets/upload`, `POST /v1/content/sessions/{id}/stage`, `POST /v1/feedback/reports`
- **DFD ref**: Part B, B4 Upload Data Flow; Part E, E3 Attack Surface Map
- **First seen**: 2026-10-04
- **Last confirmed**: 2026-10-04
- **Threat scenario**: An authenticated user uploads an arbitrarily large file (e.g., a 10 GB file) to any of the three `UploadFile` endpoints. The server reads the entire file into memory (or streams it to disk without a size check), exhausting disk space or RAM. The in-process rate limiter (100 req/min/IP) does not bound payload size.
- **Gap**:
  ```python
  # anvil/api/v1/datasets.py:240-241
  @router.post("/datasets/upload")
  async def upload_dataset(file: UploadFile, ...):
      # No size check before reading
  # anvil/api/v1/content.py:387
  async def stage_content(file: UploadFile, ...):
      # No size check
  # anvil/api/v1/feedback.py:40-41
  async def create_feedback_report(screenshot: UploadFile | None = None, ...):
      # No size check
  ```
- **Mitigation**: Add a `Content-Length` check at the middleware level (reject requests > N MB before reading the body). For `UploadFile` endpoints, add an explicit size check after reading: `if len(content) > MAX_UPLOAD_BYTES: raise HTTPException(413)`. Configure uvicorn's `--limit-max-requests` and consider adding a body-size limit middleware.
- **OWASP xref**: → A04-006 (No file size limit on /datasets/upload), → A04-007 (No file size limit on /content/stage)
- **Notes**: The OWASP findings cover the code evidence. This entry adds the DFD context: the upload path bypasses the application server (Part B, B4 shows direct S3 upload for SaaS mode, but local mode reads through the app).

#### D-004: ReDoS via catastrophic backtracking in user-controlled regex
- **Severity**: MEDIUM
- **Status**: open
- **Mode**: both
- **Flow**: Browser → anvil-web `POST /v1/datasets/{id}/curate/regex-replace` → `DatasetCuration.regex_replace()`
- **DFD ref**: Part B, B2 DFD L1 (EU→P2→D1)
- **First seen**: 2026-10-04
- **Last confirmed**: 2026-10-04
- **Threat scenario**: Same as T-001 from the DoS perspective: a catastrophically backtracking regex blocks the async event loop, making the server unresponsive. This is both a Tampering threat (data integrity) and a DoS threat (availability).
- **Gap**: See T-001 gap.
- **Mitigation**: See T-001 mitigation.
- **OWASP xref**: → A04-008 (User-controlled regex without ReDoS protection)
- **Notes**: Cross-reference with T-001. The OWASP finding covers the code evidence.

#### D-005: Rate limiter is in-process — reset on restart, not shared across workers
- **Severity**: MEDIUM
- **Status**: open
- **Mode**: local
- **Flow**: All requests → `rate_limit_middleware` → `_rate_limit_store` (in-memory dict)
- **DFD ref**: Part E, E2 Boundary Crossings (Internet→Edge: WAF rate limit); Part D, D1 Traffic Flow
- **First seen**: 2026-10-04
- **Last confirmed**: 2026-10-04
- **Threat scenario**: The rate limiter uses an in-process `defaultdict(list)` keyed by `{client_ip}:{path}`. This state is lost on server restart. If the server is restarted (e.g., via `POST /v1/services/restart-all`), the rate limit counters reset, allowing a burst of requests immediately after restart. In a multi-worker deployment (uvicorn with `--workers N`), each worker has its own counter, so the effective rate limit is N × 100 req/min.
- **Gap**:
  ```python
  # anvil/api/app.py:73
  _rate_limit_store: dict[str, list[float]] = defaultdict(list)
  # In-process — not shared across workers or restarts
  ```
- **Mitigation**: For production/SaaS deployments, use a Redis-backed rate limiter (e.g., `slowapi` with Redis storage). For local mode, the in-process limiter is acceptable. Document the limitation.
- **OWASP xref**: → A04-004 (No rate limiting middleware — partially addressed)
- **Notes**: The OWASP finding (A04-004) noted no rate limiting. The current code has added in-process rate limiting. The remaining gap is the in-process limitation.

---

### E — Elevation of Privilege

| ID | Severity | Status | Mode | Flow / Component | Title | First Seen | Last Confirmed | Resolved |
|----|----------|--------|------|-----------------|-------|------------|----------------|----------|
| E-001 | HIGH | open | local | All routes: AuthzContext | AuthzContext.require_management_action() is a no-op — no RBAC enforcement in local mode | 2026-10-04 | 2026-10-04 | — |
| E-002 | HIGH | open | both | Browser→anvil-web: SSE stream | Any authenticated user can subscribe to any training run's SSE stream by guessing run_id | 2026-10-04 | 2026-10-04 | — |
| E-003 | LOW | open | local | anvil-web→MLflow: proxy | MLflow reverse proxy (`/v1/mlflow-proxy/`) is CSRF-exempt — SPA calls bypass CSRF token check | 2026-10-04 | 2026-10-04 | — |

#### E-001: AuthzContext.require_management_action() is a no-op — no RBAC enforcement in local mode
- **Severity**: HIGH
- **Status**: open
- **Mode**: local
- **Flow**: All routes → `AuthzContext.require_management_action()` → no-op
- **DFD ref**: Part H, H2 RBAC Enforcement Points; Part H, H7 local-mode contrast (FR-038b)
- **First seen**: 2026-10-04
- **Last confirmed**: 2026-10-04
- **Threat scenario**: Any authenticated session can perform any management action (delete datasets, restart services, stop training runs, modify config) because `require_management_action()` is a no-op. There is no role-based access control in local mode. If the API key is shared with multiple users (e.g., in a team environment), any user has full admin privileges.
- **Gap**:
  ```python
  # anvil/services/content/authz.py:39-42
  def require_management_action(self, action: str) -> None:
      """In local single-user mode all management actions are permitted."""
      pass
  ```
- **Mitigation**: For local mode, this is an accepted architectural decision (ADR-030, AD-14). Document it explicitly. For SaaS mode, implement real RBAC before any multi-user deployment. Add a mode guard that raises `NotImplementedError` if `ANVIL_MODE=saas` and the stub is still in use.
- **OWASP xref**: → A07-002 (AuthzContext is a no-op stub)
- **Notes**: Cross-reference with S-002. The architecture spec (Part H, H7) explicitly documents local mode as "implicit full access." This is an accepted risk for single-user local deployment.

#### E-002: Any authenticated user can subscribe to any training run's SSE stream
- **Severity**: HIGH
- **Status**: open
- **Mode**: both
- **Flow**: Browser → anvil-web `GET /v1/training/stream/{run_id}` → SSE queue
- **DFD ref**: Part B, B2 DFD L1 (D3→P5→EU); Part G, G3 Cross-Tenant Denial Paths (SSE token scope mismatch → 401)
- **First seen**: 2026-10-04
- **Last confirmed**: 2026-10-04
- **Threat scenario**: Run IDs are sequential integers. An authenticated user can enumerate run IDs and subscribe to any active training run's SSE stream, receiving live metrics, loss curves, and completion events for runs they did not start. In a multi-user scenario, this is a cross-user privilege escalation (User A reads User B's training progress).
- **Gap**:
  ```python
  # anvil/api/v1/training.py:251-269
  @router.get("/training/stream/{run_id}")
  async def stream_training(run_id: int) -> StreamingResponse:
      queue = svc.get_queue(run_id)
      # No ownership check — any authenticated user can subscribe
  ```
- **Mitigation**: Issue a short-lived signed token at job-start time (as described in Part E, E3 and ADR-030 AD-2/FR-020). Require the token as a query parameter on the SSE endpoint. Verify the token's `run_id` claim matches the requested run.
- **OWASP xref**: → A01-005 (No ownership check on SSE training stream)
- **Notes**: Cross-reference with S-003. The architecture spec (Part G, G3) explicitly requires SSE token scope mismatch → 401. This control is not yet implemented.

#### E-003: MLflow reverse proxy is CSRF-exempt — SPA calls bypass CSRF token check
- **Severity**: LOW
- **Status**: open
- **Mode**: local
- **Flow**: Browser → anvil-web `/v1/mlflow-proxy/*` → MLflow sidecar
- **DFD ref**: Part A, US5 SaaS Developer Local Stack; Part E, E1 Zone 3 (MLflow internal)
- **First seen**: 2026-10-04
- **Last confirmed**: 2026-10-04
- **Threat scenario**: The MLflow reverse proxy path (`/v1/mlflow-proxy/`) is exempt from the CSRF synchronizer-token check. The MLflow SPA makes its own state-changing AJAX calls (create experiment, log metric, delete run) that cannot carry anvil's CSRF token. A CSRF attack against the MLflow proxy could create, modify, or delete MLflow experiments and runs.
- **Gap**:
  ```python
  # anvil/api/auth.py:261-267
  CSRF_EXEMPT_PREFIXES: tuple[str, ...] = ("/v1/mlflow-proxy",)
  # Safety relies on SameSite=Strict + same-origin (FR-027/FR-004)
  ```
- **Mitigation**: The `SameSite=Strict` cookie attribute provides CSRF protection for same-site requests. The risk is low because: (1) the session cookie is `SameSite=Strict`, preventing cross-site cookie sending; (2) MLflow is only accessible via the proxy (not directly). Document this as an accepted risk with the compensating control.
- **OWASP xref**: — (architecture gap — compensating control: SameSite=Strict)
- **Notes**: The code comment explicitly documents the compensating control: "Safety relies on `SameSite=Strict` + same-origin (FR-027/FR-004)." This is a LOW severity because the compensating control is effective for modern browsers.

---

## Architecture Observations

### AO-1: Local mode is a single-trust-zone system by design
The local mode architecture (Part H, H7) intentionally collapses all trust zones into a single implicit-admin context. This is correct for a single-user local tool but creates a sharp security cliff if the tool is ever exposed to a network or shared with multiple users. The `AuthzContext` stub (S-002, E-001) is the most visible manifestation of this design choice. **Recommendation**: Add a prominent warning in the README and startup logs when the server binds to `0.0.0.0` (LAN-accessible mode).

### AO-2: AuditService exists but is not wired to the highest-value operations
The hash-chained `AuditService` (ADR-023) is a strong positive — it provides tamper-evident audit records. However, it is only called in 5 endpoints (datasets, backup, config, governance), and all existing calls use `actor="system"` rather than the authenticated user identity (R-001, R-002, R-003). The audit trail is structurally sound but operationally incomplete.

### AO-3: MLflow is a shared, unauthenticated internal service
MLflow runs as a sidecar with `--allowed-hosts "*"` and no authentication. It is the single point of failure for experiment tracking integrity (T-002). In local mode, it is bound to `127.0.0.1`, which limits exposure. In SaaS mode, it must be behind the authenticated reverse proxy (ADR-035, AD-13) and restricted to the internal VPC.

### AO-4: Rate limiting is in-process and not distributed
The sliding-window rate limiter (100 req/min/IP) is implemented as an in-process `defaultdict`. This is appropriate for a single-process local tool but will not scale to multi-worker or multi-instance deployments. For SaaS mode, a Redis-backed rate limiter is required (D-005).

### AO-5: SaaS mode security controls are planned but not yet implemented
Several threats in this report (S-005, R-004, E-002) reference SaaS mode controls that are specified in the architecture (ADR-030, Part G, Part H) but not yet implemented in the codebase. The architecture design is sound; the implementation gap is the risk. These should be tracked as pre-implementation requirements for the SaaS launch.

---

## STRIDE ↔ OWASP Coverage Map

_Cross-reference showing which STRIDE threats map to existing OWASP findings, and which are architecture-level gaps with no OWASP equivalent._

| STRIDE ID | STRIDE Title | OWASP xref | Coverage |
|-----------|-------------|------------|---------|
| S-001 | API key stored in plaintext file with no rotation | — | Architecture gap — no OWASP equivalent |
| S-002 | Local mode implicit full-trust — AuthzContext no-op | A07-002 | OWASP covers code evidence; STRIDE adds trust-zone context (Part H, H7) |
| S-003 | SSE training stream has no run-ownership check | A01-005 | OWASP covers code evidence; STRIDE adds DFD flow context (Part E, E3 signed token) |
| S-004 | MLflow service identity not verified (no mTLS) | A05-001 | OWASP covers `--allowed-hosts "*"`; STRIDE adds Zone 3→3 crossing context |
| S-005 | OAuth callback PKCE state/code_verifier not implemented | — | Architecture gap — pre-implementation SaaS requirement |
| T-001 | User-controlled regex without ReDoS timeout | A04-008 | OWASP covers code evidence; STRIDE adds data-integrity DFD context |
| T-002 | MLflow `--allowed-hosts "*"` allows unauthenticated writes | A05-001 | OWASP covers code evidence; STRIDE adds data-store integrity context (Part B, B2 D4) |
| T-003 | Model weight files loaded without hash verification | — | Architecture gap — no OWASP equivalent |
| T-004 | `compute_backend`/`device` accept arbitrary strings | — | Architecture gap — OWASP A04-003 covers Pydantic constraints generally |
| T-005 | No DB-level append-only constraint on `job_events` | — | Architecture gap — no OWASP equivalent |
| R-001 | Training start/stop has no audit record with actor | — | Architecture gap — OWASP A09 covers logging; STRIDE adds non-repudiation context |
| R-002 | Corpus/model/experiment delete has no audit record | — | Architecture gap — no OWASP equivalent |
| R-003 | Audit records use actor="system" not authenticated user | — | Architecture gap — no OWASP equivalent |
| R-004 | MLflow run creation carries no user/org identity tag | A10-001 | OWASP covers MLflow URI config; STRIDE adds run-identity non-repudiation context |
| R-005 | Logging not configured in API lifespan | A09-001 | OWASP covers logging config; STRIDE adds structured-log availability context |
| I-001 | `str(exc)` in 36+ HTTPException details leaks internals | A05-003 | OWASP covers code evidence; STRIDE adds Z0→Z3 boundary context |
| I-002 | API key stored in `data/.api_key` (0600) | — | Architecture gap — no OWASP equivalent |
| I-003 | `GET /v1/health/detailed` returns sensitive system info | A05-002 | OWASP covers version disclosure; STRIDE adds full information-disclosure scope |
| I-004 | `ANVIL_MLFLOW_URI` user-configurable, no host allowlist | A10-001 | OWASP covers code evidence; STRIDE adds egress-boundary exfiltration context (Part F) |
| I-005 | CORS is opt-in — no default allowlist | A01-007 | OWASP covers no CORS middleware; STRIDE adds boundary-crossing context |
| D-001 | No per-user training job concurrency limit | — | Architecture gap — OWASP A04-004 covers rate limiting; STRIDE adds job-concurrency context |
| D-002 | SSE stream has no max-duration guard | — | Architecture gap — no OWASP equivalent |
| D-003 | No body-size limit on UploadFile endpoints | A04-006, A04-007 | OWASP covers code evidence; STRIDE adds upload-flow DoS context (Part B, B4) |
| D-004 | ReDoS via user-controlled regex | A04-008 | OWASP covers code evidence; STRIDE adds availability-impact context |
| D-005 | Rate limiter is in-process — not distributed | A04-004 | OWASP covers rate limiting; STRIDE adds multi-worker/restart gap context |
| E-001 | AuthzContext.require_management_action() is a no-op | A07-002 | OWASP covers code evidence; STRIDE adds privilege-boundary context (Part H, H2) |
| E-002 | Any authenticated user can subscribe to any SSE stream | A01-005 | OWASP covers code evidence; STRIDE adds cross-user EoP context (Part G, G3) |
| E-003 | MLflow proxy is CSRF-exempt | — | Architecture gap — compensating control: SameSite=Strict |

**Summary**: 14 threats cross-reference existing OWASP findings; 14 are architecture-level gaps with no OWASP equivalent.

---

## Recommendations (Priority Order)

### Immediate (HIGH — address before any multi-user or network-exposed deployment)

1. **R-001, R-002, R-003 — Wire actor identity into all audit records**: The `AuditService` infrastructure exists. Add `workbench.audit.record()` calls to training start/stop, corpus delete, model delete, and experiment delete. Pass the authenticated session identity (not `"system"`) as `actor`. This is a 1–2 day effort with high non-repudiation value.

2. **D-003 — Add upload body-size limits**: Add a `Content-Length` check at the middleware level and explicit size checks in `upload_dataset`, `stage_content`, and `create_feedback_report`. Set a configurable `ANVIL_MAX_UPLOAD_MB` env var (default: 100 MB). This prevents disk/memory exhaustion from a single request.

3. **T-001, D-004 — Add ReDoS protection to regex replace**: Wrap `re.compile()` in a thread-based timeout (e.g., `concurrent.futures.ThreadPoolExecutor` with `future.result(timeout=5)`). This prevents a single regex from blocking the event loop.

4. **S-003, E-002 — Add run-ownership check to SSE stream**: Record the authenticated session identity when a training run is created. Verify ownership on SSE subscribe. This closes the cross-user information disclosure and privilege escalation gap.

### Short-term (HIGH — address before SaaS launch)

5. **T-002, S-004 — Restrict MLflow `--allowed-hosts`**: Replace `"*"` with `["localhost", "127.0.0.1"]` in `anvil/supervisor/services.py:214-215`. This is a one-line fix with immediate impact.

6. **I-001 — Sanitize `str(exc)` in HTTPException details**: Replace `detail=str(exc)` with sanitized user-facing messages across all 36+ instances in `anvil/api/v1/`. Add a global exception handler in `app.py` for unhandled exceptions.

7. **D-001 — Add training job concurrency limit**: Add a per-session (or global) limit on active training jobs. Check `len(_tasks)` before accepting a new job. Return HTTP 429 if exceeded.

8. **D-002 — Add SSE stream max-duration guard**: Add a maximum connection duration (e.g., 2 hours) to the SSE generator. Track connection count per session.

9. **S-005 — Implement PKCE state/code_verifier validation in OAuth callback**: When implementing the Cognito callback handler for SaaS mode, validate `state` and `code_verifier` per the OAuth 2.0 PKCE spec.

### Medium-term (MEDIUM — address in next sprint)

10. **T-004 — Add enum validation to `compute_backend` and `device` fields**: Replace `str | None` with `Literal[...]` or `StrEnum` for `compute_backend` and validate `device` against a known pattern.

11. **T-005 — Add DB-level append-only constraint to `job_events`**: Add a SQLite trigger that raises on UPDATE/DELETE of `job_events` rows.

12. **R-004 — Tag MLflow runs with user/org identity**: Add `mlflow.set_tag("user_id", actor)` when creating runs. Required for SaaS tenant isolation (Part G, G1 Layer 6).

13. **T-003 — Add model weight hash verification**: Store SHA-256 hashes of model files at export time. Verify before loading.

14. **D-005 — Document rate limiter limitations**: Add a comment and README note that the in-process rate limiter is not suitable for multi-worker deployments. For SaaS mode, use a Redis-backed rate limiter.

15. **I-002 — Consider hashed API key storage**: Store a bcrypt/scrypt hash of the API key on disk rather than the plaintext. The full key is only ever in memory.

---

_Generated by `/stride-review` command | Last full scan: 2026-10-04_
