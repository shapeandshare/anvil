# Quickstart: OWASP Security Remediation

**Phase**: 1 (Design & Contracts) | **Date**: 2026-06-21 | **Plan**: `plan.md`

## Two-Minute Verification

After implementation, verify the security controls work:

### 1. Find Your API Key

The key is NEVER printed in full to logs. On first run the console shows only a prefix hint
(e.g. `API key starts with: a3F8b2c1… — run 'anvil --show-api-key' to reveal`). Retrieve the
full key on demand:

```bash
anvil --show-api-key
# Output: the full key, printed to stdout only when explicitly requested

# Or set your own key (read once, then removed from the environment):
export ANVIL_API_KEY="my-own-strong-key"
make run
```

> Do NOT pipe `make run` output through `grep` to capture the key — the full key is intentionally
> kept out of startup logs and console output to avoid credential disclosure (review finding C-4 / FR-026).

### 2. Verify Auth Blocks Unauthenticated Requests

```bash
# API route (should fail)
curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/v1/services
# Expected: 401

# API route (should succeed with key)
curl -s -o /dev/null -w "%{http_code}" \
  -H "X-API-Key: <your-key>" \
  http://localhost:8080/v1/services
# Expected: 200

# Health endpoint (public — no auth needed)
curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/v1/health
# Expected: 200

# Web page (should redirect to login)
curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/
# Expected: 303 or 302
```

### 3. Verify Rate Limiting

```bash
for i in $(seq 1 110); do
  curl -s -o /dev/null -w "%{http_code}" \
    -H "X-API-Key: <your-key>" \
    http://localhost:8080/v1/health
done | sort | uniq -c
# Expected: 100x 200, 10x 429
```

### 4. Verify Security Headers

```bash
curl -s -I -H "X-API-Key: <your-key>" http://localhost:8080/v1/health | grep -i -E "^(content-security-policy|strict-transport-security|x-frame-options|x-content-type-options):"
# Expected: All four headers present
```

### 5. Verify Typed Validation

```bash
curl -s -X POST http://localhost:8080/v1/training/start \
  -H "X-API-Key: <your-key>" \
  -H "Content-Type: application/json" \
  -d '{"invalid_field": true}'
# Expected: 422 with {"detail": "Extra inputs are not permitted", ...}
```

## Files to Check After Implementation

| File | What Changed |
|------|-------------|
| `anvil/api/app.py` | Auth middleware, security headers, CORS, rate limiting middleware added |
| `anvil/api/deps.py` | New `get_api_key()` dependency |
| `anvil/api/templates/login.html` | New login page |
| `anvil/api/static/css/login.css` | Login page styles |
| `anvil/api/static/js/login.js` | Login page JS |
| `anvil/api/v1/schemas.py` | Field constraints added |
| `anvil/api/v1/training.py` | `body: dict` → `TrainConfig`, idempotency |
| `anvil/api/v1/corpora.py` | `body: dict` → typed, path traversal fix, `str(exc)` fix |
| `anvil/api/v1/datasets.py` | `body: dict` → typed, file size, ReDoS fix, `str(exc)` fix |
| `anvil/api/v1/content.py` | `body: dict` → typed, TOCTOU fix, `str(exc)` fix |
| `anvil/api/v1/inference.py` | `body: dict` → typed models |
| `anvil/api/v1/health_ops.py` | Service management auth, version disclosure fix |
| `anvil/supervisor/services.py` | MLflow `--allowed-hosts` fixed |
| `anvil/services/content/authz.py` | AuthzContext documented/gated |
| `anvil/services/content/local_versioned_content_store.py` | Path containment |
| `anvil/storage/local.py` | Path containment after resolve |
| `anvil/services/inference/demo_model_provider.py` | `print()` → `logger` |
| `anvil/cli.py` | `print()` → `logger` |
| `Dockerfile` | Base image digest-pinned |
| `pyproject.toml` | `torch>=2.0,<3` |
| `.github/workflows/ci.yml` | SonarCloud action SHA-pinned |