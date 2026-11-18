# Security checklist

Done in the code:

- Bearer is required and is compared against `hmac.compare_digest` over the SHA-256 of the token. Without a token, the process does not start. `/mcp` without a Bearer returns 401.
- Per-account credentials, managed in the panel, grant access to a single account and only through its route. On `/mcp` or on another account's route they return 403. They cannot match the global bearer and cannot be reused.
- Route scope is enforced at a single point (`MailService._account`), so a tool cannot touch an account outside its route.
- Account passwords are stored encrypted in the database; the encryption key is kept outside it. `.gitignore` excludes `.env` and `audit.jsonl`.
- A misspelled global switch aborts startup instead of silently staying off.
- `Account.password` and `Account.bearer` with `repr=False`. Errors the model sees do not include the key or the raw IMAP or SMTP text.
- Reading: `EXAMINE`, `BODY.PEEK[]`, a type allowlist and size caps. The read proxy rejects write commands.
- Writing is globally disabled by default. Accounts inherit this unless the panel sets a more restrictive permission. With the global switch off, the tool is not registered.
- Sending and deleting require a single-use `confirmation_id` valid for 10 minutes, bound to the account and the operation. Permanent deletion is a parameter of the preparation step and travels inside the `confirmation_id`. Marking is direct and is audited.
- Daily quota, maximum number of recipients, optional domains, a cap on UIDs per delete or mark operation, and an attachment size limit.
- JSONL audit of every action, without bodies, without `confirmation_id` and without credentials. If the audit cannot be written, there is no effect on the mailbox.
- MCP surface field names must not look like credentials (`tests/test_nombres_de_campos.py`). Some platforms mask response fields by name and hand the model the masked value: with a field named `confirm_token`, the agent received `***REDACTED***` and could not complete the send. The `confirmation_id` is not a credential (without the account's bearer it is useless), and its value carries a prefix that does not make it look like any provider's key.
- A `confirmation_id` that arrives masked produces an error that says so, instead of "unknown or already used": the agent needs to know the value never arrived and that the operation must be prepared again.
- Everything that is written and can be read back returns how to find it: sending returns `message_id`, `sent_uid` and `sent_folder`, and drafting returns `message_id` and `draft_uid`. Without these, verifying a write forces guessing the folder and search criteria.
- Server instructions: email is not trusted, and `send_message` / `delete_message` only run after an explicit instruction in the conversation.
- The two-step flow is described in three layers, so the agent does not rely on just one: the server instructions, each tool's description, and the preparation response. The response carries `status: "prepared"`, `sent: false` and `next_tool`, so the state does not have to be inferred from text. Preparing does not send or delete: `prepare_send` and `prepare_delete` have no effect on the mailbox.
- A single worker. The `confirmation_id` and the quota do not leave the process.
- DNS rebinding: `allowed_hosts` and `allowed_origins`. In Docker, `MCP_PUBLIC_HOST` or the `MCP_ALLOWED_*` lists set them to the public domain.
- Listens by default on `127.0.0.1`. In the container, `0.0.0.0` only with `MCP_ALLOW_NONLOCAL_BIND=1`, and the compose file publishes `127.0.0.1:8765`.
- Image without a token or passwords. Non-root `mcp` user, read-only root filesystem, `cap_drop: ALL` and `no-new-privileges`. `GET /health` does not require a token and does not return mailbox data.

- The panel is a separate surface with its own credential (`MCP_DASHBOARD_TOKEN`), which must be different from the MCP bearer. The MCP token does not open the panel, and the panel's token does not open `/mcp`.
- Listens on `127.0.0.1`, and its port is published on loopback. The panel can see account passwords: publishing it openly is a decision that must be deliberate.
- The session is an HMAC-signed cookie, `HttpOnly` and `SameSite=Strict`, with an expiry. Requests that change something require the `X-MCP-Dashboard` header, which a form from another site cannot set.
- Account passwords are encrypted with AES-GCM and a key that is **not** in the database (`MCP_DASHBOARD_KEY`). Startup checks that the key matches the database.
- The panel does not register tools and cannot read or write a mailbox. It only manages configuration and tests connections.
- The API never returns a password, and everything the panel does is audited without secrets.

Deployment checklist:

- Generate random tokens and an encryption key (`openssl rand -base64 48`).
  Set the environment file permissions to `0600` and store a copy of the
  encryption key separately from the database.
- Use an app password for the mailbox. Keep write access off until you
  explicitly enable it.
- Configure a TLS certificate, rate limits, and, if known, the client's
  outbound IP addresses at the proxy.
- Use a service user without a shell. Harden systemd or use the limits in the
  repository's Compose configuration, and rotate the JSONL audit log.
- Bind port 8765 to loopback only. Require Bearer authentication and TLS when
  making the service reachable remotely.
- Keep the dashboard port on loopback. If you need external access, place the
  dashboard behind Cloudflare Access.
- In Portainer, set server secrets under Environment variables and enter
  account passwords in the dashboard.
- Check in the mail client that `get_message` leaves `\Seen` unset.

## With Cloudflare Tunnel

- The tunnel does not inherit the example nginx rate limit. If Cloudflare
  Access is absent, configure rate limits and WAF rules at the edge.
- `MCP_PUBLIC_HOST` must be the public tunnel hostname. `cloudflared`
  forwards the client's `Host` header and the MCP transport validates it.
  A mismatch returns 421.
- Cloudflare Access with a Service Token adds a second layer. The client
  sends `CF-Access-Client-Id` and `CF-Access-Client-Secret` along with the Bearer
  header. An automated agent cannot authenticate on its own with an email- or
  group-based policy.
- The audit log records timestamps, tools, accounts, and a reduced set of
  arguments. For client IP addresses, use the Cloudflare access logs.

## What a container restart resets

The daily sending quota and `confirmation_id` values are held in memory
because the process runs a single worker. A restart, an out-of-memory
termination, or a redeploy resets them. The daily quota helps prevent
accidental overuse. Enforce a hard cap at the SMTP server or proxy.
