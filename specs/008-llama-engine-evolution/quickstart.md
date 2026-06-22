# Quickstart: Llama Engine & Safetensors Export

**Feature**: 006-llama-engine-evolution  
**Phase**: 1 — Design & Contracts  
**Date**: 2026-06-14  

## What This Feature Gives You

- **Llama-compatible training** — Your trained models use SwiGLU, RoPE, and RMSNorm with learned weights — the architecture behind modern LLMs
- **Export anywhere** — Automatically get a safetensors checkpoint + HuggingFace-compatible config on every training run
- **Educational walkthroughs** — Learn the Llama architecture step by step through 6 progressive scripts

## Quick Start

### 1. Train a Model

```bash
# Via CLI
make train

# Via web UI
make run  # then visit http://localhost:8080
```

### 2. Find Your Export

After training completes, you'll find automatically generated files at:

```
data/models/<experiment_id>/<run_id>/
├── model.safetensors    # ← primary: load anywhere
├── config.json          # ← Llama-compatible config
├── tokenizer.json       # ← character vocabulary
└── model.json           # ← secondary: internal format
```

### 3. Use Your Model in HuggingFace

```python
from transformers import LlamaForCausalLM, LlamaConfig
from safetensors.torch import load_file
import torch

# Load the exported checkpoint
state_dict = load_file("data/models/<experiment_id>/<run_id>/model.safetensors")

# OR load by experiment from the tracking interface
```

### 4. Run the Walkthroughs

```bash
python examples/train0.py   # single neuron
python examples/train1.py   # linear layer
python examples/train2.py   # RMSNorm
python examples/train3.py   # RoPE attention
python examples/train4.py   # SwiGLU block
python examples/train5.py   # full Llama GPT
```

## What's Different From Before

| Old (GPT-2) | New (Llama) |
|-------------|-------------|
| ReLU MLP (`fc1`/`fc2`) | SwiGLU MLP (`gate`/`up`/`down`) |
| Learned position embeddings (`wpe`) | Rotary Position Encoding (RoPE) |
| RMSNorm without learned scales | RMSNorm with learned `rms_1`/`rms_2` per layer |
| JSON-only export | Safetensors as primary export artifact |
| `layer{i}.mlp_fc1` | `layer{i}.mlp_gate` + `layer{i}.mlp_up` |

## Troubleshooting

### "Model format is incompatible"
You're trying to load an old GPT-2 format model.json with the new Llama engine. The demo model auto-retrains. For custom models, re-train with the new engine.

### "safetensors generation failed"
Training still succeeded — the loss is valid. Check the UI/logs for the error message (disk full? permissions?). You can retry export later from the internal JSON format.

### "head_dim must be even"
RoPE requires `n_embd % n_head == 0` so each head has an even number of dimensions for rotary pairings.