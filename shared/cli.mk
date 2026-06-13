# CLI commands for training and utilities

train: $(VENV_DIR)/activate ## Run training from CLI
	$(PYTHON) -c "from microgpt.cli import train; train()"

progressive: $(VENV_DIR)/activate ## Run progressive training walkthrough (train0.py → train5.py)
	@for f in train0.py train1.py train2.py train3.py train4.py train5.py; do \
		if [ -f "examples/$$f" ]; then $(PYTHON) "examples/$$f"; fi; \
	done

vault: ## Open docs/vault/ in Obsidian
	@echo "Open docs/vault/ in Obsidian for the best experience."
	@open docs/vault/ 2>/dev/null || echo "Run: open docs/vault/"

.PHONY: train progressive vault