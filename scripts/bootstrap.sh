#!/bin/bash

# VPS Bootstrap Script
# Sets up a fresh VPS for native systemd-based deployments behind Caddy.

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

ACME_EMAIL=""

print_header() {
    printf "\n${BLUE}======================================${NC}\n"
    printf "${BLUE}%s${NC}\n" "$1"
    printf "${BLUE}======================================${NC}\n\n"
}

print_status() {
    printf "${GREEN}✓${NC} %s\n" "$1"
}

print_error() {
    printf "${RED}✗${NC} %s\n" "$1"
    exit 1
}

print_warning() {
    printf "${YELLOW}!${NC} %s\n" "$1"
}

check_root() {
    if [ "$EUID" -ne 0 ]; then
        print_error "Please run as root or with sudo"
    fi
}

while [[ $# -gt 0 ]]; do
    case $1 in
        --email)
            ACME_EMAIL="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo "Options:"
            echo "  --email EMAIL   Email for Caddy/Let's Encrypt notifications"
            echo "  --help          Show this help message"
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            ;;
    esac
done

main() {
    print_header "VPS Bootstrap Script"
    echo "This script will set up your VPS for native systemd deployments behind Caddy"
    echo ""

    if [ -f /etc/os-release ]; then
        . /etc/os-release
        echo "System: $NAME $VERSION"
    fi
    echo ""

    print_header "Step 1: System Update"
    apt update && apt upgrade -y
    print_status "System updated"

    print_header "Step 2: System Configuration"
    print_status "Using root account for service management"
    print_status "Service accounts will be created per service with unique passwords"

    print_header "Step 3: Configure SSH"
    configure_ssh

    print_header "Step 4: Install Native Runtimes"
    install_native_runtimes

    print_header "Step 5: Create Directory Structure"
    create_directories

    print_header "Step 6: Install Caddy"
    install_caddy

    print_header "Step 7: Configure Firewall"
    configure_firewall

    print_header "Step 8: Install Additional Tools"
    install_tools


    print_header "Bootstrap Complete!"
    echo -e "${GREEN}Your VPS is ready for native deployments!${NC}"
    echo ""
    echo "Next steps:"
    echo "1. Create your first service with scripts/create-service.py"
    echo "2. Services will run as systemd units under dedicated Unix users"
    echo "3. Caddy will route each service domain to its localhost port"
    echo ""
    print_status "Root access will be used to create service users and initial systemd/Caddy config"
    print_warning "Save the generated passwords for each service"
}

configure_ssh() {
    sed -i 's/#*PubkeyAuthentication.*/PubkeyAuthentication yes/' /etc/ssh/sshd_config
    sed -i 's/#*PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config
    sed -i 's/#*PermitRootLogin.*/PermitRootLogin yes/' /etc/ssh/sshd_config

    rm -f /etc/ssh/sshd_config.d/50-cloud-init.conf 2>/dev/null
    rm -f /etc/ssh/sshd_config.d/*cloud-init* 2>/dev/null

    cat > /etc/ssh/sshd_config.d/99-vps-manager.conf <<EOF
# VPS Manager SSH Configuration
PermitRootLogin yes
PasswordAuthentication yes
PubkeyAuthentication yes
EOF

    if systemctl list-unit-files | grep -q "^sshd.service"; then
        systemctl enable sshd
        systemctl restart sshd
    elif systemctl list-unit-files | grep -q "^ssh.service"; then
        systemctl enable ssh
        systemctl restart ssh
    fi
    print_status "SSH configured (password and key authentication enabled)"
}

install_native_runtimes() {
    apt install -y ca-certificates curl gnupg git make build-essential

    if ! command -v go >/dev/null 2>&1; then
        apt install -y golang-go
    fi

    if ! command -v cargo >/dev/null 2>&1; then
        apt install -y cargo
    fi

    if ! command -v uv >/dev/null 2>&1; then
        curl -LsSf https://astral.sh/uv/install.sh | sh
        ln -sf /root/.local/bin/uv /usr/local/bin/uv
    fi

    if ! command -v bun >/dev/null 2>&1; then
        curl -fsSL https://bun.sh/install | bash
        ln -sf /root/.bun/bin/bun /usr/local/bin/bun
    fi

    print_status "Native runtimes installed: Go, Rust, uv, Bun"
}

create_directories() {
    mkdir -p /apps /persistent /logs
    chmod 755 /apps /persistent /logs

    print_status "Directory structure created (root-owned)"
    print_status "Service directories will be created with service-specific ownership"
}

install_caddy() {
    apt install -y debian-keyring debian-archive-keyring apt-transport-https curl

    if ! command -v caddy >/dev/null 2>&1; then
        curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
        curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' > /etc/apt/sources.list.d/caddy-stable.list
        apt update
        apt install -y caddy
    fi

    mkdir -p /etc/caddy/apps /logs/caddy
    touch /etc/caddy/apps/000-empty.caddy

    if [ -n "$ACME_EMAIL" ]; then
        cat > /etc/caddy/Caddyfile <<EOF
{
    email $ACME_EMAIL
}

import /etc/caddy/apps/*.caddy
EOF
    else
        cat > /etc/caddy/Caddyfile <<EOF
import /etc/caddy/apps/*.caddy
EOF
    fi

    chown -R root:caddy /etc/caddy
    chmod 755 /etc/caddy /etc/caddy/apps
    chmod 644 /etc/caddy/Caddyfile
    chmod 644 /etc/caddy/apps/000-empty.caddy

    systemctl enable caddy
    systemctl restart caddy

    print_status "Caddy installed and running"
    print_status "Service routes will be added under /etc/caddy/apps"
}

configure_firewall() {
    if ! command -v ufw >/dev/null 2>&1; then
        apt install -y ufw
    fi
    print_status "Firewall installed but not enabled (all ports open)"
}

install_tools() {
    apt install -y wget vim htop jq ripgrep

    if ! command -v gh >/dev/null 2>&1; then
        curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
        echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | tee /etc/apt/sources.list.d/github-cli.list > /dev/null
        apt update
        apt install -y gh
    fi

    print_status "Additional tools installed: gh, jq, ripgrep, htop"
}

if [ ! -t 0 ] && [ "$EUID" -ne 0 ]; then
    echo "Error: This script must be run with sudo when piped"
    echo ""
    echo "Usage:"
    echo "  curl -sSL ... | sudo bash -s -- --email your@email.com"
    echo ""
    echo "Or download and run interactively:"
    echo "  curl -sSL ... -o bootstrap.sh"
    echo "  sudo bash bootstrap.sh"
    exit 1
fi

check_root
main "$@"
