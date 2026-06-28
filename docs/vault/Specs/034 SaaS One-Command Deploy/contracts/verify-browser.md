---
title: Verify Layer 3 — Browser Smoke
type: spec
tags:
  - type/spec
  - domain/infrastructure
created: '2026-06-27'
updated: '2026-06-27'
---

# Verify Layer 3 — Browser Smoke (`--layer browser`)

**Contract**: Minimal Playwright-driven checks for what cannot be validated headlessly. These are smoke tests (not exhaustive UI tests). A failure indicates the deployment is not usable by real users. Requires Chromium (auto-installed by Playwright on first run).

## Prerequisites

- `playwright` Python package (installed via `pip install anvil[aws]` or dev dependencies)
- Chromium browser binary (`playwright install chromium`)
- Admin credentials from `~/.anvil/admin-credentials`
- CloudFront URL from deploy config

## Check List

### Check 1: Hosted UI Login Redirect

| Property | Value |
|----------|-------|
| **Action** | Playwright navigates to the CloudFront URL |
| **Assertion** | Browser is redirected to Cognito Hosted UI (`/login?client_id=...`) |
| **Pass condition** | URL contains the Cognito Hosted UI domain |
| **Failure indicates** | CloudFront/ALB routing is broken, or Cognito app client is misconfigured |

### Check 2: Native Login + Callback

| Property | Value |
|----------|-------|
| **Action** | Playwright fills in the admin email and temporary password, submits the form, completes password change if prompted |
| **Assertion** | Browser lands on the authenticated dashboard (URL no longer shows Cognito Hosted UI) |
| **Pass condition** | Dashboard page renders without redirect back to login |
| **Failure indicates** | Cognito user pool configuration, app client callback URL, or back-end auth middleware is broken |

### Check 3: Session Through CloudFront/ALB

| Property | Value |
|----------|-------|
| **Action** | Playwright navigates to a different page (e.g., datasets page) |
| **Assertion** | Session cookie persists; page renders authenticated content |
| **Pass condition** | Page loads without redirect to login |
| **Failure indicates** | Session/Cookie configuration (CloudFront, ALB, or app) is broken |

### Check 4: SSE in Real Page

| Property | Value |
|----------|-------|
| **Action** | Playwright starts a training job through the Web UI, watches the training page |
| **Assertion** | The loss curve updates in real-time via SSE |
| **Pass condition** | At least one metric data point appears in the loss curve within 30 seconds |
| **Failure indicates** | Training pipeline, SSE, or Redis pub/sub is broken end-to-end |

## Implementation Notes

- Social login (Google/GitHub) is NOT validated by layer 3 — it is configuration-validated only (checking IdP presence in the pool) unless the customer supplies test social identities
- Layer 3 runs Layers 1+2 first (infra must be healthy + API must work before browser smoke is meaningful)
- The `--layer browser` flag runs all three layers
- A `.env` or config override should allow skipping layer 3 when Playwright/Chromium is unavailable (CI without `--layer browser` should still pass)