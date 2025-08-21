#!/usr/bin/env -S uv run
# /// script
# dependencies = [
#   "typer>=0.9.0",
#   "rich>=13.0",
#   "sh>=2.0",
#   "pyyaml>=6.0",
#   "requests>=2.31",
# ]
# ///
"""
VPS Service Creator - Unified script for creating services with DNS
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path
from typing import Optional, Annotated
from enum import Enum

import typer
from typer import Option, Argument
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm, IntPrompt
from rich.progress import Progress, SpinnerColumn, TextColumn
import requests
import secrets
import string
import sh
import json

__version__ = "2.2.0"

console = Console()
app = typer.Typer(
    help="VPS Service Creator - Create services with integrated DNS management",
    rich_markup_mode="rich",
    add_completion=True,
    no_args_is_help=True,
    pretty_exceptions_enable=True,
)

class DNSProvider(str, Enum):
    """Supported DNS providers"""
    cloudflare = "cloudflare"
    netlify = "netlify"
    digitalocean = "digitalocean"
    dnsimple = "dnsimple"
    linode = "linode"


def version_callback(value: bool):
    """Show version and exit."""
    if value:
        console.print(f"[bold blue]VPS Service Creator[/bold blue] version {__version__}")
        raise typer.Exit()


def generate_password(length: int = 16) -> str:
    """Generate a secure random password."""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def check_requirements() -> None:
    """Check that required tools are installed."""
    # Check for git
    try:
        sh.git("--version", _out=lambda x: None)
    except sh.CommandNotFound:
        console.print("[red]Error:[/red] git is required but not found")
        raise typer.Exit(1)
    
    # Check for gh CLI
    try:
        sh.gh("--version", _out=lambda x: None)
    except sh.CommandNotFound:
        console.print("[red]Error:[/red] GitHub CLI (gh) is required. Install from https://cli.github.com/")
        raise typer.Exit(1)
    
    # Check gh auth
    try:
        sh.gh("auth", "status", _out=lambda x: None, _err=lambda x: None)
    except sh.ErrorReturnCode:
        console.print("[red]Error:[/red] GitHub CLI not authenticated. Run: gh auth login")
        raise typer.Exit(1)

    # Check for jq (used to sanitize gh JSON output)
    try:
        sh.jq("--version", _out=lambda x: None)
    except sh.CommandNotFound:
        console.print("[red]Error:[/red] jq is required but not found. Install jq and retry.")
        console.print("macOS: brew install jq | Debian/Ubuntu: sudo apt-get install jq | Alpine: apk add jq")
        raise typer.Exit(1)


def clone_vps_manager_repo(repo: str) -> Path:
    """Clone vps-manager repo to a temporary directory."""
    import tempfile
    temp_dir = Path(tempfile.mkdtemp(prefix="vps-manager-"))
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task(f"Cloning {repo}...", total=None)
        try:
            sh.git("clone", f"https://github.com/{repo}.git", str(temp_dir / "vps-manager"))
            progress.update(task, completed=True)
        except sh.ErrorReturnCode as e:
            console.print(f"[red]Failed to clone {repo}[/red]")
            raise typer.Exit(1)
    
    return temp_dir / "vps-manager"


def test_ssh_connection(vps_host: str) -> str:
    """Test SSH connection and prompt for method if needed. Returns auth method."""
    console.print(f"\n[bold]Testing SSH connection to {vps_host}...[/bold]")
    
    try:
        # Try key-based auth first
        sh.ssh("-o", "BatchMode=yes", "-o", "ConnectTimeout=5", 
               f"root@{vps_host}", "echo", "Connection successful", 
               _out=lambda x: None, _err=lambda x: None)
        console.print("[green]✓[/green] SSH key authentication successful")
        return "key"
    except sh.ErrorReturnCode:
        console.print("[yellow]SSH key authentication failed[/yellow]")
        console.print("\n[bold]Choose how to proceed:[/bold]")
        
        # Create options menu
        options = [
            "[red]Abort[/red] - Exit without creating service",
            "[yellow]Continue with password + setup SSH key[/yellow] - Use password and copy SSH key for future use",
            "[blue]Continue with password only[/blue] - Use password authentication for this session"
        ]
        
        for i, option in enumerate(options, 1):
            console.print(f"{i}. {option}")
        
        # Get user choice
        choice = IntPrompt.ask(
            "\nSelect option",
            choices=["1", "2", "3"],
            default=3
        )
        
        if choice == 1:
            console.print("\n[red]Operation cancelled[/red]")
            raise typer.Exit(1)
        elif choice == 2:
            # Setup SSH key
            setup_ssh_key(vps_host)
            return "password_with_key_setup"
        else:
            console.print("\n[blue]Continuing with password authentication[/blue]")
            console.print("You will be prompted for your password for each command.")
            return "password"


def setup_ssh_key(vps_host: str) -> None:
    """Copy SSH key to the VPS for future passwordless access."""
    console.print("\n[bold]Setting up SSH key for future access...[/bold]")
    
    # Check if we have an SSH key
    import os
    ssh_key_path = os.path.expanduser("~/.ssh/id_rsa.pub")
    if not os.path.exists(ssh_key_path):
        # Try other common key types
        for key_type in ["id_ed25519.pub", "id_ecdsa.pub"]:
            alt_path = os.path.expanduser(f"~/.ssh/{key_type}")
            if os.path.exists(alt_path):
                ssh_key_path = alt_path
                break
        else:
            console.print("[yellow]No SSH key found. Generating one...[/yellow]")
            try:
                sh.ssh_keygen("-t", "ed25519", "-f", os.path.expanduser("~/.ssh/id_ed25519"), "-N", "")
                ssh_key_path = os.path.expanduser("~/.ssh/id_ed25519.pub")
                console.print("[green]✓[/green] SSH key generated")
            except sh.ErrorReturnCode:
                console.print("[red]Failed to generate SSH key[/red]")
                return
    
    # Copy the key
    console.print(f"[dim]→ ssh-copy-id -o PubkeyAuthentication=no root@{vps_host}[/dim]")
    try:
        import subprocess
        process = subprocess.run(
            ["ssh-copy-id", "-o", "PubkeyAuthentication=no", f"root@{vps_host}"],
            check=True
        )
        console.print("[green]✓[/green] SSH key copied successfully!")
        console.print("[green]Future connections will use key authentication[/green]")
    except subprocess.CalledProcessError:
        console.print("[yellow]Failed to copy SSH key, continuing with password authentication[/yellow]")


def ssh_command(host: str, command: str, description: str) -> bool:
    """Execute a single SSH command with progress reporting."""
    import subprocess
    
    # Show what we're doing
    console.print(f"\n[bold]{description}[/bold]")
    console.print(f"[dim]→ {command}[/dim]")
    
    try:
        # Use subprocess for better control over interactive SSH
        # -q and LogLevel=ERROR suppress non-essential messages like
        # "Connection to <host> closed." while keeping prompts visible
        process = subprocess.run(
            [
                "ssh",
                "-q",
                "-o",
                "LogLevel=ERROR",
                "-t",
                host,
                command,
            ],
            check=True,
        )
        console.print(f"[green]✓[/green] {description}")
        return True
    except subprocess.CalledProcessError:
        console.print(f"[red]✗ Failed: {description}[/red]")
        return False
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user[/yellow]")
        raise typer.Exit(1)


def create_vps_user(vps_host: str, service_name: str) -> tuple[str, str]:
    """Create service user on VPS and return username and password."""
    service_user = f"svc-{service_name}"
    service_password = generate_password()
    
    console.print(f"\n[bold]Creating service user: {service_user}[/bold]")
    
    # Step 1: Create user
    if not ssh_command(
        f"root@{vps_host}",
        f"useradd -m -s /bin/bash -d /home/{service_user} {service_user}",
        f"Creating user {service_user}..."
    ):
        # User might already exist, try to continue
        console.print("[yellow]User might already exist, continuing...[/yellow]")
    
    # Step 2: Set password
    if not ssh_command(
        f"root@{vps_host}",
        f"echo '{service_user}:{service_password}' | chpasswd",
        "Setting user password..."
    ):
        console.print("[red]Failed to set user password[/red]")
        raise typer.Exit(1)
    
    # Step 3: Add to docker group
    if not ssh_command(
        f"root@{vps_host}",
        f"usermod -aG docker {service_user}",
        "Adding user to docker group..."
    ):
        console.print("[red]Failed to add user to docker group[/red]")
        raise typer.Exit(1)
    
    # Step 4: Create directories
    directories = [
        f"/apps/{service_name}",
        f"/persistent/{service_name}/data",
        f"/logs/{service_name}"
    ]
    
    for directory in directories:
        if not ssh_command(
            f"root@{vps_host}",
            f"mkdir -p {directory}",
            f"Creating directory {directory}..."
        ):
            console.print(f"[red]Failed to create directory {directory}[/red]")
            raise typer.Exit(1)
    
    # Step 5: Set ownership
    for directory in directories:
        if not ssh_command(
            f"root@{vps_host}",
            f"chown -R {service_user}:{service_user} {directory}",
            f"Setting ownership for {directory}..."
        ):
            console.print(f"[red]Failed to set ownership for {directory}[/red]")
            raise typer.Exit(1)
    
    # Step 6: Set permissions
    for directory in directories:
        if not ssh_command(
            f"root@{vps_host}",
            f"chmod 755 {directory}",
            f"Setting permissions for {directory}..."
        ):
            console.print(f"[red]Failed to set permissions for {directory}[/red]")
            raise typer.Exit(1)
    
    console.print(f"[green]✓[/green] Service user {service_user} created successfully!")
    return service_user, service_password


def setup_local_files(local_path: Path, service_name: str, vps_manager_repo: str,
                     domain: Optional[str] = None, provider: Optional[str] = None) -> None:
    """Download template and set up local service files."""
    console.print(f"[green]✓[/green] Setting up local files...")
    
    # Create directory if needed
    local_path.mkdir(parents=True, exist_ok=True)
    
    # Download template
    with tempfile.TemporaryDirectory() as tmpdir:
        template_url = f"https://github.com/{vps_manager_repo}/archive/main.tar.gz"
        response = requests.get(template_url, stream=True)
        response.raise_for_status()
        
        tar_path = Path(tmpdir) / "template.tar.gz"
        with open(tar_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        # Extract template
        sh.tar("xzf", str(tar_path), "-C", tmpdir, "--strip-components=2", 
               "vps-manager-main/template/")
        
        # Copy files (don't overwrite existing)
        for item in Path(tmpdir).iterdir():
            if item.name == "template.tar.gz":
                continue
            dest = local_path / item.name
            if dest.exists():
                console.print(f"[yellow]![/yellow] Skipping existing: {item.name}")
            else:
                if item.is_dir():
                    shutil.copytree(item, dest)
                else:
                    shutil.copy2(item, dest)
    
    # Replace placeholders
    console.print(f"[green]✓[/green] Customizing template...")
    
    for file_path in local_path.rglob("*"):
        if file_path.is_file() and file_path.suffix in ['.yml', '.yaml', '.json', '.md', '.js']:
            try:
                content = file_path.read_text()
                content = content.replace("myapp", service_name)
                content = content.replace("app-template", service_name)
                
                if domain:
                    content = content.replace("myapp.example.com", domain)
                
                file_path.write_text(content)
            except:
                pass  # Skip binary files
    
    # Update package.json specifically
    package_json = local_path / "package.json"
    if package_json.exists():
        content = package_json.read_text()
        content = content.replace("app-template", service_name)
        package_json.write_text(content)
    
    # Update DNS workflows if domain and provider specified
    if domain and provider:
        for workflow in ["dns-plan.yml", "dns-apply.yml"]:
            workflow_path = local_path / ".github" / "workflows" / workflow
            if workflow_path.exists():
                content = workflow_path.read_text()
                content = content.replace("myapp.example.com", domain)
                content = content.replace("provider: cloudflare", f"provider: {provider}")
                workflow_path.write_text(content)


def setup_github_repo(local_path: Path, service_name: str, repo_name: Optional[str],
                     vps_host: str, service_user: str, service_password: str,
                     vps_manager_repo: str, domain: Optional[str] = None) -> str:
    """Initialize git repo and connect to GitHub."""
    # Change to local path
    git = sh.git.bake(_cwd=str(local_path))
    gh = sh.gh.bake(_cwd=str(local_path))
    
    # Initialize git if needed
    if not (local_path / ".git").exists():
        console.print(f"[green]✓[/green] Initializing git repository...")
        try:
            git("init", "-b", "main")
        except sh.ErrorReturnCode:
            git("init")
            git("branch", "-M", "main")
    
    # Add and commit if there are changes
    try:
        status = git("status", "--porcelain").strip()
        if status:
            console.print(f"[green]✓[/green] Committing template files...")
            git("add", ".")
            git("commit", "-m", "Add VPS service template")
    except sh.ErrorReturnCode:
        pass  # No changes to commit
    
    # Check for existing remote
    try:
        remote_url = git("remote", "get-url", "origin").strip()
        # Already has remote
        if remote_url.startswith("git@github.com:"):
            repo_name = remote_url.replace("git@github.com:", "").replace(".git", "")
        console.print(f"[green]✓[/green] Using existing GitHub remote: {repo_name}")
    except sh.ErrorReturnCode:
        # Need to create/connect repo
        if not repo_name:
            # Try to create repo with service name
            username = sh.gh("api", "user", "-q", ".login").strip()
            repo_name = f"{username}/{service_name}"
            
            console.print(f"[green]✓[/green] Creating GitHub repository: {repo_name}")
            try:
                gh("repo", "create", service_name, "--private", 
                   "--source=.", "--remote=origin", "--push")
            except sh.ErrorReturnCode:
                console.print(f"[red]Failed to create GitHub repo[/red]")
                raise typer.Exit(1)
        else:
            # Connect to specified repo
            console.print(f"[green]✓[/green] Connecting to GitHub repository: {repo_name}")
            git("remote", "add", "origin", f"git@github.com:{repo_name}.git")
            try:
                git("push", "-u", "origin", "main")
            except sh.ErrorReturnCode:
                console.print("[yellow]Warning:[/yellow] Push failed. You may need to reconcile history.")
    
    # Set up GitHub secrets and variables
    console.print(f"[green]✓[/green] Setting up GitHub secrets...")
    
    secrets = {
        "VPS_HOST": vps_host,
        "VPS_USER": service_user,
        "VPS_PASSWORD": service_password,
    }
    
    for name, value in secrets.items():
        try:
            gh("secret", "set", name, "-b", value)
        except sh.ErrorReturnCode:
            console.print(f"[yellow]Warning:[/yellow] Failed to set secret {name}")
    
    variables = {
        "APP_PORT": "3000",
        "VPS_MANAGER_REPO": vps_manager_repo,
    }
    
    if domain:
        variables["APP_DOMAIN"] = domain
    
    for name, value in variables.items():
        try:
            gh("variable", "set", name, "-b", value)
        except sh.ErrorReturnCode:
            console.print(f"[yellow]Warning:[/yellow] Failed to set variable {name}")
    
    return repo_name


def create_dns_config(vps_manager_path: Path, domain: str, vps_ip: str, 
                     service_name: str, vps_manager_repo: str) -> str:
    """Create DNS zone configuration file and PR. Returns PR URL."""
    console.print(f"[green]✓[/green] Creating DNS configuration...")
    
    zones_dir = vps_manager_path / "dns" / "zones"
    zones_dir.mkdir(parents=True, exist_ok=True)
    
    zone_file = zones_dir / f"{domain}.yaml"
    
    if zone_file.exists():
        if not Confirm.ask(f"Zone file {zone_file} already exists. Overwrite?"):
            return ""
    
    zone_config = f"""# DNS records for {domain}
# Generated by create-service.py

# Root domain pointing to VPS
'':
  type: A
  value: {vps_ip}

# WWW subdomain
www:
  type: CNAME
  value: {domain}.

# Service subdomain (if not using root domain)
{service_name}:
  type: A
  value: {vps_ip}

# API subdomain (remove if not needed)
api:
  type: A
  value: {vps_ip}

# TXT records for domain verification and SPF
'':
  type: TXT
  values:
    - '"v=spf1 a mx ~all"'
"""
    
    zone_file.write_text(zone_config)
    console.print(f"[green]✓[/green] Created {zone_file}")
    
    # Create git commit and PR
    git = sh.git.bake(_cwd=str(vps_manager_path))
    gh = sh.gh.bake(_cwd=str(vps_manager_path))
    branch_name = f"dns-setup-{domain}"
    
    # Check if we're on main/master
    current_branch = git("branch", "--show-current").strip()
    if current_branch in ["main", "master"]:
        git("checkout", "-b", branch_name)
    
    git("add", str(zone_file))
    # If there are no changes staged, skip committing/PR creation
    status = git("status", "--porcelain").strip()
    if not status:
        console.print(
            f"[yellow]No DNS changes detected for {domain}. Skipping commit and PR creation.[/yellow]"
        )
        return ""

    # Use multiple -m flags to create a multi-paragraph commit message safely
    git(
        "commit",
        "-m",
        f"Add DNS configuration for {domain}",
        "-m",
        f"- Service: {service_name}\n- VPS IP: {vps_ip}",
    )
    
    console.print(f"[green]✓[/green] Created branch: {branch_name}")
    
    # Push and create PR
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Creating pull request...", total=None)
        
        try:
            git("push", "-u", "origin", branch_name)
            pr_output = gh("pr", "create", 
                          "--title", f"Add DNS configuration for {domain}",
                          "--body", f"This PR adds DNS configuration for {domain}\n\n"
                                   f"- Service: {service_name}\n"
                                   f"- VPS IP: {vps_ip}\n\n"
                                   f"Auto-generated by create-service.py",
                          "--repo", vps_manager_repo)
            pr_url = pr_output.strip()
            progress.update(task, completed=True)
            
            console.print(f"[green]✓[/green] Created pull request: {pr_url}")
            return pr_url
        except sh.ErrorReturnCode as e:
            console.print("[red]Failed to create pull request[/red]")
            if e.stderr:
                console.print(e.stderr.decode())
            return ""


def wait_for_pr_merge(pr_url: str, repo: str, domain: str) -> bool:
    """Wait for PR to be merged. Returns True if merged, False if closed/cancelled."""
    import time
    import re
    
    # Extract PR number from URL
    pr_match = re.search(r'/pull/(\d+)$', pr_url)
    if not pr_match:
        console.print("[red]Could not extract PR number from URL[/red]")
        return False
    
    pr_number = pr_match.group(1)
    console.print(f"\n[yellow]Waiting for PR #{pr_number} to be merged...[/yellow]")
    console.print("You can merge it at: " + pr_url)
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Waiting for PR merge...", total=None)
        
        while True:
            try:
                # Check if PR still exists and get its state
                try:
                    # Use environment variables and sed to strip ANSI codes before jq
                    pr_out = sh.gh(f"pr view {pr_number} --json state --repo {repo} | jq -r .state").strip()
                    
                    if pr_out == "MERGED":
                        progress.update(task, completed=True)
                        console.print(f"[green]✓[/green] PR #{pr_number} has been merged!")
                        return True
                    elif pr_out == "CLOSED":
                        progress.update(task, completed=True)
                        console.print(f"[red]✗[/red] PR #{pr_number} was closed without merging")
                        return False
                    elif pr_out == "OPEN":
                        # Still open, continue waiting
                        pass
                    else:
                        console.print(f"[yellow]Unknown PR state: {pr_out}[/yellow]")
                        
                except sh.ErrorReturnCode:
                    # PR might not exist anymore (could mean it was merged and branch deleted)
                    # Try to check if the branch was merged by checking git log
                    try:
                        sh.bash(
                            "-lc",
                            f"gh api repos/{repo}/git/refs/heads/dns-setup-{domain}",
                            _out=lambda x: None
                        )
                        # Branch still exists, so PR wasn't merged
                        pass
                    except sh.ErrorReturnCode:
                        # Branch deleted, likely means PR was merged
                        progress.update(task, completed=True)
                        console.print(f"[green]✓[/green] PR #{pr_number} appears to have been merged (branch deleted)!")
                        return True
                
                time.sleep(5)  # Check every 5 seconds
            except sh.ErrorReturnCode as e:
                console.print(f"[red]Failed to check PR status[/red] - error: {e}")
                time.sleep(10)  # Retry on error
            except KeyboardInterrupt:
                console.print("\n[yellow]Cancelled waiting for PR merge[/yellow]")
                return False


def run_dns_apply(repo_name: str, domain: str, provider: str) -> bool:
    """Run the DNS apply workflow in the service repository."""
    console.print(f"\n[green]✓[/green] Running DNS apply workflow...")
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Triggering DNS apply...", total=None)
        
        try:
            # Trigger the workflow
            output = sh.gh("workflow", "run", "dns-apply.yml", 
                          "--repo", repo_name)
            progress.update(task, completed=True)
            
            console.print(f"[green]✓[/green] DNS apply workflow triggered successfully!")
            console.print(f"\nMonitor progress at: https://github.com/{repo_name}/actions")
            return True
        except sh.ErrorReturnCode as e:
            console.print("[red]Failed to trigger DNS apply workflow[/red]")
            if e.stderr:
                console.print(e.stderr.decode())
            return False


@app.command()
def create_service(
    service_name: Annotated[str, Argument(help="Name of the service")],
    local_path: Annotated[Path, Argument(help="Local directory for service", 
                                       callback=lambda p: Path(p).expanduser().resolve())],
    domain: Annotated[Optional[str], Option("--domain", "-d", 
                                          help="Domain name for the service")] = None,
    dns_provider: Annotated[Optional[DNSProvider], Option("--dns-provider", "-p",
                                                         help="DNS provider (required if domain is specified)")] = None,
    repo: Annotated[Optional[str], Option("--repo", "-r",
                                        help="GitHub repository (owner/name), auto-created if not specified")] = None,
    vps_host: Annotated[str, Option("--vps-host", envvar="VPS_HOST",
                                   help="[yellow]VPS hostname or IP[/yellow]",
                                   rich_help_panel="Environment Variables")] = None,
    vps_manager_repo: Annotated[str, Option("--vps-manager-repo", envvar="VPS_MANAGER_REPO",
                                          help="[yellow]VPS manager repository (owner/name)[/yellow]",
                                          rich_help_panel="Environment Variables")] = None,
    vps_manager_path: Annotated[Optional[Path], Option("--vps-manager-path", envvar="VPS_MANAGER_PATH",
                                                      help="Local path to vps-manager repo (for DNS config)",
                                                      rich_help_panel="Environment Variables")] = None,
    dns_provider_token: Annotated[Optional[str], Option("--dns-token", envvar="DNS_PROVIDER_TOKEN",
                                                       help="[yellow]DNS provider API token[/yellow]",
                                                       rich_help_panel="Environment Variables")] = None,
    version: Annotated[Optional[bool], Option("--version", "-v", callback=version_callback,
                                            help="Show version and exit")] = None,
):
    """
    Create a new VPS service with optional DNS configuration.
    
    This command will:
    • Create a service user on your VPS
    • Set up the service from template
    • Configure GitHub repository and secrets
    • Optionally set up DNS configuration
    
    [bold cyan]Examples:[/bold cyan]
    
    Basic service:
        create-service.py myapp ~/projects/myapp
    
    With DNS:
        create-service.py webapp ~/webapp --domain webapp.com --dns-provider cloudflare
    """
    
    # Validate required environment variables
    if not vps_host:
        console.print("[red]Error:[/red] VPS_HOST environment variable is required")
        raise typer.Exit(1)
    
    if not vps_manager_repo:
        console.print("[red]Error:[/red] VPS_MANAGER_REPO environment variable is required")
        raise typer.Exit(1)
    
    # Validate inputs
    if domain and not dns_provider:
        console.print("[red]Error:[/red] --dns-provider is required when --domain is specified")
        raise typer.Exit(1)
    
    if domain and not dns_provider_token:
        console.print("[red]Error:[/red] DNS_PROVIDER_TOKEN environment variable is required when using DNS")
        raise typer.Exit(1)
    
    # Clone vps-manager repo if path not provided
    temp_clone_path = None
    if domain and not vps_manager_path:
        temp_clone_path = clone_vps_manager_repo(vps_manager_repo)
        vps_manager_path = temp_clone_path
    
    # Check requirements
    check_requirements()
    
    # Show summary
    console.print(Panel.fit(
        f"[bold]Creating Service: {service_name}[/bold]\n\n"
        f"Local Path: {local_path}\n"
        f"VPS Host: {vps_host}\n"
        f"Domain: {domain or 'Not configured'}\n"
        f"DNS Provider: {dns_provider or 'N/A'}",
        title="🚀 VPS Service Creator"
    ))
    
    # Test SSH connection
    auth_method = test_ssh_connection(vps_host)
    
    # Create service user on VPS
    service_user, service_password = create_vps_user(vps_host, service_name)
    
    # Show credentials
    creds_table = Table(title="🔐 Service Credentials (SAVE THESE!)")
    creds_table.add_column("Field", style="cyan")
    creds_table.add_column("Value", style="green")
    creds_table.add_row("Username", service_user)
    creds_table.add_row("Password", service_password)
    creds_table.add_row("SSH Command", f"ssh {service_user}@{vps_host}")
    console.print(creds_table)
    
    # Set up local files
    setup_local_files(local_path, service_name, vps_manager_repo, domain, 
                     dns_provider.value if dns_provider else None)
    
    # Set up GitHub repo
    repo_name = setup_github_repo(local_path, service_name, repo, vps_host, 
                                 service_user, service_password, vps_manager_repo, domain)
    
    # Set DNS provider token if provided
    if dns_provider_token and domain:
        console.print(f"[green]✓[/green] Setting DNS provider token...")
        try:
            sh.gh("secret", "set", "DNS_PROVIDER_TOKEN", "-b", dns_provider_token, 
                  "--repo", repo_name)
        except sh.ErrorReturnCode:
            console.print(f"[yellow]Warning:[/yellow] Failed to set DNS_PROVIDER_TOKEN secret")
    
    # Create DNS configuration if domain specified
    pr_url = ""
    if domain and vps_manager_path:
        # Get VPS IP from host
        import socket
        try:
            vps_ip = socket.gethostbyname(vps_host)
        except:
            vps_ip = vps_host  # Assume it's already an IP
        
        pr_url = create_dns_config(vps_manager_path, domain, vps_ip, service_name, vps_manager_repo)
    
    # Final instructions
    console.print("\n[bold green]✅ Service created successfully![/bold green]\n")
    
    links_table = Table(title="Relevant Links")
    links_table.add_column("Description", style="cyan")
    links_table.add_column("URL", style="blue")
    links_table.add_row("GitHub Repo", f"https://github.com/{repo_name}")
    links_table.add_row("GitHub Actions", f"https://github.com/{repo_name}/actions")
    if domain:
        links_table.add_row("Service URL", f"https://{domain}")
    links_table.add_row("Local Path", str(local_path))
    console.print(links_table)
    
    console.print("\n[bold]Next Steps:[/bold]")
    console.print("1. Update your application code in src/")
    console.print("2. Make sure Dockerfile is correct for your needs")
    console.print("3. Push to main branch to deploy:")
    console.print("   git add .")
    console.print("   git commit -m 'Initial deployment'")
    console.print("   git push")
    
    # Handle DNS workflow if configured
    if domain and pr_url:
        # Wait for PR to be merged
        if wait_for_pr_merge(pr_url, vps_manager_repo, domain):
            # Run DNS apply workflow
            if run_dns_apply(repo_name, domain, dns_provider.value):
                console.print(f"\n[bold green]🎉 DNS configuration complete![/bold green]")
                console.print(f"Your service will be available at https://{domain} once DNS propagates.")
            else:
                console.print(f"\n[yellow]⚠️  DNS apply failed. You can manually run:[/yellow]")
                console.print(f"   cd {local_path}")
                console.print(f"   gh workflow run dns-apply.yml")
        else:
            console.print(f"\n[yellow]⚠️  DNS PR was not merged. To complete DNS setup:[/yellow]")
            console.print(f"1. Merge the PR at: {pr_url}")
            console.print(f"2. Run DNS apply:")
            console.print(f"   cd {local_path}")
            console.print(f"   gh workflow run dns-apply.yml")
    
    # Clean up temp clone if used
    if temp_clone_path:
        try:
            import shutil
            shutil.rmtree(temp_clone_path.parent)
        except:
            pass  # Ignore cleanup errors


if __name__ == "__main__":
    app()
