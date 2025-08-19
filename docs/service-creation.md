# Service Creation Guide

This guide explains how to create and deploy a new service to your VPS.

## Prerequisites

- VPS set up with Docker and Traefik (see [Setup Guide](setup-guide.md))
- GitHub account
- GitHub CLI installed (optional but recommended)
- Local development environment

## Quick Start

### Using the Creation Script

```bash
# Set environment variables
export VPS_HOST="your.vps.ip"
export VPS_MANAGER_REPO="YOUR_GITHUB/vps-manager"

# Source and run the script (requires root SSH access)
source <(curl -sSL https://raw.githubusercontent.com/YOUR_GITHUB/vps-manager/main/scripts/create-service.sh)
create-service myapp myapp.example.com

# IMPORTANT: Save the generated password that will be displayed!
```

The script will:
1. Create a service user (svc-myapp) with a secure password
2. Set up directories with proper ownership
3. Configure GitHub repo and secrets
4. Display credentials for your records

## Manual Service Creation

### Step 1: Create Service from Template

```bash
# Clone the template
git clone https://github.com/YOUR_GITHUB/vps-manager.git temp-vps
cp -r temp-vps/template myapp
cd myapp
rm -rf ../temp-vps

# Initialize git
git init
git add .
git commit -m "Initial commit from template"
```

### Step 2: Customize the Service

#### 2.1 Update Application Name

Replace `myapp` with your service name in:
- `docker-compose.yml`
- `package.json`
- `.github/workflows/deploy.yml`
- `README.md`

#### 2.2 Configure Environment

Edit `env.example`:
```env
NODE_ENV=development
APP_NAME=myapp
APP_DOMAIN=myapp.example.com
APP_PORT=3000

# Add your app-specific variables
DATABASE_URL=postgresql://user:password@localhost:5432/myapp
API_KEY=your-api-key
```

#### 2.3 Update Application Code

Replace the template code in `src/` with your application.

**Important**: Your app MUST expose a `/health` endpoint that returns HTTP 200 when healthy.

### Step 3: Create GitHub Repository

```bash
# Using GitHub CLI
gh repo create myapp --private --source=. --remote=origin

# Or manually
# 1. Create repo on GitHub
# 2. Add remote:
git remote add origin git@github.com:YOUR_USERNAME/myapp.git
git push -u origin main
```

### Step 4: Configure GitHub Secrets

#### Using GitHub CLI:
```bash
# Secrets (sensitive data)
gh secret set VPS_HOST -b "your.vps.ip"
gh secret set VPS_USER -b "svc-myapp"
gh secret set VPS_PASSWORD -b "generated-password-here"

# Variables (non-sensitive config)
gh variable set APP_DOMAIN -b "myapp.example.com"
gh variable set APP_PORT -b "3000"

# App-specific secrets
gh secret set DATABASE_URL -b "postgresql://user:password@db:5432/myapp"
gh secret set API_KEY -b "your-secret-api-key"
```

#### Using GitHub Web UI:
1. Go to Settings → Secrets and variables → Actions
2. Add repository secrets:
   - `VPS_HOST`: Your VPS IP or hostname
   - `VPS_USER`: Service user (e.g., `svc-myapp`)
   - `VPS_PASSWORD`: Service user password (from creation script)
3. Add repository variables:
   - `APP_DOMAIN`: Your app's domain
   - `APP_PORT`: Internal port (usually 3000)

### Step 5: Create Service User on VPS

SSH as root and create the service user:
```bash
ssh root@your.vps.ip

# Create user and set password
useradd -m -s /bin/bash -d /home/svc-myapp svc-myapp
passwd svc-myapp  # Set a secure password

# Add to docker group
usermod -aG docker svc-myapp

# Create directories with proper ownership
mkdir -p /apps/myapp /persistent/myapp/data /logs/myapp
chown -R svc-myapp:svc-myapp /apps/myapp /persistent/myapp /logs/myapp
```

Note: The create-service script does this automatically!

### Step 6: Configure DNS

Each service needs its own domain configured. Point your service's domain to your VPS:
- Type: A record
- Name: myapp (or @ for root domain)
- Value: YOUR_VPS_IP
- TTL: 300 (5 minutes)

**Note**: There's no global domain configuration. Each service manages its own domain through its docker-compose.yml labels. This allows complete flexibility - you can use different domains, subdomains, or even different domain providers for each service.

### Step 7: Deploy

```bash
# Any push to main triggers deployment
git push origin main
```

Watch the deployment in GitHub Actions tab.

## Service Configuration

### Docker Compose Options

#### Resource Limits
```yaml
deploy:
  resources:
    limits:
      cpus: '2.0'      # Max 2 CPU cores
      memory: 1024M    # Max 1GB RAM
    reservations:
      cpus: '0.5'      # Reserved 0.5 CPU cores
      memory: 256M     # Reserved 256MB RAM
```

#### Network Configuration
```yaml
networks:
  app-network:         # Private network for this app
    name: myapp-network
  public:              # Shared network for Traefik
    external: true
```

#### Volume Mounts
```yaml
volumes:
  # Persistent data
  - /persistent/myapp/data:/app/data
  - /persistent/myapp/uploads:/app/uploads
  
  # Logs (optional)
  - /logs/myapp:/app/logs
  
  # Config files
  - /persistent/myapp/config.yml:/app/config.yml:ro
```

### Traefik Labels

#### Basic HTTPS Setup
```yaml
labels:
  - "traefik.enable=true"
  - "traefik.docker.network=public"
  - "traefik.http.routers.myapp.rule=Host(`myapp.example.com`)"
  - "traefik.http.routers.myapp.entrypoints=websecure"
  - "traefik.http.routers.myapp.tls=true"
  - "traefik.http.routers.myapp.tls.certresolver=letsencrypt"
```

#### Multiple Domains
```yaml
labels:
  - "traefik.http.routers.myapp.rule=Host(`myapp.com`) || Host(`www.myapp.com`)"
```

#### Path-based Routing
```yaml
labels:
  - "traefik.http.routers.myapp.rule=Host(`example.com`) && PathPrefix(`/api`)"
```

#### Custom Headers
```yaml
labels:
  - "traefik.http.middlewares.myapp-headers.headers.customrequestheaders.X-Custom-Header=value"
  - "traefik.http.routers.myapp.middlewares=myapp-headers"
```

## Different Application Types

### Node.js (Default Template)
Already configured in the template.

### Python/Django
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "myapp.wsgi:application"]
```

### Go
```dockerfile
FROM golang:1.21-alpine AS builder
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN go build -o main .

FROM alpine:latest
RUN apk --no-cache add ca-certificates
WORKDIR /root/
COPY --from=builder /app/main .
EXPOSE 8080
CMD ["./main"]
```

### Static Site (Nginx)
```dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

## Adding Services to Existing Apps

### Database (PostgreSQL)
Add to `docker-compose.yml`:
```yaml
services:
  app:
    # ... existing config ...
    depends_on:
      - db
    environment:
      DATABASE_URL: postgresql://myapp:password@db:5432/myapp

  db:
    image: postgres:15-alpine
    container_name: myapp-db
    restart: unless-stopped
    networks:
      - app-network
    volumes:
      - /persistent/myapp/postgres:/var/lib/postgresql/data
    environment:
      POSTGRES_DB: myapp
      POSTGRES_USER: myapp
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U myapp"]
      interval: 10s
      timeout: 5s
      retries: 5
```

### Redis Cache
```yaml
services:
  redis:
    image: redis:7-alpine
    container_name: myapp-redis
    restart: unless-stopped
    networks:
      - app-network
    volumes:
      - /persistent/myapp/redis:/data
    command: redis-server --appendonly yes
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
```

## Deployment Workflow

### What Happens on Deploy

1. GitHub Action triggered on push to main
2. SSH connection established to VPS
3. `/apps/myapp` directory cleared and updated
4. `.env` file created with production secrets
5. Docker image built with commit SHA tag
6. Service restarted with new image
7. Health check verified
8. Old images pruned

### Monitoring Deployment

```bash
# Watch GitHub Actions
gh run watch

# On VPS - check logs
docker logs -f myapp

# Check service health
docker ps
curl https://myapp.example.com/health
```

### Rollback

```bash
# Revert commit
git revert HEAD
git push origin main

# Or manually on VPS
cd /apps/myapp
docker compose down
docker run -d myapp:previous-sha
```

## Best Practices

1. **Always test locally first**
   ```bash
   docker compose up --build
   ```

2. **Use environment variables for configuration**
   - Never commit secrets
   - Use `.env.example` as template

3. **Implement proper health checks**
   - Return 200 only when truly ready
   - Check database connections
   - Verify critical services

4. **Set resource limits**
   - Prevent runaway containers
   - Plan for traffic spikes

5. **Use specific image versions**
   - Pin base image versions
   - Avoid `:latest` tags

6. **Handle signals properly**
   - Graceful shutdown
   - Clean up resources

## Troubleshooting

See [Troubleshooting Guide](troubleshooting.md) for common issues and solutions.
