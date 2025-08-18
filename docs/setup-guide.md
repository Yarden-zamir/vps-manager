# VPS Setup Guide

This guide walks you through setting up a fresh VPS for hosting Docker-based services with automatic deployments.

## Prerequisites

- A fresh Ubuntu 22.04 LTS VPS (or similar Debian-based distro)
- Root or sudo access
- A domain name (optional but recommended)
- GitHub account for storing code

## Step 1: Initial Server Setup

### 1.1 Connect to Your VPS

```bash
ssh root@YOUR_VPS_IP
```

### 1.2 Create Deploy User

```bash
# Create deploy user
adduser deploy

# Add to sudo group
usermod -aG sudo deploy

# Switch to deploy user
su - deploy
```

### 1.3 Set Up SSH Key Authentication

On your local machine:
```bash
# Generate SSH key if you don't have one
ssh-keygen -t ed25519 -f ~/.ssh/vps_deploy_key -C "deploy@vps"

# Copy to VPS
ssh-copy-id -i ~/.ssh/vps_deploy_key deploy@YOUR_VPS_IP
```

### 1.4 Secure SSH Access

```bash
# Edit SSH config
sudo nano /etc/ssh/sshd_config

# Ensure these settings:
PubkeyAuthentication yes
PasswordAuthentication no
PermitRootLogin no

# Restart SSH
sudo systemctl restart sshd
```

## Step 2: Install Docker

### 2.1 Install Docker

```bash
# Update packages
sudo apt update && sudo apt upgrade -y

# Install prerequisites
sudo apt install -y apt-transport-https ca-certificates curl software-properties-common

# Add Docker's GPG key
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

# Add Docker repository
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Add deploy user to docker group
sudo usermod -aG docker deploy

# Verify installation
docker --version
docker compose version
```

### 2.2 Configure Docker

```bash
# Enable Docker to start on boot
sudo systemctl enable docker

# Configure Docker daemon
sudo tee /etc/docker/daemon.json > /dev/null <<EOF
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  },
  "metrics-addr": "127.0.0.1:9323",
  "experimental": false
}
EOF

# Restart Docker
sudo systemctl restart docker
```

## Step 3: Create Directory Structure

```bash
# Create required directories
sudo mkdir -p /apps /persistent /logs

# Set ownership
sudo chown -R deploy:deploy /apps /persistent /logs

# Set permissions
chmod 755 /apps /persistent /logs
```

## Step 4: Install Traefik

### 4.1 Create Traefik Directory

```bash
mkdir -p /apps/traefik /persistent/traefik
cd /apps/traefik
```

### 4.2 Create Traefik Configuration

Create `/apps/traefik/docker-compose.yml`:
```yaml
version: '3.8'

services:
  traefik:
    image: traefik:v3.0
    container_name: traefik
    restart: unless-stopped
    security_opt:
      - no-new-privileges:true
    networks:
      - public
    ports:
      - "80:80"
      - "443:443"
      - "8080:8080" # Dashboard (optional, remove in production)
    environment:
      - TRAEFIK_API_DASHBOARD=true
      - TRAEFIK_API_DEBUG=false
    volumes:
      - /etc/localtime:/etc/localtime:ro
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - ./traefik.yml:/traefik.yml:ro
      - /persistent/traefik/acme.json:/acme.json
      - /persistent/traefik/config:/config:ro
    labels:
      - "traefik.enable=true"
      - "traefik.docker.network=public"
      # Dashboard (optional, secure with auth in production)
      - "traefik.http.routers.dashboard.rule=Host(`traefik.${DOMAIN}`)"
      - "traefik.http.routers.dashboard.entrypoints=websecure"
      - "traefik.http.routers.dashboard.tls=true"
      - "traefik.http.routers.dashboard.tls.certresolver=letsencrypt"
      - "traefik.http.routers.dashboard.service=api@internal"

networks:
  public:
    name: public
    driver: bridge
```

### 4.3 Create Traefik Static Configuration

Create `/apps/traefik/traefik.yml`:
```yaml
api:
  dashboard: true
  debug: false

entryPoints:
  web:
    address: ":80"
    http:
      redirections:
        entrypoint:
          to: websecure
          scheme: https
          permanent: true
  websecure:
    address: ":443"
    http:
      tls:
        certResolver: letsencrypt

providers:
  docker:
    endpoint: "unix:///var/run/docker.sock"
    exposedByDefault: false
    network: public
    watch: true
  file:
    directory: /config
    watch: true

certificatesResolvers:
  letsencrypt:
    acme:
      email: your-email@example.com  # CHANGE THIS
      storage: /acme.json
      httpChallenge:
        entryPoint: web
      # Uncomment for production
      # caServer: https://acme-v02.api.letsencrypt.org/directory

log:
  level: INFO

accessLog: {}
```

### 4.4 Start Traefik

```bash
# Create acme.json for certificates
touch /persistent/traefik/acme.json
chmod 600 /persistent/traefik/acme.json

# Create config directory
mkdir -p /persistent/traefik/config

# Create .env file
echo "DOMAIN=your-domain.com" > .env  # CHANGE THIS

# Start Traefik
docker compose up -d

# Check logs
docker logs -f traefik
```

## Step 5: Set Up GitHub CLI (Optional)

```bash
# Install GitHub CLI
curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
sudo apt update
sudo apt install gh -y

# Authenticate
gh auth login
```

## Step 6: Configure Firewall (Optional)

```bash
# Install ufw
sudo apt install ufw -y

# Configure firewall rules
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow http
sudo ufw allow https

# Enable firewall
sudo ufw enable
```

## Step 7: Set Up Automatic Updates

```bash
# Install unattended-upgrades
sudo apt install unattended-upgrades -y

# Enable automatic updates
sudo dpkg-reconfigure -plow unattended-upgrades
```

## Step 8: Run Bootstrap Script

Finally, you can use our bootstrap script to verify and complete the setup:

```bash
# Replace YOUR_GITHUB with your GitHub username
# Option 1: Interactive mode
curl -sSL https://raw.githubusercontent.com/YOUR_GITHUB/vps-manager/main/scripts/bootstrap.sh -o bootstrap.sh
sudo bash bootstrap.sh

# Option 2: Non-interactive mode with parameters
curl -sSL https://raw.githubusercontent.com/YOUR_GITHUB/vps-manager/main/scripts/bootstrap.sh | sudo bash -s -- --email admin@example.com --domain example.com
```

## Verification

Check that everything is working:

```bash
# Check Docker
docker ps
docker network ls

# Check Traefik
curl -I http://YOUR_VPS_IP  # Should redirect to HTTPS

# Check directories
ls -la /apps /persistent /logs
```

## Next Steps

1. [Create your first service](service-creation.md)
2. Configure DNS for your domain
3. Set up monitoring (optional)
4. Configure backups (recommended)

## Security Considerations

This setup provides basic security suitable for hobby projects:

- SSH key-only authentication
- Non-root deploy user
- Basic firewall rules
- Automatic security updates

For production use, consider:

- Fail2ban for brute-force protection
- More restrictive firewall rules
- Regular security audits
- Proper backup solution
- Monitoring and alerting
- Database replication
- Load balancing
