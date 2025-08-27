# JavaScript/Express with Bun Makefile
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
	bun --watch src/index.js

update: ## Install/update dependencies and generate lockfile
	@echo "Installing dependencies with Bun..."
	bun install
	@echo "✓ Dependencies installed and bun.lockb generated"

test: ## Run tests
	@echo "Running tests..."
	@if [ -f "package.json" ] && grep -q '"test"' package.json; then \
		bun test; \
	else \
		echo "No tests configured in package.json"; \
	fi

clean: ## Clean generated files and dependencies
	@echo "Cleaning up..."
	rm -rf node_modules
	rm -f bun.lockb

install: update ## Alias for update

dev: run ## Alias for run

build: ## Build for production (no-op for Bun)
	@echo "No build step needed for Bun - running directly from source"

start: ## Start production server
	@echo "Starting production server..."
	bun src/index.js
