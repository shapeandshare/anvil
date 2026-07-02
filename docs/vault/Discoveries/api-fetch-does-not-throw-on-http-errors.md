---
title: apiFetch does not throw on non-2xx responses
type: discovery
tags:
  - type/discovery
  - domain/ui
status: draft
created: '2026-07-01'
updated: '2026-07-01'
aliases: api-fetch-does-not-throw-on-http-errors
source: agent
code-refs: 'anvil/api/templates/base.html:160-173'
---
# `apiFetch` does not throw on non-2xx responses

The `window.apiFetch` function (defined in `anvil/api/templates/base.html`) wraps `fetch()` to add CSRF tokens to state-changing requests, but it **does not** check `resp.ok` or throw on HTTP errors.

## Impact

Callers that assume `apiFetch` throws on error (like a typical `fetch` wrapper) silently proceed with error responses. This caused a bug in the training page where `POST /v1/training/start` returning 422 would set `runId = undefined`, save a stale "connecting" entry to `sessionStorage`, and leave the user seeing "0 steps" forever.

## Location

```javascript
// base.html lines 160-173
window.apiFetch = function(url, opts) {
  opts = opts || {};
  var method = (opts.method || 'GET').toUpperCase();
  if (['POST','PUT','DELETE','PATCH'].indexOf(method) !== -1) {
    return window.CSRF_TOKEN_PROMISE.then(function() {
      if (window.CSRF_TOKEN) {
        opts.headers = opts.headers || {};
        opts.headers['X-CSRF-Token'] = window.CSRF_TOKEN;
      }
      return fetch(url, opts);
    });
  }
  return fetch(url, opts);
};
```

## Pattern for callers

All callers of `apiFetch` that make state-changing requests MUST check `resp.ok` before proceeding:

```javascript
var resp = await globalThis.apiFetch('/v1/endpoint', { method: 'POST', ... });
if (!resp.ok) {
  var errData = await resp.json().catch(function() { return {}; });
  throw new Error(errData.detail || errData.message || resp.statusText);
}
```

## Date

2026-07-01
