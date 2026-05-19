# Caddy Configuration

This directory documents the Caddy setup used by VPS Manager.

Bootstrap installs Caddy as a native system service and writes the main config to `/etc/caddy/Caddyfile`:

```caddyfile
{
    email admin@example.com
}

import /etc/caddy/apps/*.caddy
```

Each service gets its own route file under `/etc/caddy/apps/<service>.caddy`:

```caddyfile
app.example.com {
    encode zstd gzip
    reverse_proxy 127.0.0.1:3000
    log {
        output file /logs/caddy/app.access.log
    }
}
```

## Operations

```bash
# Validate config
caddy validate --config /etc/caddy/Caddyfile

# Reload routes
systemctl reload caddy

# View logs
journalctl -u caddy -f
```

## Notes

- Caddy manages HTTPS certificates automatically.
- Services should listen on localhost-only ports through systemd.
- DNS still needs to point the public hostname at the VPS.
