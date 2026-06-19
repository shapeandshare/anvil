"""train5: Full Llama architecture using the multi-layer LlamaModel and Adam.
Demonstrates training loop via train() and safetensors export via
SafetensorsExportService."""

import random
import tempfile

random.seed(42)

from anvil.core.engine import train
from anvil.services.export import SafetensorsExportService

# --- data ---
docs = [l.strip() for l in open("input.txt") if l.strip()]
uchars = sorted(set("".join(docs)))
BOS = len(uchars)
vocab_size = len(uchars) + 1

# --- train with built-in Adam optimizer ---
print("Training full Llama model (n_layer=2, n_embd=16, n_head=4)...")
model, final_loss, samples, uchars = train(
    docs,
    num_steps=200,
    n_embd=16,
    n_head=4,
    n_layer=2,
    block_size=16,
    learning_rate=0.01,
)
print(f"Final loss: {final_loss:.4f}")
print(f"Sample outputs: {samples[:3]}")

# --- safetensors export demonstration ---
print("\nExporting to safetensors format...")
export_service = SafetensorsExportService()
with tempfile.TemporaryDirectory() as tmpdir:
    result = export_service.export(model, tmpdir, uchars)
    if result["error"]:
        print(f"Export skipped (safetensors not installed): {result['error']}")
    else:
        print(f"  Model:     {result['safetensors_path']}")
        print(f"  Config:    {result['config_path']}")
        print(f"  Tokenizer: {result['tokenizer_path']}")
        print("✓ Safetensors export successful!")