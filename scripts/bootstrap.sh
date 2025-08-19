#!/bin/bash

# VPS Bootstrap Script
# Sets up a fresh VPS for Docker-based deployments

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
TRAEFIK_EMAIL=""
DOMAIN=""

# Functions
print_header() {
    echo -e "\n${BLUE}======================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}======================================${NC}\n"
}

print_status() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
    exit 1
}

print_warning() {
    echo -e "${YELLOW}!${NC} $1"
}

# Check if running as root
check_root() {
    if [ "$EUID" -ne 0 ]; then 
        print_error "Please run as root or with sudo"
    fi
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --email)
            TRAEFIK_EMAIL="$2"
            shift 2
            ;;
        --domain)
            DOMAIN="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo "Options:"
            echo "  --email EMAIL   Email for Let's Encrypt"
            echo "  --domain DOMAIN Base domain for Traefik dashboard (optional)"
            echo "  --help          Show this help message"
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            ;;
    esac
done

# Main bootstrap process
main() {
    print_header "VPS Bootstrap Script"
    echo "This script will set up your VPS for Docker deployments"
    echo ""
    
    # Display system information
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        echo "System: $NAME $VERSION"
    fi
    echo ""
    
    # Check if we're running through a pipe
    if [ ! -t 0 ]; then
        print_warning "Running in non-interactive mode"
        if [ -z "$TRAEFIK_EMAIL" ]; then
            print_error "When running non-interactively, you must provide --email argument"
            echo ""
            echo "Usage: curl -sSL https://raw.githubusercontent.com/YOUR_GITHUB_USERNAME/vps-manager/main/scripts/bootstrap.sh | sudo bash -s -- --email your@email.com"
            echo "Or run the script directly: ./bootstrap.sh"
            exit 1
        fi
    fi
    
    # Get email if not provided
    if [ -z "$TRAEFIK_EMAIL" ]; then
        read -p "Enter email for Let's Encrypt certificates: " TRAEFIK_EMAIL
    fi
    
    # Domain is optional - only needed if you want Traefik dashboard
    if [ -z "$DOMAIN" ] && [ -t 0 ]; then
        read -p "Enter domain for Traefik dashboard (optional, press Enter to skip): " DOMAIN
    fi
    
    print_header "Step 1: System Update"
    apt update && apt upgrade -y
    print_status "System updated"
    
    print_header "Step 2: System Configuration"
    print_status "Using root account for service management"
    print_status "Service accounts will be created per service with unique passwords"
    
    print_header "Step 3: Configure SSH"
    configure_ssh
    
    print_header "Step 4: Install Docker"
    install_docker
    
    print_header "Step 5: Create Directory Structure"
    create_directories
    
    print_header "Step 6: Install Traefik"
    install_traefik
    
    print_header "Step 7: Configure Firewall"
    configure_firewall
    
    print_header "Step 8: Install Additional Tools"
    install_tools
    
    print_header "Bootstrap Complete!"
    echo -e "${GREEN}Your VPS is ready for deployments!${NC}"
    echo ""
    echo "Next steps:"
    echo "1. Create your first service with: create-service <name> <domain>"
    echo "2. Services will get their own user accounts with passwords"
    if [ -n "$DOMAIN" ]; then
        echo "3. Configure DNS for $DOMAIN (for Traefik dashboard)"
    else
        echo "3. Configure DNS for each service as you deploy them"
    fi
    echo ""
    print_status "Root access will be used to manage services"
    print_warning "Save the generated passwords for each service!"
}

configure_ssh() {
    # Enable public key authentication
    sed -i 's/#*PubkeyAuthentication.*/PubkeyAuthentication yes/' /etc/ssh/sshd_config
    
    # Enable password authentication (many VPS providers disable this by default)
    sed -i 's/#*PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config
    
    # Ensure root login is permitted with password (not just "without-password")
    sed -i 's/#*PermitRootLogin.*/PermitRootLogin yes/' /etc/ssh/sshd_config
    
    # Remove cloud-init SSH restrictions if they exist
    rm -f /etc/ssh/sshd_config.d/50-cloud-init.conf 2>/dev/null
    rm -f /etc/ssh/sshd_config.d/*cloud-init* 2>/dev/null
    
    # Create override file to ensure our settings persist
    cat > /etc/ssh/sshd_config.d/99-vps-manager.conf <<EOF
# VPS Manager SSH Configuration
# This file ensures password authentication works properly
PermitRootLogin yes
PasswordAuthentication yes
PubkeyAuthentication yes
EOF
    
    # Enable and restart SSH (handle different service names)
    if systemctl list-unit-files | grep -q "^sshd.service"; then
        systemctl enable sshd
        systemctl restart sshd
    elif systemctl list-unit-files | grep -q "^ssh.service"; then
        systemctl enable ssh
        systemctl restart ssh
    fi
    print_status "SSH configured (password and key authentication enabled)"
}

install_docker() {
    if command -v docker &> /dev/null; then
        print_warning "Docker already installed"
        return
    fi
    
    # Install prerequisites
    apt install -y apt-transport-https ca-certificates curl software-properties-common
    
    # Add Docker's GPG key
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
    
    # Add Docker repository
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
    
    # Install Docker
    apt update
    apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
    
    # Enable Docker on boot
    systemctl enable docker
    
    # Configure Docker daemon
    cat > /etc/docker/daemon.json <<EOF
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
    
    systemctl restart docker
    print_status "Docker installed and configured"
}

create_directories() {
    # Create main directories
    mkdir -p /apps /persistent /logs
    
    # Set permissions (owned by root)
    chmod 755 /apps /persistent /logs
    
    print_status "Directory structure created (root-owned)"
    print_status "Service directories will be created with service-specific ownership"
}

install_traefik() {
    # Create Traefik directories
    mkdir -p /apps/traefik /persistent/traefik/config
    cd /apps/traefik
    
    # Create docker-compose.yml
    cat > docker-compose.yml <<EOF
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

networks:
  public:
    name: public
    driver: bridge
EOF
    
    # Create traefik.yml
    cat > traefik.yml <<EOF
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
      email: $TRAEFIK_EMAIL
      storage: /acme.json
      httpChallenge:
        entryPoint: web
      # For production, comment out the line below
      caServer: https://acme-staging-v02.api.letsencrypt.org/directory

log:
  level: INFO

accessLog: {}
EOF
    
    # Create .env file (only if domain provided)
    if [ -n "$DOMAIN" ]; then
        cat > .env <<EOF
DOMAIN=$DOMAIN
EOF
    fi
    
    # Create acme.json
    touch /persistent/traefik/acme.json
    chmod 600 /persistent/traefik/acme.json
    
    # Create public network
    docker network create public 2>/dev/null || true
    
    # Start Traefik (as root)
    cd /apps/traefik
    docker compose up -d
    
    print_status "Traefik installed and running"
    print_warning "Traefik is using Let's Encrypt staging environment. Update traefik.yml for production certificates."
    if [ -z "$DOMAIN" ]; then
        print_status "No domain configured for Traefik dashboard. Each service will use its own domain."
    else
        print_status "Traefik dashboard will be available at: https://traefik.$DOMAIN (after DNS setup)"
    fi
}

configure_firewall() {
    # Install but don't enable firewall
    if ! command -v ufw &> /dev/null; then
        apt install -y ufw
    fi
    print_status "Firewall installed but not enabled (all ports open)"
}

install_tools() {
    # Install essential tools
    apt install -y curl wget git vim htop jq 
    print_status "Essential tools installed"
    curl --proto '=https' --tlsv1.2 -sSF https://sh.rustup.rs | sh
    print_status "Rust toolchain installed"
    cargo install erdtree fd-find atuin ripgrep
    echo 'eval "$(atuin init bash --disable-up-arrow)"' >> ~/.zshrc
        # Install GitHub CLI (optional)
    if ! command -v gh &> /dev/null; then
        curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
        echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | tee /etc/apt/sources.list.d/github-cli.list > /dev/null
        apt update
        apt install -y gh
    fi
    print_status "Additional tools installed and configured: erdtree, fd-find, atuin, gh, ripgrep"


}

# Check if script is being piped without sudo
if [ ! -t 0 ] && [ "$EUID" -ne 0 ]; then
    echo "Error: This script must be run with sudo when piped"
    echo ""
    echo "Usage:"
    echo "  curl -sSL ... | sudo bash -s -- --email your@email.com [--domain example.com]"
    echo ""
    echo "Or download and run interactively:"
    echo "  curl -sSL ... -o bootstrap.sh"
    echo "  sudo bash bootstrap.sh"
    exit 1
fi

# Run main function
check_root
main "$@"
