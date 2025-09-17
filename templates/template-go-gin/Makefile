# Go/Gin Makefile
.PHONY: run update test clean help

# Default target
.DEFAULT_GOAL := help

# Variables
APP_PORT ?= 3000
BINARY_NAME := app-template

help: ## Show this help message
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-10s %s\n", $$1, $$2}'

run: ## Start the development server
	@echo "Starting development server on port $(APP_PORT)..."
	go run main.go

update: ## Install/update dependencies and generate lockfile
	@echo "Downloading dependencies..."
	go mod download
	@echo "Tidying up go.mod and generating go.sum..."
	go mod tidy
	@echo "✓ Dependencies updated and go.sum generated"

test: ## Run tests
	@echo "Running tests..."
	go test -v ./...

clean: ## Clean generated files and dependencies
	@echo "Cleaning up..."
	go clean
	rm -f $(BINARY_NAME)
	rm -f main

install: update ## Alias for update

dev: run ## Alias for run

build: ## Build for production
	@echo "Building binary..."
	CGO_ENABLED=0 GOOS=linux go build -a -installsuffix cgo -o $(BINARY_NAME) .
	@echo "✓ Binary built: $(BINARY_NAME)"

start: build ## Build and start production server
	@echo "Starting production server..."
	./$(BINARY_NAME)

fmt: ## Format code
	@echo "Formatting code..."
	go fmt ./...

vet: ## Run go vet
	@echo "Running go vet..."
	go vet ./...

mod-verify: ## Verify dependencies
	@echo "Verifying dependencies..."
	go mod verify

