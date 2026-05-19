# DNS Quick Start

DNS automation is optional. When enabled, each service repo owns `infra/dns-records.json` and calls reusable Terraform workflows from `vps-manager`.

## Create A Service With DNS

```bash
export VPS_HOST="your.vps.ip"
export VPS_MANAGER_REPO="YOUR_GITHUB_USERNAME/vps-manager"
export DNS_PROVIDER_TOKEN="provider-token"

scripts/create-service.py myapp ./myapp \
  --domain myapp.example.com \
  --dns-provider cloudflare
```

The script writes records similar to:

```json
{
  "records": [
    {"zone": "example.com", "name": "myapp", "type": "A", "values": ["203.0.113.10"]},
    {"zone": "example.com", "name": "www.myapp", "type": "CNAME", "values": ["myapp.example.com."]}
  ]
}
```

After DNS resolves, Caddy can issue HTTPS certificates automatically.
