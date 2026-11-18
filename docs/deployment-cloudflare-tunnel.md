# Cloudflare Tunnel deployment

The tunnel exposes the MCP without opening any port on the host: `cloudflared` connects outbound
to Cloudflare, and traffic returns to the container over the stack's network.

## How it looks

```
MCP client ──HTTPS──▶ Cloudflare (TLS, WAF, Access) ──▶ cloudflared
                                                               │ stack network
                                                               ▼
                                                       mcp (8765)
```

The container publishes nothing reachable from the Internet. `cloudflared` reaches it by service name, inside the Compose network (`http://mcp:8765`). The port the base Compose file publishes stays at `127.0.0.1`, which is loopback on the host.

## 1. Create the tunnel

In the Cloudflare dashboard, **Networking → Tunnels → Create a tunnel**. Give it a name and choose the Docker run option. The dashboard provides a command with a token; that token goes in `CLOUDFLARE_TUNNEL_TOKEN`.

It is a **remotely managed** tunnel: the route configuration lives in the dashboard, not in a file inside the container. That is what allows you to deploy it without touching any files.

## 2. The published route

**Tunnel → your tunnel → Routes → Add route → Published application**.

- **Subdomain and domain**: the public hostname, for example `mcp.example.com`.
- **Service URL**: `http://mcp:8765`.

The Service URL is the service name on the Compose network, not `127.0.0.1`: inside the `cloudflared` container, loopback is its own.

The tunnel publishes a single hostname. The three MCP routes hang off it:

```
https://mcp.example.com/mcp                   -> the guide: the route catalog
https://mcp.example.com/mcp/corp.example.com  -> the accounts of one domain
https://mcp.example.com/mcp/ada@example.com   -> one account
```

You don't need a tunnel route for each account: the server decides the subpath, not Cloudflare.

**The dashboard does not go through the tunnel.** It lives on port 8766 of the container, and its port is exposed on loopback. Publishing it on the same hostname would open the dashboard to anyone who passes the Access filter, and the dashboard can see the accounts' passwords. If you need to reach the dashboard from outside, mount it on another hostname with its own Access policy, or connect through an SSH tunnel.

## 3. The variables

In the Portainer stack variables:

```bash
# The public hostname. It has to match the route above.
MCP_PUBLIC_HOST=mcp.example.com

# The panel token.
CLOUDFLARE_TUNNEL_TOKEN=eyJhIjoiXXXX...
```

Accounts are created from the dashboard, not through variables: create a domain, create the account inside it, and copy the token that is generated.

`MCP_PUBLIC_HOST` is not optional in this scenario, and it is not cosmetic:

- `cloudflared` forwards the client's original `Host` header. The MCP transport validates it against `allowed_hosts`. If `MCP_PUBLIC_HOST` is not the public hostname, the response is **421 Misdirected Request**.
- The origin `https://mcp.example.com` must be in `allowed_origins`. `MCP_PUBLIC_HOST` adds it automatically. If you replace it with `MCP_ALLOWED_ORIGINS`, include the origin with its scheme.

If you need more hosts, define them explicitly:

```bash
MCP_ALLOWED_HOSTS=mcp.example.com,mcp.example.com:*,127.0.0.1:*
MCP_ALLOWED_ORIGINS=https://mcp.example.com,http://127.0.0.1:*
```

A `Host` that is not allowed responds with 421. A `Origin` that is not allowed responds with 403.

## 4. Deploy

In Portainer, for the Git stack, use **Additional paths** → add `docker-compose.tunnel.yml`. It has the same semantics as two `-f` files:

```bash
docker compose -f docker-compose.yml -f docker-compose.tunnel.yml up -d --build
```

The overlay adds the `cloudflared` service with the token from the environment. The base Compose file does not change.

**Do not add `docker-compose.proxy.yml` or Caddy.** TLS is terminated by Cloudflare's edge, and `cloudflared` speaks plain HTTP with the container over the Compose network. Adding Caddy would introduce a second TLS terminator and one more open port without any gain.

The port that the base Compose file publishes on `127.0.0.1:8765` is harmless: it's loopback and is useful for debugging with `curl` from the host. If you prefer that it not exist at all, remove the `ports:` block from the `mcp` service in `docker-compose.yml`.

Containers get fixed names: `mailproxy-mcp` and `mailproxy-mcp-cloudflared`.

### The Host header

Cloudflare Tunnel forwards the client's **original `Host` header**, that is, the public hostname (`mcp.example.com`). The MCP transport validates that header against `allowed_hosts` and, if it isn't there, responds with **421**.

That is why `MCP_PUBLIC_HOST` must be the public hostname:

```bash
MCP_PUBLIC_HOST=mcp.example.com
```

And that is why **`MCP_ALLOWED_HOSTS` must not replace it with a list that does not include the domain**. If you define it, the explicit list takes precedence over the derived one:

```bash
# WRONG: the domain is left out and everything arriving through the tunnel gets a 421
MCP_ALLOWED_HOSTS=127.0.0.1:*,localhost:*

# RIGHT: it includes the domain
MCP_ALLOWED_HOSTS=mcp.example.com,mcp.example.com:*
```

Leaving `MCP_ALLOWED_HOSTS` unset is the simplest option. With `MCP_PUBLIC_HOST`,
the server builds the list automatically from the domain, its port-qualified
form, and the loopback hosts.

If something goes wrong, the server reports it at startup:

```
WARNING  MCP_PUBLIC_HOST (mcp.example.com) is not in allowed_hosts
         (127.0.0.1:*, localhost:*). Requests with that Host header
         will receive a 421. MCP_ALLOWED_HOSTS replaces the list derived from
         MCP_PUBLIC_HOST: include the domain or remove the variable.
INFO     Hosts permitidos: 127.0.0.1:*, localhost:*.
```

If the client receives a 421, the response points to the setting to check.
The SDK's default message only says "Invalid Host header".

The same applies to origins. `MCP_ALLOWED_ORIGINS` replaces the derived list.
`MCP_PUBLIC_HOST` adds only `https://mcp.example.com`, which the browser-based
Inspector needs.

## 5. Verify the tunnel

```bash
# The tunnel is connected
docker compose logs cloudflared

# The MCP server answers through the tunnel
curl -i https://mcp.example.com/mcp \
  -H "Authorization: Bearer $MCP_BEARER_TOKEN" \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'

# And with a single account, with that account's credential
curl -i https://mcp.example.com/mcp/ada@example.com \
  -H "Authorization: Bearer $BEARER_DE_LA_CUENTA" \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

Check the startup lines in the container logs:

```
INFO     Servidor listo: 2 cuentas, escucha 0.0.0.0:8765, escritura=apagada
INFO     Configuración: variables de entorno. Cuentas: ada@example.com, luis@example.com
```

If `curl` returns **421**, `MCP_PUBLIC_HOST` does not match the public hostname.
If it returns **403**, the origin is missing from `MCP_ALLOWED_ORIGINS`.
If it returns **401**, the token does not match the one configured in the stack.

## 6. Cloudflare Access (optional)

Access adds a layer in front of Bearer authentication. Cloudflare's edge
decides who can connect using rules based on IP address, email, or identity.

Use a **Service Token** for an automated agent:

1. In the dashboard, go to **Access → Applications → Add an application** and
   choose *Self-hosted*, with `mcp.example.com` as the hostname.
2. In the policy, choose **Service Token** and create a token instead of
   selecting an email address or group.
3. The MCP client must send both Service Token headers along with the
   Bearer header:

   ```
   CF-Access-Client-Id: <id>.access
   CF-Access-Client-Secret: <secreto>
   Authorization: Bearer <MCP_BEARER_TOKEN>
   ```

   Configure the headers in the MCP client. Most clients accept additional
   headers. If yours supports only `Authorization`, place a small proxy in
   front of it or use Bearer authentication without Access.

Without Access, the endpoint is public and the MCP Bearer token is its only
secret. A token with 48 random bytes provides strong authentication. Edge
access logs, IP lists, and rate limits require separate configuration.

**Access and per-account routes serve different purposes.** Access determines
whether a request reaches the server. The route determines which mailboxes the
client can see. You can use both together: an Access Service Token for the
server and per-account tokens so each agent sees only its own mailbox. A
Service Token alone cannot restrict access to a particular account. A client
that passes the Access policy without an account token sees the full route
catalog, and the global bearer grants access to every account.

## 7. Configure edge protections

The tunnel does not inherit the example nginx rate limit
(`deploy/nginx-mcp.conf`, 60 requests per minute per IP). If you use Access,
configure the policy there. Otherwise use Cloudflare's WAF at the edge:

- **Rate limiting** per IP on the tunnel route.
- **WAF rules** to block request patterns, including token brute-force attempts.
- **Bot Fight Mode** or an equivalent if all legitimate traffic comes from one
  client.

## 8. Troubleshooting

| Symptom | Probable cause |
| --- | --- |
| `421 Misdirected Request` | `MCP_PUBLIC_HOST` does not match the public hostname. |
| `403 Forbidden` | `Origin` is missing from `MCP_ALLOWED_ORIGINS`. |
| `401 Unauthorized` | The client token does not match the stack token. |
| `530` or `502` at the edge | The tunnel is disconnected or the Service URL does not resolve. |
| The tunnel connects but cannot reach the MCP server | `cloudflared` and `mcp` are on different Compose networks. |
| `timeout` instead of a response | `CLOUDFLARE_TUNNEL_PROTOCOL=quic` is set and the network blocks UDP. Try `http2`. |

## 9. Rotate the token

The MCP token is stored in the stack variables. Edit `MCP_BEARER_TOKEN`,
select **Pull and redeploy**, and update the client. The `audit` volume and
the other secrets are preserved.

To rotate the tunnel token, generate a new one in the Cloudflare dashboard,
change `CLOUDFLARE_TUNNEL_TOKEN`, and redeploy.
