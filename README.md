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
   curl -sSL https://raw.githubusercontent.com/YOUR_GITHUB_USERNAME/vps-manager/main/scripts/bootstrap.sh | sudo bash -s -- --email admin@example.com --domain example.com
   ```

2. **Create a new service**:
   ```bash
   # Replace YOUR_GITHUB_USERNAME with your actual GitHub username
   source <(curl -sSL https://raw.githubusercontent.com/YOUR_GITHUB_USERNAME/vps-manager/main/scripts/create-service.sh)
   create-service myapp
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
│   ├── create-service.sh       # New service creation
│   └── manage-accounts.py      # Service account management
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
- Automatic Let's Encrypt certificates

## 📋 Service Requirements

Every service must:

- ✅ Expose a `/health` endpoint
- ✅ Include Docker Compose healthcheck
- ✅ Set `restart: unless-stopped`
- ✅ Define CPU/memory limits
- ✅ Use commit SHA for image tags

## 🔒 Security

- SSH key authentication only (passwords disabled)
- Basic firewall rules (SSH + web ports)
- Each service runs as isolated Docker container
- Traefik handles HTTPS enforcement

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

## 📚 Learn More

- [Complete Setup Guide](docs/setup-guide.md) - Detailed VPS bootstrap instructions
- [Service Creation Guide](docs/service-creation.md) - Step-by-step service setup
- [Troubleshooting](docs/troubleshooting.md) - Common issues and fixes

## ⚠️ Limitations

This approach is designed for simplicity, not enterprise scale:

- No automatic backups
- No database migrations
- No blue-green deployments
- No rollback beyond `git revert`
- Basic security only

Perfect for hobby projects, prototypes, and small-scale applications!
