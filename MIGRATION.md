# Migration to Unified Service Creator

We've simplified the VPS Manager by combining all service creation and DNS setup into a single Python script. Here's what changed and how to migrate.

## What Changed

### Before (Multiple Scripts)
- `create-service.sh` - Created services
- `setup-dns.sh` - Set up DNS configuration  
- `quick-deploy.sh` - Helper for DNS deployment
- Complex bash scripts with compatibility issues
- DNS provider guessing from domain TLD

### After (Single Script)
- `create-service.py` - Does everything in one command
- Python script with uv for better cross-platform support
- Explicit DNS provider selection (no guessing)
- Rich terminal UI with tables and colors
- Integrated DNS configuration during service creation

## Migration Guide

### If You Were Using create-service.sh

**Old way:**
```bash
source <(curl -sSL .../create-service.sh)
create-service --local-path ~/myapp --service-name myapp --domain myapp.com
```

**New way:**
```bash
./scripts/create-service.py \
  --service-name myapp \
  --local-path ~/myapp \
  --domain myapp.com \
  --dns-provider cloudflare  # Must specify provider explicitly
```

### If You Were Using setup-dns.sh

DNS setup is now integrated into service creation!

**Old way:**
```bash
# Create service first
create-service --local-path ~/myapp --service-name myapp

# Then set up DNS separately  
./scripts/setup-dns.sh --domain myapp.com --provider cloudflare --vps-ip 1.2.3.4
```

**New way (all in one):**
```bash
./scripts/create-service.py \
  --service-name myapp \
  --local-path ~/myapp \
  --domain myapp.com \
  --dns-provider cloudflare
```

### Environment Variables

Still the same:
- `VPS_HOST` - Your VPS IP
- `VPS_MANAGER_REPO` - Your vps-manager repo

New:
- `VPS_MANAGER_PATH` - Local path to vps-manager (for DNS config)

### DNS Provider Tokens

Token setup hasn't changed:
```bash
cd ~/myapp
gh secret set DNS_PROVIDER_TOKEN

# Or with environment variable
DNS_PROVIDER_TOKEN='your-token' gh secret set DNS_PROVIDER_TOKEN
```

## Key Improvements

1. **No More Guessing** - DNS provider must be explicitly specified
2. **Single Command** - Everything happens in one script
3. **Better UX** - Clear tables, colors, and progress indicators
4. **Cross-Platform** - Python works everywhere (no bash/zsh issues)
5. **Type Safety** - Better error messages and validation

## Common Scenarios

### Create Service Without DNS
```bash
./scripts/create-service.py \
  --service-name api \
  --local-path ~/projects/api
```

### Create Service With DNS
```bash
./scripts/create-service.py \
  --service-name webapp \
  --local-path ~/projects/webapp \
  --domain webapp.example.com \
  --dns-provider cloudflare
```

### Specify Existing GitHub Repo
```bash
./scripts/create-service.py \
  --service-name backend \
  --local-path ~/backend \
  --repo myorg/backend-service \
  --domain api.example.com \
  --dns-provider netlify
```

## Troubleshooting

### Script Not Found
Make sure you have the latest vps-manager with the Python script:
```bash
git pull origin main
chmod +x scripts/create-service.py
```

### uv Not Installed
Install uv for Python script execution:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Can't Find vps-manager Path
Set the environment variable:
```bash
export VPS_MANAGER_PATH="$HOME/vps-manager"
```

Or run from within the vps-manager directory.

## Need Help?

The new script has better error messages and will guide you through any issues. Run with `--help` to see all options:

```bash
./scripts/create-service.py --help
```
