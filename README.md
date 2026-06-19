<p align="center">
  <svg viewBox="0 0 240 160" width="120" height="80" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
    <path d="M 192,62 C 202,59 213,51 224,40 C 213,29 203,23 192,21 L 192,5 L 60,5 L 60,17 L 15,17 C 23,38 41,53 60,58 L 60,77 L 94,77 C 88,98 76,115 60,129 L 47,129 L 47,141 L 47,156 L 212,156 L 212,129 L 194,129 C 177,115 165,98 159,77 L 192,77 Z" fill="currentColor" opacity="0.9"/>
  </svg>
</p>

<h1 align="center">anvil</h1>

<p align="center"><strong>Forging intelligence.</strong></p>

<p align="center">Train and experiment with LLMs from scratch — a pip-installable workbench with live training dashboards, MLflow experiment tracking, and an iOS-modern web UI.</p>

<p align="center">
  <a href="#quick-start"><kbd>Quick Start</kbd></a>&nbsp;&nbsp;
  <a href="#features"><kbd>Features</kbd></a>&nbsp;&nbsp;
  <a href="#architecture"><kbd>Architecture</kbd></a>&nbsp;&nbsp;
  <a href="#hyperparameter-guide"><kbd>Hyperparameters</kbd></a>&nbsp;&nbsp;
  <a href="#configuration"><kbd>Config</kbd></a>
</p>

<br>

---

<br>

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| **Python** ≥ 3.11 | Must be on `PATH` as `python3` or `python3.11`. [python.org](https://www.python.org/downloads/) |
| **git** | [Download](https://git-scm.com/downloads) |
| **GNU make** | macOS: Xcode CLI tools (`xcode-select --install`). Debian: `apt install build-essential` |
| **bash** | Pre-installed on macOS / Linux |
| **uv** (fast Python package manager) | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| **nvidia-smi** (optional) | Linux only — enables CUDA GPU auto-detection |

> **Windows users**: Install [WSL2](https://learn.microsoft.com/en-us/windows/wsl/install) with Ubuntu, then follow the Linux instructions.

<br>

## Quick Start

**From a built package (recommended for end users):**

```bash
# Build the wheel
make build

# Validate in a container (Docker + compose required)
make test-system
# or bring it up interactively:
make compose-up
open http://localhost:8080
```

**From source (for development):**

```bash
git clone https://github.com/shapeandshare/anvil
cd anvil
make setup
make run
```

Open `http://<your-ip>:8080` from any device on your LAN.

Open `http://<your-ip>:8080` from any device on your LAN.

> **GPU acceleration**: Auto-detected on Apple Silicon (MPS) and NVIDIA Linux (CUDA). Falls back to CPU when unavailable.

<br>

## Features

| | | |
|---|---|---|
| 🧠 **Train from scratch** | 📊 **Experiment tracking** | 📁 **Dataset management** |
| Configure hyperparameters, watch loss in real-time via SSE | MLflow-backed, compare loss curves side-by-side | Upload custom `.txt` datasets, train on anything |
| 🔧 **Operations dashboard** | ✨ **iOS-modern UI** | 📖 **Progressive walkthroughs** |
| Manage services (web, MLflow), tail logs, health checks | Glass nav bar, spring animations, dark/light mode | 6 scripts from bigrams to full transformer, interactive widgets |

<br>

## Architecture

```
anvil/                         # Python package (implicit namespace)
├── core/                      # Stdlib-only training engine (zero deps)
│   ├── engine.py              #   Transformer: RoPE, SwiGLU MLP, RMSNorm
│   ├── torch_engine.py        #   PyTorch training loop with checkpointing
│   ├── autograd.py            #   Custom autograd engine
│   └── tokenizer.py           #   Byte-level tokenizer
├── db/                        # Async SQLAlchemy
│   ├── base.py                #   Declarative base
│   ├── session.py             #   Session management
│   ├── models/                #   ORM models
│   └── repositories/          #   Repository pattern (DB access only)
├── services/                  # Business logic layer
│   ├── training.py            #   Orchestrates core training
│   ├── tracking.py            #   MLflow experiment tracking
│   ├── export.py              #   Safetensors model export
│   └── ...                    #   Corpora, datasets, inference, etc.
├── api/                       # FastAPI server + Jinja2 templates
│   ├── static/                #   CSS tokens, components, archetypes
│   ├── templates/             #   Jinja2 page templates (hero, etc.)
│   └── v1/                    #   Route definitions (v1 router)
├── storage/                   # File storage abstraction (local/S3-ready)
└── supervisor/                # Process manager for background services
```

**Layer discipline**: Repository → Service → God Class (`AnvilWorkbench`) → Routes/CLI. No shortcuts.

<br>

## Hyperparameter Guide

| Parameter | Default | Description |
|-----------|---------|-------------|
| `n_embd` | 16 | Embedding dimension (wider = more capacity) |
| `n_layer` | 1 | Transformer depth (deeper = more patterns) |
| `n_head` | 4 | Attention heads (must divide `n_embd`) |
| `num_steps` | 1000 | Training iterations |
| `learning_rate` | 0.01 | Adam learning rate |
| `temperature` | 0.5 | Sampling creativity (0=deterministic, 1=chaotic) |

<br>

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `ANVIL_PORT` | `8080` | Web server port |
| `ANVIL_STATE_DB_PATH` | `./data/anvil-state.db` | Database file (`ANVIL_DB_PATH` deprecated) |
| `ANVIL_DB_AUTO_MIGRATE` | `true` | Auto-migrate DB schema on startup. Set to `false` for strict verification |
| `ANVIL_LOG_DIR` | `./logs/` | Log directory |
| `ANVIL_MLFLOW_URI` | `http://127.0.0.1:5001` | MLflow tracking server |
| `ANVIL_STORAGE_BACKEND` | `local` | Storage backend |
| `ANVIL_DEVICE` | *(auto)* | Device override (`cpu`, `cuda:0`, `mps`) |

Copy `.env.example` to `.env` to customize.

<br>

## Web UI Routes

| Route | Description |
|-------|-------------|
| `/` | Training dashboard (hero) |
| `/v1/datasets-page` | Dataset upload & management |
| `/v1/training-page` | Training configuration & control |
| `/v1/experiments-page` | Experiment history & comparison |
| `/v1/models-page` | Model registry & versioning |
| `/v1/inference-page` | Model inference / sampling playground |
| `/v1/learn` | Interactive concept walkthroughs |
| `/v1/operations-page` | Service management & logs |

<br>

## Commands

| Command | Purpose |
|---------|---------|
| `make setup` | Create venv, install deps from lock file via uv (DB auto-created on first `make run`) |
| `make setup-gpu` | Force GPU extras (auto-detected on Apple Silicon / NVIDIA Linux) |
| `make build` | Build the project wheel (`anvil-*.whl` in `dist/`) |
| `make run` | Start all background services (web + MLflow) |
| `make stop` | Stop all background services |
| `make train` | Run training from CLI |
| `make test` | Run full unit test suite |
| `make lint` | Run ruff → black --check → isort --check → pylint |
| `make format` | Auto-format (black + isort) |
| `make typecheck` | Run mypy/pyright |
| `make test-system` | Full validation loop: build wheel → container → system tests → teardown |
| `make compose-up` | Build + start the container stack locally |

<br>

## Troubleshooting

| Problem | Likely cause | Fix |
|---------|-------------|-----|
| `make setup`: `Python 3.11+ not found` | Python missing or not on PATH | Install Python ≥ 3.11, ensure `python3` or `python3.11` is on your `PATH` |
| `make setup`: `uv: command not found` | uv not installed | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| `make run`: `Address already in use` | Port 8080 (or 5001 for MLflow) is taken | Set `ANVIL_PORT=9090` in `.env` |
| `Alembic migration fails` | Stale or corrupted database | `rm -f data/anvil-state.db` then restart server (auto-creates fresh DB) |
| `GPU not detected` | No compatible GPU, or driver missing | Auto-detection logs at setup. Force GPU extras: `make setup-gpu` |
| Web UI slow on first load | Bootstrapping demo datasets | Normal — only on first `make run` after `make setup` |
| `make` fails on Windows | Windows lacks native `make` | Install WSL2 with Ubuntu and run from there |

<br>

## License

MIT

---


