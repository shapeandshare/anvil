---
title: 033 SaaS CDK Infrastructure - data-model
type: data-model
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

# Data Model: SaaS CDK Infrastructure

This document inventories the infrastructure resources provisioned by the CDK stack, their configuration properties, and the CloudFormation stack outputs consumed by other specs.

---

## Infrastructure Resource Inventory

### 1. Networking Layer

| Resource | Logical ID | Type | Key Configuration |
|----------|------------|------|-------------------|
| VPC | `AnvilVpc` | `AWS::EC2::VPC` | CIDR `10.0.0.0/16`, `EnableDnsHostnames: true`, `EnableDnsSupport: true` |
| Public Subnet AZ1 | `AnvilVpcPublicSubnet1` | `AWS::EC2::Subnet` | CIDR `10.0.0.0/24`, mapPublicIpOnLaunch |
| Public Subnet AZ2 | `AnvilVpcPublicSubnet2` | `AWS::EC2::Subnet` | CIDR `10.0.1.0/24`, mapPublicIpOnLaunch |
| Private Subnet AZ1 | `AnvilVpcPrivateSubnet1` | `AWS::EC2::Subnet` | CIDR `10.0.2.0/24` |
| Private Subnet AZ2 | `AnvilVpcPrivateSubnet2` | `AWS::EC2::Subnet` | CIDR `10.0.3.0/24` |
| Internet Gateway | `AnvilIgw` | `AWS::EC2::InternetGateway` | Attached to VPC |
| NAT Gateway AZ1 | `AnvilNatGw1` | `AWS::EC2::NatGateway` | Elastic IP in public subnet AZ1 |
| NAT Gateway AZ2 | `AnvilNatGw2` | `AWS::EC2::NatGateway` | Elastic IP in public subnet AZ2 |
| S3 VPC Gateway Endpoint | `AnvilS3Endpoint` | `AWS::EC2::VPCEndpoint` | `GatewayType`, route table associations |
| ECR API Interface Endpoint | `AnvilEcrApiEndpoint` | `AWS::EC2::VPCEndpoint` | `InterfaceType`, security group |
| ECR DKR Interface Endpoint | `AnvilEcrDkrEndpoint` | `AWS::EC2::VPCEndpoint` | `InterfaceType`, security group |
| Secrets Manager Interface Endpoint | `AnvilSecretsEndpoint` | `AWS::EC2::VPCEndpoint` | `InterfaceType`, security group |
| CloudWatch Logs Interface Endpoint | `AnvilCwLogsEndpoint` | `AWS::EC2::VPCEndpoint` | `InterfaceType`, security group |
| ALB | `AnvilAlb` | `AWS::ElasticLoadBalancingV2::LoadBalancer` | Internet-facing, dualstack, SG |
| ALB Listener (HTTPS) | `AnvilAlbHttpsListener` | `AWS::ElasticLoadBalancingV2::Listener` | HTTPS:443, ACM certificate |
| ALB Target Group | `AnvilAlbWebTargetGroup` | `AWS::ElasticLoadBalancingV2::TargetGroup` | HTTP:8080, health check `/v1/health` |
| Application Security Group | `AnvilAppSecurityGroup` | `AWS::EC2::SecurityGroup` | Ingress: ALB → web:8080, egress: all |

### 2. RDS + RDS Proxy

| Resource | Logical ID | Type | Key Configuration |
|----------|------------|------|-------------------|
| DB Subnet Group | `AnvilDbSubnetGroup` | `AWS::RDS::DBSubnetGroup` | Private subnets AZ1 + AZ2 |
| DB Parameter Group | `AnvilDbParameterGroup` | `AWS::RDS::DBParameterGroup` | PostgreSQL 16 tuned params |
| RDS Instance | `AnvilRdsInstance` | `AWS::RDS::DBInstance` | `MultiAZ: true`, `BackupRetentionPeriod: 7`, `DBInstanceClass` per `instance_size`, `Engine: postgres`, `EngineVersion: 16`, `StorageType: gp3`, `StorageEncrypted: true`, `EnablePerformanceInsights: true`, `DeletionProtection: false` (set via config) |
| RDS Proxy | `AnvilRdsProxy` | `AWS::RDS::DBProxy` | `IAMAuth: REQUIRED`, `RequireTLS: true`, `MaxConnectionsPercent: 100` |
| RDS Proxy Target Group | `AnvilRdsProxyTargetGroup` | `AWS::RDS::DBProxyTargetGroup` | Attached to RDS instance, `ConnectionPoolConfiguration` with default settings |
| DB Master Secret | `AnvilDbMasterSecret` | `AWS::SecretsManager::Secret` | Auto-generated password, `SecretStringTemplate` for admin user |

### 3. ElastiCache Redis

| Resource | Logical ID | Type | Key Configuration |
|----------|------------|------|-------------------|
| Redis Subnet Group | `AnvilRedisSubnetGroup` | `AWS::ElastiCache::SubnetGroup` | Private subnets AZ1 + AZ2 |
| Redis Parameter Group | `AnvilRedisParamGroup` | `AWS::ElastiCache::ParameterGroup` | `default.redis7` family |
| Redis Replication Group | `AnvilRedisReplicationGroup` | `AWS::ElastiCache::ReplicationGroup` | `AutomaticFailoverEnabled: true`, `MultiAZEnabled: true`, `NumNodeGroups: 1`, `ReplicasPerNodeGroup: 1`, `TransitEncryptionEnabled: true`, `AuthToken` from Secrets Manager, `CacheNodeType` per `instance_size` |
| Redis Security Group | `AnvilRedisSecurityGroup` | `AWS::EC2::SecurityGroup` | Ingress: ECS SG + Batch SG on 6379 |
| Redis Auth Secret | `AnvilRedisAuthSecret` | `AWS::SecretsManager::Secret` | Auto-generated auth token |

### 4. S3 Storage

| Resource | Logical ID | Type | Key Configuration |
|----------|------------|------|-------------------|
| Data Bucket | `AnvilDataBucket` | `AWS::S3::Bucket` | `BucketName: anvil-data-{env}`, `Versioning: Enabled`, `PublicAccessBlock: all` |
| ML Bucket | `AnvilMlBucket` | `AWS::S3::Bucket` | `BucketName: anvil-ml-{env}`, `Versioning: Enabled`, `PublicAccessBlock: all` |
| Data Bucket Lifecycle | `AnvilDataBucketLifecycle` | `AWS::S3::BucketPolicy` + lifecycle config | `NoncurrentVersionExpiration: 30 days`, optional transition to `INTELLIGENT_TIERING` |
| ML Bucket Lifecycle | `AnvilMlBucketLifecycle` | `AWS::S3::BucketPolicy` + lifecycle config | `NoncurrentVersionExpiration: 30 days` |
| Data Bucket Policy | `AnvilDataBucketPolicy` | `AWS::S3::BucketPolicy` | Least-privilege: separate read/write actions, scoped to `{org_id}/` prefix |
| ML Bucket Policy | `AnvilMlBucketPolicy` | `AWS::S3::BucketPolicy` | MLflow-specific access patterns |

### 5. Cognito

| Resource | Logical ID | Type | Key Configuration |
|----------|------------|------|-------------------|
| User Pool | `AnvilUserPool` | `AWS::Cognito::UserPool` | Email sign-in, standard attributes, custom domain |
| User Pool Domain | `AnvilUserPoolDomain` | `AWS::Cognito::UserPoolDomain` | Domain prefix: `auth-{env}` |
| User Pool Client | `AnvilUserPoolClient` | `AWS::Cognito::UserPoolClient` | OAuth flows, callback URLs, `GenerateSecret: false` |
| User Pool IdP Google | `AnvilIdPGoogle` | `AWS::Cognito::UserPoolIdentityProvider` | Created post-deploy by `deploy config set-idp` |
| User Pool IdP GitHub | `AnvilIdPGitHub` | `AWS::Cognito::UserPoolIdentityProvider` | Created post-deploy by `deploy config set-idp` |

### 6. ECS Fargate

| Resource | Logical ID | Type | Key Configuration |
|----------|------------|------|-------------------|
| ECS Cluster | `AnvilEcsCluster` | `AWS::ECS::Cluster` | Fargate, container insights enabled |
| Cloud Map Private DNS | `AnvilCloudMapNamespace` | `AWS::ServiceDiscovery::PrivateDnsNamespace` | `Name: svc.local`, VPC |
| Web Task Definition | `AnvilWebTaskDef` | `AWS::ECS::TaskDefinition` | `FARGATE`, execution role, task role, `ContainerImage` by digest |
| Web Service | `AnvilWebService` | `AWS::ECS::Service` | 2+ replicas, ALB target group, autoscaling (CPU/memory), `ServiceConnect` or Cloud Map |
| MLflow Task Definition | `AnvilMlflowTaskDef` | `AWS::ECS::TaskDefinition` | `FARGATE`, execution role, task role, MLflow container image |
| MLflow Service | `AnvilMlflowService` | `AWS::ECS::Service` | 1 replica, Cloud Map registration as `mlflow.svc.local:5000` |
| Web Auto-scaling Target | `AnvilWebScalingTarget` | `AWS::ApplicationAutoScaling::ScalableTarget` | `MinCapacity: 2`, `MaxCapacity: 10` |
| Web Auto-scaling Policy | `AnvilWebScalingPolicy` | `AWS::ApplicationAutoScaling::ScalingPolicy` | CPU > 70% scale up, < 30% scale down |
| Web Service SG | `AnvilWebServiceSG` | `AWS::EC2::SecurityGroup` | Ingress: ALB → web:8080 |
| MLflow Service SG | `AnvilMlflowSG` | `AWS::EC2::SecurityGroup` | Ingress: web + Batch → mlflow:5000 |

### 7. AWS Batch

| Resource | Logical ID | Type | Key Configuration |
|----------|------------|------|-------------------|
| Batch Service Role | `AnvilBatchServiceRole` | `AWS::IAM::Role` | Managed: `AWSBatchServiceRole` |
| CPU Compute Environment | `AnvilBatchCpuEnv` | `AWS::Batch::ComputeEnvironment` | `EC2`, `SPOT`, instance types `c6i.*`, `m6i.*`, min vCPUs 0, max vCPUs 256 |
| GPU Compute Environment | `AnvilBatchGpuEnv` | `AWS::Batch::ComputeEnvironment` | `EC2`, `SPOT`, instance types `g4dn.*`, `g5.*`, `p3.*`, `p4d.*`, min vCPUs 0, max vCPUs 256 |
| CPU Job Queue | `AnvilBatchCpuQueue` | `AWS::Batch::JobQueue` | Priority 1, fair-share scheduling keyed on `org_id` |
| GPU Job Queue | `AnvilBatchGpuQueue` | `AWS::Batch::JobQueue` | Priority 0, fair-share scheduling keyed on `org_id` |
| Job Def: CPU | `AnvilJobDefCpu` | `AWS::Batch::JobDefinition` | Single-node, ECS task role `BatchJobRole`, image digest, `Command: ["python", "-m", "anvil._saas.compute_worker"]` |
| Job Def: GPU | `AnvilJobDefGpu` | `AWS::Batch::JobDefinition` | Single-node, GPU count parameterized, same image + entrypoint |
| Job Def: Multi-GPU | `AnvilJobDefMultiGpu` | `AWS::Batch::JobDefinition` | Single-node, N GPUs, `ResourceRequirement` for instance type |
| Job Def: Multi-Node | `AnvilJobDefMultiNode` | `AWS::Batch::JobDefinition` | Multi-node parallel, `NodeRangeProperties` for main + worker nodes, EFA support |
| Batch SG | `AnvilBatchSecurityGroup` | `AWS::EC2::SecurityGroup` | Egress: RDS Proxy:5432, Redis:6379, MLflow:5000; VPC endpoints |

### 8. CloudFront + WAF

| Resource | Logical ID | Type | Key Configuration |
|----------|------------|------|-------------------|
| WAF ACL | `AnvilWafAcl` | `AWS::WAFv2::WebACL` | Rate limit (1000/5min), SQLi/XSS rules, AWS managed rule set |
| WAF Association | `AnvilWafAssociation` | `AWS::WAFv2::WebACLAssociation` | Associated with CloudFront distribution |
| CloudFront Distribution | `AnvilCloudFrontDistribution` | `AWS::CloudFront::Distribution` | ALB origin, SSE timeouts (origin keepalive 60s, origin read 60s, viewer timeout 60s), custom error pages, WAF, HTTPS viewer protocol |
| Origin Access Control | `AnvilCloudFrontOac` | `AWS::CloudFront::OriginAccessControl` | `SigningBehavior: always`, `OriginAccessControlOriginType: elb` |
| Route53 Record | `AnvilDnsRecord` | `AWS::Route53::RecordSet` | Alias to CloudFront, only if `domainName` provided |

### 9. Migration Task

| Resource | Logical ID | Type | Key Configuration |
|----------|------------|------|-------------------|
| Migration Task Definition | `AnvilMigrationTaskDef` | `AWS::ECS::TaskDefinition` | `FARGATE`, execution role + task role, image same as web, `Command: ["alembic", "upgrade", "head"]` |
| Migration Execution (CFN Custom Resource or Lambda) | `AnvilMigrationRunner` | `Custom::MigrationRunner` | Invokes `ECS RunTask` for migration, waits for completion, reports status |

### 10. Post-Auth Lambda

| Resource | Logical ID | Type | Key Configuration |
|----------|------------|------|-------------------|
| Lambda Function | `AnvilPostAuthLambda` | `AWS::Lambda::Function` | Inline Python (or S3 zip), `Runtime: python3.11`, `Handler: index.handler` |
| Lambda Permission | `AnvilPostAuthLambdaPermission` | `AWS::Lambda::Permission` | `Principal: cognito-idp.amazonaws.com`, `Action: lambda:InvokeFunction` |
| Lambda Role | `AnvilPostAuthLambdaRole` | `AWS::IAM::Role` | `rds-db:connect` (read-only for user mapping), `cognito-idp:AdminUpdateUserAttributes` |

---

## CFN Stack Outputs Contract

The CDK stack exposes the following outputs for consumption by the deploy CLI, dependent specs, and cross-stack references.

### Output Schema

```typescript
interface AnvilStackOutputs {
    // Networking
    CloudFrontURL: string;                    // https://d123.cloudfront.net
    ALBDNSName: string;                       // anvil-123.elb.amazonaws.com
    VpcId: string;                            // vpc-12345678
    WebServiceSecurityGroupId: string;        // sg-12345678

    // Database
    RDSProxyEndpoint: string;                 // anvil-proxy.proxy-abc.rds.amazonaws.com
    RDSProxyPort: number;                     // 5432

    // Redis
    RedisPrimaryEndpoint: string;             // redis-cluster.abc.ng.0001.use1.cache.amazonaws.com
    RedisPort: number;                        // 6379

    // S3
    DataBucketName: string;                   // anvil-data-prod
    MlBucketName: string;                     // anvil-ml-prod

    // Cognito
    CognitoUserPoolId: string;                // us-east-1_abc123
    CognitoAppClientId: string;               // abc123def456
    CognitoAuthDomain: string;                // auth-prod.auth.us-east-1.amazoncognito.com

    // ECS
    EcsClusterName: string;                   // AnvilEcsCluster-abc123
    MlflowServiceDiscoveryArn: string;        // arn:aws:servicediscovery:...:service/svc-...

    // Batch
    BatchCpuQueueArn: string;                 // arn:aws:batch:...:job-queue/anvil-cpu
    BatchGpuQueueArn: string;                 // arn:aws:batch:...:job-queue/anvil-gpu

    // Monitoring (for cross-stack reference)
    WafAclArn: string;                        // arn:aws:wafv2:...:webacl/...
}
```

### Output Usage

| Consumer Spec | Outputs Consumed |
|---------------|------------------|
| 032 Durable Training | `RDSProxyEndpoint`, `RedisPrimaryEndpoint`, `DataBucketName`, `BatchCpuQueueArn`, `BatchGpuQueueArn` |
| 030 Cognito Auth | `CognitoUserPoolId`, `CognitoAppClientId`, `CognitoAuthDomain` |
| 028 SaaS Package Structure | `EcsClusterName`, `WebServiceSecurityGroupId` |
| Deploy CLI (cloudformation.py) | All outputs — for status/verify commands |
| 036 Observability | `MlBucketName`, `EcsClusterName`, `WafAclArn` |

---

## CDK Stack Parameter Schema

The CDK stack accepts the following parameters (passed as CDK context or environment variables):

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `envName` | `string` | `dev` | Environment name (`dev`, `staging`, `prod`) |
| `domainName` | `string` | `""` | Custom domain for CloudFront (empty = CloudFront URL only) |
| `hostedZoneId` | `string` | `""` | Route53 hosted zone ID (required if `domainName` set) |
| `containerImageDigest` | `string` | `latest` | ECR image digest (`sha256:...`) |
| `instanceSize` | `string` (`small\|medium\|large`) | `small` | Resource sizing tier |
| `backupRetentionDays` | `number` | `7` | RDS automated backup retention |
| `backupWindow` | `string` | `03:00-04:00` | RDS preferred backup window |
| `maintenanceWindow` | `string` | `sun:05:00-sun:06:00` | RDS preferred maintenance window |
| `s3NoncurrentVersionExpiry` | `number` | `30` | S3 noncurrent version expiry in days |
| `adminEmail` | `string` | `""` | Initial admin email (set during `deploy init`) |
| `enableDeletionProtection` | `boolean` | `false` | Enable RDS deletion protection (true for prod) |
| `enableTerminationProtection` | `boolean` | `false` | Enable CFN stack termination protection (true for prod) |
| `vpcCidr` | `string` | `10.0.0.0/16` | VPC CIDR block |
| `tags` | `object` | `{Project: anvil}` | Resource tags |
| `sseSigningSecretArn` | `string` | `""` | ARN of existing SSE signing secret (auto-created if empty) |
| `redisAuthTokenArn` | `string` | `""` | ARN of existing Redis auth token (auto-created if empty) |

---

## Deployment Environment Configuration Map

```yaml
dev:
  instanceSize: small
  backupRetentionDays: 7
  s3NoncurrentVersionExpiry: 30
  enableDeletionProtection: false
  enableTerminationProtection: false

staging:
  instanceSize: medium
  backupRetentionDays: 14
  s3NoncurrentVersionExpiry: 60
  enableDeletionProtection: true
  enableTerminationProtection: true

prod:
  instanceSize: medium
  backupRetentionDays: 30
  s3NoncurrentVersionExpiry: 90
  enableDeletionProtection: true
  enableTerminationProtection: true
```
