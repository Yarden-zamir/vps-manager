# Quick Start: Service with DNS

This guide shows how to create and deploy a service with automatic DNS configuration.

## Prerequisites

- VPS already bootstrapped with `bootstrap.sh`
- GitHub CLI (`gh`) installed and authenticated
- DNS provider account (Cloudflare, Netlify, etc.)
- Domain name you control

## 1. Create the Service

```bash
# Set environment variables
export VPS_MANAGER_REPO="yourname/vps-manager"
export VPS_HOST="your.vps.ip"
export VPS_MANAGER_PATH="$HOME/vps-manager"  # Path to your local vps-manager repo

# Create service with domain and DNS provider
./vps-manager/scripts/create-service.py \
  --service-name myapp \
  --local-path ~/projects/myapp \
  --domain myapp.com \
  --dns-provider cloudflare
```

This automatically:
- Creates service user on VPS
- Sets up GitHub repository
- Configures DNS workflows with your domain and provider
- Creates DNS zone configuration
- Prepares everything for deployment

## 2. Set DNS Provider Token

```bash
cd ~/projects/myapp

# Add your DNS provider token
gh secret set DNS_PROVIDER_TOKEN

# For Cloudflare: Use API token with Zone:Read and DNS:Edit permissions
# For Netlify: Use personal access token
# For others: See docs/dns-management.md
```

## 3. Review DNS Configuration

The service creator already created your DNS configuration:

```bash
cd ~/vps-manager
# Review the DNS configuration that was created
cat dns/zones/myapp.com.yaml

# Push the DNS branch that was created
git push -u origin dns-setup-myapp.com

# Create a pull request
gh pr create --title "Add DNS configuration for myapp.com"
```

## 4. Deploy Everything

```bash
# Back in your service directory
cd ~/projects/myapp

# Push your code (triggers deployment)
git add .
git commit -m "Initial deployment"
git push

# After DNS PR is merged in vps-manager, apply DNS
gh workflow run dns-apply.yml
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
1. Edit `dns/zones/myapp.com.yaml` in vps-manager
2. Create PR and review changes
3. Merge PR
4. Run `gh workflow run dns-apply.yml` in service repo

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
