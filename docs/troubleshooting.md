# Troubleshooting

## Service Will Not Start

```bash
sudo systemctl status myapp.service
sudo journalctl -u myapp.service -n 100 --no-pager
```

Check that `/apps/myapp/bin/start` exists and is executable.

## Health Check Fails

```bash
curl -v http://127.0.0.1:3000/health
```

Verify `APP_PORT` in `/apps/myapp/.env` matches the systemd/Caddy configuration.

## Caddy Does Not Route

```bash
sudo caddy validate --config /etc/caddy/Caddyfile
sudo systemctl reload caddy
sudo journalctl -u caddy -n 100 --no-pager
```

Check the service route at `/etc/caddy/apps/myapp.caddy` and confirm DNS points to the VPS.

## HTTPS Certificate Problems

- Confirm ports `80` and `443` are reachable from the internet.
- Confirm DNS resolves to the VPS.
- Check Caddy logs with `journalctl -u caddy`.

## Deployment Failed

Open the service repo's GitHub Actions logs. The generated workflow shows the failing phase: copy files, create `.env`, run `make deploy-prepare`, restart systemd, local health check, or public HTTPS check.
