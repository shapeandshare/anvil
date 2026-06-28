---
title: 034 SaaS One-Command Deploy - data-model
type: data-model
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

# Data Model: SaaS One-Command Deploy

This model defines the local state files managed by the deploy CLI: the deploy configuration (`deploy-config.json`), the cluster registry (`clusters.json`), and the admin credentials file. No database schema changes — the deploy CLI reads/writes only local filesystem state.

## Local File Layout

```
~/.anvil/
├── deploy-config.json        # Per-deployment configuration (one per stack)
├── clusters.json             # Multi-cluster registry (one file for all known clusters)
├── admin-credentials         # Admin username + temporary password (created by init, cleaned by destroy)
└── credentials/              # CLI remote JWT cache (0600 permissions)
```

## Entity: Deploy Config

Stored at `~/.anvil/deploy-config.json`. One config per deployment stack. Created by `anvil deploy init`, read by all lifecycle commands.

```json
{
  "stack_name": "anvil-prod",
  "region": "us-east-1",
  "domain": "models.example.com",
  "route53_zone_id": "Z1234567890",
  "cognito_domain": "auth.models.example.com",
  "admin_email": "admin@example.com",
  "social_providers": ["Google", "GitHub"],
  "container_image_tag": "v1.2.3",
  "instance_size": "medium",
  "alert_target": "arn:aws:sns:us-east-1:123456789012:anvil-alerts",
  "deployed_at": "2026-06-19T00:00:00Z"
}
```

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `stack_name` | `string` | Yes | CloudFormation stack name (`anvil-{env}`) |
| `region` | `string` | Yes | AWS region (e.g., `us-east-1`) |
| `domain` | `string` | Conditional | Custom domain (required for production; omitted for dev) |
| `route53_zone_id` | `string` | Conditional | Route53 hosted zone ID (required if domain is set) |
| `cognito_domain` | `string` | Yes | Cognito Hosted UI domain prefix |
| `admin_email` | `string` | Yes | Admin user email for initial account |
| `social_providers` | `string[]` | No | Deployed social identity providers (post-deploy via `set-idp`) |
| `container_image_tag` | `string` | Yes | Current deployed image tag/digest |
| `instance_size` | `string` | Yes | Deployment size tier (`small`, `medium`, `large`) |
| `alert_target` | `string` | No | SNS topic ARN or webhook URL for alert routing (FR-054e) |
| `deployed_at` | `string` (ISO 8601) | Yes | Timestamp of deployment or last update |

### Validation Rules

- `stack_name` matches `^[a-zA-Z][-a-zA-Z0-9]*$` (CFN naming constraint)
- `region` is a valid AWS region identifier
- `instance_size` is one of `small`, `medium`, `large`
- All date fields are ISO 8601 UTC

### Env-var Overrides (CI Mode)

When `ANVIL_DEPLOY_*` env vars are set, they override corresponding config fields. Resolution order: env var > config file > prompt (interactive) or fail (non-interactive).

| Env var | Overrides |
|---------|-----------|
| `ANVIL_DEPLOY_STACK_NAME` | `stack_name` |
| `ANVIL_DEPLOY_REGION` | `region` |
| `ANVIL_DEPLOY_DOMAIN` | `domain` |
| `ANVIL_DEPLOY_ROUTE53_ZONE_ID` | `route53_zone_id` |
| `ANVIL_DEPLOY_ADMIN_EMAIL` | `admin_email` |
| `ANVIL_DEPLOY_INSTANCE_SIZE` | `instance_size` |
| `ANVIL_DEPLOY_ALERT_TARGET` | `alert_target` |
| `ANVIL_DEPLOY_IMAGE_TAG` | `container_image_tag` |

---

## Entity: Cluster Registry

Stored at `~/.anvil/clusters.json`. A single file tracking all known SaaS clusters the local CLI can interact with. Populated automatically by `deploy init`, cleaned by `deploy destroy`, also managed by `anvil remote cluster add/list/remove`.

```json
{
  "active": "prod",
  "clusters": [
    {
      "name": "prod",
      "url": "https://models.example.com",
      "api_url": "https://models.example.com/v1",
      "region": "us-east-1",
      "auth_method": "deploy",
      "cognito_domain": "auth.models.example.com",
      "api_version": "1.0",
      "deployed_at": "2026-06-19T00:00:00Z",
      "last_login": "2026-06-20T12:00:00Z"
    },
    {
      "name": "staging-eu",
      "url": "https://staging.anvil.io",
      "api_url": "https://staging.anvil.io/v1",
      "region": "eu-west-1",
      "auth_method": "device_grant",
      "cognito_domain": "auth.staging.anvil.io",
      "api_version": "1.0",
      "deployed_at": "2026-06-18T00:00:00Z",
      "last_login": null
    }
  ]
}
```

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `active` | `string` | No | Name of the active/default cluster |
| `clusters[]` | `array` | Yes | Array of cluster objects |

#### Cluster Object

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | `string` | Yes | Cluster alias (stack name for auto-added; user-chosen for manual) |
| `url` | `string` | Yes | CloudFront URL or custom domain |
| `api_url` | `string` | Yes | API base URL (`{url}/v1`) |
| `region` | `string` | Yes | AWS region the cluster is deployed in |
| `auth_method` | `string` | Yes | One of `deploy` (deploy CLI managed) or `device_grant` (OAuth2 device grant) |
| `cognito_domain` | `string` | Conditional | Cognito Hosted UI domain (required for device_grant auth) |
| `api_version` | `string` | Yes | API version from `GET /v1/version` (FR-014c) |
| `deployed_at` | `string` (ISO 8601) | Yes | When the cluster was deployed |
| `last_login` | `string` (ISO 8601) or `null` | Yes | Last successful login, or null if never logged in |

### Validation Rules

- `name` is unique across all clusters
- `auth_method` is one of `deploy` or `device_grant`
- `api_version` matches `^\d+\.\d+$` (semver major.minor)
- At most one cluster can have `auth_method: "deploy"` per deploy config

---

## Entity: Admin Credentials

Stored at `~/.anvil/admin-credentials` (plain text, `0600` permissions). Created by `deploy init`, cleaned by `deploy destroy`.

```
# anvil admin credentials for stack: anvil-prod
# Created: 2026-06-19T00:00:00Z
# CloudFront URL: https://d123.cloudfront.net
# Login URL: https://models.example.com

Admin email: admin@example.com
Temporary password: <cognito-generated-password>
```

### Security Notes

- File permissions MUST be `0600` (user-read/write only)
- The temporary password is the Cognito-generated one from `admin-create-user`
- The admin is prompted to change password on first login
- File is deleted by `deploy destroy`

---

## Entity: CloudFormation Stack Outputs

Captured from `cloudformation.describe_stacks` after successful deployment. Not persisted to disk — resolved dynamically.

| Output Key | Type | Description |
|------------|------|-------------|
| `CloudFrontURL` | `string` | CloudFront distribution URL (`https://d123.cloudfront.net`) |
| `CustomDomainURL` | `string` | Custom domain URL (if configured) |
| `AuthDomain` | `string` | Cognito Hosted UI domain |
| `UserPoolId` | `string` | Cognito User Pool ID |
| `AppClientId` | `string` | Cognito app client ID |
| `WebServiceUrl` | `string` | ALB URL (internal) |
| `DataBucketName` | `string` | S3 data bucket name |
| `MlBucketName` | `string` | S3 MLflow bucket name |

---

## Entity: Verify Report (--json output)

Machine-readable output from `anvil deploy verify --json`. Each layer produces an array of check results.

```json
{
  "layers": {
    "infra": {
      "passed": 12,
      "failed": 0,
      "checks": [
        {"name": "StackStatus", "passed": true, "detail": "CREATE_COMPLETE"},
        {"name": "ECSService_Web", "passed": true, "detail": "runningCount=2 desiredCount=2"},
        ...
      ]
    },
    "api": {
      "passed": 12,
      "failed": 0,
      "checks": [
        {"name": "CreateTestUser", "passed": true},
        {"name": "HealthCheck", "passed": true},
        ...
      ]
    },
    "browser": {
      "passed": 4,
      "failed": 0,
      "checks": [
        {"name": "HostedUIRedirect", "passed": true},
        ...
      ]
    }
  },
  "overall": "passed"
}
```