# Service Creation

`scripts/create-service.py` is the main entrypoint for creating a new native VPS service.

## Basic Service

```bash
scripts/create-service.py myapp ./myapp
```

## Service With DNS

```bash
DNS_PROVIDER_TOKEN="token" scripts/create-service.py myapp ./myapp \
  --domain myapp.example.com \
  --dns-provider cloudflare
```

## What Gets Created

- A service user like `svc-myapp`
- Service directories under `/apps`, `/persistent`, and `/logs`
- A systemd unit named `myapp.service`
- A Caddy route file when `--domain` is provided
- A GitHub repo or remote connection
- GitHub secrets: `VPS_HOST`, `VPS_USER`, `VPS_PASSWORD`
- GitHub variables: `APP_NAME`, `APP_DOMAIN`, `APP_PORT`, `VPS_MANAGER_REPO`
- `infra/dns-records.json` when DNS is enabled

## Template Contract

Every service template must provide:

- `bin/start` as the production entrypoint
- `Makefile deploy-prepare` for dependency install/build work
- `/health` endpoint on `APP_PORT`
