# DNS Management With Terraform

This directory contains reusable DNS automation for services deployed by VPS Manager.

## Structure

- `terraform/` - Provider-neutral Terraform entrypoint and provider modules
- `terraform/modules/cloudflare/` - Cloudflare records
- `terraform/modules/netlify/` - Netlify records
- `terraform/modules/digitalocean/` - DigitalOcean records
- `terraform/modules/linode/` - Linode records

## How It Works

Service repositories own `infra/dns-records.json` and call the reusable workflows in `.github/workflows/`.

Each service provides its own `DNS_PROVIDER_TOKEN`, so there is no central DNS secret in this repo.
