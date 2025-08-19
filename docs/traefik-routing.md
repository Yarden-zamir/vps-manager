## Traefik routes and labels (how your service is exposed)

This repo uses Traefik to publish your containers on HTTPS without exposing container ports directly. You control routing entirely with Docker labels on each service.

### Core concepts (mental model)

- **Entrypoints**: Host ports Traefik listens on. In this repo: `web` (:80) and `websecure` (:443).
- **Routers**: Match incoming requests (by Host/Path/etc.) on an entrypoint and send them to a service. Optional middlewares can run in between.
- **Middlewares**: Filters/modifiers (e.g., redirect HTTP→HTTPS, auth, headers).
- **Services**: Where Traefik forwards requests inside Docker (your container’s internal port).

### What the template sets for you

In `template/docker-compose.yml` under your app service:

```yaml
labels:
  # Enable Traefik and pick the Docker network exposed to Traefik
  - "traefik.enable=true"
  - "traefik.docker.network=public"

  # HTTP router: serve your domain on port 80 and redirect to HTTPS
  - "traefik.http.routers.${APP_NAME}.rule=Host(`${APP_DOMAIN}`)"
  - "traefik.http.routers.${APP_NAME}.entrypoints=web"
  - "traefik.http.routers.${APP_NAME}.middlewares=${APP_NAME}-redirect"

  # HTTPS router: same domain on port 443 with TLS
  - "traefik.http.routers.${APP_NAME}-secure.rule=Host(`${APP_DOMAIN}`)"
  - "traefik.http.routers.${APP_NAME}-secure.entrypoints=websecure"
  - "traefik.http.routers.${APP_NAME}-secure.tls=true"
  - "traefik.http.routers.${APP_NAME}-secure.tls.certresolver=letsencrypt"

  # Middleware used by the HTTP router to force HTTPS
  - "traefik.http.middlewares.${APP_NAME}-redirect.redirectscheme.scheme=https"
  - "traefik.http.middlewares.${APP_NAME}-redirect.redirectscheme.permanent=true"

  # Which internal container port to forward to
  - "traefik.http.services.${APP_NAME}.loadbalancer.server.port=3000"
```

Notes:
- Traefik binds host ports 80/443 in `traefik/docker-compose.yml`.
- Your app is not published via `ports:` mapping; Traefik is the only ingress.

### Changing your app’s internal port

If your container listens on a different port (e.g., 8080):

```yaml
labels:
  - "traefik.http.services.${APP_NAME}.loadbalancer.server.port=8080"
healthcheck:
  test: ["CMD", "wget", "--no-verbose", "--tries=1", "--spider", "http://localhost:8080/health"]
```

Also update your app to listen on that port.

### Multiple routes (domains and paths)

Add additional routers for extra domains or paths. Examples:

```yaml
# Additional domain on HTTPS
- "traefik.http.routers.${APP_NAME}-alt.rule=Host(`alt.${APP_DOMAIN}`)"
- "traefik.http.routers.${APP_NAME}-alt.entrypoints=websecure"
- "traefik.http.routers.${APP_NAME}-alt.tls=true"

# Admin UI under a path prefix
- "traefik.http.routers.${APP_NAME}-admin.rule=Host(`${APP_DOMAIN}`) && PathPrefix(`/admin`)"
- "traefik.http.routers.${APP_NAME}-admin.entrypoints=websecure"
- "traefik.http.routers.${APP_NAME}-admin.tls=true"
```

All these routers can target the same service (the default when you don’t set `service=` on the router), or you can point to a different named service if your container exposes multiple internal ports.

### Adding basic auth (example)

Quick label-based auth for a protected route:

```yaml
# Create a middleware named `${APP_NAME}-auth` with one or more users
- "traefik.http.middlewares.${APP_NAME}-auth.basicauth.users=admin:$apr1$3c..."

# Attach it to a router
- "traefik.http.routers.${APP_NAME}-admin.middlewares=${APP_NAME}-auth"
```

Tip: Generate hashes with `htpasswd -nb admin 'your-password'`.

### Security headers via dynamic file

Place YAML under `/persistent/traefik/config/*.yml`, for example `/persistent/traefik/config/security-headers.yml`:

```yaml
http:
  middlewares:
    security-headers:
      headers:
        stsSeconds: 31536000
        stsIncludeSubdomains: true
        stsPreload: true
        frameDeny: true
```

Then reference it:

```yaml
- "traefik.http.routers.${APP_NAME}-secure.middlewares=security-headers@file"
```

### Non-HTTP services (TCP/UDP)

For raw TCP (e.g., Postgres), define an entrypoint in Traefik and route with TCP labels:

1) In `traefik/traefik.yml`, add an entrypoint and map the host port in `traefik/docker-compose.yml`:

```yaml
entryPoints:
  postgres:
    address: ":5432"
```

2) On your service, add TCP labels:

```yaml
labels:
  - "traefik.tcp.routers.${APP_NAME}-pg.rule=HostSNI(`*`)"
  - "traefik.tcp.routers.${APP_NAME}-pg.entrypoints=postgres"
  - "traefik.tcp.services.${APP_NAME}-pg.loadbalancer.server.port=5432"
```

UDP works similarly with UDP entrypoints/services.

### DNS, TLS and certificates

- Make sure the domain(s) in your router rules resolve to your VPS IP.
- Traefik handles TLS via Let’s Encrypt (see `traefik/traefik.yml`).
- For production certificates, ensure the staging `caServer` is commented out.
- The ACME store lives at `/persistent/traefik/acme.json` (chmod 600).

### Common gotchas

- The app must join the `public` Docker network and set `traefik.docker.network=public`.
- The internal port label must match the port your app actually listens on.
- If you reconfigured TLS/ACME, recreate `/persistent/traefik/acme.json` and restart Traefik.
- Check logs with `docker logs traefik` and the service logs if routing fails.

### References

- Traefik docs: routers, services, middlewares (`https://doc.traefik.io/traefik/`)
- Example labels used in this repo live in `template/docker-compose.yml`.


