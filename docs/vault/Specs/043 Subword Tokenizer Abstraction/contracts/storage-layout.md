# Tokenizer Storage Contract

## Artifact Layout

Model artifacts are stored in `FileStore` under `data/models/experiment_{id}/`:

```
data/models/experiment_{id}/
├── model.safetensors   # Model weights (HF-convention name)
├── config.json         # Model config (includes tokenizer_family + serialization_type)
├── tokenizer.json      # Tokenizer artifact:
│                       #   - char_json → anvil's native format
│                       #   - hf_fast → HuggingFace tokenizer.json (self-contained)
├── tokenizer.model     # Only present for serialization_type=sentencepiece
├── MLmodel             # MLflow pyfunc metadata (unchanged)
└── conda.yaml          # MLflow environment spec (unchanged)
```

## Export Layout (flat directory, HF convention)

When exporting a model for external use:

```
{output_dir}/
├── model.safetensors   # Weights
├── config.json         # LlamaConfig-compatible
├── tokenizer.json      # Tokenizer — for char_json, HF fast, OR sentencepiece
│                       # SentencePiece .model is renamed/copied to tokenizer.json
│                       # for HF AutoTokenizer compatibility where possible
```

## config.json Metadata

Fields related to tokenizer:

```json
{
    "model_type": "llama",
    "vocab_size": 32000,
    "tokenizer_family": "char" | "subword",
    "serialization_type": "char_json" | "hf_fast" | "sentencepiece",
    ...
}
```

## Loading Protocol

1. Read `config.json` → extract `tokenizer_family` + `serialization_type`
2. Based on `serialization_type`:
   - `char_json`: load as `Vocabulary` (native, always available)
   - `hf_fast`: load via `tokenizers.Tokenizer.from_file("tokenizer.json")` — requires `[finetune]`
   - `sentencepiece`: load via `sentencepiece.SentencePieceProcessor` — requires `[finetune]`
   - else: raise `TokenizerLoadError`
3. Wrap in appropriate implementation; return `Tokenizer` protocol instance