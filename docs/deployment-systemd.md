# Deployment with systemd

The process listens on `127.0.0.1:8765`. A proxy on the same host terminates TLS and publishes HTTPS. It's best to use a different machine from the mail server, so you don't clash with the proxy that server regenerates.

Overview, on Debian 12 or Ubuntu 24.04. Replace `mcp.example.com` with the public name and `ada@corp.example.com` with your account. The token and passwords go in `/etc/mailproxy-mcp/env`, mode `0600`, and are not committed.

That `env` is a plain environment file, in the same format as the `.env`
of Portainer. You can generate it with the same `.env.example` from the repository,
removing the commented lines and changing the dummy values.

```bash
sudo apt update && sudo apt install -y python3-venv nginx certbot python3-certbot-nginx ufw git
sudo useradd --system --home /opt/mailproxy-mcp --shell /usr/sbin/nologin mcpmail
sudo git clone <repo-url> /opt/mailproxy-mcp
sudo python3 -m venv /opt/mailproxy-mcp/.venv
sudo /opt/mailproxy-mcp/.venv/bin/pip install -r /opt/mailproxy-mcp/requirements.txt
sudo chown -R root:mcpmail /opt/mailproxy-mcp && sudo chmod -R o-rwx /opt/mailproxy-mcp

sudo install -d -m 0750 -o root -g mcpmail /etc/mailproxy-mcp
sudo install -m 0600 -o root -g root /dev/null /etc/mailproxy-mcp/env
sudo install -d -m 0750 -o mcpmail -g mcpmail /var/log/mcp-correo
sudo install -d -m 0750 -o mcpmail -g mcpmail /var/lib/mcp-correo
# Edit /etc/mailproxy-mcp/env: MCP_BEARER_TOKEN, MCP_DASHBOARD_KEY,
# MCP_DASHBOARD_TOKEN and MCP_DASHBOARD_DB=/var/lib/mcp-correo/cuentas.db.
# After startup, create the domains and accounts from the panel.

sudo cp deploy/mailproxy-mcp.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now mailproxy-mcp
sudo cp deploy/nginx-mcp.conf /etc/nginx/conf.d/mcp.example.com.conf
sudo certbot --nginx -d mcp.example.com
sudo nginx -t && sudo systemctl reload nginx
sudo cp deploy/logrotate.conf /etc/logrotate.d/mailproxy-mcp
```

The variable contract is the same as for Docker and is described in
[configuration.md](configuration.md). The server configuration goes in the
`EnvironmentFile`; accounts are managed from the panel.

Watch out for `MCP_BIND_HOST` and `MCP_BIND_PORT` here: the unit sets the bind to loopback in its `ExecStart` and does not read them. Leave them unset, or set them to `127.0.0.1`
and `8765`. Setting `0.0.0.0` makes the process refuse to start, even though
nginx won't publish that port.

`deploy/mailproxy-mcp.service` runs as `mcpmail`, with no new privileges, with the filesystem read-only except for `/var/log/mcp-correo`, a 512 MiB limit, and a single worker. That `--workers 1` holds the `confirmation_id` and the daily quota, which are not shared between processes.

`deploy/nginx-mcp.conf` offers TLS 1.2+, limits requests to 60 per minute per IP, and proxies `/mcp` to `127.0.0.1:8765`. The example `server_name` is `mcp.example.com`. The commented IP `203.0.113.10` is a documentation address (TEST-NET, RFC 5737), not anyone's real address.

The `location` is a prefix (`location /mcp`), not an exact match, so that all three paths work: `/mcp`, `/mcp/<account>` and
`/mcp/<domain>`. With `proxy_pass` and no path part, nginx passes the path through unchanged. The panel (8766) is **not** proxied: it stays on loopback, behind an SSH tunnel or another filter.

`deploy/logrotate.conf` rotates `/var/log/mcp-correo/audit.jsonl` weekly, keeps 12 copies, and uses `copytruncate` because the systemd process keeps the descriptor open.

The firewall can restrict 22 to the admin IP, plus 80 and 443. Port 8765 is not published, and neither is 8766.

Connecting from the MCP client: URL `https://mcp.example.com/mcp` and header `Authorization: Bearer <token>`. For a specific mailbox, `https://mcp.example.com/mcp/ada@corp.example.com`.

Put the database in `/var/lib/mcp-correo` and add that path to
`ReadWritePaths` in the unit: with `ProtectSystem=strict`. Without it, the process cannot write the database.

The Docker alternative is described in [portainer-deployment.md](deployment-portainer.md). The two are not used at the same time on the same port.
