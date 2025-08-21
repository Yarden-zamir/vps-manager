#!/usr/bin/env bash
#
# VPS Service Creator
# This script creates a new service from the template and sets up deployment
# Compatible with both bash and zsh

# Detect if script is being sourced (works in both bash and zsh)
if [ -n "$ZSH_VERSION" ]; then
    # zsh
    SOURCED=0
    if [[ "$ZSH_EVAL_CONTEXT" =~ :file$ ]]; then
        SOURCED=1
    fi
elif [ -n "$BASH_VERSION" ]; then
    # bash
    SOURCED=0
    if [ "${BASH_SOURCE[0]}" != "${0}" ]; then
        SOURCED=1
    fi
else
    # Unknown shell, assume not sourced
    SOURCED=0
fi

# Don't use set -e when script is sourced - it will crash the shell
if [ "$SOURCED" -eq 0 ]; then
    set -e
fi

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output (using printf for portability)
print_status() {
    printf "${GREEN}✓${NC} %s\n" "$1"
}

print_error() {
    printf "${RED}✗${NC} %s\n" "$1"
}

print_warning() {
    printf "${YELLOW}!${NC} %s\n" "$1"
}

# Check required environment variables
if [ -z "$VPS_MANAGER_REPO" ]; then
    print_error "Please set VPS_MANAGER_REPO environment variable (e.g., 'username/vps-manager')"
    return 1 2>/dev/null || exit 1
fi

if [ -z "$GITHUB_USERNAME" ]; then
    GITHUB_USERNAME=$(git config user.name)
fi

if [ -z "$VPS_HOST" ]; then
    print_error "Please set VPS_HOST environment variable"
    return 1 2>/dev/null || exit 1
fi

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
    local SERVICE_NAME=""
    local APP_DOMAIN=""
    while [[ "$1" == --* ]]; do
        case "$1" in
            --repo)
                REPO_NAME="$2"
                shift 2
                ;;
            --local-path)
                LOCAL_PATH="$2"
                shift 2
                ;;
            --service-name)
                SERVICE_NAME="$2"
                shift 2
                ;;
            --domain)
                APP_DOMAIN="$2"
                shift 2
                ;;
            *)
                print_error "Unknown option: $1"
                return 1
                ;;
        esac
    done

    # Do not allow positional arguments
    if [ -n "$1" ]; then
        print_error "Unexpected positional arguments: $*"
        return 1
    fi
    
    # Require GitHub CLI
    if ! command -v gh &> /dev/null; then
        print_error "GitHub CLI 'gh' is required. Install from https://cli.github.com/ and run 'gh auth login'."
        return 1
    fi
    
    if [ -z "$SERVICE_NAME" ]; then
        print_error "Error: --service-name is required"
        echo "Usage: create-service --local-path <path> --service-name <name> [--domain <domain>] [--repo <owner/name>]"
        return 1
    fi
    
    if [ -z "$LOCAL_PATH" ]; then
        print_error "Error: --local-path is required"
        echo "Usage: create-service --local-path <path> --service-name <name> [--domain <domain>] [--repo <owner/name>]"
        return 1
    fi
    
    # Handle domain
    if [ -z "$APP_DOMAIN" ]; then
        print_warning "No domain provided. Domain-specific features will be skipped."
    fi
    
    echo "🚀 Creating new service: $SERVICE_NAME"
    if [ -n "$APP_DOMAIN" ]; then
        echo "📍 Domain: $APP_DOMAIN"
    fi
    echo ""
    
    # Generate service user credentials
    local SERVICE_USER="svc-${SERVICE_NAME}"
    local SERVICE_PASSWORD
    SERVICE_PASSWORD=$(generate_password)
    
    print_status "Creating service user on VPS..."
    
    # Create user and directories on VPS (as root)
    ssh "root@$VPS_HOST" << ENDSSH
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
    
    # Use provided local path as working directory
    local WORK_DIR="$LOCAL_PATH"
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
                # Extract owner/repo from git URL (portable regex)
                local DETECTED_REPO=""
                DETECTED_REPO=$(echo "$EXISTING_REMOTE" | sed -E 's/.*github\.com[:\/]([^\/]+\/[^\/\.]+)(\.git)?$/\1/' | grep -E '^[^/]+/[^/]+$' || echo "")
                
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
        if [ -n "$APP_DOMAIN" ]; then
            sed -i '' "s/myapp.example.com/$APP_DOMAIN/g" env.example
        fi
    else
        # Linux
        find . -type f \( -name "*.yml" -o -name "*.yaml" -o -name "*.json" -o -name "*.md" -o -name "*.js" \) -print0 | \
            xargs -0 sed -i "s/myapp/$SERVICE_NAME/g"
        sed -i "s/app-template/$SERVICE_NAME/g" package.json
        if [ -n "$APP_DOMAIN" ]; then
            sed -i "s/myapp.example.com/$APP_DOMAIN/g" env.example
        fi
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
                # Update EXISTING_REMOTE since gh repo create with --source and --remote sets it up
                EXISTING_REMOTE="git@github.com:$REPO_NAME.git"
            fi
        fi
        
        # Connect to specified/detected repo if not already connected
        if [ -z "$EXISTING_REMOTE" ] && [ -n "$REPO_NAME" ]; then
            print_status "Connecting to GitHub repository: $REPO_NAME"
            if ! gh repo view "$REPO_NAME" &> /dev/null; then
                # Try to create it if it doesn't exist and matches pattern
                # Extract repo name after username/ (portable)
                local REPO_SHORT_NAME=""
                REPO_SHORT_NAME=$(echo "$REPO_NAME" | sed "s/^$GITHUB_USERNAME\///")
                if [ "$REPO_SHORT_NAME" != "$REPO_NAME" ]; then
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
        if [ -n "$APP_DOMAIN" ]; then
            gh variable set APP_DOMAIN -b "$APP_DOMAIN" || print_warning "Failed to set APP_DOMAIN variable"
        fi
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
    echo "Relevant links:"
    echo "--------------------------------"
    echo "https://github.com/$REPO_NAME"
    echo "https://github.com/$REPO_NAME/actions"
    if [ -n "$APP_DOMAIN" ]; then
        echo "https://$APP_DOMAIN"
    fi
    echo "$(realpath $WORK_DIR)"
    echo "--------------------------------"
    echo "Next steps:"
    echo "1. Update your application code in src/ and make sure dockerfile is correct to your needs"
    if [ -n "$APP_DOMAIN" ]; then
        echo "2. Configure DNS to point $APP_DOMAIN to $VPS_HOST"
    else
        echo "2. Configure your domain when ready"
    fi
    echo "3. Push to main branch to deploy"

}

# Note: Functions cannot be exported in zsh, but they're available after sourcing

# If script is executed directly, show usage
if [ "$SOURCED" -eq 0 ]; then
    echo "VPS Service Creator"
    echo ""
    echo "Usage:"
    echo "  source $0"
    echo "  create-service --local-path <path> --service-name <name> [--domain <domain>] [--repo <owner/name>]"
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
    echo "Required options:"
    echo "  --local-path <path>     Path to the local directory for your service"
    echo "                          This is where template files will be created"
    echo "                          and where your service code will live"
    echo "  --service-name <name>   Name of the service (used for user/repo names)"
    echo ""
    echo "Optional options:"
    echo "  --domain <domain>       Domain for your service (can be added later)"
    echo "  --repo <owner/name>     Specify GitHub repo (auto-detected if omitted)"
    echo ""
    echo "Note: Run this with SSH access to root@VPS_HOST"
fi
