# DNS Management

DNS is managed by Terraform through reusable GitHub Actions workflows.

## Record Schema

Service repos define `infra/dns-records.json`:

```json
{
  "records": [
    {"zone": "example.com", "name": "api", "type": "A", "values": ["203.0.113.10"], "ttl": 300}
  ]
}
```

## Workflows

- Pull requests run `dns-plan.yml`.
- Pushes to `main` run `dns-apply.yml`.

## Providers

- Cloudflare
- Netlify
- DigitalOcean
- Linode

The service repo supplies `DNS_PROVIDER_TOKEN`; the central repo supplies Terraform code.
