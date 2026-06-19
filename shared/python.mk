# Generic Python development workflow using uv
# This file contains reusable targets for Python projects using uv + venv

VENV_DIR := .venv
VENV_BIN := $(VENV_DIR)/bin
PYTHON := $(VENV_BIN)/python3

# Auto-detect GPU platform: outputs ",gpu" on Apple Silicon or NVIDIA Linux,
# empty string otherwise. Used to conditionally include GPU extras.
GPU_EXTRA := $(shell ./scripts/detect-gpu-platform.sh)

# Convert GPU_EXTRA (pip-style ",gpu") to uv-style flag
GPU_EXTRA_UV := $(if $(GPU_EXTRA),--extra gpu,)

# Auto-create venv via uv if missing
$(VENV_DIR)/activate: pyproject.toml uv.lock
	uv venv $(VENV_DIR)
	uv sync --extra dev $(GPU_EXTRA_UV)
	@touch $(VENV_DIR)/activate

install: $(VENV_DIR)/activate ## Install/update deps from lock file
	uv sync --extra dev $(GPU_EXTRA_UV)

install-gpu: $(VENV_DIR)/activate ## Force install with GPU support (torch + CUDA/MPS)
	uv sync --extra dev --extra gpu
	@echo "GPU extras installed. Run 'make train-gpu' or toggle GPU in the web UI."
	@$(PYTHON) -c "import torch; msg = 'no GPU detected, will use CPU'; cu = torch.cuda.is_available(); msg = torch.cuda.get_device_name(0) if cu else msg; msg = 'Apple Silicon (MPS)' if torch.backends.mps.is_available() else msg; print(f'Detected: {msg}')" 2>/dev/null || echo "(torch not yet available in this shell)"

lint: $(VENV_DIR)/activate ## Run ruff, black --check, isort --check, pylint, and project-specific checks
	$(PYTHON) -m ruff check .
	$(PYTHON) -m black --check .
	$(PYTHON) -m isort --check .
	$(PYTHON) -m pylint anvil/ --disable=R,C
	@echo "Checking for disallowed patterns..."
	@! grep -rn '^@dataclass' anvil/ --include='*.py' | grep -v '# noqa: dataclass' || { echo "ERROR: @dataclass is disallowed — use Pydantic BaseModel instead. See constitution.md"; exit 1; }

build: ## Build a PEP 517 wheel via uv (fall back to python -m build)
	uv build --wheel --out-dir dist . 2>/dev/null || python3 -m build --wheel --outdir dist .

.PHONY: install build lint format typecheck clean