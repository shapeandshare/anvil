---
title: 034 SaaS One-Command Deploy - plan
type: plan
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

# Implementation Plan: SaaS One-Command Deploy + Agentic Verify

**Branch**: `034-saas-one-command-deploy` | **Date**: 2026-06-27 | **Spec**: docs/vault/Specs/034 SaaS One-Command Deploy/spec.md
**Input**: Feature specification from `docs/vault/Specs/034 SaaS One-Command Deploy/spec.md`
**Parent plan**: [[Specs/016 SaaS Architecture/016 SaaS Architecture - plan|016 SaaS Architecture - plan]] (Phases 7+8)

## Summary

Add a one-command deploy CLI to the anvil package (`anvil deploy init/up/status/destroy/update/restore/config`) that deploys the full SaaS stack into any AWS account using pre-synthesized CloudFormation templates — no Node.js, no CDK CLI, no manual console steps. Includes a 3-layer agentic validation loop (`anvil deploy verify --layer infra/api/browser`) for automated post-deploy verification, plus cluster-registry auto-add/remove. The deploy CLI is gated on the `[aws]` optional extra and fails cleanly without it.

## High-Level Architecture

### Deploy CLI Structure

```
anvil/deploy/
├── __init__.py                   # Package docstring
├── command.py                    # Click/typer CLI group: init, up, destroy, update, status, restore, config
├── cloudformation.py             # CFN template loading, create-or-update, waiters, output retrieval
├── verify.py                     # 3-layer verify: infra checks, API canary, browser smoke
├── cluster_registry.py           # ~/.anvil/clusters.json read/write
└── templates/                    # Pre-synthesized CloudFormation templates (bundled in wheel)
    ├── anvil-stack.json          # Main stack template
    └── ...                       # Nested templates if CDK produces them
```

### Pipeline Integration

```
CI Build
│
├── 1. Build container image → push to GHCR (one digest)
├── 2. cdk synth → asset-free templates to cdk.out/
├── 3. Copy templates to anvil/deploy/templates/
│     └── Record image digest in template parameters
├── 4. python -m build → wheel bundles templates
└── 5. CI E2E: pip install anvil[aws] → deploy init → verify --layer api → destroy
```

### Flow: Deploy Init

```
User runs: anvil deploy init
│
├── 1. command.py checks [aws] extra availability
├── 2. cloudformation.py loads pre-synthesized template from package data
├── 3. Interactive prompts for domain, region, admin email, instance size
├── 4. cloudformation.py: create_stack() with waiter (60 min timeout)
├── 5. Post-deploy: run migration task, create admin user, bootstrap org+owner
├── 6. cluster_registry.py: add entry for this deployment
└── 7. Output URL, admin credentials, cluster name
```

### Flow: Deploy Verify

```
User runs: anvil deploy verify --layer api
│
├── 1. verify.py loads deploy config from ~/.anvil/deploy-config.json
├── 2. --layer infra: boto3 control-plane checks (12 discrete assertions)
├── 3. --layer api: headless API canary (12-step pipeline exercise)
│     ├── Cognito admin-create-user → JWT
│     ├── Health, org/team, corpus upload, training submit
│     ├── SSE subscribe, poll completion, artifact check, usage check
│     └── RBAC negative test, cleanup
├── 4. --layer browser: Playwright smoke (Hosted UI, session, SSE in page)
└── 5. Exit 0 if all layers pass, non-zero with report on failure
```

## Phasing

### Phase 1 — CI Pipeline + Template Bundling (US7 dependency)

CI step to synth asset-free CFN templates, copy into package source, record image digests. **Gate: templates bundled in wheel, `importlib.resources` can load them.**

### Phase 2 — CloudFormation Logic (US7)

`anvil/deploy/cloudformation.py` — create-or-update with waiters, output retrieval, "no updates" graceful handling, asset publishing (Lambda inline code to S3). **Gate: can deploy a test stack from CI-synth'd templates.**

### Phase 3 — Deploy Init + Status (US7)

`anvil deploy init` with interactive prompts, full stack deployment, post-deploy bootstrap (migrations, admin user, org/owner), `anvil deploy status`. **Gate G6 (init → login page).**

### Phase 4 — Agentic Verify (US7)

3-layer `anvil deploy verify` — infra checks (boto3), API canary (headless Cognito → pipeline), browser smoke (Playwright). **Gate: verify --layer api green on a deployed stack.**

### Phase 5 — Lifecycle Commands (US8)

`destroy` (S3 cleanup + final-snapshot safety), `update` (image roll), `restore --snapshot` (DR), `config set/get/list`, `config set-idp` (social BYO). **Gate G7 (lifecycle complete).**

### Phase 6 — Non-Interactive CI Mode (US8)

`ANVIL_DEPLOY_*` env var resolution, `--non-interactive` flag, `--json` machine-readable output. CI-safe destroy with `--force`. **Gate: CI pipeline can deploy and destroy without any TTY.**

### Phase 7 — Cluster Registry Integration

Auto-add on `deploy init`, remove on `deploy destroy`, `anvil remote cluster add/list/remove` for clusters not deployed by this CLI.

## Complexity Tracking

| Item | Justification |
|------|---------------|
| Pre-synthesized CFN templates via `cdk synth` in CI | Zero Node.js/CDK on user machine. AD-7 binding. |
| 3-layer verification pyramid (infra/api/browser) | User requirement — automated post-deploy validation. Each layer has different speed/coverage tradeoffs. |
| Non-interactive CI mode via `ANVIL_DEPLOY_*` | Required for CI/CD pipeline integration. Standard env-var pattern. |
| Cluster registry auto-add/remove | Keeps local CLI in sync with deployed clusters. State file pattern, not a service. |
| S3 version cleanup before destroy | Required for CFN stack deletion (S3 with objects cannot be deleted). Safety-critical. |
| Final RDS snapshot during destroy | User data protection. `DeletionPolicy: Snapshot` pattern. Snapshot incurs ongoing cost until manual delete. |

## Dependency Changes

No new dependencies. `boto3`, `redis`, `aws-jwt-verify` already declared in `[aws]` extra (from [[Specs/016 SaaS Architecture/016 SaaS Architecture - plan|016 plan]]). Playwright is a test/dev dependency only (for `--layer browser`).

## Related Documentation

- [[Reference/SaaSArchitectureDecisions|SaaS Architecture Decisions]] — AD-3, AD-6, AD-7
- [[034 SaaS One-Command Deploy - spec|spec]]
- [[034 SaaS One-Command Deploy - tasks|tasks]]
- [[034 SaaS One-Command Deploy - research|research]]
- [[034 SaaS One-Command Deploy - data-model|data-model]]