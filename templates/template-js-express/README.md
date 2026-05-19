# JavaScript/Express with Bun

A native Bun service template for systemd deployments behind Caddy.

## Features

- **Bun Runtime**: Much faster than Node.js for startup and execution
- **Express.js**: Popular and familiar web framework
- **No Build Step**: Direct execution of TypeScript/JavaScript
- **Built-in Package Manager**: Fast dependency installation
- **Native Deployment**: systemd runs `bin/start`; Caddy handles HTTPS

## Quick Start

```bash
bun install
bun dev      # Development with hot reload
bun start    # Production server
```

## Stack

- **Runtime**: Bun 1.x
- **Framework**: Express.js 4.x
- **Process Manager**: systemd
- **Port**: Configurable via APP_PORT (default: 3000)
