# DNS Management with OctoDNS

This guide explains how DNS management is integrated into the VPS Manager using OctoDNS and GitHub Actions.

## Overview

The VPS Manager provides centralized DNS configuration management while maintaining decentralized control. Each service owns its domain and provides its own DNS provider credentials, ensuring security and autonomy.

## Architecture

### Components

1. **Central Config Repository** (`vps-manager`)
   - Stores all DNS zone configurations in `dns/zones/`
   - Stores provider metadata in `dns/zones-meta/`
   - Provides reusable GitHub workflows
   - Single source of truth with git history

2. **Service Repositories**
   - Own their domains
   - Store DNS provider tokens as secrets
   - Call central workflows to manage DNS

3. **GitHub Actions Workflows**
   - `dns-plan.yml` - Shows what changes will be made
   - `dns-apply.yml` - Applies changes to DNS provider

### Security Model

- **No central secrets** - Each service provides its own provider token
- **Domain isolation** - Services can only modify their own domains
- **Audit trail** - All changes tracked in git
- **PR review** - Changes go through standard review process

## Setting Up DNS for Your Service

### 1. Choose Your DNS Provider

Supported providers:
- **Cloudflare** - Fast, reliable, good API
- **Netlify DNS** - Great for Netlify-hosted sites
- **DigitalOcean** - If you're already using DO
- **DNSimple** - Professional DNS service
- **Linode** - Another VPS provider option

### 2. Add DNS Configuration

Create a pull request to `vps-manager` adding your zone configuration:

#### Zone Configuration
Create `dns/zones/yourdomain.com.yaml`:

```yaml
# DNS records for yourdomain.com

# Root domain pointing to VPS
'':
  type: A
  value: YOUR_VPS_IP

# WWW redirect
www:
  type: CNAME
  value: yourdomain.com.

# Your service subdomain
myapp:
  type: A
  value: YOUR_VPS_IP
```

Note: No metadata file needed - just provide your DNS provider token!

### 3. Set Up Provider Token

In your service repository, add the DNS provider token as a secret:

1. Go to Settings → Secrets and variables → Actions
2. Add repository secret `DNS_PROVIDER_TOKEN`

Token format by provider:
- **Cloudflare**: API token with Zone:Read and DNS:Edit permissions
- **Netlify**: Personal access token
- **DigitalOcean**: Personal access token with read/write scope
- **DNSimple**: Format as `account_id:api_token`
- **Linode**: Personal access token with domains:read_write scope

### 4. Add DNS Workflows to Your Service

Create `.github/workflows/dns-plan.yml` in your service repo:

```yaml
name: DNS Plan

on:
  pull_request:
    paths:
      - '.github/workflows/dns-*.yml'
  workflow_dispatch:

jobs:
  plan:
    uses: YOUR_GITHUB_USERNAME/vps-manager/.github/workflows/dns-plan.yml@main
    with:
      zone: yourdomain.com
      provider: cloudflare  # Match zones-meta provider
    secrets:
      PROVIDER_TOKEN: ${{ secrets.DNS_PROVIDER_TOKEN }}
```

Create `.github/workflows/dns-apply.yml`:

```yaml
name: DNS Apply

on:
  push:
    branches: [main]
    paths:
      - '.github/workflows/dns-*.yml'
  workflow_dispatch:

jobs:
  apply:
    uses: YOUR_GITHUB_USERNAME/vps-manager/.github/workflows/dns-apply.yml@main
    with:
      zone: yourdomain.com
      provider: cloudflare  # Match zones-meta provider
    secrets:
      PROVIDER_TOKEN: ${{ secrets.DNS_PROVIDER_TOKEN }}
```

## Making DNS Changes

### Adding Records

1. Create a PR in `vps-manager` modifying `dns/zones/yourdomain.com.yaml`
2. Add your new records:
   ```yaml
   api:
     type: A
     value: YOUR_VPS_IP
   
   staging:
     type: A
     value: YOUR_VPS_IP
   ```
3. The PR will show the DNS plan via GitHub Actions
4. After merge, trigger the apply workflow in your service repo

### Updating Records

1. Modify the existing records in `dns/zones/yourdomain.com.yaml`
2. Submit PR, review plan, merge
3. Apply changes from your service repo

### Deleting Records

1. Remove the records from `dns/zones/yourdomain.com.yaml`
2. Submit PR, review plan, merge
3. Apply changes from your service repo

## Integration with Service Creation

When creating a new service with `create-service.sh`, you'll need to:

1. Add DNS configuration for your domain (follow steps above)
2. Configure the DNS provider secret in your service repo
3. Update Traefik labels to use your domain

The service creation script already sets up:
- Traefik routing with your domain
- SSL certificates via Let's Encrypt
- Health checks and monitoring

## Common Patterns

### Wildcard Subdomains

For dynamic environments:
```yaml
# Matches *.dev.yourdomain.com
'*.dev':
  type: A
  value: YOUR_VPS_IP
```

### Multiple Environments

```yaml
# Production
'':
  type: A
  value: PROD_VPS_IP

# Staging
staging:
  type: A
  value: STAGING_VPS_IP

# Development
dev:
  type: A
  value: DEV_VPS_IP
```

### Load Balancing

```yaml
# Multiple A records for round-robin
api:
  type: A
  values:
    - 192.0.2.1
    - 192.0.2.2
    - 192.0.2.3
```

## Troubleshooting

### DNS Plan Shows No Changes

- Verify the zone file has actual modifications
- Check that the provider can access the domain
- Ensure records are properly formatted

### Apply Workflow Fails

- Check provider token is valid
- Verify domain ownership in provider dashboard
- Look at workflow logs for specific errors

### Records Not Resolving

- DNS propagation can take time (up to 48 hours)
- Use `dig` or `nslookup` to check specific nameservers
- Verify nameservers are set correctly at registrar

## Best Practices

1. **Use Variables** - Store common IPs in GitHub variables
2. **Low TTLs for Dev** - Use 300s TTL for frequently changing records
3. **Document Changes** - Use meaningful PR descriptions
4. **Test First** - Always run plan before apply
5. **Monitor DNS** - Set up monitoring for critical records

## Advanced Usage

### Custom Providers

To add a new DNS provider:

1. Add the provider package to `dns/pyproject.toml`
2. Update workflows to handle provider config
3. Document the token format

### Automation

You can automate DNS updates by:
- Triggering workflows from deployment pipelines
- Using GitHub API to create DNS change PRs
- Setting up scheduled checks for drift

### Multi-Region

For services in multiple regions:
```yaml
# GeoDNS with multiple pools
'':
  type: A
  values:
    - value: 192.0.2.1  # US East
    - value: 192.0.2.2  # EU West
    - value: 192.0.2.3  # Asia Pacific
```

## Migration from Existing DNS

1. Export current DNS records from provider
2. Convert to OctoDNS YAML format
3. Run plan to verify no unintended changes
4. Apply to sync state

## Security Considerations

- **Token Scope** - Use minimum required permissions
- **Token Rotation** - Rotate tokens periodically
- **Access Control** - Limit who can modify DNS configs
- **Change Review** - Require PR approvals for production

## Next Steps

1. Set up DNS for your domain
2. Test with a subdomain first
3. Migrate existing records gradually
4. Set up monitoring and alerts
