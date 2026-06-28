---
title: 034 SaaS One-Command Deploy - research
type: research
tags:
  - type/spec
  - domain/infrastructure
spec-refs:
  - docs/vault/Specs/034 SaaS One-Command Deploy/
related:
  - '[[034 SaaS One-Command Deploy]]'
created: '2026-06-27'
updated: '2026-06-27'
---

# Research: SaaS One-Command Deploy — CloudFormation via boto3 + Agentic Validation

**Phase 0 / PR output** — resolves deployment and agentic-validation unknowns for the per-feature spec.

> **Provenance**: This research extracts and consolidates the deploy-relevant findings from the umbrella
> spec [[Specs/016 SaaS Architecture/016 SaaS Architecture - research|016 research]] (sections 2 and 6),
> updated for the per-feature scope of 034.

## 1. CloudFormation Deployment via boto3

### Decision

Pre-synthesize CDK templates during CI, bundle in the pip package as `package_data`, deploy via `boto3` CloudFormation client using create-or-update pattern with waiters.

### Rationale

- Zero Node.js or CDK CLI dependency on the user's machine — only Python + AWS credentials
- CDK remains the canonical infra definition for the team (in `packages/infra/`)
- CI pipeline runs `cdk synth --output cdk.out/` → packages JSON templates into the wheel
- `anvil deploy up` uses `create_stack` / `update_stack` with waiter polling

### Key Findings

| Aspect | Decision |
|--------|----------|
| **Template source** | `cdk synth` in CI → `cdk.out/AnvilStack/AnvilStack.template.json` → bundled as `anvil/deploy/templates/*.json` |
| **Deploy strategy** | Check stack exists → `create_stack` or `update_stack` (with "No updates" graceful handling) |
| **Waiters** | `get_waiter("stack_create_complete")` with `Delay=30, MaxAttempts=120` (60 min timeout) |
| **Parameters** | Dict → `[{"ParameterKey": k, "ParameterValue": v}]` format, injected per environment |
| **Outputs** | `describe_stacks` → `Stacks[0].Outputs` → `{OutputKey: OutputValue}` |
| **Stack naming** | `anvil-{env}` (e.g., `anvil-dev`, `anvil-prod`) |
| **OnFailure** | `OnFailure="ROLLBACK"` for auto-cleanup on failed creation |
| **Termination protection** | `enable_termination_protection=False` for dev, `True` for prod |
| **package_data** | `[tool.setuptools.package-data]` → `anvil = ["deploy/templates/*.json"]` |
| **Runtime loading** | `importlib.resources.files("anvil.deploy.templates").joinpath("stack.json").read_text()` |
| **Credentials** | Standard boto3 credential chain: env vars, OIDC web-identity role, `~/.aws/credentials`, instance profile. No custom credential management. |

### Alternatives Considered

- Running CDK CLI on user machine: Requires Node.js + `cdk bootstrap`. Adds friction. **Rejected.**
- AWS CLI subprocess: Fragile, platform-dependent. **Rejected.**
- Terraform: Different toolchain, steep learning curve for team. **Rejected.**

---

## 2. Asset-Free Template Constraints

### Decision

CloudFormation templates MUST be asset-free (no CDK asset parameters/buckets) with digest-pinned container images. Per AD-7.

### Implications

| Constraint | Implementation |
|------------|---------------|
| **No CDKToolkit dependency** | Template references no `cdk bootstrap` asset bucket. Stack deploys in any account without bootstrapping. |
| **Container images by digest** | `@sha256:...` in ECS task definitions, not mutable tags. Image pushed to GHCR/public ECR during CI. |
| **Lambda code** | Inline (small, <4KB) or versioned S3 object that deploy CLI publishes before stack creation. No CDK asset reference. |
| **Post-auth Lambda** | Inline in template (Python source as `ZipFile`) — small enough for CFN parameter. |
| **Reconciler** | Same image as web (AD-10), referenced by digest. |

### Key CDK flag for asset-free synth

```typescript
// In bin/anvil.ts — disable default asset behavior
const app = new cdk.App();
new AnvilStack(app, 'AnvilStack', {
  env: { account: process.env.CDK_DEFAULT_ACCOUNT, region: process.env.CDK_DEFAULT_REGION },
  // Asset-free: use inline code, digest-pinned images, no cdk bootstrap
});
```

---

## 3. Agentic Validation Pyramid

### Decision

Three layers of post-deploy verification, each with different speed and coverage characteristics. All layers runnable independently via `--layer` flag. Per FR-049/FR-050.

### Layer Breakdown

| Layer | Speed | Coverage | AWS Creds Needed | Auth Token Needed |
|-------|-------|----------|------------------|-------------------|
| **Layer 1: infra** | ~10s | AWS control-plane health | Yes | No |
| **Layer 2: api** | ~3-5 min | End-to-end pipeline (tiny job) | Yes | Yes (cognito admin) |
| **Layer 3: browser** | ~30s | UI smoke (Playwright) | No | Yes (end-user login) |

### API Canary Implementation Considerations

| Step | AWS API / HTTP | Complexity |
|------|---------------|------------|
| Create test user | `cognito-idp.admin-create-user` + `admin-set-password` | Low |
| Authenticate | `cognito-idp.admin-initiate-auth` (ADMIN_USER_PASSWORD_AUTH) | Low |
| Health check | `GET /v1/health` with JWT Bearer header | Low |
| Create org/team | `POST /v1/organizations`, `POST /v1/teams` | Medium |
| Upload corpus | `POST /v1/corpora` (signed URL upload) | Medium |
| Submit training | `POST /v1/training/start` (1 layer, 20 steps) | Medium |
| SSE subscribe | `GET /v1/training/stream/{id}?token=...` | Medium |
| Poll completion | `GET /v1/training/{id}` | Low |
| Assert artifact | `s3.head_object` + MLflow API | Low |
| Assert usage | `GET /v1/usage` | Low |
| RBAC negative | `GET /v1/corpora` as second user in different org | Low |
| Cleanup | Delete test user, delete resources | Low |

### API Canary Flow

```
1. Create native Cognito test user (cognito-idp.admin-create-user + admin-set-password)
2. Authenticate (cognito-idp.admin-initiate-auth ADMIN_USER_PASSWORD_AUTH) → JWT
3. Call GET /v1/health with JWT → 200
4. Create test org + team via API → assert RBAC rows
5. Upload a tiny corpus via signed S3 URL → assert S3 object + DB row
6. Submit a CPU training job (1 layer, 20 steps) → assert TrainingJob row, Batch job submitted
7. Open SSE stream with signed token → assert ≥1 metrics event arrives
8. Poll job to completion → assert status=completed
9. Assert model artifact in S3 + MLflow run finalized
10. Assert usage_record created with correct org_id/user_id/gpu_seconds
11. RBAC negative test: second user in different org cannot read first org's corpus → 403
12. Cleanup: delete test resources, delete test Cognito user
```

### Browser Smoke Considerations (Layer 3)

- Playwright navigates to the CloudFront URL and asserts Cognito Hosted UI redirect
- Fills in native email/password credentials and asserts dashboard is rendered
- Verifies session cookie persists across page navigation
- Starts a training job through the Web UI and asserts SSE loss curve updates live
- **Note**: Social login (Google/GitHub) is configuration-validated only (IdP present in pool) unless the customer supplies test identities — full social login round-trip requires real provider credentials beyond the scope of automated verify.

---

## 4. Deploy Config Management

### Decision

Persistent JSON config at `~/.anvil/deploy-config.json` with env-var override for CI. No TOML, no YAML. Stored in the standard XDG config location for the `anvil` CLI.

### Key Findings

| Aspect | Decision |
|--------|----------|
| **Format** | JSON (stdlib, no new dep) |
| **Location** | `~/.anvil/deploy-config.json` |
| **Env override** | `ANVIL_DEPLOY_*` supersedes file values |
| **Validation** | Pydantic model or manual schema check on load |
| **Sensitive fields** | No secrets in config (credentials are separate file `~/.anvil/admin-credentials`) |
| **Corruption handling** | Invalid JSON → warn and re-prompt interactively; fail fast in non-interactive mode |
| **Migration** | Backward-compatible key additions (unknown keys preserved, missing keys defaulted) |

### Config Schema

```json
{
  "stack_name": "anvil-prod",
  "region": "us-east-1",
  "domain": "models.example.com",
  "route53_zone_id": "Z1234567890",
  "cognito_domain": "auth.models.example.com",
  "admin_email": "admin@example.com",
  "social_providers": ["Google"],
  "container_image_tag": "v1.2.3",
  "instance_size": "medium",
  "alert_target": "arn:aws:sns:...",
  "deployed_at": "2026-06-19T00:00:00Z"
}
```

---

## 5. S3 Bucket Cleanup for Destroy

### Decision

Before deleting the CloudFormation stack, the destroy command MUST enumerate and delete ALL objects (including all versions and delete markers) in the data and MLflow S3 buckets. Buckets with remaining objects cause CFN stack deletion to fail.

### Key Findings

| Aspect | Decision |
|--------|----------|
| **API** | `s3.list_object_versions` + `s3.delete_objects` (batch of 1000) |
| **Delete markers** | MUST also delete delete markers (S3 versioning creates them on delete) |
| **Versioned delete** | Include `VersionId` in delete request for each version |
| **Order** | Delete all versions/markers first, THEN delete bucket (CFN handles bucket deletion) |
| **Safety** | The final-snapshot flag applies ONLY to RDS, NOT S3 — S3 versioning provides S3-side recovery |
| **Progress** | Output progress for large buckets (number of objects deleted) |
| **Error handling** | Continue on individual object delete failures (throttling), fail only if too many failures |

```python
# Pseudocode for S3 bucket cleanup
def empty_bucket(s3, bucket_name: str) -> None:
    paginator = s3.get_paginator("list_object_versions")
    for page in paginator.paginate(Bucket=bucket_name):
        objects = []
        for version in page.get("Versions", []):
            objects.append({"Key": version["Key"], "VersionId": version["VersionId"]})
        for marker in page.get("DeleteMarkers", []):
            objects.append({"Key": marker["Key"], "VersionId": marker["VersionId"]})
        if objects:
            s3.delete_objects(Bucket=bucket_name, Delete={"Objects": objects})
```

---

## 6. Destroy Final Snapshot

### Decision

The destroy command MUST offer (and default to YES) taking a final RDS snapshot before stack deletion. The CFN template MUST use `DeletionPolicy: Snapshot` on the RDS resource so the snapshot survives stack deletion.

### Key Findings

| Aspect | Decision |
|--------|----------|
| **Mechanism** | `DeletionPolicy: Snapshot` in CFN template (not manual `create_db_snapshot` API call) |
| **Snapshot naming** | `{stack-name}-final-{YYYYMMDD}` — auto-generated, printed in destroy output |
| **Cost warning** | User warned that snapshot incurs ongoing storage cost until manually deleted |
| **Skip flag** | `--no-final-snapshot` or `--force` skips the prompt |
| **Restore** | `anvil deploy restore --snapshot <id>` stands up new stack from snapshot (FR-061) |

### CFN Template Snippet

```json
{
  "AnvilDatabase": {
    "Type": "AWS::RDS::DBInstance",
    "DeletionPolicy": "Snapshot",
    "Properties": {
      ...
    }
  }
}
```

---

## Summary of Architecture Decisions

| Area | Decision | Impact |
|------|----------|--------|
| **Template source** | Pre-synthesized CDK in CI | Zero Node.js on user machine |
| **Template delivery** | Bundled in pip wheel as package_data | Single `pip install anvil[aws]` |
| **Deploy API** | `boto3` CloudFormation create/update/delete | Stdlib + boto3 only |
| **Auth for verify** | Cognito admin APIs (ADMIN_USER_PASSWORD_AUTH) | Headless, no browser needed for Layer 2 |
| **S3 cleanup** | List+delete all versions before CFN delete | Required for stack deletion |
| **Final snapshot** | CFN DeletionPolicy: Snapshot | Survives stack deletion, incurs cost |
| **Config storage** | `~/.anvil/deploy-config.json` + env override | XDG-compliant, CI-safe |
| **Cluster registry** | `~/.anvil/clusters.json` | Syncs CLI with deployments |