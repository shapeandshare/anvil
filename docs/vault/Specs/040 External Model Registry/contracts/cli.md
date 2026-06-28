# CLI Contract: `anvil import`

## Entry Point

Registered in `pyproject.toml` under `[project.scripts]`:

```toml
anvil-import = "anvil.cli:import_main"
```

## Usage

```bash
# Import from HuggingFace Hub
anvil import huggingface TinyLlama/TinyLlama-1.1B-Chat-v1.0

# Import with custom name and revision
anvil import huggingface TinyLlama/TinyLlama-1.1B-Chat-v1.0 \
    --name "My TinyLlama" \
    --revision v1.0

# Import from local path
anvil import local /path/to/model/directory

# With HF token for gated models
HF_TOKEN=hf_xxx anvil import huggingface meta-llama/Llama-2-7b
```

## Exit Codes

| Exit Code | Meaning |
|-----------|---------|
| 0 | Import job submitted successfully (prints job ID) |
| 1 | Error during submission (invalid args, unknown source) |

## Output

On success, prints the job ID:

```
Import submitted. Job ID: 42
Poll status: anvil import-status 42
```
