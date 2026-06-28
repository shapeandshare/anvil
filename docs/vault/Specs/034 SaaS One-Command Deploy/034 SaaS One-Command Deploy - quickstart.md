---
title: 034 SaaS One-Command Deploy - quickstart
type: quickstart
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

# Quickstart: SaaS One-Command Deploy

## Prerequisites

### Local Deploy CLI
- Python 3.11+
- `pip install anvil[aws]`
- AWS credentials configured (env vars, `~/.aws/credentials`, or OIDC web-identity role)
- Route53 public hosted zone (for custom domain)

### CI/CD Deploy
- Same prerequisites resolved via env vars + OIDC role
- No TTY required

---

## Deploy a New Stack

### Interactive Mode

```bash
pip install anvil[aws]

anvil deploy init

# Follow the prompts:
#   Stack name [anvil-prod]:
#   Domain: models.example.com
#   Route53 zone ID: Z1234567890
#   Admin email: admin@example.com
#   Instance size [medium]:

# ~15 minutes later:
#   CloudFront URL: https://d123.cloudfront.net
#   Custom domain: https://models.example.com
#   Login: admin@example.com
#   Credentials saved to: ~/.anvil/admin-credentials
#   Cluster added to: ~/.anvil/clusters.json (name: prod)
```

### CI/CD Mode

```bash
export ANVIL_DEPLOY_STACK_NAME=anvil-ci-123
export ANVIL_DEPLOY_REGION=us-east-1
export ANVIL_DEPLOY_DOMAIN=ci-123.models.example.com
export ANVIL_DEPLOY_ADMIN_EMAIL=ci@example.com
export ANVIL_DEPLOY_INSTANCE_SIZE=small

anvil deploy up --non-interactive --json

# Output:
# {"status": "CREATE_COMPLETE", "url": "https://d456.cloudfront.net", ...}
```

---

## Verify a Deployment

```bash
# Fast infra check (~10s)
anvil deploy verify --layer infra

# Full API canary (~3-5 min, exercises auth→upload→train→SSE→artifact→usage→RBAC)
anvil deploy verify --layer api

# Full verification including Playwright browser smoke
anvil deploy verify --layer browser

# All layers in one command
anvil deploy verify

# Machine-readable CI output
anvil deploy verify --layer api --json
```

---

## Day-2 Operations

### Destroy

```bash
anvil deploy destroy

# WARNING: This destroys ALL data, RDS backups, and S3 versions.
# Take a final RDS snapshot before deleting? [Y/n]:
# Type the stack name to confirm: anvil-prod

# OR non-interactive (CI):
anvil deploy destroy --force --no-final-snapshot
```

### Update

```bash
anvil deploy update
# Or pin a specific version:
anvil deploy update --version v1.3.0
```

### Configure

```bash
anvil deploy config set instance_size large
anvil deploy config get domain
anvil deploy config list

# Add social login post-deploy (BYO OAuth credentials)
anvil deploy config set-idp --provider Google --client-id xxx --client-secret yyy
```

### Restore from Snapshot (DR)

```bash
anvil deploy restore --snapshot anvil-prod-final-20260619
```

### Check Status

```bash
anvil deploy status
# Output:
#   Stack: anvil-prod (CREATE_COMPLETE)
#   URL: https://models.example.com
#   Version: v1.2.3
```

---

## Architecture Cheatsheet

### File Layout

```
~/.anvil/
├── deploy-config.json        # Per-stack configuration (read by all lifecycle commands)
├── clusters.json             # Multi-cluster registry (auto-added by init, cleaned by destroy)
├── admin-credentials         # Admin username + temp password (0600 perms, deleted by destroy)
└── credentials/              # CLI remote JWT cache
```

### Layer Timing

| Layer | Wall time | What it validates |
|-------|-----------|-------------------|
| `--layer infra` | ~10s | CFN status, ECS health, Batch, RDS, Redis, S3, Cognito |
| `--layer api` | ~3-5 min | Full end-to-end pipeline via headless API canary |
| `--layer browser` | ~30s | Playwright smoke: login redirect, session, SSE in page |

### Safety Features

| Feature | How it works |
|---------|-------------|
| Destroy confirmation | Prompts for stack name (typed), warns of data loss |
| Final RDS snapshot | CFN `DeletionPolicy: Snapshot` — snapshot survives stack delete |
| S3 bucket cleanup | Lists+deletes ALL versions before CFN delete |
| Double-destroy | Detects non-existent stack, exits cleanly (FR-031) |
| CI safety | `--force` required for non-interactive destroy |
| No Node.js | Pre-synthesized templates bundled in pip wheel |

---

## Project Commands

```bash
# Deployment (requires anvil[aws] extra)
anvil deploy init             # Deploy full SaaS stack (interactive)
anvil deploy up               # Deploy from env vars (CI-safe)
anvil deploy destroy          # Tear down (with safety prompts)
anvil deploy update           # Upgrade to latest version
anvil deploy status           # Show deployment status
anvil deploy verify           # 3-layer agentic validation
anvil deploy restore          # DR: stand up from RDS snapshot
anvil deploy config set       # Update configuration
anvil deploy config get       # Read configuration value
anvil deploy config list      # Show all configuration
```