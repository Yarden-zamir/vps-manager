# Base Makefile - This will be overridden by template-specific Makefile
.PHONY: run update test clean help

# Default target
.DEFAULT_GOAL := help

help: ## Show this help message
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-10s %s\n", $$1, $$2}'

run: ## Start the development server
	@echo "No run target defined for this template"

update: ## Install/update dependencies and generate lockfile
	@echo "No update target defined for this template"

test: ## Run tests
	@echo "No test target defined for this template"

clean: ## Clean generated files and dependencies
	@echo "No clean target defined for this template"

