---
description: Review the architecture and codebase against STRIDE threat categories (Spoofing, Tampering, Repudiation, Information Disclosure, Denial of Service, Elevation of Privilege) using the project's DFDs and trust-boundary model, and maintain a living task-tracking report.
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

The argument is an optional target path or scope (e.g., `anvil/api/`, `SaaS`, `local`). If omitted, default to the full project — both local and SaaS-mode surfaces.

## Goal

Apply the STRIDE threat-modeling methodology against the anvil architecture — grounded in the DFDs, trust-zone model, and boundary-crossing inventory in `docs/vault/Reference/SaaSSecurityAndFlowDiagrams.md` — and maintain a **living task-tracking report** in TWO formats:

1. **Living markdown report** at `docs/stride-review.md` — human-readable, with Scan History, Progress Summary, and Flat Threat Register.
2. **Running CSV tracker** at `docs/stride-tracker.csv` — machine-parseable, for import into Sheets/Excel/scripts, tracking each threat's lifecycle across all runs.

If the report already exists, read it, re-check each threat against the current codebase and architecture, merge in new threats, update statuses, and write back both files.

STRIDE complements the OWASP review (`docs/owasp-review.md`): OWASP identifies vulnerable implementation patterns; STRIDE identifies architectural threat categories. Where a threat maps to a known OWASP finding, cross-reference it rather than duplicate the evidence.

## STRIDE vs OWASP — Scope Clarification

| STRIDE Category | Primary OWASP Overlap | What STRIDE adds |
|---|---|---|
| Spoofing | A07 Identification & Authentication Failures | Identity trust at every trust-zone crossing, not just login |
| Tampering | A03 Injection, A08 Data Integrity | Integrity of data in flight and at rest across DFD flows |
| Repudiation | A09 Security Logging & Monitoring | Accountability and non-repudiation guarantees per actor |
| Information Disclosure | A02 Crypto Failures, A05 Misconfiguration | Data classification and confidentiality at every boundary |
| Denial of Service | A04 Insecure Design (partial) | Availability attacks at each layer and flow |
| Elevation of Privilege | A01 Broken Access Control, A04 Insecure Design | Privilege escalation paths across trust-zone boundaries |

## Operating Constraints

1. **Architecture-first**: Start from the DFDs and trust zones in `docs/vault/Reference/SaaSSecurityAndFlowDiagrams.md` (Parts B, E, F, G, H). Threats are identified per data flow and trust-zone boundary, not just per code pattern.
2. **Read-only on source**: Do not modify any source files. Findings only.
3. **Evidence-based**: Every threat must cite the specific data flow, trust-zone crossing, or file:line where the gap exists. No vague claims.
4. **Severity rating**: Every threat gets a severity — `CRITICAL`, `HIGH`, `MEDIUM`, `LOW`, or `INFO`.
5. **OWASP cross-reference**: If a threat is already tracked in `docs/owasp-review.md`, reference it by OWASP finding ID (e.g., `→ A01-003`) instead of re-documenting the same evidence. Add the architecture/DFD context that OWASP missed.
6. **Codebase-specific**: Checks must be relevant to this stack: Python, FastAPI, SQLAlchemy, Jinja2, SQLite (local mode), PostgreSQL/RDS + Redis + S3 + Cognito (SaaS mode), AWS Batch, MLflow.
7. **Mode-aware**: Distinguish local-mode threats (single-user, SQLite, in-process) from SaaS-mode threats (multi-tenant, Cognito, Batch, cloud data stores). Scope each finding with `[local]`, `[SaaS]`, or `[both]`.
8. **Living doc discipline**: The report is the authoritative task list. Every update must preserve: threat IDs, history (first_seen, last_confirmed, resolved_date), and status transitions. Never silently drop a threat — if it's no longer present in the report, it must be explicitly marked `fixed` or `wontfix`.
9. **Tracker sync discipline**: The CSV tracker at `docs/stride-tracker.csv` mirrors the Flat Threat Register. Both must be written in the same run with identical data. Never write one without the other.
10. **Pre-seeded context**: Load architecture docs before scanning. Note deployment mode implications, known accepted risks, and cross-references to existing OWASP findings.

## Threat Lifecycle Model

Every threat in the report has these fields:

```
<threat-id> | <category> | <severity> | <status> | <mode> | <flow/component> | <title> | <first_seen> | <last_confirmed> | <resolved_date>
```

**Threat IDs**: Prefixed by STRIDE letter — `S-001` (Spoofing), `T-001` (Tampering), `R-001` (Repudiation), `I-001` (Information Disclosure), `D-001` (Denial of Service), `E-001` (Elevation of Privilege).

**Mode**: `local`, `SaaS`, or `both`.

**Statuses** (task-tracked):
| Status | Meaning |
|--------|---------|
| `open` | Identified, not yet addressed |
| `in_progress` | Work underway (set when someone starts mitigating it) |
| `fixed` | Confirmed mitigated in codebase or architecture |
| `wontfix` | Accepted risk — will not fix (with reason) |
| `false_positive` | Initial threat assessment was incorrect |

**Status transitions allowed**:
- `open` ↔ `in_progress` ↔ `fixed`
- `fixed` → `open` (regression — mitigation removed)
- `open` → `wontfix` | `false_positive`
- `wontfix` → `open` (re-opened after risk re-evaluation)

**Merge rules** (when report already exists):
1. For each threat in the **existing report**:
   - Re-check the cited flow/component against current architecture and codebase
   - If the gap still exists → update `last_confirmed` to today; keep status
   - If the gap is closed → mark `fixed`, set `resolved_date`
2. For each **new threat** discovered in this scan:
   - Check if it already exists (same flow + same category)
   - If truly new → add with `status: open`, `first_seen: today`, `last_confirmed: today`
3. **Scan History**: Append a new row for this scan. Never prune or edit historical rows.
4. Never delete entries. Never change existing threat IDs.

## Execution Steps

### Phase 0: Architecture Load

1. **Read the trust-boundary and DFD reference** — `docs/vault/Reference/SaaSSecurityAndFlowDiagrams.md`:
   - **Part B** — DFD L0 (context) and L1 (internal processes and stores): identify all data flows and external entities
   - **Part E** — Trust zones (Z0 Untrusted → Z5 Data), boundary crossings and controls (E2), attack surface map (E3)
   - **Part F** — Egress paths and exfiltration controls
   - **Part G** — Tenant data boundaries and org isolation layers
   - **Part H** — IAM + RBAC enforcement points

2. **Build the threat surface inventory** from the DFD. For each data flow crossing a trust boundary, note:
   - Source zone and destination zone
   - Data carried (credentials, model weights, training params, tenant data, metrics, signed URLs)
   - Existing controls (TLS, JWT, SG, IAM, RBAC middleware)
   - Flows to scrutinize: Browser → CloudFront → ALB → anvil-web, anvil-web → RDS/Redis/S3, anvil-web → Batch, Batch → S3/Redis/RDS, Cognito → anvil-web callback, MLflow ↔ anvil-web, signed S3 URLs → browser

3. **Load the OWASP tracker** — read `docs/owasp-review.md` (if present) and build a cross-reference index keyed by `(file_path, pattern_type)`. Use this to avoid duplicate evidence; instead add architecture context.

4. **Load pre-seeded context**:
   - `AGENTS.md` — Active Technologies and "What to watch out for" sections
   - `docs/vault/Specs/016 SaaS Architecture/spec.md` — for accepted architecture decisions
   - `anvil/cfg/` or `anvil/config.py` for deployment-mode config
   - Any ADRs in `docs/vault/Decisions/` related to security or auth

5. If `$ARGUMENTS` contains a path or mode keyword (`local`, `SaaS`), scope the review accordingly.

### Phase 0.5: Load Existing Report

1. Check if `docs/stride-review.md` exists.
2. If it does, read it in full and parse the threat register into a structured index keyed by `<threat-id>`.
3. Note the current status of each threat.
4. If it does not exist, start from a clean slate.

### Phase 1: Per-Category Analysis

For each of the 6 STRIDE categories below, evaluate threats per data flow and trust-zone boundary. Fire parallel background exploration agents (subagent_type="explore") for bulk code-pattern searches across independent categories.

For each threat, capture:
- **Threat ID**: Generated if new (e.g., `S-001`). Preserved if re-checking an existing one.
- **Category**: STRIDE letter (S/T/R/I/D/E) and full name
- **Severity**: CRITICAL / HIGH / MEDIUM / LOW / INFO
- **Mode**: `local`, `SaaS`, or `both`
- **Flow/Component**: The specific DFD flow or component where the threat applies (e.g., `Browser → ALB → anvil-web: JWT`)
- **Title**: Short, actionable description
- **Threat scenario**: What an attacker could do, using the trust-zone model (e.g., "An attacker in Z0 intercepts the authorization code before PKCE exchange...")
- **Gap**: The missing control or architectural weakness
- **Mitigation**: Specific architectural or code fix
- **OWASP xref**: Corresponding OWASP finding ID(s) if already tracked (e.g., `→ A07-002`)
- **First seen**: Today's date if new
- **Last confirmed**: Today's date

---

#### S — Spoofing

**Question**: Can an attacker impersonate a legitimate entity (user, service, component) at any trust-zone crossing?

**Trust-zone crossings to evaluate:**

| Crossing | What could be spoofed | Controls to verify |
|---|---|---|
| Z0 → Z1 (internet → Cognito) | End-user identity | PKCE, state param CSRF protection, redirect URI validation |
| Z1 → Z3 (Cognito callback → anvil-web) | Authorization code or JWT | PKCE code_verifier, JWKS signature verification, `iss`/`aud` claims |
| Z3 → Z3 (anvil-web → MLflow) | Service identity | Cloud Map DNS only (no mTLS), SSRF from web to MLflow |
| Z3 → Z4 (anvil-web → Batch) | Job submitter identity | IAM role assumed, job parameters signed or verified? |
| Z3 → Z5 (anvil-web → RDS/Redis/S3) | Database connection identity | IAM DB auth, Redis AUTH, S3 SigV4 |
| Z4 → Z5 (Batch pod → RDS/Redis/S3) | Compute pod identity | IAM instance role, no shared credentials |
| Browser → anvil-web (SSE) | SSE subscriber identity | Signed token on SSE endpoint, job-scoped |

**Code patterns to search (local + SaaS):**

```python
# HIGH: JWT not fully validated (missing iss/aud/exp checks)
jwt.decode(token, key, algorithms=["HS256"])  # No options for iss/aud

# HIGH: PKCE state param not validated (CSRF on OAuth callback)
@router.get("/callback")
async def callback(code: str, state: str = None):  # state not checked

# MEDIUM: SSE endpoint missing identity check
@router.get("/training/{job_id}/events")
async def stream_events(job_id: int):  # No signed-token or session check

# HIGH: Service-to-service call without identity (SSRF to internal)
async with httpx.AsyncClient() as client:
    await client.get(f"http://mlflow.internal{path}")  # Any request, no auth
```

Search scope: `anvil/api/deps.py`, `anvil/api/v1/`, `anvil/api/app.py`, `anvil/workbench.py`

---

#### T — Tampering

**Question**: Can an attacker modify data — in transit, at rest, or in processing — without detection?

**Data flows to evaluate:**

| Flow | Data at risk | Controls to verify |
|---|---|---|
| Z0 → Z1 (internet → edge) | HTTP request bodies | TLS termination at CloudFront, WAF |
| Authorization code in redirect | OAuth code | PKCE code_challenge binds code to client |
| Training hyperparams (POST /v1/training/start) | Job parameters | Input validation, Pydantic constraints |
| Model weights in S3 | `.safetensors`/`.pt` files | S3 object integrity (ETag/checksum), IAM write restrictions |
| MLflow run metadata | Experiment params, metrics | MLflow write path — is it open or gated? |
| Job events in PostgreSQL | append-only `job_events` | DB-level append-only constraints or equivalent |
| Redis metrics channel | Live metrics stream | Redis AUTH, channel namespace isolation per job |
| Signed S3 URLs | Download integrity | URL TTL, key scope |
| Local SQLite database | All app state | File permissions, no network exposure |

**Code patterns to search:**

```python
# HIGH: Model files loaded without hash verification
torch.load("data/models/some_model.pt")   # No checksum check
with open(path, "rb") as f:
    data = pickle.load(f)                 # Tamperable + RCE risk

# MEDIUM: Pydantic model fields with no constraints (tamperable via oversized input)
class TrainingParams(BaseModel):
    learning_rate: float   # No ge/le bounds
    epochs: int            # No upper bound → resource exhaustion

# HIGH: MLflow experiment metadata written without authz check
mlflow.set_experiment(name)   # No org_id scoping?

# MEDIUM: Redis channel not namespaced per tenant
channel = f"job:{job_id}"   # Missing org_id prefix → cross-tenant channel guess
```

Search scope: `anvil/services/`, `anvil/api/v1/`, any MLflow integration code, `anvil/storage/`, `data/models/`

---

#### R — Repudiation

**Question**: Can an actor (user, service, attacker) deny having performed an action, because the audit trail is incomplete or forgeable?

**Actions that require non-repudiation:**

| Action | Required evidence | Controls to verify |
|---|---|---|
| User login / session creation | Who authenticated, when, from where | Cognito event logs, session audit in anvil |
| Training job submission | Who submitted, what params, when | `job_events` row with `created_by`, timestamp |
| Dataset/corpus upload | Who uploaded, what content | Upload event logged with user identity |
| Model weight download (signed URL) | Who requested the URL, when | URL issuance logged with user/job scope |
| Admin or ops actions | Who invoked, what endpoint | Structured audit log per request |
| MLflow run creation | Which user/org created the run | MLflow `user_id` tag or equivalent |
| Delete operations | Who deleted, what, when | Soft-delete or tombstone with actor |

**Code patterns to search:**

```python
# HIGH: State-changing endpoint with no structured audit log
@router.delete("/datasets/{dataset_id}")
async def delete_dataset(dataset_id: int, session: AsyncSession = Depends(get_db)):
    await dataset_service.delete(session, dataset_id)
    # No log of who deleted what

# HIGH: Silent exception handling hides action outcomes
try:
    await do_important_thing()
except Exception:
    pass   # Action may have partially succeeded — no record

# MEDIUM: print() instead of structured logger (not parseable for SIEM)
print(f"Job {job_id} started by user {user_id}")

# HIGH: No request-level audit context (user/org not attached to log entry)
logger.info(f"Training started: job_id={job_id}")   # Missing user/org identity
```

Search scope: `anvil/api/v1/`, `anvil/services/`, `anvil/supervisor/`, `anvil/workbench.py`

---

#### I — Information Disclosure

**Question**: Can an attacker gain access to data they should not see — in transit, at rest, in errors, or through side channels?

**Data flows and stores to evaluate:**

| Asset | Confidentiality requirement | Controls to verify |
|---|---|---|
| JWT / session tokens | Must not leak in logs, URLs, errors | Tokens not in query params, not logged |
| Database credentials / secrets | Must never appear in code or logs | Secrets Manager, env vars, no hardcoding |
| Tenant training data (corpora/datasets) | Org-isolated — invisible to other orgs | RBAC middleware + repo WHERE org_id |
| Model weights in S3 | Org-isolated — signed URL scoped | IAM key policy, URL scope, short TTL |
| Exception tracebacks in API responses | Must not reveal internal paths/queries | FastAPI exception handler sanitizes |
| MLflow experiment data | Org-isolated | MLflow experiment tag filter |
| Redis job metrics | Job-scoped — other tenants must not subscribe | Channel namespace, AUTH |
| `ANVIL_*` environment variables | Must not be returned by any API endpoint | No env-dump endpoint, no debug mode in prod |
| Log files | Must not contain PII, tokens, or tenant data | Log scrubbing / structured logging review |

**Code patterns to search:**

```python
# CRITICAL: Hardcoded secret
SECRET_KEY = "some-hardcoded-value"
DATABASE_URL = "postgresql://user:password@host/db"

# HIGH: Token in query string (leaks in logs, referrer)
@router.get("/sse")
async def stream(token: str = Query(...)):   # Token in URL

# HIGH: Stack trace in error response
return JSONResponse(
    content={"error": str(exc), "traceback": traceback.format_exc()},
    status_code=500
)

# HIGH: Logging a token or credential
logger.debug(f"Auth header: {request.headers.get('Authorization')}")

# HIGH: CORS wildcard (any origin reads response body)
app.add_middleware(CORSMiddleware, allow_origins=["*"])

# MEDIUM: Debug endpoint exposing config/env
@router.get("/debug/config")
async def debug_config():
    return os.environ   # Exposes all env vars
```

Search scope: All `.py`, `.env*`, `Dockerfile`, `compose.*`, `anvil/api/`, `anvil/cfg/`, `anvil/workbench.py`

---

#### D — Denial of Service

**Question**: Can an attacker (or runaway legitimate user) exhaust resources and make the system unavailable to others?

**Attack vectors to evaluate per layer:**

| Layer / Flow | DoS vector | Controls to verify |
|---|---|---|
| Z0 → Z1 (internet → CloudFront/WAF) | HTTP flood, large payloads | WAF rate limiting, CloudFront DDoS shield |
| Z1 → Z3 (ALB → anvil-web) | Slow clients, connection exhaustion | ALB idle timeout, ECS task limits |
| POST /v1/training/start | Unlimited job submission | Per-user/org job concurrency limit |
| POST upload endpoints | Arbitrarily large file upload | Body size limit on FastAPI/uvicorn |
| SSE endpoint | Holding connections open indefinitely | Connection timeout, max connections per user |
| Compute tier (Batch) | Submitting jobs that consume all Batch capacity | Batch job queue concurrency limits |
| MLflow (internal) | Write-flooding MLflow metrics | MLflow write rate, internal SG |
| Redis | Unlimited pub/sub channel creation | Redis memory limit, channel TTL |
| SQLite (local mode) | Large write operations blocking the single file | WAL mode, no network exposure |
| MCP autostart (local mode) | Multiple simultaneous MCP calls launching processes | `process.start` lock + pidfile |

**Code patterns to search:**

```python
# HIGH: No body size limit on upload
@router.post("/corpora/{corpus_id}/upload")
async def upload(file: UploadFile):   # No size check

# HIGH: No concurrency limit on training job submission
@router.post("/training/start")
async def start_training(params: TrainingParams):
    await training_service.submit(params)   # No per-user concurrency check

# MEDIUM: uvicorn started without limit_concurrency or timeout
uvicorn.run(app, host="0.0.0.0", port=8080)   # No timeout_keep_alive override

# HIGH: SSE endpoint without connection limits
@router.get("/training/{job_id}/events")
async def stream_events(...):
    async def event_generator():
        while True:   # No max-duration guard
            yield ...

# MEDIUM: Redis subscribe without TTL or cleanup on disconnect
async def subscribe_job_channel(job_id: int):
    pubsub = redis.pubsub()
    await pubsub.subscribe(f"job:{job_id}")
    # No cleanup on client disconnect
```

Search scope: `anvil/api/v1/`, `anvil/api/app.py`, `anvil/workbench.py`, `anvil/services/`, compose files

---

#### E — Elevation of Privilege

**Question**: Can an attacker (or an unprivileged user) gain capabilities beyond their intended authorization level — by exploiting trust assumptions, RBAC gaps, or privilege boundaries between zones?

**Privilege boundaries to evaluate:**

| Boundary | EoP vector | Controls to verify |
|---|---|---|
| Viewer → Admin within same org | RBAC role not enforced on mutation endpoints | `require_management_action` guard on every write |
| User Org A → User Org B data | Missing `org_id` scope on repo queries | Every repo query includes `WHERE org_id = ctx.org_id` |
| Batch pod → arbitrary AWS actions | Over-permissive IAM instance role | Least-privilege IAM policy for Batch pod role |
| anvil-web ECS task → arbitrary AWS actions | Over-permissive ECS task role | Least-privilege IAM for web task role |
| Anonymous → authenticated API | Missing auth dependency on any route | All `/v1/*` routes have `Depends(auth)` |
| Local user → arbitrary OS commands | Command injection from training params | No `subprocess` with user-controlled args |
| Jupyter/MLflow notebook → host | If notebook execution exposed | MLflow tracking server: no notebook exec exposed |
| Local mode (no auth) → SaaS mode confusion | Auth bypass if `ANVIL_MODE` check missing | Mode guard on every auth bypass |

**Code patterns to search:**

```python
# CRITICAL: Route without auth dependency
@router.post("/training/start")
async def start_training(params: TrainingParams):   # Missing Depends(auth)
    ...

# HIGH: RBAC guard missing on a mutation endpoint
@router.delete("/datasets/{dataset_id}")
async def delete_dataset(dataset_id: int, db: AsyncSession = Depends(get_db)):
    await repo.delete(dataset_id)   # No require_management_action() check

# HIGH: Repository query without org_id filter
async def list_corpora(session: AsyncSession) -> list[Corpus]:
    result = await session.execute(select(Corpus))   # Missing WHERE org_id

# CRITICAL: subprocess with user-controlled argument
subprocess.run(["train", user_params["script"]], shell=True)

# HIGH: ANVIL_MODE check missing — local auth bypass leaks into SaaS
if ANVIL_MODE == "local":
    return  # Skips auth — but what if mode detection is wrong?
```

Search scope: `anvil/api/v1/`, `anvil/api/deps.py`, `anvil/services/`, `anvil/db/repositories/`, `anvil/workbench.py`

---

### Phase 2: Deep-Dive for Critical and High Threats

For threats rated `CRITICAL` or `HIGH`:
1. Read the surrounding 20 lines of context to confirm the threat is real (not a false positive)
2. Check for compensating controls (e.g., RBAC applied at router level vs. per-route; WAF rate limit compensating for missing app-level rate limit)
3. Confirm or downgrade the severity
4. Check if a corresponding OWASP finding already captures the code-level evidence — if so, reference it and add only the architecture/DFD context

### Phase 3: Merge & Reconcile

After completing the scan:

1. **Build the new-threats index**: keyed by `(flow_or_component, category)` for deduplication
2. **Process existing threats** (if report existed):
   - Re-check cited flow/component against current architecture and codebase
   - Apply status transitions per the merge rules above
   - Carry forward all old threats (even resolved ones) into the new report
3. **Merge new threats**: check for duplicates; assign new IDs if truly new (sequential within category: e.g., highest existing `S-N` + 1)
4. **Preserve history**: Never drop resolved/fixed entries.

### Phase 4: Report Generation

Write the merged report to `docs/stride-review.md` with the following structure:

```markdown
# STRIDE Threat Model Review

**Living task-tracking report.** Last updated: <YYYY-MM-DD>
**Scope**: <local / SaaS / both — path if scoped>
**DFD reference**: `docs/vault/Reference/SaaSSecurityAndFlowDiagrams.md`
**OWASP cross-reference**: `docs/owasp-review.md`
**Reviewer**: Sisyphus (agent)

---

## Scan History

_A chronological log of every scan run. Newest first._

| Scan Date | New Threats | Resolved | Regressed | Total Open | Scope |
|-----------|-------------|----------|-----------|------------|-------|
| <YYYY-MM-DD> | +N | -N | +N | N | <scope> |

_This section grows with each scan — never prune rows._

---

## Progress Summary

| Metric | Value |
|--------|-------|
| Total threats (all time) | **N** |
| Currently open | **X** |
| In progress | **Y** |
| Fixed / resolved | **Z** |
| Wontfix / False positive | **W** |
| Resolved rate | **P%** |

### Open Threats by Category

| Category | Open | Critical | High |
|----------|------|----------|------|
| S — Spoofing | N | N | N |
| T — Tampering | N | N | N |
| R — Repudiation | N | N | N |
| I — Information Disclosure | N | N | N |
| D — Denial of Service | N | N | N |
| E — Elevation of Privilege | N | N | N |

### Open Threats by Severity

| Severity | Count |
|----------|-------|
| CRITICAL | N |
| HIGH | N |
| MEDIUM | N |
| LOW | N |
| INFO | N |

### Trend Since Last Review

- New threats added: +N
- Threats resolved: −N
- Threats regressed: +N

> ⚠️ **Top 3 Risks**:
> 1. ...

---

## Flat Threat Register (All Categories)

_A single flat table covering every threat across all STRIDE categories. Sortable by status (open first), severity, or date._

| ID | Cat | Sev | Status | Mode | Flow / Component | Title | OWASP xref | First Seen | Last Confirmed | Resolved |
|----|-----|-----|--------|------|-----------------|-------|------------|------------|----------------|----------|
| S-001 | S | HIGH | open | SaaS | Browser→Cognito callback | PKCE state param not verified | → A07-002 | 2026-10-04 | 2026-10-04 | — |
| T-001 | T | MEDIUM | open | both | Batch→S3: model weights | No checksum on model load | → A08-001 | 2026-10-04 | 2026-10-04 | — |
| ... | ... | ... | ... | ... | ... | ... | ... | ... | ... | ... |

_Sort order: open/in_progress first (by severity desc), then fixed/wontfix (by resolved_date desc)._

---

## Detailed Threat Register

_Per-category context for each threat — scenario, gap, mitigation, and DFD flow._

### S — Spoofing

| ID | Severity | Status | Mode | Flow / Component | Title | First Seen | Last Confirmed | Resolved |
|----|----------|--------|------|-----------------|-------|------------|----------------|----------|
| S-001 | HIGH | open | SaaS | Browser→Cognito→anvil-web: OAuth callback | PKCE state param not verified | 2026-10-04 | 2026-10-04 | — |

#### S-001: [Title]
- **Severity**: HIGH
- **Status**: open
- **Mode**: SaaS
- **Flow**: Browser → Z1 (Cognito) → Z3 (anvil-web /callback)
- **DFD ref**: Part B, B2; Part E, E1 Zone 1→3 crossing
- **First seen**: 2026-10-04
- **Last confirmed**: 2026-10-04
- **Threat scenario**: An attacker initiates a parallel OAuth flow and injects their authorization code into the victim's session (CSRF on the callback). Without `state` parameter verification, the victim's session is bound to the attacker's identity.
- **Gap**:
  ```python
  # callback does not verify state matches session-stored nonce
  ```
- **Mitigation**:
  ```python
  # Generate and store a cryptographically random state nonce in session before redirect
  # Verify state == session["oauth_state"] on callback; reject if mismatch
  ```
- **OWASP xref**: → A07-002 (if tracked)
- **Notes**: Mitigated in SaaS mode by Cognito Hosted UI's built-in PKCE; verify anvil's /callback handler validates the PKCE `code_verifier` and `state`.

[Repeat for each threat in this category]

### T — Tampering
...

### R — Repudiation
...

### I — Information Disclosure
...

### D — Denial of Service
...

### E — Elevation of Privilege
...

---

## Architecture Observations

Observations about structural gaps in the trust model that span multiple STRIDE categories or require architectural changes (not just code fixes).

---

## STRIDE ↔ OWASP Coverage Map

_Cross-reference showing which STRIDE threats map to existing OWASP findings, and which are architecture-level gaps with no OWASP equivalent._

| STRIDE ID | STRIDE Title | OWASP xref | Coverage |
|-----------|-------------|------------|---------|
| S-001 | ... | A07-002 | OWASP covers code evidence; STRIDE adds DFD context |
| D-002 | ... | — | Architecture gap — no OWASP equivalent |

---

## Recommendations (Priority Order)

1. **Immediate** (CRITICAL): ...
2. **Short-term** (HIGH): ...
3. **Medium-term** (MEDIUM): ...

---

_Generated by `/stride-review` command | Last full scan: <YYYY-MM-DD>_
```

### Phase 4.5: Write Running Tracker CSV

After the markdown report is written, generate or update `docs/stride-tracker.csv` with ALL threats (all statuses) in CSV format:

```
threat_id,category,severity,status,mode,flow_component,title,owasp_xref,first_seen,last_confirmed,resolved_date,notes
S-001,S,HIGH,open,SaaS,"Browser→Cognito→anvil-web: OAuth callback","PKCE state param not verified","A07-002",2026-10-04,2026-10-04,,"Verify state nonce in /callback handler"
T-001,T,MEDIUM,open,both,"Batch→S3: model weights","No checksum on model load","A08-001",2026-10-04,2026-10-04,,"torch.load without hash check"
```

**CSV formatting rules:**
- No spaces after commas in the header row
- Fields containing commas MUST be double-quoted
- Quoted fields escape internal double quotes as `""`
- Date format: `YYYY-MM-DD`
- Empty cells: leave blank (no space between commas)
- Sorting: open/in_progress first (sorted by severity CRITICAL→HIGH→MEDIUM→LOW→INFO, then by threat_id), then fixed/wontfix/false_positive (sorted by resolved_date descending, then threat_id)

### Phase 5: Summary

After writing the report and CSV, print a brief summary to the user:
- **Threats delta**: X new, Y resolved, Z regressed since last scan
- **Open burden**: N open (X critical, Y high) across N STRIDE categories
- **OWASP overlap**: N threats already tracked in OWASP review; N are architecture-only gaps
- **Outputs**: `docs/stride-review.md` (markdown) and `docs/stride-tracker.csv` (CSV)
- **Top 3 things to fix first** (by severity × exploitability × architectural blast radius)

## Context

$ARGUMENTS
