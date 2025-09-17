# Python/FastAPI with uv Makefile
.PHONY: run update test clean help

# Default target
.DEFAULT_GOAL := help

# Variables
APP_PORT ?= 3000

help: ## Show this help message
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-10s %s\n", $$1, $$2}'

run: ## Start the development server
	@echo "Starting development server on port $(APP_PORT)..."
	uv run src/main.py

update: ## Install/update dependencies and generate lockfile
	@echo "Installing dependencies with uv..."
	uv sync
	@echo "✓ Dependencies installed and uv.lock generated"

test: ## Run tests
	@echo "Running tests..."
	@if uv run --quiet python -c "import pytest" 2>/dev/null; then \
		uv run pytest; \
	else \
		echo "pytest not installed - skipping tests"; \
	fi

clean: ## Clean generated files and dependencies
	@echo "Cleaning up..."
	rm -rf .venv
	rm -f uv.lock
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

install: update ## Alias for update

dev: run ## Alias for run

build: ## Build for production (no-op for Python)
	@echo "No build step needed for Python - running directly from source"

start: ## Start production server
	@echo "Starting production server..."
	uv run src/main.py

lint: ## Run linting
	@echo "Running linting..."
	@if uv run --quiet python -c "import ruff" 2>/dev/null; then \
		uv run ruff check .; \
	else \
		echo "ruff not installed - skipping linting"; \
	fi

format: ## Format code
	@echo "Formatting code..."
	@if uv run --quiet python -c "import black" 2>/dev/null; then \
		uv run black .; \
	else \
		echo "black not installed - skipping formatting"; \
	fi

