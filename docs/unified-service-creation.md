# Unified Service Creation

The VPS Manager includes a modern Python script built with Typer that handles both service creation and DNS configuration in one seamless process.

## Overview

The `create-service.py` script (v2.2.0):
- Creates service users on your VPS
- Downloads and configures the service template
- Sets up GitHub repository and secrets
- Configures DNS records (optional)
- Prepares everything for deployment
- Rich terminal UI with progress indicators
- Shell completion support
- Cross-platform compatibility
- SSH connection testing with password authentication support
- Detailed step-by-step progress reporting

## Installation

The script uses Python with uv's inline script dependencies, so you only need:
- Python 3.8+ 
- [uv](https://github.com/astral-sh/uv) installed
- GitHub CLI (`gh`) authenticated
- SSH access to your VPS as root

### Shell Completion

Enable tab completion for your shell:

```bash
# Bash
./scripts/create-service.py --install-completion

# Zsh
./scripts/create-service.py --install-completion

# Fish
./scripts/create-service.py --install-completion
```

This enables:
- Command completion
- Option name completion
- DNS provider name completion
- File path completion

## Usage

### Basic Usage (No DNS)

```bash
export VPS_HOST="your.vps.ip"
export VPS_MANAGER_REPO="yourname/vps-manager"

./scripts/create-service.py \
  --service-name myapp \
  --local-path ~/projects/myapp
```

### With DNS Configuration

```bash
export VPS_HOST="your.vps.ip"
export VPS_MANAGER_REPO="yourname/vps-manager"
export VPS_MANAGER_PATH="/path/to/vps-manager"  # Your local vps-manager repo

./scripts/create-service.py \
  --service-name myapp \
  --local-path ~/projects/myapp \
  --domain myapp.com \
  --dns-provider cloudflare
```

### All Options

```bash
./scripts/create-service.py --help

Options:
  --service-name TEXT       Name of the service  [required]
  --local-path PATH         Local directory for service  [required]
  --domain TEXT             Domain name for the service
  --dns-provider TEXT       DNS provider (cloudflare|netlify|digitalocean|dnsimple|linode)
  --repo TEXT               GitHub repository (owner/name)
  --vps-host TEXT           VPS hostname or IP (env: VPS_HOST)  [required]
  --vps-manager-repo TEXT   VPS manager repository (env: VPS_MANAGER_REPO)  [required]
  --vps-manager-path PATH   Local path to vps-manager repo (env: VPS_MANAGER_PATH)
```

## Environment Variables

### Required
- `VPS_HOST` - Your VPS IP address or hostname
- `VPS_MANAGER_REPO` - GitHub repo containing templates (e.g., "yourname/vps-manager")

### Optional
- `VPS_MANAGER_PATH` - Local path to vps-manager repo (defaults to temp clone)
- `DNS_PROVIDER_TOKEN` - Your DNS provider API token (required when using --domain)

## DNS Provider Tokens

When using the `--domain` option, provide your DNS provider token via the `DNS_PROVIDER_TOKEN` environment variable. The script will automatically:
- Set it as a GitHub secret in your service repository
- Use it for the DNS apply workflow

```bash
# Set token before running the script
export DNS_PROVIDER_TOKEN='your-api-token-here'

# Or provide inline
DNS_PROVIDER_TOKEN='your-token' ./scripts/create-service.py myapp ./myapp \
  --domain myapp.com --dns-provider cloudflare
```

### Token Requirements by Provider

- **Cloudflare**: API token with `Zone:Read` and `DNS:Edit` permissions
- **Netlify**: Personal access token
- **DigitalOcean**: Personal access token with read/write scope
- **DNSimple**: Format as `account_id:api_token`
- **Linode**: Personal access token with `domains:read_write` scope

## What Happens

1. **VPS Setup**
   - Creates dedicated Unix user (`svc-myapp`)
   - Generates secure password
   - Creates directories with proper permissions
   - Adds user to docker group

2. **Local Setup**
   - Downloads service template
   - Replaces placeholders with your values
   - Configures DNS workflows if domain specified

3. **GitHub Setup**
   - Initializes git repository
   - Creates/connects GitHub repo
   - Sets up secrets (VPS_HOST, VPS_USER, VPS_PASSWORD)
   - Sets up variables (APP_DOMAIN, APP_PORT, VPS_MANAGER_REPO)

4. **DNS Setup** (if domain specified)
   - Clones vps-manager repo to temp directory (if path not provided)
   - Creates DNS zone configuration
   - Creates and pushes branch
   - Creates pull request automatically
   - Waits for PR to be merged
   - Runs DNS apply workflow automatically

## Example: Complete Service with DNS

```bash
# 1. Set up environment
export VPS_HOST="192.0.2.1"
export VPS_MANAGER_REPO="myusername/vps-manager"
export DNS_PROVIDER_TOKEN="your-cloudflare-api-token"

# 2. Create service with DNS (fully automated!)
./scripts/create-service.py webapp ~/projects/webapp \
  --domain webapp.example.com \
  --dns-provider cloudflare

# The script will:
# - Create service and configure everything
# - Set DNS provider token as GitHub secret
# - Create DNS configuration PR
# - Wait for you to merge the PR
# - Automatically run DNS apply after merge

# 3. Deploy your service
cd ~/projects/webapp
git add .
git commit -m "Initial deployment"
git push
```

## Benefits

- **Single Command**: One script handles everything
- **Modern CLI**: Built with Typer for excellent UX
- **Type Safety**: Full type hints and validation
- **Rich UI**: Beautiful terminal output with progress indicators
- **Shell Completion**: Tab completion for commands and options
- **Cross-Platform**: Works on macOS, Linux, and WSL
- **No Bash Issues**: Python with sh library for reliable command execution
- **Clear Dependencies**: All deps specified in script header
- **Error Handling**: Clear error messages with helpful suggestions

## SSH Authentication

The script now handles both key-based and password authentication with an interactive menu:

1. **Key-based (preferred)**: If you have SSH keys set up, the script will use them automatically
2. **Password-based with options**: If keys aren't configured, you'll see a menu:

### Authentication Menu

```
Testing SSH connection to your.vps.ip...
SSH key authentication failed

Choose how to proceed:
1. Abort - Exit without creating service
2. Continue with password + setup SSH key - Use password and copy SSH key for future use
3. Continue with password only - Use password authentication for this session

Select option [3]: _
```

#### Option 1: Abort
Exits the script without making any changes.

#### Option 2: Password + SSH Key Setup
- Uses password authentication for this session
- Automatically generates an SSH key if you don't have one
- Copies your SSH key to the server using `ssh-copy-id -o PubkeyAuthentication=no`
- Future connections will use key authentication

#### Option 3: Password Only
- Uses password authentication for this session only
- You'll be prompted for your password for each command
- No SSH keys are set up

### What You'll See During Operations

```
Creating service user: svc-myapp

Creating user svc-myapp...
→ useradd -m -s /bin/bash -d /home/svc-myapp svc-myapp
root@your.vps.ip's password: [enter password]
✓ Creating user svc-myapp...

Setting user password...
→ echo 'svc-myapp:generatedpassword' | chpasswd
root@your.vps.ip's password: [enter password]
✓ Setting user password...
```

Each command shows:
- What it's doing (description)
- The exact command being run (→ command)
- Success/failure status (✓/✗)

## Troubleshooting

### Script Won't Run
```bash
# Make sure uv is installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or with pip
pip install uv
```

### Can't Find vps-manager
- Set `VPS_MANAGER_PATH` environment variable
- Or run the script from within your vps-manager directory

### DNS Configuration Failed
- Ensure you have the correct `--dns-provider` specified
- Check that `VPS_MANAGER_PATH` points to your local repo
- Make sure you're not on the main branch (script creates new branch)

### GitHub Authentication
```bash
# Install GitHub CLI
brew install gh  # macOS
# Or see: https://cli.github.com/

# Authenticate
gh auth login
```
