---
title: 033 SaaS CDK Infrastructure
type: spec
tags:
  - type/spec
  - domain/infrastructure
spec-refs:
  - docs/vault/Specs/033 SaaS CDK Infrastructure/
status: draft
created: '2026-06-27'
updated: '2026-06-27'
aliases:
  - 033 SaaS CDK Infrastructure
---

# 033 SaaS CDK Infrastructure

## Summary

Codified, repeatable AWS infrastructure for the anvil SaaS deployment. A full CDK stack in TypeScript (`packages/infra/`) provisioning VPC (2-AZ), RDS PostgreSQL + RDS Proxy (IAM auth, Multi-AZ, automated snapshots/PITR), ElastiCache Redis (Multi-AZ failover), S3 (versioned data + ML buckets), Batch-on-EC2 (CPU + GPU + multi-node), ECS Fargate (web + MLflow), Cloud Map service discovery, migration task (pre-rollout, AD-6), least-privilege IAM (execution vs job/task split, FR-045c/f), CloudFront + WAF, and post-auth Lambda. Asset-free synth with digest-pinned images (AD-7). Cognito User Pool as a first-class CDK resource (FR-022). Pre-synthesized CloudFormation templates bundled into the pip package for `boto3`-based deployment (FR-029). Multi-environment support via different stack names (FR-032).

## Artifacts

- [[033 SaaS CDK Infrastructure - spec|spec]]
- [[033 SaaS CDK Infrastructure - plan|plan]]
- [[033 SaaS CDK Infrastructure - tasks|tasks]]
- [[033 SaaS CDK Infrastructure - research|research]]
- [[033 SaaS CDK Infrastructure - data-model|data-model]]
- [[033 SaaS CDK Infrastructure - quickstart|quickstart]]
- [[033 SaaS CDK Infrastructure/contracts/stack-outputs-schema|contract/stack-outputs-schema]]
- [[033 SaaS CDK Infrastructure/contracts/cfn-parameter-schema|contract/cfn-parameter-schema]]

## Parent

[[Specs/016 SaaS Architecture/016 SaaS Architecture|016 SaaS Architecture (superseded umbrella)]]

## Decisions

[[Reference/SaaSArchitectureDecisions|SaaS Architecture Decisions]] — AD-1 (Batch on EC2), AD-6 (migrations pre-deploy), AD-7 (asset-free digest-pinned images), AD-10 (single image, two entrypoints)

## References

- [[Specs/Specs|Specs]]
- [[Specs/028 SaaS Abstraction Framework/028 SaaS Abstraction Framework|028 SaaS Package Structure]]
- [[Specs/030 SaaS Authentication/030 SaaS Authentication|030 SaaS Cognito Auth]]
- [[Specs/032 SaaS Training Pipeline/032 SaaS Training Pipeline|032 SaaS Durable Training]]
