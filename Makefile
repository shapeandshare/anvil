include shared/helper.mk
include shared/python.mk
include shared/server.mk
include shared/testing.mk
include shared/cli.mk
include shared/database.mk

## Convenience aliases

setup-gpu: install-gpu ## Force GPU setup (auto-detected on Apple Silicon / NVIDIA Linux; use this to override)
	@echo ""
	@echo "GPU setup complete. Start the web app with 'make run' or train with 'make train-gpu'."

run-gpu: export MICROGPT_DEVICE=auto
run-gpu: run ## Start web server with GPU auto-detection

train-gpu: export USE_GPU=true
train-gpu: $(VENV_DIR)/activate ## Train with GPU acceleration (also defined in cli.mk)
	$(PYTHON) -c "from microgpt.cli import train; train()"