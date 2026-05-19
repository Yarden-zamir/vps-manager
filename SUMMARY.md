# VPS Manager - Repository Summary

This repository manages native VPS deployments using systemd for process supervision, Caddy for HTTPS ingress, GitHub Actions for deployment, and Terraform for optional DNS automation.

## Main Pieces

- `scripts/bootstrap.sh` prepares a VPS with native runtimes, Caddy, directories, SSH settings, and support tooling.
- `scripts/create-service.py` creates service users, systemd units, Caddy route files, GitHub repos, GitHub secrets/variables, and optional DNS records.
- `templates/template-base` provides shared deployment and DNS workflows.
- `templates/template-js-express`, `template-python-fastapi`, and `template-go-gin` provide native service starters with `bin/start` entrypoints.
- `caddy/` documents the Caddy config model used on the VPS.
- `dns/terraform/` contains reusable DNS modules for Cloudflare, Netlify, DigitalOcean, and Linode.

## Runtime Architecture

```text
Client HTTPS request
    -> Caddy :443
    -> reverse_proxy 127.0.0.1:APP_PORT
    -> systemd service running /apps/APP_NAME/bin/start
```

Each service has:

- A Unix user like `svc-myapp`
- `/apps/myapp` for deployable code
- `/persistent/myapp` for data
- `/logs/myapp` for logs
- `/etc/systemd/system/myapp.service`
- `/etc/caddy/apps/myapp.caddy` when a domain is configured

## Usage Flow

1. Run `scripts/bootstrap.sh` once on the VPS.
2. Run `scripts/create-service.py myapp ./myapp --domain myapp.example.com --dns-provider cloudflare` locally.
3. Push application changes to `main`.
4. GitHub Actions copies files, runs `make deploy-prepare`, restarts systemd, and verifies health.

## Design Tradeoff

The repo is optimized for simple, low-ceremony deployments. It intentionally avoids Docker and orchestration layers in favor of native processes and a small number of predictable files on the VPS.
