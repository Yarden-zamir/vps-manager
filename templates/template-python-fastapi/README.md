# Python/FastAPI with uv

Modern Python API development with FastAPI, uv, systemd, and Caddy.

## Features

- **FastAPI**: High-performance async web framework
- **uv Package Manager**: Extremely fast Python package installation
- **Type Safety**: Full Pydantic integration for request/response validation
- **Auto Documentation**: Built-in OpenAPI/Swagger docs
- **Production Ready**: Native systemd process, Caddy HTTPS, health checks, and error handling

## Quick Start

```bash
uv sync              # Install dependencies
uv run src/main.py   # Development server
```

## Stack

- **Language**: Python 3.11+
- **Framework**: FastAPI with Uvicorn
- **Package Manager**: uv (faster than pip)
- **Validation**: Pydantic v2
- **Process Manager**: systemd
- **Port**: Configurable via APP_PORT (default: 3000)
