# Security Considerations

This project favors simple VPS operations over hardened multi-tenant security.

## Defaults

- Services run as dedicated Unix users.
- Public HTTPS is terminated by Caddy.
- Service processes are supervised by systemd.
- Service deploy users get limited passwordless sudo for restarting and inspecting their own systemd unit.
- Bootstrap enables root/password SSH for convenience.

## Recommended Hardening

- Disable root/password SSH after initial setup if you do not need it.
- Restrict firewall access to ports `22`, `80`, and `443`.
- Add systemd limits such as `MemoryMax`, `CPUQuota`, and `NoNewPrivileges` to generated units.
- Keep DNS provider tokens scoped as narrowly as the provider allows.
