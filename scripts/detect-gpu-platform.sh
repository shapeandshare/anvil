#!/usr/bin/env bash
# detect-gpu-platform.sh
#
# Detects whether the current platform can use GPU-accelerated PyTorch.
# Outputs "gpu" if GPU support is available, empty string otherwise.
#
# Detection logic:
#   - macOS ARM64      → MPS is built into PyPI torch → always install GPU extras
#   - Linux + nvidia-smi → CUDA drivers present → install GPU extras
#   - Everything else   → CPU-only → skip GPU extras

set -euo pipefail

case "$(uname -s)" in
    Darwin)
        # macOS Apple Silicon has MPS built into the standard PyTorch wheel
        if [ "$(uname -m)" = "arm64" ]; then
            echo "gpu"
        fi
        ;;
    Linux)
        # NVIDIA GPU: nvidia-smi is the standard driver diagnostic tool
        if command -v nvidia-smi &>/dev/null; then
            echo "gpu"
        fi
        ;;
esac