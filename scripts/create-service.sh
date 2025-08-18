#!/bin/bash

# VPS Service Creator
# This script creates a new service from the template and sets up deployment

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Required environment variables
: ${VPS_MANAGER_REPO:?"Please set VPS_MANAGER_REPO environment variable (e.g., 'username/vps-manager')"}
: ${GITHUB_USERNAME:=$(git config user.name)}
: ${VPS_HOST:?"Please set VPS_HOST environment variable"}
: ${VPS_USER:="deploy"}
: ${VPS_SSH_KEY_PATH:="$HOME/.ssh/vps_deploy_key"}

# Function to print colored output
print_status() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}!${NC} $1"
}

# Main function to create service
create-service() {
    local SERVICE_NAME=$1
    local APP_DOMAIN=$2
    
    if [ -z "$SERVICE_NAME" ]; then
        print_error "Usage: create-service <service-name> [domain]"
        return 1
    fi
    
    # Set default domain if not provided
    if [ -z "$APP_DOMAIN" ]; then
        APP_DOMAIN="${SERVICE_NAME}.${VPS_HOST}"
        print_warning "No domain provided, using: $APP_DOMAIN"
    fi
    
    echo "🚀 Creating new service: $SERVICE_NAME"
    echo "📍 Domain: $APP_DOMAIN"
    echo ""
    
    # Create service directory
    if [ -d "$SERVICE_NAME" ]; then
        print_error "Directory $SERVICE_NAME already exists!"
        return 1
    fi
    
    print_status "Creating service directory..."
    mkdir -p "$SERVICE_NAME"
    cd "$SERVICE_NAME"
    
    # Download template
    print_status "Downloading template from $VPS_MANAGER_REPO..."
    curl -sL "https://github.com/${VPS_MANAGER_REPO}/archive/main.tar.gz" | \
        tar xz --strip-components=2 "vps-manager-main/template/"
    
    # Update service name in files
    print_status "Customizing template for $SERVICE_NAME..."
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        find . -type f -name "*.yml" -o -name "*.yaml" -o -name "*.json" -o -name "*.md" -o -name "*.js" | \
            xargs sed -i '' "s/myapp/$SERVICE_NAME/g"
        sed -i '' "s/app-template/$SERVICE_NAME/g" package.json
        sed -i '' "s/myapp.example.com/$APP_DOMAIN/g" env.example
    else
        # Linux
        find . -type f -name "*.yml" -o -name "*.yaml" -o -name "*.json" -o -name "*.md" -o -name "*.js" | \
            xargs sed -i "s/myapp/$SERVICE_NAME/g"
        sed -i "s/app-template/$SERVICE_NAME/g" package.json
        sed -i "s/myapp.example.com/$APP_DOMAIN/g" env.example
    fi
    
    # Initialize git repo
    print_status "Initializing git repository..."
    git init
    git add .
    git commit -m "Initial commit from VPS service template"
    
    # Create GitHub repository
    if command -v gh &> /dev/null; then
        print_status "Creating GitHub repository..."
        gh repo create "$SERVICE_NAME" --private --source=. --remote=origin --push || {
            print_warning "Failed to create GitHub repo. You'll need to create it manually."
        }
    else
        print_warning "GitHub CLI not found. Please create repository manually:"
        echo "  1. Go to https://github.com/new"
        echo "  2. Name it: $SERVICE_NAME"
        echo "  3. Run: git remote add origin git@github.com:$GITHUB_USERNAME/$SERVICE_NAME.git"
        echo "  4. Run: git push -u origin main"
    fi
    
    # Set up GitHub secrets
    if command -v gh &> /dev/null && git remote get-url origin &> /dev/null; then
        print_status "Setting up GitHub secrets..."
        
        # Set secrets
        gh secret set VPS_HOST -b "$VPS_HOST" || print_warning "Failed to set VPS_HOST secret"
        gh secret set VPS_USER -b "$VPS_USER" || print_warning "Failed to set VPS_USER secret"
        
        # Set SSH key if available
        if [ -f "$VPS_SSH_KEY_PATH" ]; then
            gh secret set VPS_SSH_KEY < "$VPS_SSH_KEY_PATH" || print_warning "Failed to set VPS_SSH_KEY secret"
        else
            print_warning "SSH key not found at $VPS_SSH_KEY_PATH"
            print_warning "Please manually add VPS_SSH_KEY secret in GitHub"
        fi
        
        # Set variables
        gh variable set APP_DOMAIN -b "$APP_DOMAIN" || print_warning "Failed to set APP_DOMAIN variable"
        gh variable set APP_PORT -b "3000" || print_warning "Failed to set APP_PORT variable"
    else
        print_warning "Please manually set up the following GitHub secrets:"
        echo "  Secrets:"
        echo "    - VPS_HOST: $VPS_HOST"
        echo "    - VPS_USER: $VPS_USER"
        echo "    - VPS_SSH_KEY: (contents of $VPS_SSH_KEY_PATH)"
        echo "  Variables:"
        echo "    - APP_DOMAIN: $APP_DOMAIN"
        echo "    - APP_PORT: 3000"
    fi
    
    # Create directories on VPS
    print_status "Creating directories on VPS..."
    ssh -i "$VPS_SSH_KEY_PATH" "$VPS_USER@$VPS_HOST" \
        "mkdir -p /apps/$SERVICE_NAME /persistent/$SERVICE_NAME/data /logs/$SERVICE_NAME" || \
        print_warning "Failed to create VPS directories. You may need to do this manually."
    
    # Final instructions
    echo ""
    echo "✅ Service $SERVICE_NAME created successfully!"
    echo ""
    echo "Next steps:"
    echo "1. Update your application code in src/"
    echo "2. Add any required secrets to GitHub"
    echo "3. Configure DNS to point $APP_DOMAIN to $VPS_HOST"
    echo "4. Push to main branch to deploy:"
    echo "   git push origin main"
    echo ""
    echo "Local development:"
    echo "   cd $SERVICE_NAME"
    echo "   npm install"
    echo "   npm run dev"
}

# Export the function so it can be used when sourced
export -f create-service
export -f print_status
export -f print_error
export -f print_warning

# If script is executed directly, show usage
if [ "${BASH_SOURCE[0]}" == "${0}" ]; then
    echo "VPS Service Creator"
    echo ""
    echo "Usage:"
    echo "  source $0"
    echo "  create-service <service-name> [domain]"
    echo ""
    echo "Required environment variables:"
    echo "  VPS_HOST - Your VPS IP or hostname"
    echo "  VPS_USER - SSH user (default: deploy)"
    echo "  VPS_SSH_KEY_PATH - Path to SSH private key (default: ~/.ssh/vps_deploy_key)"
    echo "  VPS_MANAGER_REPO - GitHub repo for templates (default: YOUR_GITHUB/vps-manager)"
fi
