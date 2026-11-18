# Configuration

The server is configured through environment variables. Domains, accounts, passwords, and specific credentials are managed from the [panel](dashboard.md) and stored in SQLite. A new installation starts with no accounts.

## Required variables

| Variable | Use |
| --- | --- |
| `MCP_BEARER_TOKEN` | General MCP credential, minimum 16 characters. |
| `MCP_DASHBOARD_KEY` | Encryption key for passwords, minimum 16 characters. Store it separately from the database. |
| `MCP_DASHBOARD_TOKEN` | Panel credential, minimum 16 characters and different from the MCP bearer. |

Generate each secret independently with `openssl rand -base64 48`.
Without the encryption key, saved passwords cannot be recovered.

## Network and panel

| Variable | Default value | Use |
| --- | --- | --- |
| `MCP_PUBLIC_HOST` | `127.0.0.1` | Public host used to derive the allowed hosts and origins. |
| `MCP_ALLOWED_HOSTS` | derived | Comma-separated list that replaces the derived hosts. |
| `MCP_ALLOWED_ORIGINS` | derived | Comma-separated list that replaces the derived origins. |
| `MCP_BIND_HOST`, `MCP_BIND_PORT` | `127.0.0.1`, `8765` | MCP listen address; compose sets it inside the container. |
| `MCP_DASHBOARD_BIND_HOST`, `MCP_DASHBOARD_BIND_PORT` | `127.0.0.1`, `8766` | Panel listen address; compose sets it inside the container. |
| `MCP_ALLOW_NONLOCAL_BIND` | not set | `1` allows listening outside loopback. |
| `MCP_DASHBOARD_DB` | `cuentas.db` | SQLite path; compose uses `/var/lib/mcp-correo/cuentas.db` on the `data` volume. |
| `MCP_AUDIT_LOG` | `audit.jsonl` | Path of the audit JSONL file. |

Keep the panel on loopback or protect it with private access. The database must persist and be backed up together with a separate copy of the key.

## Permissions and limits

`MCP_ENABLE_SEND`, `MCP_ENABLE_MARK`, `MCP_ENABLE_DELETE`, `MCP_ENABLE_DRAFTS` and `MCP_ENABLE_DIRECT_SEND` are global switches, off by default. They only accept `true`, `false`, `1` and `0`. Domain and account permissions are configured in the panel and cannot bypass a global switch that is off.

`MCP_ENABLE_DIRECT_SEND` enables sending in a single call, without `confirmation_id` and without human confirmation for each message. It is meant for automated routines that already have authorization in advance. The per-account permission is `allow_direct_send` and is independent of `allow_send`: an account can have both, or only one.

| Variable | Default value |
| --- | --- |
| `MCP_MAX_RESULTS` | `100` |
| `MCP_MAX_CHARS` | `20000` |
| `MCP_MAX_ATTACHMENT_BYTES` | `5000000` |
| `MCP_MAX_MESSAGE_BYTES` | `15000000` |
| `MCP_IMAP_TIMEOUT` | `20` seconds |
| `MCP_SENT_SCAN_LIMIT` | `300` |
| `MCP_CONFIRM_TTL_SECONDS` | `600` |
| `MCP_MAX_RECIPIENTS` | `10` |
| `MCP_MAX_SENDS_PER_DAY` | `30` |
| `MCP_MAX_DELETE_PER_CALL` | `20` |
| `MCP_MAX_MARK_PER_CALL` | `50` |
| `MCP_SMTP_TIMEOUT` | `30` seconds |
| `MCP_SMTP_SECURITY` | `ssl`; also accepts `starttls` |
| `MCP_ALLOWED_RECIPIENT_DOMAINS` | empty: any domain; comma-separated list |
| `MCP_ALLOWED_ATTACHMENT_TYPES` | default MIME list; can be replaced with a comma-separated list |

## Tool arguments, also accepted as written text

Tool arguments can be sent in their typed form or written out, and the server accepts both forms:

| Argument | Forms |
| --- | --- |
| `uids` (`mark_read`, `mark_unread`, `prepare_delete`) | `[21055, 21051]`, `["21055", "21051"]`, `"[21055,21051]"`, `"21055,21051"`, `"21055"` |
| `uid`, `index`, `limit`, `max_chars` | `20` or `"20"` |
| `unseen`, `permanent` | `true`/`false` or `"true"`/`"false"`/`"1"`/`"0"` |
| `to`, `cc`, `bcc` | `["ana@example.com"]` or `"ana@example.com"` |
| `attachments` | `[{"filename": "nota.txt", ...}]` or its JSON text |

**Why it is needed.** The OpenMausBot MCP bridge, the one the mail team uses, validates each tool's arguments against the schema the server publishes, using Ajv **without coercion** (`server/mcp-schema-validator.ts` in `milind-soni/OpenMausBot`). An argument that arrives as text, either because the model wrote it as text or because the bridge converted it, is rejected there with "must be integer" or "must be boolean", and **the call never leaves the bridge**: the server never sees it. With the written forms, that call arrives and is carried out.

By the generic MCP route (`mcp_call_tool`) the bridge converts **every** argument that is not text to text: numbers, booleans, and also the numbers inside an array (`uids: [21055]` arrives as `["21055"]`, and the validator rejects it with «uids.0: must be integer»). That is why the schema declares both forms of each type, not only the textual form for numbers: a `unseen: true` that arrives as `"true"` must also pass the bridge's filter.

The bridge for connected apps does adjust types (`server/connector-arguments.ts`); the one for MCP tools does not. The root fix belongs to that bridge, not here: if the validator coerced, the server would receive the `20` as a number and this tolerance would not be needed. It is reported separately.

A value that cannot be understood is not discarded: it is rejected with an error that says what was received. A uid that gets lost is an email that the agent believed it had marked and that remains unmarked, and that is not visible.

## Docker and deployment

`.env.example` documents the Compose options, rotation, Cloudflare Tunnel, and Caddy. Copy the example to `.env` and replace the dummy secrets. The compose file publishes the MCP and the panel on loopback and mounts the volumes `data` and `audit`. For remote deployment, see [Portainer](deployment-portainer.md) and [Cloudflare Tunnel](deployment-cloudflare-tunnel.md).

---
mailproxy-mcp 2.4.0 | [Home](../README.md)
