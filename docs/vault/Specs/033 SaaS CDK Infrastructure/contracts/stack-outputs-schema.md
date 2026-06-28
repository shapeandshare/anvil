---
title: CDK Stack Outputs Contract
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

# Contract: CDK Stack Outputs Schema

## Purpose

Defines the CloudFormation stack outputs produced by the `AnvilStack` CDK construct. These outputs are consumed by:

- The `deploy` CLI (`anvil/deploy/cloudformation.py`) for stack status and URL retrieval
- The `verify` CLI for infrastructure layer checks
- Dependent specs (030 Cognito Auth, 032 Durable Training, 036 Observability) for resource references
- The `anvil/_saas/app.py` factory for SaaS-mode configuration

## Output Schema

| Output Key | Type | Description | Source Construct | Consumer |
|------------|------|-------------|------------------|----------|
| `CloudFrontURL` | `string` | CloudFront distribution URL (e.g. `https://d123.cloudfront.net`) | cloudfront.ts | Deploy CLI, quickstart, browser access |
| `ALBDNSName` | `string` | ALB DNS name (`anvil-123.elb.amazonaws.com`) | networking.ts | CloudFront origin, deploy verify (Layer 1) |
| `VpcId` | `string` | VPC ID (`vpc-12345678`) | networking.ts | Deploy verify, cross-stack |
| `WebServiceSecurityGroupId` | `string` | Web ECS service security group ID | networking.ts | Cross-stack references |
| `RDSProxyEndpoint` | `string` | RDS Proxy endpoint hostname | database.ts | 032 Durable Training, `_saas/app.py` |
| `RDSProxyPort` | `number` | RDS Proxy port (`5432`) | database.ts | 032 Durable Training, `_saas/app.py` |
| `RedisPrimaryEndpoint` | `string` | ElastiCache Redis primary endpoint | redis.ts | 032 Durable Training, `_saas/app.py` |
| `RedisPort` | `number` | Redis port (`6379`) | redis.ts | 032 Durable Training, `_saas/app.py` |
| `DataBucketName` | `string` | S3 data bucket name (`anvil-data-{env}`) | s3-storage.ts | 032 Durable Training, deploy CLI |
| `MlBucketName` | `string` | S3 MLflow bucket name (`anvil-ml-{env}`) | s3-storage.ts | MLflow config, deploy verify |
| `CognitoUserPoolId` | `string` | Cognito User Pool ID | cognito-auth.ts | 030 Cognito Auth, `_saas/app.py` |
| `CognitoAppClientId` | `string` | Cognito app client ID | cognito-auth.ts | 030 Cognito Auth, `_saas/app.py` |
| `CognitoAuthDomain` | `string` | Cognito Hosted UI domain | cognito-auth.ts | 030 Cognito Auth |
| `EcsClusterName` | `string` | ECS cluster name | ecs-services.ts | Deploy CLI, deploy verify |
| `MlflowServiceDiscoveryArn` | `string` | Cloud Map service ARN for MLflow | ecs-services.ts | MLflow internal routing |
| `BatchCpuQueueArn` | `string` | Batch CPU job queue ARN | batch-environment.ts | 032 Durable Training |
| `BatchGpuQueueArn` | `string` | Batch GPU job queue ARN | batch-environment.ts | 032 Durable Training |
| `WafAclArn` | `string` | WAF web ACL ARN | cloudfront.ts | Cross-stack, security audits |

## Usage (boto3)

```python
import boto3

cfn = boto3.client("cloudformation")
response = cfn.describe_stacks(StackName="AnvilStack-dev")
outputs = {
    o["OutputKey"]: o["OutputValue"]
    for o in response["Stacks"][0]["Outputs"]
}

DATABASE_URL = (
    f"postgresql+asyncpg://anvil_worker:"
    f"{generate_iam_token(outputs['RDSProxyEndpoint'])}"
    f"@{outputs['RDSProxyEndpoint']}:{outputs['RDSProxyPort']}/anvil_app"
)
REDIS_URL = f"rediss://:{redis_token}@{outputs['RedisPrimaryEndpoint']}:{outputs['RedisPort']}/0"
```

## Versioning

The output schema is versioned with the stack. Adding a new output key is backward-compatible. Renaming or removing a key is a breaking change that requires updating all consumers. Output keys MUST be added (not changed) during the v1 lifecycle; any breaking change increments the CFN template version.
