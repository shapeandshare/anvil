<p align="center">
  <img src="docs/assets/anvil-banner.svg" alt="anvil — Forging intelligence" width="100%">
</p>

<p align="center">
  <a href="https://www.python.org/downloads/"><img alt="Python 3.11+" src="https://img.shields.io/badge/python-3.11%2B-3776ab?style=for-the-badge&logo=python&logoColor=white"></a>&nbsp;
  <a href="#license"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-ff9500?style=for-the-badge"></a>&nbsp;
  <a href="https://github.com/psf/black"><img alt="Code style: black" src="https://img.shields.io/badge/code%20style-black-000000?style=for-the-badge"></a>&nbsp;
  <a href="https://mypy-lang.org/"><img alt="Typed: mypy strict" src="https://img.shields.io/badge/typed-mypy%20strict-2a6db2?style=for-the-badge&logo=python&logoColor=white"></a>&nbsp;
  <a href="https://www.conventionalcommits.org/"><img alt="Conventional Commits" src="https://img.shields.io/badge/commits-conventional-ffcc00?style=for-the-badge"></a>
</p>

<p align="center">
  <strong>Train and experiment with LLMs from scratch.</strong><br>
  A pip-installable workbench with live training dashboards, MLflow experiment tracking, and an iOS-modern web UI.
</p>

<p align="center">
  <a href="#-quick-start"><kbd>&nbsp;Quick Start&nbsp;</kbd></a>&nbsp;
  <a href="#-features"><kbd>&nbsp;Features&nbsp;</kbd></a>&nbsp;
  <a href="#-architecture"><kbd>&nbsp;Architecture&nbsp;</kbd></a>&nbsp;
  <a href="#-hyperparameter-guide"><kbd>&nbsp;Hyperparameters&nbsp;</kbd></a>&nbsp;
  <a href="#-configuration"><kbd>&nbsp;Config&nbsp;</kbd></a>&nbsp;
  <a href="#-troubleshooting"><kbd>&nbsp;Troubleshooting&nbsp;</kbd></a>
</p>

<br>

---

## ✨ What is anvil?

**anvil** is an interactive workbench for understanding how language models actually work — by building one from the ground up. It pairs a **dependency-free training engine** (RoPE, SwiGLU MLP, RMSNorm — the same primitives as production Llama models) with a polished web UI: configure a model, pick your data, and **watch it learn character by character in real time**.

Every concept here scales up directly to real models. Train in seconds, then open the interactive lessons to see what's happening under the hood.

<br>

<p align="center">
  <img src="docs/assets/showcase.svg" alt="anvil training dashboard: live loss curve, step/loss/device metrics, and sample generated output" width="100%">
</p>

<br>

<p align="center">
  <img src="docs/assets/stats.svg" alt="By the numbers: 0 core deps, 8 UI pages, 100% typed, 3 Llama primitives, MIT licensed" width="100%">
</p>

<br>

<p align="center"><img src="docs/assets/divider.svg" alt="" width="100%"></p>

### How it works

<p align="center">
  <img src="docs/assets/workflow.svg" alt="anvil workflow: upload data → train → track → export → play" width="100%">
</p>

<br>

<p align="center"><img src="docs/assets/divider.svg" alt="" width="100%"></p>

## 🚀 Quick Start

> [!IMPORTANT]
> anvil targets **macOS and Linux**. The toolchain is `make` + `bash`-based, so a POSIX shell is required.

**From source** (for development):

```bash
git clone https://github.com/shapeandshare/anvil
cd anvil
make setup     # create venv, install deps via uv, init DB
make run       # start web UI + MLflow
```

Then open **`http://localhost:8080`** — or `http://<your-ip>:8080` from any device on your LAN.

**From a built wheel** (for end users):

```bash
make build         # build anvil-*.whl into dist/
make compose-up    # build + run the container stack
open http://localhost:8080
# or run the full validation loop:
make test-system   # build → container → system tests → teardown
```

<br>

<p align="center"><img src="docs/assets/divider.svg" alt="" width="100%"></p>

## 🎯 Features

<p align="center">
  <img src="docs/assets/features.svg" alt="Features: Data, Train, Experiments, Models, Learn, Ops" width="100%">
</p>

<table>
<tr>
<td width="33%" valign="top">

**🧠 Train from scratch**<br>
Configure hyperparameters and watch loss curves stream live over SSE — no black boxes.

</td>
<td width="33%" valign="top">

**📊 Experiment tracking**<br>
MLflow-backed runs. Compare loss curves side-by-side and register your best models.

</td>
<td width="33%" valign="top">

**📁 Dataset management**<br>
Upload custom `.txt` corpora, curate datasets, and train on anything you like.

</td>
</tr>
<tr>
<td width="33%" valign="top">

**🔧 Operations dashboard**<br>
Manage services, monitor CPU/GPU/memory, tail logs, run health checks.

</td>
<td width="33%" valign="top">

**📱 iOS-modern UI**<br>
Glass nav bars, spring animations, fluid type, and adaptive dark/light mode.

</td>
<td width="33%" valign="top">

**📖 Interactive lessons**<br>
Progressive walkthroughs from bigrams to a full transformer, with live widgets.

</td>
</tr>
</table>

<br>

<p align="center"><img src="docs/assets/divider.svg" alt="" width="100%"></p>

## 🧬 The Engine

anvil's core (`anvil/core/`) is a **zero-dependency, stdlib-only** training engine that mirrors modern Llama-class architecture:

<p align="center">
  <img src="docs/assets/engine.svg" alt="anvil transformer block: token embedding → RMSNorm → Multi-Head Attention + RoPE → RMSNorm → SwiGLU MLP → RMSNorm → LM head" width="80%">
</p>

<br>

| Component | What it is | Why it matters |
|-----------|-----------|----------------|
| **RoPE** | Rotary Position Encoding | Same half-split/rotate convention as HuggingFace Llama — positions encoded in attention, no learned embeddings |
| **SwiGLU MLP** | SiLU-gated feed-forward | Gate/up/down projections replace ReLU; `intermediate_size ≈ 8·n_embd/3` for parameter parity |
| **RMSNorm** | Learned-scale normalization | Lighter than LayerNorm, learnable `rms_1` / `rms_2` / `rms_final` weights |
| **Safetensors** | HF-convention export | Emits `model.safetensors` + `config.json` + `tokenizer.json`, ready to load elsewhere |

<br>

<p align="center"><img src="docs/assets/divider.svg" alt="" width="100%"></p>

## 🏛️ Architecture

<p align="center">
  <img src="docs/assets/architecture.svg" alt="Layered architecture: Routes/CLI → AnvilWorkbench god class → Services → Repositories → Core Engine + Storage" width="100%">
</p>

<br>

```
anvil/                         # Python package (implicit namespace)
├── core/                      # Stdlib-only training engine (zero deps)
│   ├── engine.py              #   Transformer: RoPE, SwiGLU MLP, RMSNorm
│   ├── torch_engine.py        #   PyTorch training loop with checkpointing
│   ├── autograd.py            #   Custom autograd engine
│   └── tokenizer.py           #   Byte-level tokenizer
├── db/                        # Async SQLAlchemy
│   ├── models/                #   ORM models (domain sub-packages)
│   └── repositories/          #   Repository pattern (DB access only)
├── services/                  # Business logic — domain sub-packages
│   ├── training/              #   Orchestration, export, memory estimation
│   ├── tracking/              #   MLflow experiment tracking, metrics
│   ├── datasets/              #   Corpora, datasets, import, curation
│   ├── inference/             #   Inference, loaded model, demo provider
│   └── _shared/               #   Cross-domain types (internal)
├── api/                       # FastAPI server + Jinja2 + SSE
│   ├── static/                #   CSS tokens, components, archetypes
│   ├── templates/             #   Jinja2 page templates (hero, etc.)
│   └── v1/                    #   Route definitions (v1 router)
├── storage/                   # File storage abstraction (local/S3-ready)
└── supervisor/                # Process manager for background services
```

> **Layer discipline:** Repository → Service → God Class (`AnvilWorkbench`) → Routes/CLI. No shortcuts.

<br>

<p align="center"><img src="docs/assets/divider.svg" alt="" width="100%"></p>

## 🎛️ Hyperparameter Guide

<p align="center">
  <img src="docs/assets/hyperparams.svg" alt="Model anatomy (n_embd, n_head, n_layer) and default hyperparameter values" width="100%">
</p>

<br>

| Parameter | Default | Description |
|-----------|---------|-------------|
| `n_embd` | `16` | Embedding dimension — wider = more capacity |
| `n_layer` | `1` | Transformer depth — deeper = more patterns |
| `n_head` | `4` | Attention heads (must divide `n_embd`) |
| `num_steps` | `1000` | Training iterations |
| `learning_rate` | `0.01` | Adam learning rate |
| `temperature` | `0.5` | Sampling creativity (`0` = deterministic, `1` = chaotic) |

<br>

<p align="center"><img src="docs/assets/divider.svg" alt="" width="100%"></p>

## ⚙️ Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `ANVIL_PORT` | `8080` | Web server port |
| `ANVIL_STATE_DB_PATH` | `./data/anvil-state.db` | Database file (`ANVIL_DB_PATH` deprecated) |
| `ANVIL_DB_AUTO_MIGRATE` | `true` | Auto-migrate schema on startup; set `false` for strict verification |
| `ANVIL_LOG_DIR` | `./logs/` | Log directory |
| `ANVIL_MLFLOW_URI` | `http://127.0.0.1:5001` | MLflow tracking server |
| `ANVIL_STORAGE_BACKEND` | `local` | Storage backend |
| `ANVIL_DEVICE` | *(auto)* | Device override (`cpu`, `cuda:0`, `mps`) |

> Copy `.env.example` to `.env` to customize.

<br>

<p align="center"><img src="docs/assets/divider.svg" alt="" width="100%"></p>

## 🗺️ Web UI Routes

<p align="center">
  <img src="docs/assets/routes.svg" alt="Web UI sitemap: Dashboard, Datasets, Training, Experiments, Models, Playground, Learn, Operations" width="100%">
</p>

<br>

| Route | Page |
|-------|------|
| `/` | Training dashboard (hero) |
| `/v1/datasets-page` | Dataset upload & management |
| `/v1/training-page` | Training configuration & control |
| `/v1/experiments-page` | Experiment history & comparison |
| `/v1/models-page` | Model registry & versioning |
| `/v1/inference-page` | Inference / sampling playground |
| `/v1/learn` | Interactive concept walkthroughs |
| `/v1/operations-page` | Service management & logs |

<br>

<p align="center"><img src="docs/assets/divider.svg" alt="" width="100%"></p>

## 💻 Platform Support

anvil is developed and exercised on **macOS** and **Linux**. The dev workflow relies on `make` and `bash`, so a POSIX shell is required.

| Platform | Status | Notes |
|----------|--------|-------|
| **macOS** (Apple Silicon) | ✅ Supported | GPU (MPS) works out of the box — it ships in the standard PyTorch wheel |
| **macOS** (Intel) | ✅ Supported | CPU only |
| **Linux** (x86_64) | ✅ Supported | CPU by default; NVIDIA GPU supported with a working driver (see below) |

### GPU acceleration

GPU support is **auto-detected** at `make setup` and can be forced with `make setup-gpu`:

- **Apple Silicon (macOS)** — MPS is built into the standard PyTorch wheel; nothing extra to install.
- **NVIDIA (Linux)** — requires a working NVIDIA **driver** on the host (`nvidia-smi` must be on `PATH`). anvil installs the standard PyPI `torch` wheel, which **bundles the CUDA runtime**, so you do *not* need a separate CUDA Toolkit — but you *do* need a compatible host driver.

When no GPU is detected, anvil runs on CPU.

<br>

<p align="center"><img src="docs/assets/divider.svg" alt="" width="100%"></p>

## 📋 Prerequisites

| Requirement | Notes |
|-------------|-------|
| **Python ≥ 3.11** | Must be on `PATH` as `python3` or `python3.11` — [python.org](https://www.python.org/downloads/) |
| **git** | [Download](https://git-scm.com/downloads) |
| **GNU make** | macOS: `xcode-select --install` · Debian/Ubuntu: `apt install build-essential` |
| **bash** | Pre-installed on macOS / Linux |
| **uv** | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| **NVIDIA driver + `nvidia-smi`** *(optional)* | Linux only — required for CUDA GPU acceleration & auto-detection |

<br>

<p align="center"><img src="docs/assets/divider.svg" alt="" width="100%"></p>

## 🛠️ Commands

| Command | Purpose |
|---------|---------|
| `make setup` | Create venv, install deps from lock file via uv (DB auto-created on first `make run`) |
| `make setup-gpu` | Force GPU extras (auto-detected on Apple Silicon / NVIDIA Linux) |
| `make build` | Build the project wheel (`anvil-*.whl` in `dist/`) |
| `make run` | Start all background services (web + MLflow) |
| `make stop` | Stop all background services |
| `make train` | Run training from the CLI |
| `make test` | Run the full unit test suite |
| `make lint` | Run ruff → black --check → isort --check → pylint |
| `make format` | Auto-format (black + isort) |
| `make typecheck` | Run mypy/pyright |
| `make test-system` | Full loop: build wheel → container → system tests → teardown |
| `make compose-up` | Build + start the container stack locally |

<br>

<p align="center"><img src="docs/assets/divider.svg" alt="" width="100%"></p>

## 🩺 Troubleshooting

| Problem | Likely cause | Fix |
|---------|-------------|-----|
| `make setup`: `Python 3.11+ not found` | Python missing or not on PATH | Install Python ≥ 3.11; ensure `python3`/`python3.11` is on `PATH` |
| `make setup`: `uv: command not found` | uv not installed | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| `make run`: `Address already in use` | Port 8080 (or 5001 for MLflow) is taken | Set `ANVIL_PORT=9090` in `.env` |
| `Alembic migration fails` | Stale or corrupted database | `rm -f data/anvil-state.db`, then restart (auto-creates fresh DB) |
| GPU not detected (Linux) | NVIDIA driver missing, or `nvidia-smi` not on `PATH` | Install the NVIDIA driver; verify `nvidia-smi` runs, then `make setup-gpu` |
| Web UI slow on first load | Bootstrapping demo datasets | Normal — only on the first `make run` after `make setup` |

<br>

<p align="center"><img src="docs/assets/divider.svg" alt="" width="100%"></p>

## License

Released under the **MIT License**.

<br>

<p align="center">
  <sub>Built with 🔨 by <a href="https://github.com/joshburt">Josh Burt</a> · <em>Forging intelligence.</em></sub>
</p>
