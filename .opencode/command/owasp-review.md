---
description: Review code against the OWASP Top 10 (2021) web application security risks and maintain a living task-tracking report.
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

The argument is an optional target path. If omitted, default to the whole project source tree.

## Goal

Review the codebase against each of the OWASP Top 10 (2021) categories, identify vulnerabilities, risky patterns, and missing controls, and maintain a **living task-tracking report** in TWO formats:

1. **Living markdown report** at `docs/owasp-review.md` — human-readable, with Scan History, Progress Summary, and Flat Finding Register.
2. **Running CSV tracker** at `docs/owasp-tracker.csv` — machine-parseable, for import into Sheets/Excel/scripts, tracking each finding's lifecycle across all runs.

If the report already exists, read it, re-check each finding against the current codebase, merge in new findings, update statuses, and write back both files.

## Operating Constraints

1. **Read-only on source**: Do not modify any source files. Findings only.
2. **Evidence-based**: Every finding must cite specific file paths and line numbers. No vague claims.
3. **Severity rating**: Every finding gets a severity — `CRITICAL`, `HIGH`, `MEDIUM`, `LOW`, or `INFO`.
4. **FP-aware**: If you're uncertain, flag as `LOW` or `INFO` and explain why it's ambiguous.
5. **Codebase-specific**: Checks must be relevant to the specific languages and frameworks in this project (Python, FastAPI, SQLAlchemy, Jinja2, JavaScript, CSS, YAML, Dockerfile, Makefile, shell scripts).
6. **Timebox**: If the codebase is large, sample a representative cross-section of each layer (API routes, services, DB repositories, static JS, templates, config files, CI/CD workflows) rather than reading every file exhaustively.
7. **Living doc discipline**: The report is the authoritative task list. Every update must preserve: finding IDs, history (first_seen, last_confirmed, resolved_date), and status transitions. Never silently drop a finding — if it's no longer present in the report, it must be explicitly marked `fixed` or `wontfix`.
8. **Tracker sync discipline**: The CSV tracker at `docs/owasp-tracker.csv` mirrors the Flat Finding Register. Both must be written in the same run with identical data. Never write one without the other.
9. **Pre-seeded context**: Review the project's existing architecture docs and known-risk notes before starting the scan. Note relevant findings from `ADRs`, `AGENTS.md`, and vault docs to avoid rediscovering documented issues.

## Finding Lifecycle Model

Every finding in the report has these fields:

```
<finding-id> | <category> | <severity> | <status> | <file:line> | <title> | <first_seen> | <last_confirmed> | <resolved_date>
```

**Statuses** (task-tracked):
| Status | Meaning |
|--------|---------|
| `open` | Identified, not yet addressed |
| `in_progress` | Work underway (set when someone starts fixing it) |
| `fixed` | Confirmed remediated in codebase |
| `wontfix` | Accepted risk — will not fix (with reason) |
| `false_positive` | Initial finding was incorrect |

**Status transitions allowed**:
- `open` ↔ `in_progress` ↔ `fixed`
- `fixed` → `open` (regression — issue reappeared)
- `open` → `wontfix` | `false_positive`
- `wontfix` → `open` (re-opened after risk re-evaluation)

**Merge rules** (when report already exists):
1. For each finding in the **existing report**:
   - Re-check the cited file:line against current codebase
   - If the vulnerable pattern still exists → update `last_confirmed` to today; keep status (unless fixed items that regressed → `open`)
   - If the vulnerable pattern is gone → mark `fixed`, set `resolved_date`
   - If the cited file no longer exists → mark `fixed` (removed), set `resolved_date`
2. For each **new finding** discovered in this scan:
   - Check if it already exists in the report (same file + same pattern type)
   - If truly new → add with `status: open`, `first_seen: today`, `last_confirmed: today`
3. **Scan History**: Read the existing Scan History table. Append a new row for this scan with today's date, count of new/resolved/regressed findings, total open, and scope. Never prune or edit historical rows.
4. Never delete entries. Never change existing finding IDs.

## Execution Steps

### Phase 0: Scope & Inventory

1. If `$ARGUMENTS` contains a path, scope the review to that path. Otherwise, review the full project.
2. **Load pre-seeded context** — read relevant project documentation before starting:
   - `AGENTS.md` — Active Technologies section for framework specifics
   - `docs/vault/Decisions/` — any ADRs related to security, auth, deployment (e.g., ADR-030 SaaS architecture for auth model)
   - `ANVIL_ENV` and config patterns from `anvil/config.py`
   - Note anything that would change finding severity (e.g., "local-only deployment = lower SSRF risk")
3. Build a quick file inventory of relevant targets:
   - Python files (`**/*.py`) — API routes, services, models, CLI, config
   - JavaScript files (`**/*.js`) — frontend code
   - HTML/Jinja2 templates (`**/*.html`)
   - CSS files (`**/*.css`)
   - Config files: `pyproject.toml`, `*.yaml`, `*.yml`, `*.env*`, `Dockerfile`, `compose.*`
   - CI/CD workflows (`.github/workflows/*.yml`)
   - Shell scripts (`**/*.sh`, `Makefile`)
4. Note the project's technology stack from `pyproject.toml` and `AGENTS.md`.

### Phase 0.5: Load Existing Report

1. Check if `docs/owasp-review.md` exists.
2. If it does, read it in full and parse the findings table into a structured index keyed by `<finding-id>`.
3. Note the current status of each finding.
4. If it does not exist, start from a clean slate.

### Phase 1: Per-Category Analysis

For each of the 10 categories below, search for vulnerable patterns using the project's specific frameworks.

Scan broadly using `grep`/`ast_grep_search` across the codebase. Fire parallel background exploration agents (subagent_type="explore") for bulk pattern searches across independent categories.

For each finding, capture:
- **Finding ID**: Generated if new (e.g., `A01-001`, `A02-001`). Preserved if re-checking an existing one.
- **Category**: The OWASP rank (A01–A10)
- **Severity**: CRITICAL / HIGH / MEDIUM / LOW / INFO
- **File**: Absolute or repo-root-relative path with line numbers
- **Title**: Short, actionable description
- **Pattern**: The specific risky code or configuration observed
- **Risk**: What an attacker could achieve
- **Recommendation**: Specific fix with code example
- **First seen**: Today's date if new
- **Last confirmed**: Today's date

#### A01 — Broken Access Control

**What to check in a FastAPI/Python project:**

| Check | Pattern to search | Why |
|-------|-------------------|-----|
| Missing auth on endpoints | Routes without `Depends(auth)` or similar in `anvil/api/v1/` | Unauthenticated access to sensitive endpoints |
| IDOR (Insecure Direct Object Reference) | Routes taking `id`/`name` path/query params without ownership check | User A accesses User B's data by changing an ID |
| HTTP method confusion | `@router.api_route` or routes allowing unintended methods | Bypassing access controls via method override |
| Mass assignment | `model_dump()` or direct dict unpacking into ORM models | User sets fields they shouldn't |
| Path traversal | `open()`, `aiofiles.open()` with user-controlled paths | Accessing files outside intended directories |
| Missing CSRF protection | Form-handling endpoints without CSRF tokens | Cross-site request forgery on state-changing actions |
| Admin/ops endpoints accessible | Ops routes without role checks | Non-admin users reaching privileged operations |
| CORS misconfiguration | `CORSMiddleware` with `allow_origins=["*"]` | Any origin can call the API from a browser |
| Unauthed WebSocket/SSE | SSE endpoints without session validation | Unauthenticated real-time data access |

Search scope: `anvil/api/v1/`, `anvil/api/app.py`, `anvil/api/deps.py`, `anvil/workbench.py`

Specific patterns:
```python
# HIGH: Route without auth dependency
@router.get("/some-resource")
async def get_resource(...):

# HIGH: CORS wide open
app.add_middleware(CORSMiddleware, allow_origins=["*"])

# HIGH: File operations with user input
aiofiles.open(f"data/{user_input}")
open(os.path.join(some_dir, user_provided_name))

# MEDIUM: Object reference from user input without ownership check
db_id = request.query_params["id"]
obj = await repo.get(db_id)  # No check: does this user own this object?
```

#### A02 — Cryptographic Failures

**What to check:**

| Check | Pattern to search | Why |
|-------|-------------------|-----|
| Hardcoded secrets | API keys, tokens, passwords in source | Credential leakage via git |
| Weak/absent TLS | HTTP-only endpoints, missing HTTPS redirect | Data in transit plaintext |
| Weak hashing | `md5`, `sha1` used for security purposes | Fast to brute-force |
| Missing encryption at rest | Sensitive data (PII, tokens) stored in DB plaintext | DB compromise leaks everything |
| Predictable random | `random` module (not `secrets`) for security contexts | Token/session ID prediction |
| Hardcoded JWT secret | Static `SECRET_KEY` string in code | JWT forgery |

Search scope: All `.py`, `.env*`, `.yaml`, `.json`, `Dockerfile`, config files

Specific patterns:
```python
# CRITICAL: Hardcoded secret
SECRET_KEY = "my-super-secret-key"
API_KEY = "sk-xxx..."

# HIGH: Weak hash for security
hashlib.md5(password.encode()).hexdigest()

# MEDIUM: Non-cryptographic random
random.choice(string.ascii_letters)  # Use secrets.choice for tokens

# HIGH: Missing algorithm/secret validation
jwt.decode(token, options={"verify_signature": False})
```

#### A03 — Injection

**What to check:**

| Check | Pattern to search | Why |
|-------|-------------------|-----|
| SQL injection | Raw SQL strings via `text()`, `execute()` with user input | SQLite/PostgreSQL injection |
| Command injection | `os.system()`, `subprocess.*` with user-controlled args | Remote command execution |
| Template injection | `render_template_string()` with user input | Jinja2 SSTI |
| Eval injection | `eval()`, `exec()`, `compile()` with untrusted input | Arbitrary code execution |
| Pickle deserialization | `pickle.loads()` from untrusted source | Remote code execution via pickle |
| YAML deserialization | `yaml.load()` (not `yaml.safe_load()`) | Arbitrary code execution via YAML tags |
| NoSQL injection | MongoDB queries with user input | Query operator injection |

Search scope: All `.py`, template files, JS

Specific patterns:
```python
# CRITICAL: Raw SQL with f-string interpolation
await db.execute(text(f"SELECT * FROM users WHERE id = {user_input}"))

# CRITICAL: Command injection
subprocess.run(f"grep {user_input} /some/file", shell=True)
os.system(f"echo {user_input}")

# CRITICAL: Template injection
from jinja2 import Template
Template(user_input).render()

# CRITICAL: Unsafe eval
eval(user_input)

# CRITICAL: Unsafe deserialization
pickle.loads(untrusted_data)
yaml.load(untrusted_data, Loader=yaml.Loader)  # Use safe_load

# HIGH: SQLAlchemy text() with f-string
stmt = text(f"SELECT * FROM items WHERE name = '{user_input}'")
```

#### A04 — Insecure Design

**What to check:**

| Check | Pattern to search | Why |
|-------|-------------------|-----|
| Missing rate limiting | No rate-limit middleware on API routes | Brute force, DoS, enumeration |
| Missing input validation | Pydantic models missing `Field(..., pattern=...)` or constraints | Unexpected input bypasses business logic |
| Trust of client-side data | Using `request.client.host` for auth decisions | IP spoofing behind proxies |
| Insufficient throttling | Training/Compute endpoints with no concurrency limits | Resource exhaustion |
| Business logic flaws | Missing state machines, no idempotency keys | Duplicate operations, race conditions |
| No request size limits | No `max_request_size` or body limits | DoS via large payloads |
| Missing security headers | No CSP, HSTS, X-Frame-Options headers | Clickjacking, XSS amplification |

Search scope: `anvil/api/`, `anvil/services/`, `anvil/workbench.py`

Specific patterns:
```python
# HIGH: No auth/ownership check on mutation
@router.delete("/datasets/{dataset_id}")
async def delete_dataset(dataset_id: int):
    # No check: does the user own this dataset?
    await dataset_service.delete(dataset_id)

# MEDIUM: Pydantic model without constraints (string fields with no max_length)
class DatasetCreate(BaseModel):
    name: str  # No max_length

# MEDIUM: No rate limiting on auth/login-like endpoints
# (check if any middleware adds rate limiting)

# INFO: Check response headers for security headers
# Content-Security-Policy, Strict-Transport-Security, etc.
```

#### A05 — Security Misconfiguration

**What to check:**

| Check | Pattern to search | Why |
|-------|-------------------|-----|
| Debug mode enabled | `debug=True` or `reload=True` in production config | Stack trace leakage, code reload |
| Verbose error responses | FastAPI exception handlers returning details in prod | Information disclosure |
| Default credentials | Default passwords, test accounts in code | Easy brute force |
| Unnecessary features | Unused endpoints, CORS origins, HTTP methods | Expanded attack surface |
| Directory listing | Static file serving without restrictions | Source code exposure |
| Stack trace leakage | Unhandled exceptions in API handlers | Internal path/query disclosure |
| Unpinned base images | `FROM python:3.11` (no digest) in Dockerfile | Supply chain via mutable tags |
| Exposed ports | Extra ports in Dockerfile/compose | Unintended service exposure |

Search scope: `anvil/api/app.py`, `Dockerfile`, `compose.*`, `anvil/api/v1/router.py`, GitHub workflows, Makefile

Specific patterns:
```python
# HIGH: Debug enabled
uvicorn.run(app, debug=True)

# HIGH: Generic exception handler leaking details
@app.exception_handler(Exception)
async def handler(request, exc):
    return JSONResponse(
        content={"error": str(exc), "traceback": traceback.format_exc()},  # Too much info
        status_code=500
    )

# MEDIUM: Unpinned Docker base image
FROM python:3.11  # No SHA256 digest

# MEDIUM: Allowed hosts / CORS too permissive
app.add_middleware(CORSMiddleware, allow_origins=["*"])
```

#### A06 — Vulnerable & Outdated Components

**What to check:**

| Check | Pattern to search | Why |
|-------|-------------------|-----|
| Unpinned dependency versions | `django>=4.0` (no upper bound) in `pyproject.toml` | Breaking/malicious changes on minor bump |
| Known-vulnerable deps | `mlflow<3.1`, `torch` version, `httpx` version | Known CVEs in specific ranges |
| Old Python version | `requires-python = ">=3.8"` (EOL) | No security patches |
| No SCA in CI | Missing `pip-audit`, `safety`, or Dependabot in workflows | Vulnerabilities go undetected |
| Lock file stale | `uv.lock` / `requirements.txt` not matching `pyproject.toml` | Installed versions differ from spec |

Search scope: `pyproject.toml`, `uv.lock`, `.github/workflows/*.yml`, `Dockerfile`

Specific checks:
```python
# Check pyproject.toml for pinned vs unpinned deps
# Check if deps like mlflow, torch, fastapi have upper bounds
# Check CI workflows for dependabot or pip-audit steps
# Check if pyproject.toml dependencies are on latest stable versions
```

#### A07 — Identification & Authentication Failures

**What to check:**

| Check | Pattern to search | Why |
|-------|-------------------|-----|
| No auth at all | Public API with no authentication middleware | Anyone can call any endpoint |
| Weak credential policy | No password complexity, no MFA support | Easy credential compromise |
| Session fixation | No session regeneration on login | Attacker pre-sets a session |
| Token in URL | Tokens passed as query params | Leakage in server logs, referrer headers |
| No session timeout | Sessions that never expire | Long-lived session hijacking |
| JWT with long expiry | `exp` claim > 24h | Stolen token usable for extended period |
| Weak JWT algorithm | `"alg": "none"` or HS256 vs RS256 | JWT confusion attacks |

Search scope: `anvil/api/deps.py`, `anvil/api/v1/`, `anvil/services/`, `anvil/workbench.py`

Specific patterns:
```python
# HIGH: No auth dependency on a state-changing endpoint
@router.post("/train")
async def start_training(params: TrainParams):
    ...

# HIGH: Token in query string
@app.get("/verify")
async def verify(token: str = Query(...)):  # Token leaks in logs

# MEDIUM: JWT with no expiry check
jwt.encode(payload={"user_id": user.id}, key=secret)

# MEDIUM: Weak/guessable session IDs
session_id = str(random.randint(100000, 999999))
```

#### A08 — Software & Data Integrity Failures

**What to check:**

| Check | Pattern to search | Why |
|-------|-------------------|-----|
| Unsafe deserialization | `pickle`, `yaml.load`, `marshal` | RCE via crafted payloads |
| CI/CD pipeline integrity | No signed commits, no branch protection | Compromised pipeline deploys malicious code |
| Dependency confusion | Private package names not scoped | Attacker publishes same name to public repo |
| Integrity verification missing | No hash checks on downloaded artifacts | Tampered dependencies in transit |
| Insecure model serialization | Loading `.pkl` or `.pt` model files without verification | Trojaned model weights |
| No signature verification | Package installs without `--require-hashes` or PEP 740 | Man-in-the-middle on package install |
| Unvalidated redirects/forwards | `RedirectResponse` with user-controlled URL | Open redirect phishing |

Search scope: All `.py`, `.github/workflows/*.yml`, `Dockerfile`, `Makefile`

Specific patterns:
```python
# CRITICAL: Unsafe deserialization
with open("model.pkl", "rb") as f:
    model = pickle.load(f)  # Arbitrary code execution

# HIGH: Open redirect
@router.get("/redirect")
async def redirect(url: str = Query(...)):
    return RedirectResponse(url)  # User-controlled redirect

# MEDIUM: Loading model files without integrity check
torch.load("data/models/some_model.pt")  # No hash verification
```

#### A09 — Security Logging & Monitoring Failures

**What to check:**

| Check | Pattern to search | Why |
|-------|-------------------|-----|
| No audit trail | State-changing operations not logged | No post-breach accountability |
| Unlogged auth failures | Login attempts not logged | Brute force goes undetected |
| No structured logging | `print()` instead of proper logger | Logs not parseable for SIEM |
| Sensitive data in logs | Logging passwords, tokens, PII | Credential leakage in log files |
| No alerting | No integration with monitoring (Grafana, CloudWatch) | Attacks invisible until breach |
| Insufficient log retention | No log rotation or retention policy | Forensic window too short |
| No user-action attribution | Actions logged without user/session context | Cannot trace who did what |

Search scope: `anvil/api/`, `anvil/services/`, `anvil/supervisor/`, `anvil/workbench.py`

Specific patterns:
```python
# HIGH: Silent exception handling (no logging)
try:
    await do_something()
except Exception:
    pass  # Silent failure — no log, no alert

# MEDIUM: Using print instead of logger
print(f"User {user_id} logged in")

# HIGH: Logging sensitive data
logger.info(f"Password reset for user: {user_input}, new hash: {pw_hash}")

# MEDIUM: Auth failure not logged
if not verify_password(input_pw, stored_pw):
    return JSONResponse({"error": "Invalid credentials"})  # No log of the attempt
```

#### A10 — SSRF (Server-Side Request Forgery)

**What to check:**

| Check | Pattern to search | Why |
|-------|-------------------|-----|
| User-controlled URL fetch | `httpx.get(user_url)`, `aiohttp.get(user_input)` | Access internal services/metadata |
| Unvalidated redirect following | `follow_redirects=True` with user URL | SSRF via redirect chain |
| Cloud metadata exposure | Requests to `169.254.169.254` | AWS/GCP/Azure credential exfiltration |
| Internal network probing | No IP allowlist on outbound requests | Port scan internal network via SSRF |
| URL scheme abuse | No scheme validation (`file://`, `gopher://`, `dict://`) | Protocol handler abuse |

Search scope: `anvil/services/`, `anvil/api/`, `anvil/storage/`

Specific patterns:
```python
# HIGH: User-controlled URL
url = request.query_params["url"]
async with httpx.AsyncClient() as client:
    resp = await client.get(url)  # SSRF if url points to internal

# HIGH: No URL validation
@router.post("/fetch-external")
async def fetch_external(url: str = Body(...)):
    response = await httpx.get(url)  # No allowlist, no scheme check

# MEDIUM: Following redirects to internal
await client.get(url, follow_redirects=True)  # SSRF via redirect chains
```

### Phase 2: Deep-Dive For Critical Patterns

For findings rated `CRITICAL` or `HIGH`:
1. Read the surrounding 20 lines of context to confirm the finding is real (not a false positive)
2. Check if there are compensating controls (e.g., auth middleware applied at router level vs. per-route)
3. Confirm or downgrade the severity

### Phase 3: Merge & Reconcile

After completing the scan and collecting all current findings:

1. **Build the new-findings index**: keyed by `(file_path, pattern_type)` for deduplication
2. **Process existing findings** (if report existed):
   - For each finding in the old report, determine its current state:
     - Check the cited file still exists
     - Check if the vulnerable pattern is still present at the cited location
     - If the file was renamed/moved, try to trace it (check git log, check similar patterns in new location)
   - Apply status transitions per the merge rules above
   - Carry forward all old findings (even resolved ones) into the new report
3. **Merge new findings**:
   - For each new finding, check if it duplicates an existing finding (same file, same pattern type)
   - If truly new, assign a new finding ID (sequential within category: e.g., highest existing `A01-N` + 1)
   - If it overlaps with an existing finding, update the existing entry's `last_confirmed` and add a note
4. **Preserve history**: Never drop resolved/fixed entries. The report's history is its value as a task tracker.

### Phase 4: Report Generation

Write the merged report to `docs/owasp-review.md` with the following structure. The **Flat Finding Register** (a single table covering all categories) and **Scan History** are the key running-list elements — easy to parse, export to CSV, and track over time.

```markdown
# OWASP Top 10 Security Review

**Living task-tracking report.** Last updated: <YYYY-MM-DD>
**Target**: <path reviewed>
**Scope**: <summary of files/lines checked>
**Reviewer**: Sisyphus (agent)

---

## Scan History

_A chronological log of every scan run. Newest first._

| Scan Date | New Findings | Resolved | Regressed | Total Open | Coverage |
|-----------|-------------|----------|-----------|------------|----------|
| <YYYY-MM-DD> | +N | -N | +N | N | <paths/files> |
| <YYYY-MM-DD> | +N | -N | +N | N | <paths/files> |

_This section grows with each scan — never prune rows._

---

## Progress Summary

| Metric | Value |
|--------|-------|
| Total findings (all time) | **N** |
| Currently open | **X** |
| In progress | **Y** |
| Fixed / resolved | **Z** |
| Wontfix / False positive | **W** |
| Resolved rate | **P%** |

### Open Findings by Severity

| Severity | Count |
|----------|-------|
| CRITICAL | N |
| HIGH | N |
| MEDIUM | N |
| LOW | N |
| INFO | N |

### Trend Since Last Review

- New findings added: +N
- Findings resolved: −N
- Findings regressed: +N

> ⚠️ **Top 3 Risks**:
> 1. ...

---

## Flat Finding Register (All Categories)

_A single flat table covering every finding across all OWASP categories. Sortable by status (open first), severity, or date. Copy-paste friendly for export to CSV/ Sheets._

| ID | Cat | Sev | Status | File:Line | Title | First Seen | Last Confirmed | Resolved |
|----|-----|-----|--------|-----------|-------|------------|----------------|----------|
| A01-001 | A01 | HIGH | open | `api/v1/train.py:42` | Missing auth on /train | 2026-06-20 | 2026-06-20 | — |
| A02-001 | A02 | CRIT | fixed | `config.py:15` | Hardcoded API key | 2026-06-15 | 2026-06-18 | 2026-06-19 |
| ... | ... | ... | ... | ... | ... | ... | ... | ... |

_Sort order: open/in_progress first (by severity desc), then fixed/wontfix (by resolved_date desc)._

---

## Detailed Finding Register

_Per-category deep context for each finding — pattern, risk, recommendation, and remediation notes._

### A01 — Broken Access Control

| ID | Severity | Status | File | Title | First Seen | Last Confirmed | Resolved |
|----|----------|--------|------|-------|------------|----------------|----------|
| A01-001 | HIGH | open | path/file.py:L12 | Missing auth on /api/endpoint | 2026-06-20 | 2026-06-20 | — |

#### A01-001: [Title]
- **Severity**: HIGH
- **Status**: open
- **File**: `path/file.py:L12-L18`
- **First seen**: 2026-06-20
- **Last confirmed**: 2026-06-20
- **Pattern**:
  ```python
  # vulnerable code snippet
  ```
- **Risk**: What an attacker could do
- **Recommendation**:
  ```python
  # fixed code snippet
  ```
- **Notes**: Any context or caveats

[Repeat for each finding in this category]

### A02 — Cryptographic Failures
...

---

## Cross-Cutting Observations

Observations that span multiple categories or don't fit neatly into one.

---

## Recommendations (Priority Order)

1. **Immediate** (CRITICAL): ...
2. **Short-term** (HIGH): ...
3. **Medium-term** (MEDIUM): ...

---

_Generated by `/owasp-review` command | Last full scan: <YYYY-MM-DD>_
```

### Phase 4.5: Write Running Tracker CSV

After the markdown report is written, generate or update `docs/owasp-tracker.csv` with ALL findings (all statuses) in CSV format:

```
finding_id,category,severity,status,file_line,title,first_seen,last_confirmed,resolved_date,notes
A01-001,A01,HIGH,open,"api/v1/train.py:42","Missing auth on /train endpoint",2026-06-20,2026-06-20,,"Route has no Depends(auth)"
A02-001,A02,CRITICAL,fixed,"config.py:15","Hardcoded API key in source",2026-06-15,2026-06-18,2026-06-19,"Moved to env var"
```

**CSV formatting rules:**
- No spaces after commas in the header row
- Fields containing commas MUST be double-quoted
- Quoted fields escape internal double quotes as `""`
- Date format: `YYYY-MM-DD`
- Empty cells: leave blank (no space between commas) — e.g. `,,` for `resolved_date` on open findings
- Sorting: open/in_progress first (sorted by severity CRITICAL→HIGH→MEDIUM→LOW→INFO, then by finding_id), then fixed/wontfix/false_positive (sorted by resolved_date descending, then finding_id)

### Phase 5: Summary

After writing the report and CSV, print a brief summary to the user:
- **Findings delta**: X new, Y resolved, Z regressed since last scan
- **Open burden**: N open (X critical, Y high)
- **Resolved rate**: P% of all-time findings
- **Outputs**: `docs/owasp-review.md` (markdown) and `docs/owasp-tracker.csv` (CSV)
- **Top 3 things to fix first** (by severity × exploitability)

## Context

$ARGUMENTS