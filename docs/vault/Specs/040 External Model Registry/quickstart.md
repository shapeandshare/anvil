# Quickstart: 040 External Model Registry

## Prerequisites

- anvil installed with `[finetune]` extra for HuggingFace Hub support:
  ```bash
  pip install anvil[finetune]
  ```
- Running anvil server: `anvil serve`

## CLI

### Import a model from HuggingFace Hub

```bash
# Basic import (revision defaults to "main", name auto-derived)
anvil import huggingface TinyLlama/TinyLlama-1.1B-Chat-v1.0
# Output: Import submitted. Job ID: 42

# Poll for status
anvil import-status 42
# Output: Status: complete | Model ID: 7

# Import a gated model (set HF_TOKEN env var)
HF_TOKEN=hf_xxx anvil import huggingface meta-llama/Llama-2-7b

# Import a specific revision with a custom name
anvil import huggingface TinyLlama/TinyLlama-1.1B-Chat-v1.0 \
    --name "My TinyLlama" --revision v1.0
```

### Import from local path

```bash
# Import a model from a local directory
anvil import local /path/to/model/dir
```

## REST API

```bash
# Submit import
curl -X POST http://localhost:8080/v1/models/import \
  -H "Content-Type: application/json" \
  -d '{
    "source": "huggingface",
    "identifier": "TinyLlama/TinyLlama-1.1B-Chat-v1.0",
    "name": "My TinyLlama"
  }'
# Response: {"job_id": 42, "status": "queued"}

# Poll status
curl http://localhost:8080/v1/models/import/42/status
# Response: {"job_id": 42, "status": "complete", "external_model_id": 7, ...}

# List imported models
curl http://localhost:8080/v1/models/external
```

## Python SDK

```python
import asyncio
from anvil.client import AnvilClient


async def main() -> None:
    async with AnvilClient(base_url="http://localhost:8080") as client:
        # Submit import
        result = await client.models.import_model(
            source="huggingface",
            identifier="TinyLlama/TinyLlama-1.1B-Chat-v1.0",
            name="My TinyLlama",
        )
        print(f"Import submitted: job_id={result.job_id}")

        # Poll until complete
        import time
        while True:
            status = await client.models.get_import_status(job_id=result.job_id)
            if status.status in ("complete", "failed"):
                break
            await asyncio.sleep(1)

        if status.status == "complete":
            model = await client.models.get(model_id=status.external_model_id)
            print(f"Model imported: {model.display_name} ({model.architecture_family})")
        else:
            print(f"Import failed: {status.error_code} — {status.error_message}")


asyncio.run(main())
```
