# Terraform DNS Management (Local State)

Minimal Terraform for universal DNS records. Providers supported: netlify, cloudflare, digitalocean, linode. Uses a single generic token.

## Layout

- `main.tf` – Backend, providers, orchestration
- `records.tf` – Input variable schema and dynamic records wiring
- `modules/netlify/` – Netlify DNS module
- `modules/cloudflare/` – Cloudflare DNS module
- `modules/digitalocean/` – DigitalOcean DNS module
- `modules/linode/` – Linode DNS module
- `scripts/` – Helper scripts

## Prerequisites

- Terraform >= 1.5
- Provide `TF_VAR_dns_provider` with one of: `netlify`, `cloudflare`, `digitalocean`, `linode`
- Provide `TF_VAR_dns_provider_token` with the provider token (single generic secret)

## Usage

1) Initialize

```bash
cd dns/terraform
terraform init
```

2) Plan and apply

```bash
terraform plan -var='dns_provider=netlify' -var='dns_provider_token=${DNS_PROVIDER_TOKEN}'
terraform apply -auto-approve -var='dns_provider=netlify' -var='dns_provider_token=${DNS_PROVIDER_TOKEN}'
```

## Inputs

`records` is a list of objects with fields:

- `zone` – zone/domain name, e.g. "example.com"
- `name` – label/hostname ("" for apex, "*" for wildcard)
- `type` – A, AAAA, CNAME, TXT, MX, etc.
- `values` – list of strings; for MX/priority records, embed as `"10 mail.example.com."`
- `ttl` – optional number (provider permitting)

Example `records.auto.tfvars.json`:

```json
{
  "records": [
    {"zone": "example.com", "name": "", "type": "A", "values": ["192.0.2.1"]},
    {"zone": "example.com", "name": "www", "type": "CNAME", "values": ["example.com."]},
    {"zone": "example.com", "name": "", "type": "TXT", "values": ["\"v=spf1 a mx ~all\""]}
  ]
}
```

## Notes

- Local backend is used intentionally; state file is ignored by git.
- Only DNS record setup is handled here; keep other infrastructure separate.
- You can extend with more providers later if needed.


