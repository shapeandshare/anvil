# Quickstart — Local LoRA Fine-Tuning

## Prerequisites

```bash
pip install anvil[finetune]   # Install with LoRA/QLoRA dependencies
```

## Fine-Tune a Model (CLI / API)

### 1. Import a model

From the HF Model Browser (UI) or via API:

```bash
curl -X POST /v1/models/import \
  -H "Content-Type: application/json" \
  -d '{"source_type": "huggingface", "source_identifier": "TinyLlama/TinyLlama-1.1B-Chat-v1.0"}'
```

### 2. Upload training data

Upload a `.txt` corpus or prepare a structured dataset.

**Ad-hoc fine-tuning (`.txt` corpus)**: Upload a text file — each document is a training example.

**Instruction-tuning (structured dataset)**: Use the fine-tune dataset preparation API (spec 053) to
create a `FineTuneDataset` with structured instruction/response content.

### 3. Start fine-tuning

From the training page UI:
1. Select the base model (already imported)
2. Choose method: **LoRA** or **QLoRA**
3. Configure LoRA hyperparameters (rank, alpha, target modules)
4. Select your dataset
5. Click **Train**

Or via API:

```bash
curl -X POST /v1/training/start \
  -H "Content-Type: application/json" \
  -d '{
    "method": "lora",
    "base_model_ref": 1,
    "dataset_id": 5,
    "lora_rank": 8,
    "lora_alpha": 16,
    "lora_target_modules": ["q_proj", "v_proj"],
    "num_steps": 500,
    "learning_rate": 2e-4
  }'
```

### 4. Generate text with the adapter

> Note: this uses the NEW `POST /v1/inference/generate` endpoint introduced by this feature. The
> existing inference API is educational-only and has no text-generation route.

```bash
curl -X POST /v1/inference/generate \
  -H "Content-Type: application/json" \
  -d '{
    "model_id": 1,
    "adapter_id": "run_42",
    "prompt": "Explain LoRA fine-tuning in one sentence."
  }'
```

Without `adapter_id`, generation uses the base model alone.

### 5. (Optional) Merge the adapter

Merge adapter weights into the base model to produce a standalone artifact:

```bash
curl -X POST /v1/models/1/adapters/run_42/merge
```

## Which Dataset Format Should I Use?

| Your goal | Use |
|---|---|
| "I want to teach my model my writing style" | Upload a `.txt` corpus of your writing |
| "I want my model to follow instructions" | Use a structured instruction/conversation dataset (a prepared `FineTuneDataset`) |
| "I'm not sure" | Start with `.txt` — it works for both cases, though instruction datasets give better results for chat models |

## Platform Notes

| Platform | LoRA | QLoRA |
|---|---|---|
| Linux + NVIDIA GPU | ✅ | ✅ (requires `bitsandbytes`) |
| macOS (Apple Silicon) | ✅ | ⚠️ Falls back to LoRA (MPS not supported by `bitsandbytes`) |
| CPU only | ✅ | ❌ (QLoRA requires GPU) |