# Contract: Help Page Route

**Type**: HTTP Route | **Version**: 1.0

## Route

```
GET /v1/help
```

Renders the non-educational help guide page as a single-page anchor-index layout.

## Response

- **Status**: `200 OK`
- **Content-Type**: `text/html`
- **Body**: Jinja2-rendered HTML page (`archetypes/help.html`)

## Template Context

| Key | Type | Description |
|-----|------|-------------|
| `sections` | `list[HelpSection]` | Ordered list of help sections for the index and detail areas |

## URL Anchors

Each help section is addressable via anchor ID:

```
/v1/help                      # Index at top of page
/v1/help#training             # Training section
/v1/help#data                 # Data section
/v1/help#experiments          # Experiments section
/v1/help#models               # Models section
/v1/help#playground           # Playground section
/v1/help#operations           # Operations section
/v1/help#content-library      # Content Library section
```

## Authentication

Follows existing page-route auth rules — requires session cookie or API key
(same as all other `/v1/*` page routes).