# Unified Service Creation

Service creation and DNS setup are handled by one command: `scripts/create-service.py`.

The script performs local, GitHub, VPS, systemd, Caddy, and optional DNS setup in one flow.

## Required Environment

- `VPS_HOST`
- `VPS_MANAGER_REPO`
- `DNS_PROVIDER_TOKEN` when using `--domain`

## Examples

```bash
scripts/create-service.py api ~/projects/api
```

```bash
scripts/create-service.py web ~/projects/web \
  --domain web.example.com \
  --dns-provider netlify
```

## Native Runtime

The generated app runs as a systemd service. Public HTTPS is handled by Caddy, which proxies to the service's localhost port.
