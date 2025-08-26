# Quick Start: Service with DNS

This guide shows how to create and deploy a service with automatic DNS configuration.

## Prerequisites

- VPS already bootstrapped with `bootstrap.sh`
- GitHub CLI (`gh`) installed and authenticated
- DNS provider account (Netlify, Cloudflare, DigitalOcean, Linode)
- Domain name you control

## 1. Create the Service

```bash
# Set environment variables
export VPS_MANAGER_REPO="yourname/vps-manager"
export VPS_HOST="your.vps.ip"
export VPS_MANAGER_PATH="$HOME/vps-manager"  # Path to your local vps-manager repo

# Create service (domain optional)
./vps-manager/scripts/create-service.py \
  myapp \
  ~/projects/myapp \
  --domain myapp.com \
  --dns-provider netlify
```

This automatically:
- Creates service user on VPS
- Sets up GitHub repository
- Configures DNS workflows with your domain and provider
- Creates DNS zone configuration
- Prepares everything for deployment

## 2. Set DNS Provider Token (generic)

```bash
cd ~/projects/myapp

# Add your DNS provider token (generic)
gh secret set DNS_PROVIDER_TOKEN

# Set provider in your DNS workflow as dns_provider=netlify|cloudflare|digitalocean|linode
```

## 3. Prepare DNS records JSON in your service repo

Create (or update) `infra/dns-records.json` in your service repo:

```json
{
  "records": [
    {"zone": "myapp.com", "name": "", "type": "A", "values": ["YOUR_VPS_IP"]},
    {"zone": "myapp.com", "name": "www", "type": "CNAME", "values": ["myapp.com."]}
  ]
}
```

## 4. Deploy Everything

```bash
# Back in your service directory
cd ~/projects/myapp

# Push your code (triggers deployment)
git add .
git commit -m "Initial deployment"
git push

# Trigger DNS apply in your service repo (example)
gh workflow run dns.yml
```

## That's It! 🎉

Your service is now:
- ✅ Deployed to your VPS
- ✅ Running with Docker
- ✅ Accessible via HTTPS
- ✅ DNS configured automatically

Visit https://myapp.com to see your service!

## What Just Happened?

1. **Service Creation**: Set up user, directories, and GitHub repo
2. **DNS Workflows**: Automatically configured for your domain
3. **DNS Records**: Created A records pointing to your VPS
4. **Deployment**: GitHub Actions built and deployed your app
5. **HTTPS**: Traefik automatically got Let's Encrypt certificate

## Making Changes

### Update Code
```bash
git add .
git commit -m "Update feature"
git push  # Auto-deploys
```

### Update DNS
1. Edit `infra/dns-records.json` in your service repo
2. Open PR to review plan
3. Merge to main to apply

### Add Subdomain
```yaml
# In dns/zones/myapp.com.yaml
api:
  type: A
  value: YOUR_VPS_IP
```

## Tips

- DNS workflows are pre-configured with your domain
- Provider is guessed from TLD (.dev → Netlify)
- All DNS changes go through PR review
- No shared secrets - each service has its own token

## Troubleshooting

### DNS Not Updating
- Check workflow runs: `gh run list --workflow=dns-apply.yml`
- Verify token: `gh secret list`
- Check provider dashboard

### Service Not Accessible
- DNS propagation can take time
- Check deployment: `gh run list --workflow=deploy.yml`
- SSH to VPS: `ssh svc-myapp@your.vps.ip`

See [DNS Management Guide](dns-management.md) for detailed information.
