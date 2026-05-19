# Setup Guide

## Bootstrap A VPS

```bash
curl -sSL https://raw.githubusercontent.com/YOUR_GITHUB_USERNAME/vps-manager/main/scripts/bootstrap.sh -o bootstrap.sh
sudo bash bootstrap.sh --email admin@example.com
```

Bootstrap installs native runtimes, Caddy, GitHub CLI, support tools, and creates the base directories:

```text
/apps
/persistent
/logs
/etc/caddy/apps
```

## Create A Service

```bash
export VPS_HOST="your.vps.ip"
export VPS_MANAGER_REPO="YOUR_GITHUB_USERNAME/vps-manager"
export DNS_PROVIDER_TOKEN="your-provider-token"

scripts/create-service.py myapp ./myapp \
  --domain myapp.example.com \
  --dns-provider cloudflare
```

The creator configures:

- `svc-myapp` Unix user
- `/apps/myapp`, `/persistent/myapp`, `/logs/myapp`
- `/etc/systemd/system/myapp.service`
- `/etc/caddy/apps/myapp.caddy`
- GitHub Actions secrets and variables

## Deploy

Push to `main`. The generated workflow copies files to the VPS, runs `make deploy-prepare`, restarts `myapp.service`, and checks `/health`.
