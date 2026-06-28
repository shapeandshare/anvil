# Contract: Multi-stage Dockerfile

**Feature**: `009-pip-installable-package`

Defines the contract for the rewritten root `Dockerfile`. The image MUST install anvil from a built wheel into a source-free runtime (FR-007, Q1).

## Structure (normative)

```dockerfile
# ---- Stage 1: builder — build the wheel ----
FROM python:3.11-slim AS builder
WORKDIR /src
# Copy the minimum needed to build the wheel (source + pyproject)
COPY pyproject.toml ./
COPY anvil/ anvil/
# (uv optional for speed) build a PEP 517 wheel
RUN pip install --no-cache-dir build && python -m build --wheel --outdir /dist .

# ---- Stage 2: runtime — install ONLY the wheel ----
FROM python:3.11-slim AS runtime
# Non-root user
RUN useradd --create-home --uid 1000 anvil
# Install the wheel + dependencies (NO source tree copied)
COPY --from=builder /dist/*.whl /tmp/wheels/
RUN pip install --no-cache-dir /tmp/wheels/*.whl && rm -rf /tmp/wheels
USER anvil
WORKDIR /workspace          # writable runtime workspace (data/, logs/, mlruns/)
EXPOSE 8080 5001
CMD ["anvil"]
```

## Requirements

- R-D1: The runtime stage MUST NOT `COPY` the anvil source tree — only the `.whl` from the builder (FR-007).
- R-D2: After install, `anvil` and all other console scripts MUST be on `PATH` (FR-005).
- R-D3: The container MUST run as a non-root user with a writable workspace (FR-011, read-only edge case).
- R-D4: ~~`EXPOSE 8080 5001`~~ → **SUPERSEDED by Spec 024/056**: `EXPOSE 8080` only. MLflow binds loopback and is reached via `/v1/mlflow-proxy/`; its port is not exposed (ADR-037 single-origin). See `docs/vault/Specs/056 Reverse-Proxy Registry/`.
- R-D5: `CMD` MUST launch via the `anvil` console script (FR-009), which triggers lifespan: auto-migrate + MLflow start + demo bootstrap.
- R-D6: Migrations bundled in the wheel MUST resolve and apply (no repo-root `alembic.ini`/`migrations/` dependency).
- R-D7: `.dockerignore` MUST exclude runtime artifacts and VCS metadata: `data/` (runtime DB/output), `logs/`, `mlruns/`, `.git/`. The previous `!data/demo/` negation MUST be removed — demo/seed content now lives inside the `anvil` package and is bundled by the wheel, so it is no longer needed in the build context.

## Acceptance checks

| ID | Check | Maps to |
|----|-------|---------|
| DOCK-1 | `docker build` succeeds; runtime image has no `/src` or anvil source | FR-007 |
| DOCK-2 | `docker run` → container starts, `/v1/health` returns healthy | US3, FR-009 |
| DOCK-3 | `docker run` on a base built against Python <3.11 fails fast at install | FR-006 |
| DOCK-4 | First run inside container auto-creates+migrates DB and bootstraps demo | FR-005, FR-010, FR-003a |
