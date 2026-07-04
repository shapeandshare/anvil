# Security Policy

## Reporting a Vulnerability

**Please report security vulnerabilities by opening a
[GitHub Security Advisory](https://github.com/shapeandshare/anvil/security/advisories/new).**

You may also send an email to **joshburt@shapeandshare.com**. This is an alias to the
project maintainer.

### What to include

- A clear description of the vulnerability
- Steps to reproduce (PoC or proof-of-concept preferred)
- Affected versions (if known)
- Any potential mitigations you've identified

### What to expect

- **Confirmation** — we'll acknowledge receipt
- **Assessment** — we'll triage and determine severity
- **Fix** — a patch will be developed privately and released as a security
  update. We'll coordinate disclosure timing with you.
- **Credit** — you'll be credited in the advisory (unless you prefer to remain
  anonymous)

We ask that you **do not** publicly disclose the vulnerability until we've had
reasonable time to address it.

## Security-Sensitive Areas

### Model weights and arbitrary code execution

anvil imports and exports model weights in the standard `safetensors` format.
The `safetensors` format is designed to prevent arbitrary code execution during
model loading. **We strongly recommend using `safetensors` rather than `pickle`**
for any model artifacts you load into anvil.

When importing models from HuggingFace Hub or other external sources, be aware
that loading untrusted model artifacts carries inherent risk. Only load models
from sources you trust.

### Web server

anvil's web server (FastAPI) runs on a configurable port (default `:8080`). By
default it binds to `127.0.0.1` (localhost only). If you expose it to your LAN
via `ANVIL_HOST=0.0.0.0`, ensure your network is trusted.

### MLflow server

anvil starts an MLflow sidecar on `:5001` bound to `127.0.0.1`. This is a
development-convenience setup and is not hardened for production. Do not expose
it to untrusted networks.

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| latest  | :white_check_mark: |
| < latest| :x:                |

anvil follows a continuous delivery model — only the latest release receives
security patches. We recommend always running the latest version.