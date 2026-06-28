---
title: Cluster Registry Schema
type: reference
tags:
  - type/reference
  - domain/infrastructure
spec-refs:
  - docs/vault/Specs/035 SaaS CLI Remote/
related:
  - '[[035 SaaS CLI Remote]]'
created: '2026-06-27'
updated: '2026-06-27'
status: draft
---

# Cluster Registry Schema

Canonical JSON schema for `~/.anvil/clusters.json`.

## Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "ClusterRegistry",
  "type": "object",
  "required": ["clusters"],
  "properties": {
    "active": {
      "type": ["string", "null"],
      "description": "Name of the active/default cluster. Must match one of the cluster entries."
    },
    "clusters": {
      "type": "array",
      "items": { "$ref": "#/definitions/ClusterEntry" },
      "minItems": 0
    }
  },
  "definitions": {
    "ClusterEntry": {
      "type": "object",
      "required": [
        "name", "url", "api_url", "region",
        "auth_method", "api_version", "deployed_at"
      ],
      "properties": {
        "name": {
          "type": "string",
          "pattern": "^[a-zA-Z0-9_-]+$",
          "description": "User-assigned alias, unique across entries."
        },
        "url": {
          "type": "string",
          "format": "uri",
          "pattern": "^https://",
          "description": "CloudFront URL or custom domain (HTTPS only)."
        },
        "api_url": {
          "type": "string",
          "format": "uri",
          "description": "API base path, typically {url}/v1."
        },
        "region": {
          "type": "string",
          "pattern": "^[a-z]{2}-[a-z]+-\\d{1}$",
          "description": "AWS region (e.g. us-east-1, eu-west-1)."
        },
        "auth_method": {
          "type": "string",
          "enum": ["deploy", "device_grant"],
          "description": "Authentication method for this cluster."
        },
        "cognito_domain": {
          "type": "string",
          "description": "Cognito domain for device-grant auth. Required if auth_method=device_grant."
        },
        "cognito_client_id": {
          "type": "string",
          "description": "Cognito app client ID for device-grant auth. Required if auth_method=device_grant."
        },
        "api_version": {
          "type": "string",
          "pattern": "^\\d+\\.\\d+$",
          "description": "API version reported by GET /v1/version (e.g. '1.0')."
        },
        "deployed_at": {
          "type": "string",
          "format": "date-time",
          "description": "ISO 8601 timestamp of when the cluster was deployed or added."
        },
        "last_login": {
          "type": ["string", "null"],
          "format": "date-time",
          "description": "ISO 8601 timestamp of the most recent successful login."
        }
      },
      "allOf": [
        {
          "if": { "properties": { "auth_method": { "const": "device_grant" } } },
          "then": {
            "required": ["cognito_domain", "cognito_client_id"]
          }
        }
      ]
    }
  }
}
```

## Example

```json
{
  "active": "prod",
  "clusters": [
    {
      "name": "prod",
      "url": "https://models.example.com",
      "api_url": "https://models.example.com/v1",
      "region": "us-east-1",
      "auth_method": "device_grant",
      "cognito_domain": "auth.models.example.com",
      "cognito_client_id": "xxxxxxxxxxxxxxxxxx",
      "api_version": "1.0",
      "deployed_at": "2026-06-19T00:00:00Z",
      "last_login": "2026-06-20T12:00:00Z"
    }
  ]
}
```
