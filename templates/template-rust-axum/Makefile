# Rust/Axum Makefile
.PHONY: run update deploy-prepare test clean help build start fmt

.DEFAULT_GOAL := help

APP_PORT ?= 3000
BINARY_NAME := app-template

help: ## Show this help message
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-10s %s\n", $$1, $$2}'

run: ## Start the development server
	cargo run

update: ## Fetch dependencies and generate lockfile
	cargo fetch
	cargo generate-lockfile

deploy-prepare: update build ## Prepare binary for native deployment
	@echo "✓ Rust service ready for systemd"

test: ## Run tests
	cargo test

clean: ## Clean generated files
	cargo clean
	rm -f $(BINARY_NAME)

build: ## Build for production
	cargo build --release
	cp target/release/$(BINARY_NAME) ./$(BINARY_NAME)

start: build ## Build and start production server
	./$(BINARY_NAME)

fmt: ## Format code
	cargo fmt
