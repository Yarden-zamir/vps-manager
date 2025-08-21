# DNS Management with OctoDNS

This directory contains the DNS configuration for all services deployed via this VPS manager.

## Directory Structure

- `zones/` - DNS record configurations (one YAML file per zone)
- `pyproject.toml` - Python dependencies for OctoDNS
- `config.yaml` - Base OctoDNS configuration

## How It Works

1. Each zone (domain) has a single configuration file:
   - `zones/<domain>.yaml` - The DNS records for that domain

2. Service repositories provide their own DNS provider tokens as secrets
3. GitHub Actions workflows handle plan/apply operations
4. Changes are made via pull requests with review

## Security Model

- No central secrets - each service provides its own provider token
- Authorization is token-based - if you have the token, you can manage the domain
- All changes tracked via git history
- PR review process for changes

## Supported Providers

- Cloudflare
- Netlify DNS
- DigitalOcean
- DNSimple
- Linode

See the main documentation for setup instructions.
