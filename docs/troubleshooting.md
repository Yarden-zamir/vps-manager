# Troubleshooting Guide

Common issues and solutions for VPS-deployed services.

## Deployment Issues

### GitHub Action Fails

#### SSH Connection Failed
```
Error: ssh: connect to host x.x.x.x port 22: Connection refused
```

**Solution:**
1. Verify VPS is accessible: `ssh deploy@YOUR_VPS_IP`
2. Check SSH key is correct: `gh secret list`
3. Ensure firewall allows SSH: `sudo ufw status`
4. Verify SSH service is running: `sudo systemctl status sshd`

#### Permission Denied
```
Error: Permission denied (publickey)
```

**Solution:**
1. Check SSH key format (should start with `-----BEGIN OPENSSH PRIVATE KEY-----`)
2. Verify key permissions locally: `chmod 600 ~/.ssh/vps_deploy_key`
3. Re-add key to GitHub secrets without extra newlines
4. Ensure authorized_keys on VPS has correct permissions: `chmod 600 ~/.ssh/authorized_keys`

#### Docker Command Not Found
```
Error: docker: command not found
```

**Solution:**
1. Ensure deploy user is in docker group:
   ```bash
   sudo usermod -aG docker deploy
   # Log out and back in
   ```
2. Verify Docker installation: `which docker`
3. Check PATH includes Docker: `echo $PATH`

### Build Failures

#### Package Installation Failed
```
Error: npm ERR! code ENOENT
```

**Solution:**
1. Ensure package.json and package-lock.json are committed
2. Clear Docker cache: `docker system prune -a`
3. Check Node version compatibility
4. Try building locally first

#### Out of Disk Space
```
Error: no space left on device
```

**Solution:**
1. Check disk usage: `df -h`
2. Clean Docker:
   ```bash
   docker system prune -a
   docker volume prune
   ```
3. Remove old logs: `sudo journalctl --vacuum-time=7d`
4. Check persistent data usage: `du -sh /persistent/*`

## Runtime Issues

### Service Won't Start

#### Port Already in Use
```
Error: bind: address already in use
```

**Solution:**
1. Find process using port: `sudo lsof -i :3000`
2. Stop conflicting service: `docker ps`
3. Use different port in docker-compose.yml
4. Check for duplicate services

#### Health Check Failing
```
Error: container is unhealthy
```

**Solution:**
1. Check health endpoint: `curl localhost:3000/health`
2. View container logs: `docker logs myapp`
3. Exec into container: `docker exec -it myapp sh`
4. Verify environment variables: `docker exec myapp env`
5. Increase health check timeout/retries

#### Memory Limits Exceeded
```
Error: Container killed due to memory limit
```

**Solution:**
1. Check current usage: `docker stats`
2. Increase limits in docker-compose.yml:
   ```yaml
   deploy:
     resources:
       limits:
         memory: 1024M  # Increase this
   ```
3. Optimize application memory usage
4. Check for memory leaks

### Network Issues

#### Traefik Not Routing
```
Error: 404 page not found
```

**Solution:**
1. Check Traefik dashboard: `http://YOUR_VPS_IP:8080`
2. Verify labels in docker-compose.yml
3. Ensure service is on public network:
   ```bash
   docker network ls
   docker inspect myapp | grep -A 5 Networks
   ```
4. Check Traefik logs: `docker logs traefik`

#### SSL Certificate Issues
```
Error: SSL_ERROR_INTERNAL_ERROR_ALERT
```

**Solution:**
1. Check ACME configuration in traefik.yml
2. Verify domain DNS points to VPS
3. Check certificate storage:
   ```bash
   ls -la /persistent/traefik/acme.json
   cat /persistent/traefik/acme.json | jq .
   ```
4. Wait for rate limits (Let's Encrypt: 5 failures/hour)
5. Use staging environment for testing

#### Container Can't Reach Internet
```
Error: getaddrinfo ENOTFOUND
```

**Solution:**
1. Check Docker DNS: `docker exec myapp nslookup google.com`
2. Restart Docker daemon: `sudo systemctl restart docker`
3. Check firewall rules: `sudo iptables -L`
4. Verify Docker network: `docker network inspect bridge`

## Database Issues

### Connection Refused
```
Error: connect ECONNREFUSED 127.0.0.1:5432
```

**Solution:**
1. Use service name, not localhost: `postgresql://user:pass@db:5432/myapp`
2. Check service is running: `docker ps`
3. Verify network connectivity: `docker exec app ping db`
4. Check database logs: `docker logs myapp-db`

### Data Loss After Deploy
```
Error: relation "users" does not exist
```

**Solution:**
1. Ensure volumes are mounted correctly:
   ```yaml
   volumes:
     - /persistent/myapp/postgres:/var/lib/postgresql/data
   ```
2. Check volume exists: `ls /persistent/myapp/`
3. Never mount to `/apps/` directory (replaced on deploy)
4. Run migrations after deploy

## Debugging Techniques

### Container Inspection

```bash
# View all container details
docker inspect myapp

# Check environment variables
docker exec myapp env

# View running processes
docker exec myapp ps aux

# Check file system
docker exec myapp ls -la /app

# Interactive shell
docker exec -it myapp sh
```

### Log Analysis

```bash
# View logs with timestamps
docker logs -t myapp

# Follow logs
docker logs -f myapp

# Last 100 lines
docker logs --tail 100 myapp

# Logs since 1 hour ago
docker logs --since 1h myapp

# Save logs to file
docker logs myapp > myapp.log 2>&1
```

### Network Debugging

```bash
# Test internal connectivity
docker exec myapp ping db
docker exec myapp wget -O- http://other-service:3000/health

# Check exposed ports
docker port myapp

# Inspect network
docker network inspect myapp-network

# Test from host
curl -I http://localhost:3000
curl -I https://myapp.example.com
```

### Performance Analysis

```bash
# Real-time stats
docker stats

# Check resource limits
docker inspect myapp | jq '.[0].HostConfig.Resources'

# System resources
htop
df -h
free -h

# Docker disk usage
docker system df
```

## Common Fixes

### Reset Everything

```bash
# Stop all containers
docker compose down

# Remove all containers and networks
docker system prune -a

# Rebuild from scratch
docker compose build --no-cache
docker compose up -d
```

### Fix Permissions

```bash
# Fix directory ownership
sudo chown -R deploy:deploy /apps /persistent /logs

# Fix Docker socket permissions
sudo chmod 666 /var/run/docker.sock

# Fix SSH key permissions
chmod 700 ~/.ssh
chmod 600 ~/.ssh/authorized_keys
chmod 600 ~/.ssh/vps_deploy_key
```

### Emergency Recovery

```bash
# If Traefik is down
docker run -d -p 80:80 -p 443:443 \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v /persistent/traefik:/persistent/traefik \
  --name traefik-temp \
  traefik:v3.0

# Run app without compose
docker run -d -p 3000:3000 \
  -e NODE_ENV=production \
  --name myapp-temp \
  myapp:last-known-good-sha

# Restore from backup (if available)
rsync -av backup/ /persistent/myapp/
```

## Bootstrap Script Issues

### SSH Password Authentication Not Working
After running the bootstrap script, password authentication may not work.

**Cause:**
1. Many VPS providers (DigitalOcean, Vultr, Linode, etc.) disable password authentication by default when provisioning servers with SSH keys.
2. The SSH service itself may be disabled.
3. Cloud-init creates override files that set `PermitRootLogin without-password` (allows only SSH key login for root).

**Solution:**
```bash
# Check current SSH settings
sudo sshd -T | grep -E "permitrootlogin|passwordauthentication"

# If you see "permitrootlogin without-password", that's the issue!
# Remove cloud-init override
sudo rm -f /etc/ssh/sshd_config.d/50-cloud-init.conf

# Create proper override file
sudo tee /etc/ssh/sshd_config.d/99-enable-passwords.conf > /dev/null <<EOF
PermitRootLogin yes
PasswordAuthentication yes
PubkeyAuthentication yes
EOF

# Restart SSH service
sudo systemctl restart ssh  # Ubuntu/Debian
# or
sudo systemctl restart sshd  # RHEL/CentOS

# Verify the fix
sudo sshd -T | grep permitrootlogin  # Should show "permitrootlogin yes"
```

**Understanding PermitRootLogin Values:**
- `yes` - Root can login with password OR SSH keys
- `without-password` or `prohibit-password` - Root can ONLY login with SSH keys (no passwords)
- `no` - Root cannot login at all

Note: The updated bootstrap script now handles this automatically by removing cloud-init overrides.

### SSH Service Not Found
```
Error: Failed to restart sshd.service: Unit sshd.service not found
```

**Solution:**
The bootstrap script now handles this automatically, but if you encounter this:
- On Ubuntu/Debian: The service is called `ssh` not `sshd`
- On RHEL/CentOS: The service is called `sshd`
- Manual restart: `sudo systemctl restart ssh` (Ubuntu) or `sudo systemctl restart sshd` (RHEL)

### Script Exits Immediately
If the bootstrap script exits without doing anything:

**Solution:**
1. Make sure you're running with sudo
2. If piping through curl, provide required parameters:
   ```bash
   curl -sSL ... | sudo bash -s -- --email your@email.com --domain example.com
   ```
3. Or download first for interactive mode:
   ```bash
   curl -sSL ... -o bootstrap.sh
   sudo bash bootstrap.sh
   ```

## Getting Help

### Collect Diagnostic Information

```bash
# System info
uname -a
cat /etc/os-release
docker version
docker compose version

# Service status
docker ps -a
docker compose ps

# Recent logs
docker logs --tail 100 myapp
docker logs --tail 100 traefik

# Network status
docker network ls
ip addr show

# Disk usage
df -h
du -sh /apps/* /persistent/*
```

### Where to Get Help

1. Check container logs first
2. Search error messages
3. Review configuration files
4. Test locally with same Docker setup
5. Check GitHub Actions logs
6. Use Docker documentation
7. Ask in Docker/DevOps communities

## Prevention

1. **Test locally before deploying**
2. **Monitor resource usage**
3. **Set up alerts for failures**
4. **Keep backups of persistent data**
5. **Document custom configurations**
6. **Use health checks effectively**
7. **Plan for graceful degradation**
