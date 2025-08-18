#!/usr/bin/env python3

"""
Service Account Manager for VPS
Creates isolated Unix users for each service with proper permissions
"""

import os
import sys
import argparse
import subprocess
import pwd
import grp
from pathlib import Path
from typing import List, Tuple

try:
    import sh
except ImportError:
    print("Error: 'sh' library not found. Install with: pip install sh")
    sys.exit(1)


class Colors:
    """Terminal color codes"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'


def print_success(message: str):
    """Print success message in green"""
    print(f"{Colors.GREEN}✓{Colors.END} {message}")


def print_error(message: str):
    """Print error message in red"""
    print(f"{Colors.RED}✗{Colors.END} {message}")


def print_warning(message: str):
    """Print warning message in yellow"""
    print(f"{Colors.YELLOW}!{Colors.END} {message}")


def print_info(message: str):
    """Print info message in blue"""
    print(f"{Colors.BLUE}ℹ{Colors.END} {message}")


class ServiceAccountManager:
    """Manages service accounts on VPS"""
    
    def __init__(self):
        self.base_dirs = {
            'apps': Path('/apps'),
            'persistent': Path('/persistent'),
            'logs': Path('/logs')
        }
        
    def check_root(self):
        """Check if running as root"""
        if os.geteuid() != 0:
            print_error("This script must be run as root")
            sys.exit(1)
    
    def user_exists(self, username: str) -> bool:
        """Check if user already exists"""
        try:
            pwd.getpwnam(username)
            return True
        except KeyError:
            return False
    
    def create_user(self, service_name: str) -> bool:
        """Create a new service user"""
        username = f"svc-{service_name}"
        
        if self.user_exists(username):
            print_warning(f"User {username} already exists")
            return False
        
        try:
            # Create user with no login shell and home directory
            sh.useradd(
                username,
                '--system',
                '--shell', '/usr/sbin/nologin',
                '--home-dir', f'/apps/{service_name}',
                '--no-create-home',
                '--comment', f'Service account for {service_name}'
            )
            
            # Add user to docker group
            sh.usermod('-aG', 'docker', username)
            
            print_success(f"Created user {username}")
            return True
            
        except sh.ErrorReturnCode as e:
            print_error(f"Failed to create user: {e}")
            return False
    
    def create_directories(self, service_name: str) -> bool:
        """Create service directories with proper permissions"""
        username = f"svc-{service_name}"
        
        try:
            for base_name, base_path in self.base_dirs.items():
                service_dir = base_path / service_name
                
                # Create directory
                service_dir.mkdir(parents=True, exist_ok=True)
                
                # Set ownership
                uid = pwd.getpwnam(username).pw_uid
                gid = pwd.getpwnam(username).pw_gid
                os.chown(service_dir, uid, gid)
                
                # Set permissions
                service_dir.chmod(0o755)
                
                print_success(f"Created {service_dir}")
                
                # Create subdirectories for persistent data
                if base_name == 'persistent':
                    for subdir in ['data', 'config', 'backups']:
                        sub_path = service_dir / subdir
                        sub_path.mkdir(exist_ok=True)
                        os.chown(sub_path, uid, gid)
                        sub_path.chmod(0o755)
            
            return True
            
        except Exception as e:
            print_error(f"Failed to create directories: {e}")
            return False
    
    def setup_ssh_key(self, service_name: str, public_key: str = None) -> bool:
        """Set up SSH key for service account"""
        username = f"svc-{service_name}"
        
        try:
            # Create .ssh directory
            ssh_dir = Path(f'/apps/{service_name}/.ssh')
            ssh_dir.mkdir(parents=True, exist_ok=True)
            
            # Create authorized_keys file
            auth_keys = ssh_dir / 'authorized_keys'
            auth_keys.touch(exist_ok=True)
            
            # Add public key if provided
            if public_key:
                with open(auth_keys, 'a') as f:
                    f.write(f"\n{public_key.strip()}\n")
                print_success("Added SSH public key")
            
            # Set ownership and permissions
            uid = pwd.getpwnam(username).pw_uid
            gid = pwd.getpwnam(username).pw_gid
            
            os.chown(ssh_dir, uid, gid)
            os.chown(auth_keys, uid, gid)
            
            ssh_dir.chmod(0o700)
            auth_keys.chmod(0o600)
            
            print_success(f"SSH directory configured for {username}")
            return True
            
        except Exception as e:
            print_error(f"Failed to setup SSH key: {e}")
            return False
    
    def create_service_account(self, service_name: str, ssh_key: str = None):
        """Create complete service account with directories"""
        print_info(f"Creating service account for: {service_name}")
        
        # Create user
        if not self.create_user(service_name):
            return False
        
        # Create directories
        if not self.create_directories(service_name):
            return False
        
        # Setup SSH if key provided
        if ssh_key:
            self.setup_ssh_key(service_name, ssh_key)
        
        print_success(f"Service account created successfully!")
        print_info(f"Username: svc-{service_name}")
        print_info(f"Directories created:")
        for base_name, base_path in self.base_dirs.items():
            print(f"  - {base_path}/{service_name}")
        
        return True
    
    def remove_service_account(self, service_name: str, keep_data: bool = True):
        """Remove service account"""
        username = f"svc-{service_name}"
        
        if not self.user_exists(username):
            print_error(f"User {username} does not exist")
            return False
        
        print_warning(f"Removing service account: {username}")
        
        try:
            # Remove user
            sh.userdel(username)
            print_success(f"Removed user {username}")
            
            # Handle directories
            if keep_data:
                print_info("Keeping data directories (use --purge to remove)")
            else:
                print_warning("Removing all service directories...")
                for base_path in self.base_dirs.values():
                    service_dir = base_path / service_name
                    if service_dir.exists():
                        sh.rm('-rf', str(service_dir))
                        print_success(f"Removed {service_dir}")
            
            return True
            
        except sh.ErrorReturnCode as e:
            print_error(f"Failed to remove user: {e}")
            return False
    
    def list_service_accounts(self):
        """List all service accounts"""
        print_info("Service accounts:")
        
        # Get all users starting with svc-
        for user in pwd.getpwall():
            if user.pw_name.startswith('svc-'):
                service_name = user.pw_name.replace('svc-', '')
                print(f"  • {user.pw_name} ({service_name})")
                
                # Check directories
                for base_name, base_path in self.base_dirs.items():
                    service_dir = base_path / service_name
                    if service_dir.exists():
                        size = sh.du('-sh', str(service_dir)).split()[0]
                        print(f"    - {service_dir} ({size})")
    
    def check_service_account(self, service_name: str):
        """Check status of service account"""
        username = f"svc-{service_name}"
        
        print_info(f"Checking service account: {service_name}")
        
        # Check user
        if self.user_exists(username):
            user = pwd.getpwnam(username)
            print_success(f"User exists: {username} (UID: {user.pw_uid})")
            
            # Check group membership
            groups = [g.gr_name for g in grp.getgrall() if username in g.gr_mem]
            if 'docker' in groups:
                print_success("User is in docker group")
            else:
                print_warning("User is NOT in docker group")
        else:
            print_error(f"User does not exist: {username}")
        
        # Check directories
        for base_name, base_path in self.base_dirs.items():
            service_dir = base_path / service_name
            if service_dir.exists():
                stat = service_dir.stat()
                owner = pwd.getpwuid(stat.st_uid).pw_name
                print_success(f"{service_dir} exists (owner: {owner})")
            else:
                print_warning(f"{service_dir} does not exist")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Manage service accounts for VPS deployments'
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Create command
    create_parser = subparsers.add_parser('create', help='Create service account')
    create_parser.add_argument('service', help='Service name')
    create_parser.add_argument('--ssh-key', help='SSH public key to add')
    
    # Remove command
    remove_parser = subparsers.add_parser('remove', help='Remove service account')
    remove_parser.add_argument('service', help='Service name')
    remove_parser.add_argument('--purge', action='store_true', 
                              help='Also remove all data directories')
    
    # List command
    list_parser = subparsers.add_parser('list', help='List all service accounts')
    
    # Check command
    check_parser = subparsers.add_parser('check', help='Check service account status')
    check_parser.add_argument('service', help='Service name')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    manager = ServiceAccountManager()
    manager.check_root()
    
    if args.command == 'create':
        manager.create_service_account(args.service, args.ssh_key)
    elif args.command == 'remove':
        manager.remove_service_account(args.service, keep_data=not args.purge)
    elif args.command == 'list':
        manager.list_service_accounts()
    elif args.command == 'check':
        manager.check_service_account(args.service)


if __name__ == '__main__':
    main()
