# VPS Manager

A lightweight, native deployment toolkit for running web services on a VPS with systemd, Caddy and GitHub Actions.

## Philosophy

- **Native by default**: Services run directly on the VPS as systemd units.
- **Caddy for ingress**: Public HTTPS routing is handled by Caddy, not per-app proxy config.
- **Git-based deploys**: Push to `main` triggers deployment through GitHub Actions.
- **Simple operations**: No Docker, Compose, Kubernetes, or Swarm required.
- **Per-service isolation**: Each service gets its own Unix user and app/data/log directories.

## Quick Start

0. Clone the repo
1. Bootstrap your VPS:

```bash
curl -sSL https://raw.githubusercontent.com/YOUR_GITHUB_USERNAME/vps-manager/main/scripts/bootstrap.sh -o bootstrap.sh
sudo bash bootstrap.sh --email admin@example.com
```

2. Create a new service from your local machine:

```bash
export VPS_HOST="your.vps.ip"
export VPS_MANAGER_REPO="YOUR_GITHUB_USERNAME/vps-manager"
export DNS_PROVIDER_TOKEN="your-api-token"

/path/to/vps-manager/scripts/create-service.py myapp ./myapp \
  --domain myapp.example.com \
  --dns-provider cloudflare
```

3. Deploy by pushing to `main`.

## Repository Structure

```text
vps-manager/
├── caddy/                      # Caddy reference config and docs
├── dns/                        # Terraform DNS automation
├── docs/                       # Detailed documentation
├── scripts/
│   ├── bootstrap.sh            # One-time VPS setup
│   └── create-service.py       # Service creation/orchestration
└── templates/
    ├── template-base/          # Shared GitHub Actions and DNS workflow
    ├── template-js-express/    # Bun + Express native service
    ├── template-python-fastapi/# uv + FastAPI native service
    ├── template-go-gin/        # Go + Gin native service
    └── template-rust-axum/     # Rust + Axum starter docs
```

## Deployment Flow

1. Push to `main` triggers the service repo deploy workflow.
2. The workflow copies source to `/apps/{appname}` over SSH/SCP.
3. The workflow writes `/apps/{appname}/.env`.
4. `make deploy-prepare` installs dependencies or builds artifacts.
5. `sudo systemctl restart {appname}.service` restarts the service.
6. The workflow checks `http://127.0.0.1:{APP_PORT}/health`.
7. Caddy serves `https://{APP_DOMAIN}` and proxies to the localhost port.

## VPS Layout

```text
/
├── apps/              # Application code replaced on deploy
│   └── myapp/
├── persistent/        # Data that survives deploys
│   └── myapp/
├── logs/              # Application/proxy logs
│   ├── myapp/
│   └── caddy/
└── etc/
    ├── systemd/system/myapp.service
    └── caddy/apps/myapp.caddy
```

## Service Requirements

- Provide an executable `bin/start` script.
- Listen on `APP_PORT`.
- Expose `/health` with HTTP 200 when healthy.
- Keep persistent data under `/persistent/{APP_NAME}`.

## DNS

DNS is optional and handled through reusable Terraform workflows. Service repos own `infra/dns-records.json` and provide their own `DNS_PROVIDER_TOKEN`.

Supported providers: Cloudflare, Netlify, DigitalOcean, and Linode.

## Security Notes

This setup prioritizes convenience for hobby projects and prototypes. It creates per-service users and uses HTTPS by default, but root/password SSH remains enabled by bootstrap for simple automation.
