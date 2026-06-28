---
title: 033 SaaS CDK Infrastructure - quickstart
type: quickstart
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

# Quickstart: SaaS CDK Infrastructure Development

## Prerequisites

- Node.js 18+ and npm
- AWS CLI configured (`aws configure`)
- Sufficient IAM permissions (AdministratorAccess or equivalent)
- Docker (for building the container image)
- Route53 public hosted zone (if using custom domain)
- Python 3.11+ (for the deploy CLI — separate from CDK dev)

## CDK Dev Setup

```bash
# Navigate to the infra package
cd packages/infra

# Install dependencies
npm ci

# Verify CDK is available
npx cdk --version
```

## CDK Development Workflow

### 1. Synthesize the CDK Stack

```bash
# Quick synth (validate construct tree compiles)
npx cdk synth

# Full synth with environment parameters
ANVIL_ENV=dev npx cdk synth

# Prod
ANVIL_ENV=prod npx cdk synth
```

### 2. Diff Against Deployed Stack

```bash
# See what changes would be applied
ANVIL_ENV=dev npx cdk diff AnvilStack-dev

# Use context parameters for custom settings
npx cdk diff AnvilStack-dev \
    --context envName=dev \
    --context instanceSize=small
```

### 3. Deploy to Dev AWS

```bash
# Full deploy (creates or updates CloudFormation stack)
ANVIL_ENV=dev npx cdk deploy AnvilStack-dev

# With hotswap for faster iteration (container image updates only)
ANVIL_ENV=dev npx cdk deploy AnvilStack-dev --hotswap

# Watch mode — auto-deploy on file changes
ANVIL_ENV=dev npx cdk watch AnvilStack-dev
```

### 4. Post-Deploy Verification

```bash
# Check stack outputs
aws cloudformation describe-stacks \
    --stack-name AnvilStack-dev \
    --query "Stacks[0].Outputs"

# Check ECS service health
aws ecs describe-services \
    --cluster AnvilStack-dev-AnvilEcsCluster-ABC123 \
    --services AnvilWebService-ABC123

# Verify CloudFront distribution
aws cloudfront get-distribution \
    --id E1234567890ABC

# Verify Cognito User Pool
aws cognito-idp describe-user-pool \
    --user-pool-id us-east-1_ABC123
```

### 5. Full CI Synth (Asset-Free Template Bundle)

```bash
# The CI pipeline runs:
cd packages/infra
npm ci
npx cdk synth \
    --output cdk.out/ \
    --no-version-reporting \
    --no-path-metadata \
    --no-asset-metadata \
    --context envName=dev

# Verify no CDK bootstrap dependencies
grep -c "cdk-bootstrap" cdk.out/AnvilStack-dev.template.json
# Expected: 0

# Copy templates to Python package
cp cdk.out/*.template.json ../../anvil/deploy/templates/
```

## CDK Construct Architecture

```text
packages/infra/
├── bin/anvil.ts                    # CDK app entrypoint
├── lib/
│   ├── anvil-stack.ts              # Main stack orchestrator
│   ├── networking.ts               # VPC, ALB, NAT, VPC Endpoints
│   ├── database.ts                 # RDS + RDS Proxy
│   ├── redis.ts                    # ElastiCache Redis (Multi-AZ)
│   ├── s3-storage.ts               # Versioned S3 buckets
│   ├── cognito-auth.ts             # Cognito User Pool + client
│   ├── ecs-services.ts             # ECS Fargate: web + MLflow
│   ├── batch-environment.ts        # Batch-on-EC2: CPU + GPU
│   ├── migration-task.ts           # Pre-deploy migration task
│   └── iam.ts                      # IAM role definitions
├── lambdas/
│   └── post_auth.py                # Cognito post-auth trigger
├── cdk.json
├── package.json
└── tsconfig.json
```

## Key Construct Configurations

### Networking

```typescript
const vpc = new Vpc(this, 'AnvilVpc', {
    maxAzs: 2,
    natGateways: 2,
    subnetConfiguration: [
        { name: 'Public', subnetType: SubnetType.PUBLIC, cidrMask: 24 },
        { name: 'Private', subnetType: SubnetType.PRIVATE_WITH_EGRESS, cidrMask: 24 },
    ],
});
```

### RDS with RDS Proxy

```typescript
const database = new DatabaseInstance(this, 'AnvilRds', {
    engine: DatabaseInstanceEngine.postgres({ version: PostgresEngineVersion.VER_16 }),
    multiAz: true,
    backupRetention: Duration.days(backupRetentionDays),
    vpc,
    vpcSubnets: { subnetType: SubnetType.PRIVATE_WITH_EGRESS },
});

const proxy = new DatabaseProxy(this, 'AnvilRdsProxy', {
    proxyTarget: ProxyTarget.fromInstance(database),
    secrets: [database.secret!],
    iamAuth: true,
    vpc,
});
```

### ECS with Autoscaling

```typescript
const webTaskDef = new FargateTaskDefinition(this, 'AnvilWebTaskDef', {
    cpu: webCpu,
    memoryLimitMiB: webMemory,
    executionRole: executionRole,
    taskRole: taskRole,
});

webTaskDef.addContainer('AnvilWebContainer', {
    image: ContainerImage.fromEcrRepository(ecrRepo, containerImageDigest),
    portMappings: [{ containerPort: 8080 }],
    environment: { ... },
    secrets: { ... },
});

const webService = new FargateService(this, 'AnvilWebService', {
    cluster,
    taskDefinition: webTaskDef,
    desiredCount: 2,
    serviceConnectConfiguration: { ... },
});

const scalingTarget = webService.autoScaleTaskCount({
    minCapacity: 2,
    maxCapacity: 10,
});
scalingTarget.scaleOnCpuUtilization('CpuScaling', {
    targetUtilizationPercent: 70,
});
```

## CDK Deployment Cheatsheet

| Command | Purpose |
|---------|---------|
| `npx cdk synth` | Validate and generate CloudFormation template |
| `npx cdk diff` | Show planned changes |
| `npx cdk deploy` | Deploy stack to AWS |
| `npx cdk deploy --hotswap` | Fast dev iteration (container only) |
| `npx cdk watch` | Auto-deploy on file changes |
| `npx cdk destroy` | Tear down stack |
| `npx cdk list` | List stacks in app |

## Environment Notes

- **Dev**: `ANVIL_ENV=dev` — minimal sizing, short backup retention, no deletion protection
- **Staging**: `ANVIL_ENV=staging` — medium sizing, 14-day backups, deletion protection enabled
- **Prod**: `ANVIL_ENV=prod` — medium+ sizing, 30-day backups, deletion + termination protection

## See Also

- [[033 SaaS CDK Infrastructure - spec|spec]] — full specification
- [[033 SaaS CDK Infrastructure - plan|plan]] — implementation plan
- [[033 SaaS CDK Infrastructure - tasks|tasks]] — task breakdown
- [[033 SaaS CDK Infrastructure - research|research]] — research findings
- [[033 SaaS CDK Infrastructure - data-model|data-model]] — resource inventory + stack outputs
- [[Specs/016 SaaS Architecture/016 SaaS Architecture - quickstart|016 Architecture Quickstart]] — parent quickstart
