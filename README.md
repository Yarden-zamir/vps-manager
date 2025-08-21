# VPS Manager

A lightweight, Docker-based approach to deploying web applications and services to a VPS with minimal complexity and fast iteration cycles.

## 🎯 Philosophy

- **Simplicity First**: Designed for hobby projects and rapid deployment cycles
- **Docker Everything**: All services run in Docker containers with Docker Compose
- **Build on VPS**: Images built directly on the server to leverage build cache
- **Git-based Deploys**: Push to main = automatic deployment
- **No Complex Orchestration**: Just Docker Compose, no Kubernetes or Swarm

## 🚀 Quick Start

1. **Bootstrap your VPS** (one-time setup):
   ```bash
   # Replace YOUR_GITHUB_USERNAME with your actual GitHub username
   # Option 1: Interactive mode (download and run)
   curl -sSL https://raw.githubusercontent.com/YOUR_GITHUB_USERNAME/vps-manager/main/scripts/bootstrap.sh -o bootstrap.sh
   sudo bash bootstrap.sh
   
   # Option 2: Non-interactive mode (provide parameters)
   curl -sSL https://raw.githubusercontent.com/YOUR_GITHUB_USERNAME/vps-manager/main/scripts/bootstrap.sh | sudo bash -s -- --email admin@example.com
   
   # Note: --domain is optional, only needed if you want Traefik dashboard access
   ```

2. **Create a new service** (run from your local machine):
   ```bash
   # Set required environment variables
   export VPS_HOST="your.vps.ip"
   export VPS_MANAGER_REPO="YOUR_GITHUB_USERNAME/vps-manager"
   export DNS_PROVIDER_TOKEN="your-api-token"  # Required for DNS setup
   
   # Run the service creator (requires Python with uv)
   # Option 1: If you have vps-manager cloned locally
   /path/to/vps-manager/scripts/create-service.py myapp ./myapp \
     --domain myapp.com --dns-provider cloudflare
   
   # Option 2: Download and run
   curl -sSL https://raw.githubusercontent.com/YOUR_GITHUB_USERNAME/vps-manager/main/scripts/create-service.py -o create-service.py
   chmod +x create-service.py
   ./create-service.py myapp ./myapp --domain myapp.com --dns-provider cloudflare
   
   # The script will handle everything including DNS configuration!
   ```

3. **Deploy** by pushing to main branch - GitHub Actions handles the rest!

## 📁 Repository Structure

```
vps-manager/
├── README.md                    # This file
├── docs/                        # Detailed documentation
│   ├── setup-guide.md          # Complete VPS setup instructions
│   ├── service-creation.md     # How to create new services
│   └── troubleshooting.md      # Common issues and solutions
├── template/                    # Template for new services
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── .github/workflows/deploy.yml
│   └── src/
├── scripts/                     # Utility scripts
│   ├── bootstrap.sh            # Initial VPS setup
│   └── create-service.sh       # Service creation with user management
└── traefik/                     # Reverse proxy configuration
    └── docker-compose.yml
```

## 🔧 How It Works

### Deployment Flow

1. **Push to main** triggers GitHub Action
2. Action **SSHs to VPS** using deploy keys
3. **Replaces** `/apps/{appname}` with latest code
4. **Injects** production environment variables
5. **Builds** Docker image with commit SHA tag
6. **Restarts** service with `docker compose up -d`

### Directory Structure on VPS

```
/
├── apps/           # Application code (replaced on deploy)
│   └── myapp/
├── persistent/     # Data that survives deploys
│   └── myapp/
│       └── sqlite/
└── logs/           # Application logs
    └── myapp/
```

### Networking

- **Traefik** reverse proxy handles TLS and routing
- Each app gets its own Docker network
- Apps join shared `public` network for proxy access
- Automatic Let's Encrypt certificates per service
- Each service configures its own domain (no global domain needed)

## 📋 Service Requirements

Every service must:

- ✅ Expose a `/health` endpoint
- ✅ Include Docker Compose healthcheck
- ✅ Set `restart: unless-stopped`
- ✅ Define CPU/memory limits
- ✅ Use commit SHA for image tags

## 🔒 Security Approach

**This setup prioritizes convenience over maximum security** - perfect for hobby projects!

- Root account manages the VPS and creates services
- Each service gets its own Unix user with password
- Service isolation through separate user accounts
- Basic security through Docker isolation
- HTTPS automatically configured via Traefik

## 🛠️ Common Commands

```bash
# View all running services
docker ps

# Check service logs
docker logs -f myapp

# Restart a service
cd /apps/myapp && docker compose restart

# Clean old images
docker image prune -a

# Check Traefik routing
docker logs traefik
```

## 📚 Documentation

- [Setup Guide](docs/setup-guide.md) - VPS bootstrap instructions
- [Service Creation](docs/service-creation.md) - How to create services
- [DNS Management](docs/dns-management.md) - Centralized DNS with OctoDNS
- [Troubleshooting](docs/troubleshooting.md) - Common issues

## ⚠️ Limitations

This approach is designed for **simplicity and convenience**, not enterprise scale:

- No automatic backups
- No database migrations  
- No blue-green deployments
- No rollback beyond `git revert`
- **Security is relaxed by default** (password/root login enabled)
- All Docker ports are publicly exposed

Perfect for hobby projects, prototypes, and small-scale applications where ease of use matters more than strict security!
