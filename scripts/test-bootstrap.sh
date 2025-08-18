#!/bin/bash

# Test script to verify bootstrap requirements

echo "Bootstrap Test Script"
echo "===================="
echo ""

# Check if running as root
if [ "$EUID" -eq 0 ]; then 
    echo "✓ Running as root/sudo"
else
    echo "✗ NOT running as root"
    echo "  Please run with: sudo bash test-bootstrap.sh"
    exit 1
fi

# Check if interactive
if [ -t 0 ]; then
    echo "✓ Running in interactive mode"
else
    echo "! Running in non-interactive mode (piped)"
fi

# Check OS
if [ -f /etc/os-release ]; then
    . /etc/os-release
    echo "✓ OS: $NAME $VERSION"
else
    echo "? Cannot determine OS"
fi

# Check if curl is available
if command -v curl &> /dev/null; then
    echo "✓ curl is installed"
else
    echo "✗ curl is NOT installed"
fi

# Test network connectivity
if curl -s --head https://raw.githubusercontent.com &> /dev/null; then
    echo "✓ Can reach GitHub"
else
    echo "✗ Cannot reach GitHub"
fi

echo ""
echo "To run the bootstrap script:"
echo "1. Download it first:"
echo "   curl -sSL https://raw.githubusercontent.com/yarden-zamir/vps-manager/main/scripts/bootstrap.sh -o bootstrap.sh"
echo ""
echo "2. Then run it with sudo:"
echo "   sudo bash bootstrap.sh"
echo ""
echo "OR run non-interactively with parameters:"
echo "   curl -sSL ... | sudo bash -s -- --email your@email.com --domain yourdomain.com"
