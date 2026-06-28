---
title: 033 SaaS CDK Infrastructure - research
type: research
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

# Research: SaaS CDK Infrastructure

**Phase 0 output** — resolves infrastructure research unknowns for CDK implementation planning. Lifts and refines findings from `016 SaaS Architecture - research.md` sections 2 (CloudFormation via boto3) and 4 (Batch Compute Pod Access).

---

## 1. CloudFormation Deployment via boto3 (from 016 research section 2)

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
| **Rollback** | `enable_termination_protection=False` for dev, `True` for prod |
| **package_data** | `[tool.setuptools.package-data]` → `anvil = ["deploy/templates/*.json"]` |
| **Runtime loading** | `importlib.resources.files("anvil.deploy.templates").joinpath("stack.json").read_text()` |

### Alternatives Considered

- Running CDK CLI on user machine: Requires Node.js + `cdk bootstrap`. Adds friction. Rejected.
- AWS CLI subprocess: Fragile, platform-dependent. Rejected.
- Terraform: Different toolchain, steep learning curve for team. Rejected.

---

## 2. Asset-Free Synth Strategy (AD-7)

### Decision

The CDK app MUST produce CloudFormation templates with NO CDK asset references. Container images referenced by immutable digest; Lambda code inlined or S3-versioned; no dependency on `cdk bootstrap` / CDKToolkit.

### Key Findings

| Aspect | Decision | Implementation |
|--------|----------|----------------|
| **Container images** | Digest-pinned (`@sha256:...`) from ECR | `ecs.ContainerImage.fromEcrRepository(repo, tag: digest)` with digest string from CI build |
| **Lambda code** | Inline Python or S3-uploaded zip | CDK `lambda.Code.fromInline()` or reference to versioned S3 key published by deploy CLI |
| **CDK assets** | None in final template | `cdk synth --no-version-reporting --no-path-metadata --no-asset-metadata` |
| **CDKToolkit** | Not referenced | Verify output template contains no `CDKToolkit` or `cdk-bootstrap` strings |
| **Nested stacks** | Avoid unless necessary | Single stack preferred; nested stack output is also asset-checked |
| **Synthesis command** | Full CI command | `npx cdk synth --output cdk.out/ --no-version-reporting --no-path-metadata --no-asset-metadata --app "npx ts-node bin/anvil.ts"` |
| **Verification** | Post-synth grep check | `grep -c "cdk-bootstrap" cdk.out/*.template.json` = 0 |

### Gotchas

- CDK constructs that auto-generate assets: `lambda.Code.fromAsset()`, `ecs.ContainerImage.fromAsset()`, `custom_resources`, `s3deploy.BucketDeployment`. These MUST be avoided or manually replaced.
- `ecs.ContainerImage.fromEcrRepository()` with a digest string is the safe path. `fromRegistry()` with a registry URL and digest also works for GHCR/public ECR.
- `lambda.Code.fromInline()` has a 4 KB limit for inline Python. For the post-auth trigger (simple mapping logic), inline is fine. For the reconciler Lambda (if Lambda-based), use S3 upload by the deploy CLI.

---

## 3. Batch Compute Pod Access (from 016 research section 4)

### Decision

Two distinct IAM roles (execution + job), IAM database authentication via RDS Proxy, VPC endpoints for AWS services, and Cloud Map service discovery for MLflow.

### Key Findings

| Aspect | Decision |
|--------|----------|
| **IAM execution role** | ECR pull, Secrets Manager read, CloudWatch logs |
| **IAM job role** | S3 read/write, RDS IAM connect, ElastiCache connect, KMS decrypt |
| **RDS access** | RDS Proxy + IAM database authentication (15-min tokens) — no static passwords |
| **S3 access** | Job role IAM policy with separate read/write resource ARNs, scoped by `{org_id}/` prefix |
| **MLflow from pod** | Cloud Map service discovery (`mlflow.svc.local:5000`) — HTTP, no auth needed internally |
| **Network** | Batch pods in private subnets. VPC Gateway Endpoint for S3. VPC Interface Endpoints for ECR, Secrets Manager, CloudWatch Logs. |
| **Security groups** | Batch SG → RDS Proxy SG:5432, Batch SG → Redis SG:6379, Batch SG → MLflow SG:5000 |
| **Environment** | Non-sensitive config via container overrides (`MLFLOW_TRACKING_URI`, `REDIS_HOST`, bucket names). Sensitive via Secrets Manager. |

### IAM Policy Example (Job Role)

```json
{
  "Effect": "Allow",
  "Action": ["s3:GetObject", "s3:ListBucket"],
  "Resource": ["arn:aws:s3:::anvil-data-*", "arn:aws:s3:::anvil-data-*/*"]
},
{
  "Effect": "Allow",
  "Action": ["s3:PutObject"],
  "Resource": ["arn:aws:s3:::anvil-data-*/{org_id}/models/*"]
},
{
  "Effect": "Allow",
  "Action": ["rds-db:connect"],
  "Resource": "arn:aws:rds-db:*:*:dbuser:*/anvil_worker"
}
```

---

## 4. CDK Construct Reference

### CDK Library Versions

| Library | Version (target) | Purpose |
|---------|------------------|---------|
| `aws-cdk-lib` | `^2.150` | Core CDK, all service constructs |
| `constructs` | `^10.0` | Base construct class |
| `ts-node` | Dev | TypeScript execution for CDK |
| `typescript` | Dev | TypeScript compiler |
| `@types/node` | Dev | Node.js type definitions |
| `aws-cdk` (CLI) | Dev | CDK CLI for synthesis |

### Key CDK Constructs Used

| AWS Service | CDK Construct | Notes |
|-------------|---------------|-------|
| VPC | `aws-cdk-lib/aws-ec2.Vpc` | `maxAzs: 2`, `natGateways: 2` |
| ALB | `aws-cdk-lib/aws-elasticloadbalancingv2.ApplicationLoadBalancer` | Internet-facing, SG |
| RDS | `aws-cdk-lib/aws-rds.DatabaseInstance` | PostgreSQL 16, `multiAz: true`, `backupRetention: Duration.days(7)` |
| RDS Proxy | `aws-cdk-lib/aws-rds.DatabaseProxy` | IAM auth, `requireTls: true`, default `max_connections_pool_percent: 100` |
| ElastiCache | `aws-cdk-lib/aws-elasticache.CfnReplicationGroup` | Multi-AZ, in-transit encryption, `AutomaticFailoverEnabled: true` |
| S3 | `aws-cdk-lib/aws-s3.Bucket` | `versioned: true`, `lifecycleRules: [...]` |
| ECS | `aws-cdk-lib/aws-ecs.FargateTaskDefinition`, `FargateService` | Execution role + task role split |
| Cloud Map | `aws-cdk-lib/aws-servicediscovery.PriveDnsNamespace` + `Service` | `mlflow.svc.local` |
| Batch | `aws-cdk-lib/aws-batch.*` | `ManagedComputeEnvironment`, `JobQueue`, `CfnJobDefinition` |
| Cognito | `aws-cdk-lib/aws-cognito.UserPool` + `UserPoolClient` + `UserPoolDomain` | No ALB auth |
| CloudFront | `aws-cdk-lib/aws-cloudfront.Distribution` | ALB origin, WAF, custom error pages |
| WAF | `aws-cdk-lib/aws-wafv2.CfnWebACL` | Rate limit, SQLi/XSS rules |
| Lambda | `aws-cdk-lib/aws-lambda.Function` | Inline code, `PostAuthentication` trigger |
| IAM | `aws-cdk-lib/aws-iam.Role` + `PolicyStatement` | Least-privilege design |
| Secrets Manager | `aws-cdk-lib/aws-secretsmanager.Secret` | `secretName: "anvil/{env}/..."` |

---

## 5. Stack Output Schema

The CDK stack produces the following outputs (consumed by the `deploy` CLI and by dependent specs):

| Output Key | Source | Consumer |
|------------|--------|----------|
| `CloudFrontURL` | CloudFront distribution `distributionDomainName` | Deploy CLI, Quickstart docs |
| `ALBDNSName` | ALB `loadBalancerDnsName` | CloudFront origin config, deploy verify |
| `CognitoUserPoolId` | User Pool `userPoolId` | 030 Cognito Auth, deploy config |
| `CognitoAppClientId` | User Pool client `userPoolClientId` | 030 Cognito Auth |
| `CognitoAuthDomain` | User Pool domain | 030 Cognito Auth, Hosted UI |
| `DataBucketName` | `anvil-data-{env}` | 032 Durable Training (S3FileStore) |
| `MLBucketName` | `anvil-ml-{env}` | MLflow artifact store |
| `RDSProxyEndpoint` | RDS Proxy endpoint | DB connection string construction |
| `RedisPrimaryEndpoint` | ElastiCache primary endpoint | 032 Durable Training (RedisEventBus) |
| `EcsClusterName` | ECS cluster `clusterName` | Migration task, deploy verify |
| `BatchCpuQueueArn` | CPU job queue ARN | 032 Durable Training (BatchJobQueue) |
| `BatchGpuQueueArn` | GPU job queue ARN | 032 Durable Training (BatchJobQueue) |
| `MlflowServiceDiscoveryArn` | Cloud Map service ARN | MLflow internal URI |
| `WebServiceSecurityGroupId` | Web service SG | Cross-stack references |
| `VpcId` | VPC ID | Cross-stack references, deploy verify |

---

## 6. RDS Proxy IAM Auth Details

### How It Works

1. RDS Proxy holds the actual DB master password (read from Secrets Manager at creation).
2. Compute pods and web tier assume an IAM role with `rds-db:connect` permission on the RDS Proxy resource.
3. At connection time, the application generates a 15-minute IAM auth token using `boto3`'s `rds.generate_db_auth_token()`.
4. RDS Proxy validates the token against the caller's IAM role and proxies the connection to RDS.

### CDK Implementation

```typescript
// RDS Proxy with IAM auth
const proxy = new DatabaseProxy(this, 'RdsProxy', {
    proxyTarget: ProxyTarget.fromInstance(database),
    secrets: [database.secret],   // Master password — RDS Proxy reads it
    iamAuth: true,                // Enable IAM database authentication
    vpc: vpc,
    securityGroups: [proxySg],
    requireTls: true,
});

// IAM policy for the task role
taskRole.addToPrincipalPolicy(new PolicyStatement({
    actions: ['rds-db:connect'],
    resources: [`arn:aws:rds-db:${region}:${account}:dbuser:${proxy.proxyId}/${dbUser}`],
}));
```

### Gotchas

- The `rds-db:connect` resource ARN uses `dbuser:*/anvil_worker` — the database user name matters. RDS Proxy maps IAM auth to a specific DB user.
- The token is valid for 15 minutes. SQLAlchemy connection pools need a token-provider callback that regenerates on each new connection (FR-045e).
- RDS Proxy adds ~15 seconds to failover time during a Multi-AZ RDS failover. Application connection retry logic must account for this.

---

## See Also

- [[033 SaaS CDK Infrastructure - spec|spec]] — CDK gate criteria, FRs
- [[033 SaaS CDK Infrastructure - plan|plan]] — implementation ordering
- [[033 SaaS CDK Infrastructure - data-model|data-model]] — stack outputs contract
- [[Specs/016 SaaS Architecture/016 SaaS Architecture - research|016 research]] — parent research
