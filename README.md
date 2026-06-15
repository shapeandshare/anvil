<p align="center">
  <svg viewBox="0 0 240 160" width="120" height="80" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
    <path d="M 10,66 C 23,46 30,14 46,14 L 200,14 C 218,14 224,14 224,44 C 224,68 178,92 158,98 L 158,124 C 158,128 168,130 216,130 L 216,155 L 24,155 L 24,130 C 72,130 82,128 82,124 L 82,98 C 60,90 24,78 20,74 C 14,70 10,68 10,66 Z" fill="currentColor" opacity="0.9"/>
  </svg>
</p>

<h1 align="center">anvil</h1>

<p align="center"><strong>Forging intelligence.</strong></p>

<p align="center">Train and experiment with LLMs from scratch — a pip-installable workbench built on Karpathy's microgpt.py with live training dashboards, MLflow experiment tracking, and an iOS-modern web UI.</p>

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

## Quick Start

```bash
git clone https://github.com/shapeandshare/anvil
cd anvil
make setup
make run
```

Open `http://<your-ip>:8080` from any device on your LAN.

> **GPU acceleration**: Auto-detected on Apple Silicon (MPS) and NVIDIA Linux (CUDA). Falls back to CPU when unavailable.

<br>

## Features

| | | |
|---|---|---|
| 🧠 **Train GPT from scratch** | 📊 **Experiment tracking** | 📁 **Dataset management** |
| Configure hyperparameters, watch loss in real-time via SSE | MLflow-backed, compare loss curves side-by-side | Upload custom `.txt` datasets, train on anything |
| 🔧 **Operations dashboard** | ✨ **iOS-modern UI** | 📖 **Progressive walkthroughs** |
| Manage services (web, MLflow), tail logs, health checks | Glass nav bar, spring animations, dark/light mode | 6 scripts from bigrams to full GPT, interactive widgets |

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
| `ANVIL_DB_PATH` | `./data/anvil.db` | Database file |
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
| `make setup` | Create venv, install deps, init DB |
| `make run` | Start all background services (web + MLflow) |
| `make stop` | Stop all background services |
| `make train` | Run training from CLI |
| `make test` | Run full test suite |
| `make lint` | Run ruff → black --check → isort --check → pylint |
| `make format` | Auto-format (black + isort) |
| `make typecheck` | Run mypy/pyright |

<br>

## License

MIT

---

<p align="center"><sub>Built with Swift-like care for the craft of learning.</sub></p>
