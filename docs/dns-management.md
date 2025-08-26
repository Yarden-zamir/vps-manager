# DNS Management with Terraform (Local State)

This guide explains how DNS management is integrated into the VPS Manager using Terraform with a local backend. Minimal setup targeting Netlify DNS only.

## Overview

The VPS Manager provides centralized DNS configuration management while maintaining decentralized control. Each service owns its domain and provides its own DNS provider credentials, ensuring security and autonomy.

## Architecture

### Components

1. **Central Config Repository** (`vps-manager`)
   - Stores DNS zone definitions in `dns/zones/` (simple YAML)
   - Stores Terraform configuration in `dns/terraform/`
   - Provides reusable helper scripts
   - Single source of truth with git history

2. **Service Repositories**
   - Own their domains
   - Store DNS provider tokens as secrets
   - Call central workflows to manage DNS

3. **Terraform via CI**
   - Define records JSON in your service repo or generate it in the workflow
   - Call shared workflows `dns-plan.yml` / `dns-apply.yml` using repo secrets

### Security Model

- **No central secrets** - Each service provides its own provider token
- **Domain isolation** - Services can only modify their own domains
- **Audit trail** - All changes tracked in git
- **PR review** - Changes go through standard review process

## Setting Up DNS for Your Service

### 1. Choose Your DNS Provider

Supported providers:
- **Netlify DNS** - Great for Netlify-hosted sites
  - Others can be added later if needed

### 2. Define DNS Records (tfvars JSON)

Create a pull request to `vps-manager` adding your zone configuration:

#### Zone Configuration
Create `dns/terraform/records.auto.tfvars.json`:

```json
{
  "records": [
    {"zone": "yourdomain.com", "name": "", "type": "A", "values": ["YOUR_VPS_IP"]},
    {"zone": "yourdomain.com", "name": "www", "type": "CNAME", "values": ["yourdomain.com."]},
    {"zone": "yourdomain.com", "name": "api", "type": "A", "values": ["YOUR_VPS_IP"]}
  ]
}
```

### 3. Authenticate Provider

Export credentials locally before running Terraform:

- Netlify: `export NETLIFY_TOKEN=...`

### 4. Apply via Terraform (CI)

```bash
In your service repo, call the reusable workflows with inputs and secrets:

```yaml
name: DNS

on:
  workflow_dispatch:

jobs:
  plan:
    uses: YOUR_ORG/vps-manager/.github/workflows/dns-plan.yml@main
    with:
      records_json: |
        {
          "records": [
            {"zone": "yourdomain.com", "name": "", "type": "A", "values": ["YOUR_VPS_IP"]}
          ]
        }
    secrets:
      NETLIFY_TOKEN: ${{ secrets.NETLIFY_TOKEN }}

  apply:
    needs: plan
    uses: YOUR_ORG/vps-manager/.github/workflows/dns-apply.yml@main
    with:
      records_json: |
        {
          "records": [
            {"zone": "yourdomain.com", "name": "", "type": "A", "values": ["YOUR_VPS_IP"]}
          ]
        }
    secrets:
      NETLIFY_TOKEN: ${{ secrets.NETLIFY_TOKEN }}
```
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
3. Run `terraform plan` locally to see changes, then apply when ready

### Updating Records

1. Modify the existing records in `dns/zones/yourdomain.com.yaml`
2. Submit PR, review plan, merge
3. Apply changes from your service repo

### Deleting Records

1. Remove the records from `dns/zones/yourdomain.com.yaml`
2. Submit PR, review plan, merge
3. Re-run Terraform apply

## Integration with Service Creation

When creating a new service with `create-service.py`, you'll need to:

1. Add DNS configuration for your domain (follow steps above)
2. Export provider token locally: `export NETLIFY_TOKEN=...`
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

You can automate Terraform in your own CI/CD, but this repo assumes local state.

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
