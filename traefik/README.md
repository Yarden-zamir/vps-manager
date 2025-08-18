# Traefik Configuration

This directory contains the Traefik reverse proxy configuration for the VPS.

## Setup

1. **Copy environment file**:
   ```bash
   cp env.example .env
   ```

2. **Edit `.env`** with your settings:
   - `DOMAIN`: Your base domain
   - `ACME_EMAIL`: Email for Let's Encrypt certificates

3. **Create required directories**:
   ```bash
   mkdir -p /persistent/traefik/config
   touch /persistent/traefik/acme.json
   chmod 600 /persistent/traefik/acme.json
   ```

4. **Start Traefik**:
   ```bash
   docker compose up -d
   ```

## Configuration Files

- `docker-compose.yml` - Docker Compose configuration
- `traefik.yml` - Static configuration (rarely changes)
- `env.example` - Environment variables template
- Dynamic configurations go in `/persistent/traefik/config/`

## Security

### Dashboard Access

The dashboard is exposed by default for initial setup. Secure it by:

1. **Basic Authentication**:
   ```bash
   # Generate password
   htpasswd -nb admin your-password
   
   # Add to docker-compose.yml labels
   - "traefik.http.middlewares.dashboard-auth.basicauth.users=admin:$$2y$$10$$..."
   ```

2. **IP Whitelisting**:
   ```yaml
   - "traefik.http.middlewares.dashboard-ipwhitelist.ipwhitelist.sourcerange=1.2.3.4/32"
   ```

3. **Remove Dashboard** (production):
   - Remove port 8080 from docker-compose.yml
   - Set `api.dashboard: false` in traefik.yml

## SSL Certificates

### Let's Encrypt Staging (Default)

The configuration uses Let's Encrypt staging by default to avoid rate limits during testing.

To switch to production certificates:
1. Edit `traefik.yml`
2. Comment out or remove the `caServer` line
3. Delete the staging certificates: `rm /persistent/traefik/acme.json`
4. Restart Traefik: `docker compose restart`

### Wildcard Certificates

To use wildcard certificates with DNS challenge:

1. Uncomment DNS challenge section in `traefik.yml`
2. Set your DNS provider and credentials
3. Update entry point TLS domains

## Custom Middleware

Create custom middleware in `/persistent/traefik/config/`:

```yaml
# /persistent/traefik/config/middleware.yml
http:
  middlewares:
    security-headers:
      headers:
        customResponseHeaders:
          X-Frame-Options: "DENY"
          X-Content-Type-Options: "nosniff"
          X-XSS-Protection: "1; mode=block"
```

## Monitoring

### Logs
- Traefik logs: `/logs/traefik/traefik.log`
- Access logs: `/logs/traefik/access.log`

### Metrics
Prometheus metrics available at `:8082/metrics`

### Health Check
```bash
curl http://localhost/ping
```

## Troubleshooting

### Certificate Issues
```bash
# Check ACME status
cat /persistent/traefik/acme.json | jq .

# Force certificate renewal
docker compose exec traefik rm /acme.json
docker compose restart traefik
```

### Routing Issues
1. Check service labels are correct
2. Verify service is on `public` network
3. Check Traefik logs: `docker logs traefik`
4. Visit dashboard (if enabled): `https://traefik.your-domain.com`

### Common Problems

**404 Not Found**
- Service not labeled with `traefik.enable=true`
- Wrong router rule (check Host)
- Service not on public network

**SSL Error**
- DNS not pointing to server
- Let's Encrypt rate limit hit
- Wrong email in configuration

**502 Bad Gateway**
- Service not running
- Wrong port in service configuration
- Health check failing
