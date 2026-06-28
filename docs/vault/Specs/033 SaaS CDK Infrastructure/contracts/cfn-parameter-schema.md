---
title: CFN Parameter Schema
type: reference
tags:
  - type/spec
spec-refs:
  - docs/vault/Specs/033 SaaS CDK Infrastructure/
related:
  - '[[033 SaaS CDK Infrastructure]]'
created: '2026-06-27'
updated: '2026-06-27'
status: draft
---

# Contract: CloudFormation Parameter Schema

## Purpose

Defines the parameters accepted by the `AnvilStack` CloudFormation template. These parameters are set by the `deploy` CLI (`anvil/deploy/cloudformation.py`) during stack creation and update operations, and by the CDK app entrypoint (`packages/infra/bin/anvil.ts`) during development deployment.

## Parameter Schema

| Parameter Key | Type | Default | Allowed Values | Description |
|---------------|------|---------|----------------|-------------|
| `EnvName` | `String` | `dev` | `dev`, `staging`, `prod` | Environment name used for resource naming |
| `DomainName` | `String` | (empty) | - | Custom domain for CloudFront (empty = CloudFront URL only) |
| `HostedZoneId` | `String` | (empty) | - | Route53 hosted zone ID (required if DomainName set) |
| `ContainerImageDigest` | `String` | (required) | `sha256:[a-f0-9]{64}` | ECR image digest |
| `InstanceSize` | `String` | `small` | `small`, `medium`, `large` | Resource sizing tier |
| `BackupRetentionDays` | `Number` | `7` | `7`–`35` | RDS automated backup retention in days |
| `PreferredBackupWindow` | `String` | `03:00-04:00` | - | RDS daily backup window |
| `PreferredMaintenanceWindow` | `String` | `sun:05:00-sun:06:00` | - | RDS weekly maintenance window |
| `S3NoncurrentVersionExpiry` | `Number` | `30` | `1`–`365` | S3 noncurrent version expiry in days |
| `AdminEmail` | `String` | (empty) | - | Initial admin email (set during deploy init) |
| `EnableDeletionProtection` | `String` | `false` | `true`, `false` | Enable RDS deletion protection |
| `EnableTerminationProtection` | `String` | `false` | `true`, `false` | Enable CFN stack termination protection |
| `VpcCidr` | `String` | `10.0.0.0/16` | Valid IPv4 CIDR | VPC CIDR block |
| `SseSigningSecretArn` | `String` | (auto) | - | ARN of SSE signing secret (auto-created if empty) |
| `RedisAuthTokenArn` | `String` | (auto) | - | ARN of Redis auth token (auto-created if empty) |

## Instance Size → Resource Mapping

### small
- Web: 0.5 vCPU / 1 GB
- MLflow: 0.5 vCPU / 1 GB
- RDS: `db.t4g.small`
- Redis: `cache.t4g.small`
- Batch CPU instances: `c6i.large`
- Batch GPU instances: `g4dn.xlarge`

### medium
- Web: 1 vCPU / 2 GB
- MLflow: 1 vCPU / 2 GB
- RDS: `db.t4g.medium`
- Redis: `cache.t4g.medium`
- Batch CPU instances: `c6i.2xlarge`
- Batch GPU instances: `g4dn.2xlarge`

### large
- Web: 2 vCPU / 4 GB
- MLflow: 2 vCPU / 4 GB
- RDS: `db.r6g.large`
- Redis: `cache.r6g.large`
- Batch CPU instances: `c6i.4xlarge`
- Batch GPU instances: `g4dn.4xlarge`

## Parameter Injection (deploy CLI)

```python
cfn_params = [
    {"ParameterKey": "EnvName", "ParameterValue": "dev"},
    {"ParameterKey": "ContainerImageDigest", "ParameterValue": "sha256:abc123..."},
    {"ParameterKey": "InstanceSize", "ParameterValue": "small"},
    {"ParameterKey": "BackupRetentionDays", "ParameterValue": "7"},
    {"ParameterKey": "VpcCidr", "ParameterValue": "10.0.0.0/16"},
]

cfn.create_stack(
    StackName="AnvilStack-dev",
    TemplateBody=template_json,
    Parameters=cfn_params,
    OnFailure="ROLLBACK",
    Capabilities=["CAPABILITY_IAM"],
    Tags=[{"Key": "Project", "Value": "anvil"}],
)
```

## Parameter Injection (CDK context)

```typescript
const app = new App({
    context: {
        envName: 'dev',
        instanceSize: 'small',
        backupRetentionDays: 7,
        vpcCidr: '10.0.0.0/16',
    },
});
new AnvilStack(app, 'AnvilStack-dev', {
    env: { account, region },
    ...app.node.tryGetContext('dev'),
});
```

## Constraints

1. All parameters except `ContainerImageDigest` have defaults — the stack can synth and deploy with minimal configuration.
2. `ContainerImageDigest` is required — no default. The CDK app entrypoint or deploy CLI MUST supply it.
3. Boolean parameters (`EnableDeletionProtection`, `EnableTerminationProtection`) are `String` type with `true`/`false` values because CloudFormation Parameter types do not have a native boolean type.
4. Parameter keys are PascalCase to follow CloudFormation Parameter convention. The deploy CLI maps from `snake_case` config keys to `PascalCase` CFN keys during template loading.
5. The parameter schema is versioned with the stack. Adding a new parameter is backward-compatible. Renaming or removing a parameter is breaking.
