# Simple helper for colors and help

# Colors
GREEN := $(shell printf '\033[0;32m')
BLUE := $(shell printf '\033[0;34m')
RESET := $(shell printf '\033[0m')

# Help target (auto-discovers documented targets marked with "##")
help: ## Show all documented commands
	@echo "$(BLUE)microgpt-workbench$(RESET)"
	@echo "======================"
	@echo ""
	@grep -hE '^[a-zA-Z0-9_.-]+:.*##' Makefile shared/*.mk 2>/dev/null | \
		sed -E 's/:.*##/:##/' | \
		sort | \
		awk -F':##' '{ printf "  %-28s %s\n", $$1, $$2 }'
	@echo ""

.PHONY: help