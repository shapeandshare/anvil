# 🦄 microgpt-workbench

**Train and experiment with LLMs from scratch — all in your browser.**

microgpt-workbench is a pip-installable Python package wrapping [Karpathy's microgpt.py](https://gist.github.com/karpathy/8627fe009c40f57531cb18360106ce95) with a FastAPI web server, MLflow experiment tracking, and a whimsical retro UI.

## Quick Start

```bash
pip install microgpt-workbench
make run
```

Open `http://<your-ip>:8080` from any device on your LAN.

## Features

- **🧠 Train GPT from scratch** — configure hyperparameters, watch loss in real-time via SSE
- **📊 Experiment tracking** — MLflow-backed, compare loss curves side-by-side
- **📁 Dataset management** — upload custom `.txt` datasets, train on anything
- **🔧 Operations dashboard** — manage services (web, MLflow), tail logs, health checks
- **🎮 Retro web UI** — pixel art, ASCII banners, unicorn mascot 🦄, CSS animations
- **🚀 GPU acceleration** — MPS on Apple Silicon, CUDA on Linux (optional)
- **📖 Progressive walkthrough** — 6 training scripts from bigrams to full GPT

## Architecture

```
microgpt/          # Python package (implicit namespace)
├── core/          # Stdlib-only training engine (zero deps)
├── db/            # Async SQLAlchemy + repositories
├── services/      # Business logic layer
├── api/           # FastAPI server + Jinja2 templates + SSE
├── storage/       # File storage abstraction (local/S3-ready)
└── supervisor/    # Process manager for background services
```

## Hyperparameter Guide

| Parameter | Default | Description |
|-----------|---------|-------------|
| `n_embd` | 16 | Embedding dimension (wider = more capacity) |
| `n_layer` | 1 | Transformer depth (deeper = more patterns) |
| `n_head` | 4 | Attention heads (must divide n_embd) |
| `num_steps` | 1000 | Training iterations |
| `learning_rate` | 0.01 | Adam learning rate |
| `temperature` | 0.5 | Sampling creativity (0=deterministic, 1=chaotic) |

## Web UI Routes

| Route | Description |
|-------|-------------|
| `/` | Training dashboard |
| `/experiments` | Experiment history & comparison |
| `/datasets` | Dataset upload & management |
| `/operations` | Service management & logs |
| `/inference` | Model inference/sampling |
| `/v1/docs` | Auto-generated Swagger API docs |

## Configuration

Copy `.env.example` to `.env` and customize:

| Variable | Default | Description |
|----------|---------|-------------|
| `MICROGPT_PORT` | `8080` | Web server port |
| `MICROGPT_DB_PATH` | `./data/microgpt.db` | Database file |
| `MICROGPT_LOG_DIR` | `./logs/` | Log directory |
| `MICROGPT_MLFLOW_URI` | `http://127.0.0.1:5000` | MLflow HTTP tracking server URI (drives writers AND readers) |

> **MLflow**: Requires MLflow 3.x (`mlflow>=3.1,<4`). Uses source-keyed model registry (one registered model per dataset/corpus source).
| `MICROGPT_STORAGE_BACKEND` | `local` | Storage backend |

## License

MIT
