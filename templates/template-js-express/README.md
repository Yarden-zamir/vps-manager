# JavaScript/Express with Bun

A high-performance Node.js alternative using Bun runtime with Express.js framework.

## Features

- **Bun Runtime**: Much faster than Node.js for startup and execution
- **Express.js**: Popular and familiar web framework
- **No Build Step**: Direct execution of TypeScript/JavaScript
- **Built-in Package Manager**: Fast dependency installation
- **Docker Support**: Optimized Dockerfile for production

## Quick Start

```bash
bun install
bun dev      # Development with hot reload
bun start    # Production server
```

## Stack

- **Runtime**: Bun 1.x
- **Framework**: Express.js 4.x
- **Container**: Alpine Linux
- **Port**: Configurable via APP_PORT (default: 3000)
