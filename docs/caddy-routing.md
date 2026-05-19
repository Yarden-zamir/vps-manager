# Caddy Routing

VPS Manager uses Caddy for all public HTTPS ingress.

## How Routes Are Created

`scripts/create-service.py` writes one Caddy file per service:

```text
/etc/caddy/apps/<service>.caddy
```

Example:

```caddyfile
myapp.example.com {
    encode zstd gzip
    reverse_proxy 127.0.0.1:3000
    log {
        output file /logs/caddy/myapp.access.log
    }
}
```

The main Caddyfile imports all service routes:

```caddyfile
import /etc/caddy/apps/*.caddy
```

## Service Contract

- The app listens on `APP_PORT`.
- Caddy proxies to `127.0.0.1:APP_PORT`.
- The app exposes `/health` for deployment verification.
- DNS points the public hostname at the VPS.

## Useful Commands

```bash
caddy validate --config /etc/caddy/Caddyfile
systemctl reload caddy
journalctl -u caddy -f
```
