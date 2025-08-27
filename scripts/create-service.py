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

__version__ = "2.3.0"

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


def suggest_free_port(vps_host: str, preferred_port: int = 3000) -> int:
    """Suggest a free TCP port on the VPS, starting from preferred_port.
    Checks common listeners using ss/lsof, increments until free.
    """
    import subprocess
    port = preferred_port
    while port < 65535:
        try:
            cmd = [
                "ssh", "-q", "-o", "LogLevel=ERROR", f"root@{vps_host}",
                f"(command -v ss >/dev/null && ss -ltn '( sport = :{port} )' | tail -n +2) || (command -v lsof >/dev/null && lsof -iTCP:{port} -sTCP:LISTEN) || true"
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            busy = bool(result.stdout.strip())
            if not busy:
                return port
        except Exception:
            # On error, still try next port
            pass
        port += 1
    # Fallback
    return preferred_port


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
                      vps_manager_repo: str, domain: Optional[str] = None, app_port: Optional[int] = None) -> str:
    """Initialize git repo and connect to GitHub."""
    # Change to local path
    git = sh.git.bake(_cwd=str(local_path))
    gh = sh.gh.bake(_cwd=str(local_path))
    
    # Ensure we have a repo_name by the end
    final_repo_name = repo_name
    
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
        # Already has remote - extract repo name from URL
        if remote_url.startswith("git@github.com:"):
            final_repo_name = remote_url.replace("git@github.com:", "").replace(".git", "")
        elif remote_url.startswith("https://github.com/"):
            final_repo_name = remote_url.replace("https://github.com/", "").replace(".git", "")
        console.print(f"[green]✓[/green] Using existing GitHub remote: {final_repo_name}")
    except sh.ErrorReturnCode:
        # Need to create/connect repo
        if not final_repo_name:
            # Try to create repo with service name
            username = sh.gh("api", "user", "-q", ".login").strip()
            final_repo_name = f"{username}/{service_name}"
            
            console.print(f"[green]✓[/green] Creating GitHub repository: {final_repo_name}")
            try:
                gh("repo", "create", service_name, "--private", 
                   "--source=.", "--remote=origin", "--push")
            except sh.ErrorReturnCode:
                console.print(f"[red]Failed to create GitHub repo[/red]")
                raise typer.Exit(1)
        else:
            # Connect to specified repo
            console.print(f"[green]✓[/green] Connecting to GitHub repository: {final_repo_name}")
            git("remote", "add", "origin", f"git@github.com:{final_repo_name}.git")
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
        "APP_PORT": str(app_port or 3000),
        "VPS_MANAGER_REPO": vps_manager_repo,
    }
    
    if domain:
        variables["APP_DOMAIN"] = domain
    
    for name, value in variables.items():
        try:
            gh("variable", "set", name, "-b", value)
        except sh.ErrorReturnCode:
            console.print(f"[yellow]Warning:[/yellow] Failed to set variable {name}")
    
    return final_repo_name


def write_dns_records_json(local_path: Path, domain: str, vps_ip: str, service_name: str,
                           netlify_team_slug: str = "") -> Path:
    """Write a minimal infra/dns-records.json into the service repo.
    Optionally embeds Netlify team slug to allow zone creation.
    """
    infra_dir = local_path / "infra"
    infra_dir.mkdir(parents=True, exist_ok=True)
    records_path = infra_dir / "dns-records.json"
    
    # Detect if domain is a subdomain (e.g., potato24.yarden-zamir.com)
    # We'll assume TLD + one level is the zone (e.g., yarden-zamir.com)
    parts = domain.split('.')
    if len(parts) > 2:
        # Likely a subdomain - extract the zone and subdomain
        zone = '.'.join(parts[-2:])  # e.g., "yarden-zamir.com"
        subdomain = '.'.join(parts[:-2])  # e.g., "potato24"
        
        records = [
            {"zone": zone, "name": subdomain, "type": "A", "values": [vps_ip]},
            {"zone": zone, "name": f"www.{subdomain}", "type": "CNAME", "values": [f"{domain}."]},
        ]
    else:
        # It's an apex domain (e.g., example.com)
        records = [
            {"zone": domain, "name": "", "type": "A", "values": [vps_ip]},
            {"zone": domain, "name": "www", "type": "CNAME", "values": [f"{domain}."]},
        ]
        # Add service subdomain only if domain isn't already prefixed with service name
        if not domain.startswith(f"{service_name}."):
            records.append({"zone": domain, "name": service_name, "type": "A", "values": [vps_ip]})
    
    payload = {"records": records}
    if netlify_team_slug:
        payload["netlify_team_slug"] = netlify_team_slug
    try:
        records_path.write_text(json.dumps(payload, indent=2) + "\n")
        console.print(f"[green]✓[/green] Wrote {records_path}")
    except Exception:
        console.print(f"[yellow]Warning:[/yellow] Failed writing {records_path}")
    return records_path


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
    
    # Check for a free application port on your VPS...
    preferred_port = 3000
    console.print("\n[bold]Checking for a free application port on your VPS...[/bold]")
    free_port = suggest_free_port(vps_host, preferred_port)
    if free_port != preferred_port:
        console.print(f"[yellow]Port {preferred_port} appears to be in use. Suggesting free port: {free_port}[/yellow]")
        use_suggested = Confirm.ask(f"Use suggested port {free_port}?", default=True)
        if use_suggested:
            chosen_port = free_port
        else:
            while True:
                try:
                    desired = IntPrompt.ask("Enter desired port (1024-65535)", default=free_port)
                    if desired < 1024 or desired > 65535:
                        console.print("[red]Port must be between 1024 and 65535[/red]")
                        continue
                    # Check if desired is free
                    import subprocess
                    cmd = [
                        "ssh", "-q", "-o", "LogLevel=ERROR", f"root@{vps_host}",
                        f"(command -v ss >/dev/null && ss -ltn '( sport = :{desired} )' | tail -n +2) || (command -v lsof >/dev/null && lsof -iTCP:{desired} -sTCP:LISTEN) || true"
                    ]
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    busy = bool(result.stdout.strip())
                    if busy:
                        console.print(f"[red]Port {desired} is in use on the VPS. Pick another.")
                        continue
                    chosen_port = desired
                    break
                except Exception:
                    console.print("[red]Failed to validate port. Try again.")
                    continue
    else:
        console.print(f"[green]✓[/green] Port {free_port} looks free")
        chosen_port = free_port
    
    # Set up local files
    setup_local_files(local_path, service_name, vps_manager_repo, domain, 
                     dns_provider.value if dns_provider else None)
    
    # Ensure .env has the chosen APP_PORT
    try:
        env_path = local_path / ".env"
        if not env_path.exists():
            example_path = local_path / "env.example"
            if example_path.exists():
                shutil.copy2(example_path, env_path)
        if env_path.exists():
            env_lines = env_path.read_text().splitlines()
            found = False
            for i, line in enumerate(env_lines):
                if line.startswith("APP_PORT="):
                    env_lines[i] = f"APP_PORT={chosen_port}"
                    found = True
                    break
            if not found:
                env_lines.append(f"APP_PORT={chosen_port}")
            env_path.write_text("\n".join(env_lines) + "\n")
    except Exception:
        pass
    
    # Set up GitHub repo
    repo_name = setup_github_repo(local_path, service_name, repo, vps_host, 
                                  service_user, service_password, vps_manager_repo, domain, chosen_port)
    
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
    if domain:
        # Get VPS IP from host
        import socket
        try:
            vps_ip = socket.gethostbyname(vps_host)
        except:
            vps_ip = vps_host  # Assume it's already an IP
        # Prompt for Netlify team slug (optional)
        team_slug = ""
        if dns_provider and dns_provider.value == "netlify":
            # Extract zone from domain
            parts = domain.split('.')
            zone = '.'.join(parts[-2:]) if len(parts) > 2 else domain
            
            console.print(f"\n[bold]Netlify DNS Configuration[/bold]")
            console.print(f"Zone: {zone}")
            console.print("\nIf this zone already exists in Netlify, leave the team slug empty.")
            console.print("Only provide a team slug if you need to create a NEW zone.")
            
            if Confirm.ask("Does this zone need to be created?", default=False):
                team_slug = Prompt.ask("Enter Netlify team slug", default="")
                if team_slug:
                    console.print(f"[green]✓[/green] Will create zone with team slug: {team_slug}")
            else:
                console.print(f"[green]✓[/green] Using existing zone")
        # Write service-local DNS records JSON instead of opening a PR in vps-manager
        write_dns_records_json(local_path, domain, vps_ip, service_name, team_slug)
    
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
    
    if domain:
        console.print("\n[bold]DNS via CI:[/bold]")
        console.print("- Ensure secrets.DNS_PROVIDER_TOKEN is set in your service repo")
        console.print("- Ensure your DNS workflow passes records_path: infra/dns-records.json and sets dns_provider")
    
    # Clean up temp clone if used
    if temp_clone_path:
        try:
            import shutil
            shutil.rmtree(temp_clone_path.parent)
        except:
            pass  # Ignore cleanup errors


if __name__ == "__main__":
    app()
