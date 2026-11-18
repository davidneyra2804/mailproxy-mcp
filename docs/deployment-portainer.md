# Deployment with Portainer

The base stack runs the MCP, the dashboard, and the audit rotator. The dashboard
manages accounts in a persistent SQLite database; no accounts are defined in
the stack variables.

1. Copy `.env.example` and replace its three dummy secrets with independent values
   generated with `openssl rand -base64 48`. The key `MCP_DASHBOARD_KEY` encrypts the passwords: store it
   separately from the database.
2. In Portainer, create a stack from the repository and select
   `docker-compose.yml`. Load the variables file under **Environment
   variables → Load variables from .env file**.
3. To use Cloudflare Tunnel, add `docker-compose.tunnel.yml` as an
   **Additional path** and configure `CLOUDFLARE_TUNNEL_TOKEN` and
   `MCP_PUBLIC_HOST`. See [the tunnel guide](deployment-cloudflare-tunnel.md).
4. Deploy the stack. Keep the `data` volume: it contains the database.
   The `audit` volume contains the audit log.
5. Access the dashboard through a private channel at `127.0.0.1:8766`, log in
   with `MCP_DASHBOARD_TOKEN`, and create domains and accounts. Test the
   connection before saving and copy the token shown, which is displayed only once.

The MCP and dashboard ports are published on loopback by default. Do not
expose the dashboard directly to the Internet. To publish the MCP, use TLS or the
tunnel. The full options are in [configuration](configuration.md) and the
dashboard flow is in [dashboard](dashboard.md).
