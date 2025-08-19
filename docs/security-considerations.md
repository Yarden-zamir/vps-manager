# Security Considerations

This setup prioritizes **convenience and simplicity** over maximum security. It's designed for hobby projects, development environments, and situations where ease of use is more important than strict security.

## Current Security Stance

### What's Enabled (for convenience)

1. **Password Authentication** - Each service has its own user with password
2. **Root Login** - Root manages the VPS and creates services
3. **All Ports Open** - Services exposed in Docker are immediately accessible
4. **Per-Service Isolation** - Each service runs under its own Unix user

### Why This Approach?

- **Service Isolation**: Compromised service can't access other services' files
- **Simple Deployment**: Password-based deployment via GitHub Actions
- **Easy Management**: Root creates and manages all services
- **Development Friendly**: No firewall blocking during development
- **No SSH Keys**: Simpler setup, passwords are auto-generated

## Security Trade-offs

### Risks

1. **Brute Force Attacks**: Password auth is vulnerable to automated attacks
2. **Root Compromise**: Direct root access means one breach = full control
3. **Exposed Services**: Any misconfigured service is immediately public

### Mitigations Already in Place

1. **User Isolation**: Each service has its own Unix user
2. **Docker Isolation**: Services run in containers
3. **Separate Networks**: Each app has its own network
4. **HTTPS by Default**: Traefik provides TLS encryption
5. **Non-root Containers**: Services don't run as root inside containers
6. **Auto-generated Passwords**: Strong passwords created automatically

## Per-Service User Architecture

Each service gets:
- **Dedicated Unix user**: `svc-{servicename}`
- **Own directories**: `/apps/{service}`, `/persistent/{service}`, `/logs/{service}`
- **Docker access**: User is in docker group
- **Password auth**: For deployment via GitHub Actions

Benefits:
- Services can't read each other's files
- Separate credentials per service
- Easy to track resource usage
- Simple to remove a service completely

## Hardening Options

If you want better security, you can selectively enable these:



### 1. Disable Password Authentication

```bash
# Edit SSH config
sudo nano /etc/ssh/sshd_config

# Change to:
PasswordAuthentication no

# Restart SSH
sudo systemctl restart ssh
```

**Note**: Make sure you have SSH key access first!

### 2. Disable Root Login

```bash
# Edit SSH config
sudo nano /etc/ssh/sshd_config

# Change to:
PermitRootLogin no

# Restart SSH
sudo systemctl restart ssh
```

### 3. Configure Firewall

```bash
# Basic firewall rules
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw enable
```

### 4. Install Fail2ban

```bash
# Already installed by bootstrap, just configure:
sudo nano /etc/fail2ban/jail.local

# Add:
[sshd]
enabled = true
maxretry = 5
bantime = 3600
```

### 5. Use Strong Passwords

If keeping password auth:
- Use long, random passwords
- Consider using a password manager
- Different password for each user

## Recommended Approach

### For Development/Testing
- Keep current settings (convenience first)
- Use strong passwords
- Regular backups

### For Production
1. Disable password auth after setting up SSH keys
2. Disable root login
3. Enable firewall with specific rules
4. Set up monitoring/alerts
5. Regular security updates

## Quick Security Check

```bash
# Check current SSH settings
grep -E "^(PasswordAuthentication|PermitRootLogin|PubkeyAuthentication)" /etc/ssh/sshd_config

# Check open ports
sudo ss -tlnp

# Check failed login attempts
sudo grep "Failed password" /var/log/auth.log | tail -20

# Check firewall status
sudo ufw status
```

## Remember

This setup is intentionally permissive to avoid lockouts and reduce complexity. You can always harden security later based on your needs. The goal is to get you deployed quickly, not to build Fort Knox.

For truly sensitive applications, consider:
- Managed hosting platforms
- Professional security audits
- Dedicated security tools
- Regular penetration testing
