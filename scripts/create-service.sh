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

# Function to generate secure random password
generate_password() {
    # Generate 16-character password with letters, numbers, and basic symbols
    openssl rand -base64 32 | tr -d "=+/" | cut -c1-16
}

# Main function to create service
create-service() {
    # Parse options
    local REPO_NAME=""
    local LOCAL_PATH=""
    while [[ "$1" == --* ]]; do
        case "$1" in
            --repo|-r)
                REPO_NAME="$2"
                shift 2
                ;;
            --local-path|-p)
                LOCAL_PATH="$2"
                shift 2
                ;;
            *)
                print_error "Unknown option: $1"
                return 1
                ;;
        esac
    done

    local SERVICE_NAME=$1
    local APP_DOMAIN=$2
    
    # Require GitHub CLI
    if ! command -v gh &> /dev/null; then
        print_error "GitHub CLI 'gh' is required. Install from https://cli.github.com/ and run 'gh auth login'."
        return 1
    fi
    
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
    
    # Generate service user credentials
    local SERVICE_USER="svc-${SERVICE_NAME}"
    local SERVICE_PASSWORD
    SERVICE_PASSWORD=$(generate_password)
    
    print_status "Creating service user on VPS..."
    
    # Create user and directories on VPS (as root)
    ssh "root@$VPS_HOST" << 'ENDSSH'
# Create service user with password
useradd -m -s /bin/bash -d /home/$SERVICE_USER $SERVICE_USER
echo "$SERVICE_USER:$SERVICE_PASSWORD" | chpasswd

# Add to docker group
usermod -aG docker $SERVICE_USER

# Create service directories with proper ownership
mkdir -p /apps/$SERVICE_NAME /persistent/$SERVICE_NAME/data /logs/$SERVICE_NAME
chown -R $SERVICE_USER:$SERVICE_USER /apps/$SERVICE_NAME
chown -R $SERVICE_USER:$SERVICE_USER /persistent/$SERVICE_NAME
chown -R $SERVICE_USER:$SERVICE_USER /logs/$SERVICE_NAME
chmod 755 /apps/$SERVICE_NAME /persistent/$SERVICE_NAME /logs/$SERVICE_NAME

echo "User $SERVICE_USER created successfully"
ENDSSH
    
    if [ $? -eq 0 ]; then
        print_status "Service user created on VPS"
        echo ""
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "🔐 SERVICE CREDENTIALS (SAVE THESE!)"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "Username: $SERVICE_USER"
        echo "Password: $SERVICE_PASSWORD"
        echo "SSH: ssh $SERVICE_USER@$VPS_HOST"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""
    else
        print_error "Failed to create service user on VPS"
        return 1
    fi
    
    # Determine working directory
    local WORK_DIR="${LOCAL_PATH:-$SERVICE_NAME}"
    # EXISTING_DIR tracks if we're using an existing directory (used for messaging)
    local EXISTING_DIR=0
    local EXISTING_GIT_REPO=0
    local EXISTING_REMOTE=""
    
    # Check if directory exists
    if [ -d "$WORK_DIR" ]; then
        EXISTING_DIR=1
        print_status "Using existing directory: $WORK_DIR"
        cd "$WORK_DIR"
        
        # Check if it's a git repo
        if [ -d ".git" ]; then
            EXISTING_GIT_REPO=1
            EXISTING_REMOTE=$(git remote get-url origin 2>/dev/null || echo "")
            
            if [ -n "$EXISTING_REMOTE" ]; then
                # Extract owner/repo from git URL
                local DETECTED_REPO=""
                if [[ "$EXISTING_REMOTE" =~ github\.com[:/]([^/]+/[^/.]+)(\.git)?$ ]]; then
                    DETECTED_REPO="${BASH_REMATCH[1]}"
                fi
                
                if [ -n "$REPO_NAME" ] && [ "$REPO_NAME" != "$DETECTED_REPO" ]; then
                    print_error "Existing repo ($DETECTED_REPO) doesn't match specified repo ($REPO_NAME)"
                    return 1
                fi
                
                if [ -z "$REPO_NAME" ] && [ -n "$DETECTED_REPO" ]; then
                    REPO_NAME="$DETECTED_REPO"
                    print_status "Detected existing repo: $REPO_NAME"
                fi
            fi
        fi
    else
        print_status "Creating directory: $WORK_DIR"
        mkdir -p "$WORK_DIR"
        cd "$WORK_DIR"
    fi
    
    # Log whether we're using an existing directory (affects template behavior)
    if [ "$EXISTING_DIR" -eq 1 ]; then
        print_status "Working in existing directory - will preserve existing files"
    fi
    
    # Download template
    print_status "Downloading template from $VPS_MANAGER_REPO..."
    
    # Create temp directory for template
    local TEMP_DIR
    TEMP_DIR=$(mktemp -d)
    curl -sL "https://github.com/${VPS_MANAGER_REPO}/archive/main.tar.gz" | \
        tar xz -C "$TEMP_DIR" --strip-components=2 "vps-manager-main/template/"
    
    # Copy template files without overwriting existing ones
    print_status "Copying template files (preserving existing files)..."
    find "$TEMP_DIR" -type f -print0 | while IFS= read -r -d '' file; do
        local rel_path="${file#$TEMP_DIR/}"
        local target_file="./$rel_path"
        local target_dir
        target_dir=$(dirname "$target_file")
        
        # Create directory if needed
        [ ! -d "$target_dir" ] && mkdir -p "$target_dir"
        
        # Copy file only if it doesn't exist
        if [ ! -f "$target_file" ]; then
            cp "$file" "$target_file"
        else
            print_warning "Skipping existing file: $rel_path"
        fi
    done
    
    # Clean up temp directory
    rm -rf "$TEMP_DIR"
    
    # Update service name in files
    print_status "Customizing template for $SERVICE_NAME..."
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        find . -type f \( -name "*.yml" -o -name "*.yaml" -o -name "*.json" -o -name "*.md" -o -name "*.js" \) -print0 | \
            xargs -0 sed -i '' "s/myapp/$SERVICE_NAME/g"
        sed -i '' "s/app-template/$SERVICE_NAME/g" package.json
        sed -i '' "s/myapp.example.com/$APP_DOMAIN/g" env.example
    else
        # Linux
        find . -type f \( -name "*.yml" -o -name "*.yaml" -o -name "*.json" -o -name "*.md" -o -name "*.js" \) -print0 | \
            xargs -0 sed -i "s/myapp/$SERVICE_NAME/g"
        sed -i "s/app-template/$SERVICE_NAME/g" package.json
        sed -i "s/myapp.example.com/$APP_DOMAIN/g" env.example
    fi
    
    # Initialize git repo if needed
    if [ "$EXISTING_GIT_REPO" -eq 0 ]; then
        print_status "Initializing git repository..."
        git init -b main || { git init && git branch -M main; }
    fi
    
    # Add and commit changes
    if [ -n "$(git status --porcelain 2>/dev/null)" ]; then
        print_status "Committing template files..."
        git add .
        git commit -m "Add VPS service template" || print_warning "Nothing to commit"
    else
        print_status "No changes to commit"
    fi
    
    # Handle GitHub repository
    if [ -n "$EXISTING_REMOTE" ]; then
        # Already has remote, just push if needed
        print_status "Using existing GitHub remote: $REPO_NAME"
        if [ -n "$(git log origin/main..HEAD 2>/dev/null)" ]; then
            git push origin main || print_warning "Push failed. You may need to pull first."
        fi
    else
        # Need to create or connect repo
        if [ -z "$REPO_NAME" ]; then
            # Auto-detect if repo exists
            print_status "Checking if GitHub repo '$SERVICE_NAME' exists..."
            if gh repo view "$GITHUB_USERNAME/$SERVICE_NAME" &> /dev/null; then
                REPO_NAME="$GITHUB_USERNAME/$SERVICE_NAME"
                print_status "Found existing repo: $REPO_NAME"
            else
                # Create new repo
                print_status "Creating new GitHub repository..."
                gh repo create "$SERVICE_NAME" --private --source=. --remote=origin --push || {
                    print_error "Failed to create and push to GitHub repo."
                    return 1
                }
                REPO_NAME="$GITHUB_USERNAME/$SERVICE_NAME"
            fi
        fi
        
        # Connect to specified/detected repo if not already connected
        if [ -z "$EXISTING_REMOTE" ] && [ -n "$REPO_NAME" ]; then
            print_status "Connecting to GitHub repository: $REPO_NAME"
            if ! gh repo view "$REPO_NAME" &> /dev/null; then
                # Try to create it if it doesn't exist and matches pattern
                if [[ "$REPO_NAME" =~ ^$GITHUB_USERNAME/(.+)$ ]]; then
                    local REPO_SHORT_NAME="${BASH_REMATCH[1]}"
                    print_status "Creating GitHub repository: $REPO_NAME"
                    gh repo create "$REPO_SHORT_NAME" --private || {
                        print_error "Failed to create GitHub repo: $REPO_NAME"
                        return 1
                    }
                else
                    print_error "Repository '$REPO_NAME' not found or inaccessible."
                    return 1
                fi
            fi
            
            git remote add origin "git@github.com:$REPO_NAME.git" || {
                print_error "Failed to add remote origin."
                return 1
            }
            git push -u origin main || print_warning "Push failed. You may need to reconcile history."
        fi
    fi
    
    # Set up GitHub secrets
    if git remote get-url origin &> /dev/null; then
        print_status "Setting up GitHub secrets..."
        
        # Set secrets
        gh secret set VPS_HOST -b "$VPS_HOST" || print_warning "Failed to set VPS_HOST secret"
        gh secret set VPS_USER -b "$SERVICE_USER" || print_warning "Failed to set VPS_USER secret"
        gh secret set VPS_PASSWORD -b "$SERVICE_PASSWORD" || print_warning "Failed to set VPS_PASSWORD secret"
        
        # Set variables
        gh variable set APP_DOMAIN -b "$APP_DOMAIN" || print_warning "Failed to set APP_DOMAIN variable"
        gh variable set APP_PORT -b "3000" || print_warning "Failed to set APP_PORT variable"
        
        print_status "GitHub secrets configured for password-based deployment"
    else
        print_error "Git remote 'origin' is not configured. Cannot set GitHub secrets."
        return 1
    fi
    
    # Directories already created with user
    
    # Final instructions
    echo ""
    echo "✅ Service $SERVICE_NAME created successfully!"
    echo ""
    echo "Next steps:"
    echo "1. Update your application code in src/"
    echo "2. Configure DNS to point $APP_DOMAIN to $VPS_HOST"
    echo "3. Push to main branch to deploy"
}

# Export the function
export -f create-service

# If script is executed directly, show usage
if [ "${BASH_SOURCE[0]}" == "${0}" ]; then
    echo "VPS Service Creator"
    echo ""
    echo "Usage:"
    echo "  source $0"
    echo "  create-service [--repo|-r owner/name] [--local-path|-p path] <service-name> [domain]"
    echo ""
    echo "This script will:"
    echo "  - Create a service-specific user on the VPS"
    echo "  - Generate a secure password"
    echo "  - Set up directories with proper ownership"
    echo "  - Create or connect a GitHub repo and configure secrets"
    echo ""
    echo "Required environment variables:"
    echo "  VPS_HOST - Your VPS IP or hostname"
    echo "  VPS_MANAGER_REPO - GitHub repo for templates"
    echo ""
    echo "Requirements:"
    echo "  - gh (GitHub CLI) installed and authenticated (run: gh auth login)"
    echo "  - SSH access as root to your VPS host"
    echo ""
    echo "Options:"
    echo "  --repo|-r owner/name    Specify GitHub repo (auto-detected if omitted)"
    echo "  --local-path|-p path    Use specific local directory (defaults to service-name)"
    echo ""
    echo "Note: Run this with SSH access to root@VPS_HOST"
fi
