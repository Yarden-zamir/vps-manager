# Service Template

This is the shared base for services that deploy natively to a VPS.

## Runtime Model

- GitHub Actions copies the repo to `/apps/<service>`.
- `make deploy-prepare` installs dependencies or builds artifacts.
- systemd runs `/apps/<service>/bin/start` as the dedicated service user.
- Caddy reverse proxies the public domain to `127.0.0.1:$APP_PORT`.

## Required GitHub Secrets

- `VPS_HOST` - VPS IP address or hostname
- `VPS_USER` - Service user, for example `svc-myapp`
- `VPS_PASSWORD` - Service user password generated during creation
- `DNS_PROVIDER_TOKEN` - Only required when DNS automation is used

## Required GitHub Variables

- `APP_NAME` - Service/systemd unit name
- `APP_DOMAIN` - Public hostname, for example `myapp.example.com`
- `APP_PORT` - Internal localhost port, usually `3000`
- `DNS_PROVIDER` - `netlify`, `cloudflare`, `digitalocean`, or `linode` when DNS automation is used

## DNS Management

DNS is managed via reusable Terraform workflows from `vps-manager`.

1. Define records in `infra/dns-records.json`.
2. Open a PR to run the DNS plan.
3. Merge to `main` to apply DNS changes.

## Service Requirements

- Include an executable `bin/start` script.
- Expose a `/health` endpoint on `APP_PORT`.
- Listen on `127.0.0.1` or `0.0.0.0`; Caddy handles public HTTPS.
