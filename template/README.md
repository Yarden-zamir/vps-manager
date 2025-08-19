# Service Template

This is a template for creating new services that deploy to your VPS.

## Quick Start

1. Copy this template to create your new service
2. Update `APP_NAME` in the files to match your service name
3. Modify the application code in `src/`
4. Set up GitHub repository secrets and variables
5. Push to main branch to deploy!

## Required GitHub Secrets

Set these in your repository settings under Secrets and Variables > Actions:

### Secrets:
- `VPS_HOST` - Your VPS IP address or hostname
- `VPS_USER` - Service user (e.g., `svc-myapp`)
- `VPS_PASSWORD` - Service user password (generated during creation)

### Variables:
- `APP_DOMAIN` - Your app's domain (e.g., `myapp.example.com`)
- `APP_PORT` - Internal port (usually `3000`)

## Customization

### Application Type

This template is set up for Node.js. To use a different stack:

1. Replace `Dockerfile` with appropriate base image
2. Update `docker-compose.yml` health check
3. Replace `src/` with your application code
4. Ensure you have a `/health` endpoint

### Environment Variables

1. Copy `env.example` to `.env` for local development
2. Add production secrets to GitHub Secrets
3. Update `.github/workflows/deploy.yml` to include your secrets

### Resource Limits

Adjust CPU and memory limits in `docker-compose.yml`:

```yaml
deploy:
  resources:
    limits:
      cpus: '1.0'
      memory: 512M
```

## Development

```bash
# Install dependencies
npm install

# Run locally
npm run dev

# Build
npm run build

# Run with Docker
docker compose up --build
```

## Health Check

Your application MUST expose a `/health` endpoint that returns HTTP 200 when healthy.
