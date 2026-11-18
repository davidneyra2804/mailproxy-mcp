# The control panel

A web panel for adding mail accounts without touching the deployment. It listens on **its own port**, separate from the MCP, and has its own credential.

Accounts are stored in a SQLite database. As soon as they exist, they are exposed at `/mcp`: **there is no need to restart anything**.

## What it is and what it is not

| | |
| --- | --- |
| Manages domains and accounts | Yes |
| Generates and rotates tokens | Yes |
| Tests an IMAP or SMTP connection before saving | Yes |
| Reads or writes a mailbox | **No** |

The panel does not register MCP tools, does not talk to the SDK, and cannot touch a mailbox. This boundary is intentional: an exposed panel must not be able to send email.

## Starting it

The panel and the database **are always present**: they are the way to manage accounts. There is no switch that turns them on.

Two secrets are mandatory:

```bash
MCP_DASHBOARD_KEY=la-clave-con-la-que-se-cifran-las-contrasenas
MCP_DASHBOARD_TOKEN=la-credencial-de-acceso-al-panel
```

If either one is missing, the process **does not start** and reports which one is missing. It does not start halfway.

The database path is `MCP_DASHBOARD_DB`, and by default it is `cuentas.db`, in the working directory. **Put it where it will persist**: in the container, on the data volume.

### In Docker

```yaml
environment:
  MCP_DASHBOARD_DB: /var/lib/mcp-correo/cuentas.db
volumes:
  - data:/var/lib/mcp-correo
```

The container is read-only: without that volume, the database cannot be written and startup fails. And without a volume, accounts are lost on every restart.

### The key

`MCP_DASHBOARD_KEY` encrypts account passwords with AES-GCM. **It is not stored in the database**: if it is lost, the saved passwords cannot be decrypted and must be entered again. Store it in the same place as the other secrets.

Startup checks that the key matches the database: if not, it stops and says so. Without this check, the symptom would be "the accounts don't work" and nobody would know whether the problem is the key or the IMAP server.

### The token

`MCP_DASHBOARD_TOKEN` is the panel's credential, and it must be different from `MCP_BEARER_TOKEN`. These are two surfaces with two credentials: the MCP token does not open the panel, and the panel token does not open `/mcp`.

## The accounts: where they live

The database is **the only source of accounts**. They are created, edited, and deleted from the panel; they are not imported from environment variables or files. A newly created database is empty until accounts are added in the panel.

## The interface

Access has its own screen: enter the **panel access key**, not the mailbox password. The technical configuration help is in a collapsible section.

When adding an account, you only need to type the **email address once**, its password and, optionally, the name recipients will see. The email address is used as the route identifier and as the connection user. The domain is selected automatically if it already exists, and you can change it manually.

Under **Advanced options** you can set a route alias, a label, or a different connection user, and your own servers. When editing, existing exceptions are kept; leaving the password empty keeps the current one.

Here are also the **write permissions**, with three values: *Inherit* (undecided, the domain decides and behind it the global switch), *Allow* and *Deny*. Domain permissions are set when editing the domain; account permissions, when editing the account. Each capability is set separately:

| Permission | Capability |
| --- | --- |
| `allow_send` | Send with confirmation (`prepare_send` + `send_message`). |
| `allow_mark` | Mark as read or unread. |
| `allow_delete` | Move to Trash or delete. |
| `allow_drafts` | Save drafts. |
| `allow_direct_send` | Send in a single call, without per-message confirmation. |

The panel is at `http://127.0.0.1:8766` (or wherever you publish it). You sign in with the token and a session is opened.

- **Domains** are listed as sections, each with its accounts.
- Each account shows its **route**, exactly as it is written: `/mcp/ada@corp.example.com`. This is what is passed to a client.
- Each account has two copy buttons: **Copy URL** copies the full MCP URL for that account to the clipboard, with the public host (`https://mcp.example.com/mcp/ada@corp.example.com`), and **Copy token** copies that account's current access token. Neither one renews the token: copying does not change anything. If the clipboard is not available, the panel warns you and shows the value so you can copy it by hand.
- A button marks a domain as **default**: it is the one that `/mcp` opens. Only one can be default.
- The **Token** button generates a new one for an account or a domain, and shows it **only once**.
- The **Test** button validates the IMAP connection with what is in the form, without saving anything. If something is wrong (the host, the port, SSL, the password), it shows up there and not when the agent tries to read the mailbox.
- An account can be **disabled** without being deleted: it stops being exposed, and its data remains in place.

### Cancel and the three-dot menu

Two details of the panel's behavior that should not be mistaken for a bug:

- **"Cancelar"** closes the dialog without saving anything and without asking about empty fields. "Guardar cambios" does validate them: an invalid email or password is an error, and nothing is saved. Cancel is the way out, so it cannot depend on the form being filled in.
- Each account's **three-dot menu** opens **in full**, even when the account is near the bottom edge of the panel. If it does not fit below, it opens upward. All of its entries (renew the key, disable, and delete) can be clicked.

### Checking it in a real browser

What a test cannot verify (that the modal really closes, that a menu is not clipped, that the keyboard reaches the controls) is checked by opening the panel in Chromium:

```bash
.venv/bin/pip install -r requirements-browser.txt
.venv/bin/playwright install chromium

MCP_PUBLIC_HOST=mcp.example.com \
  .venv/bin/python herramientas/comprobar_cuentas_navegador.py
```

It raises the panel over a fictitious base (RFC 2606 domains and dummy tokens) and checks the account modal and the three-dot menu. `herramientas/comprobar_panel_navegador.py` does the same with the theme and the copy buttons.

### Copying the URL and the token

The two copy buttons solve the step that is most annoying when configuring an MCP client: having to read the path from the screen, remember the public host, and look for the token somewhere.

- **Copiar URL** returns the full URL: scheme, public host, and the account's path. The host is that of `MCP_PUBLIC_HOST`, not the listening one: the client talks to the server from outside the tunnel.
- **Copiar token** returns the **current** token for that account, the same one that opens its path. It does not renew it: the operation is a read.

An account's token is stored in the database in plain text, just as it was before this button: the security model has not changed, only what was already there is read. The password is still encrypted with `MCP_DASHBOARD_KEY`.

What the panel **does not** do is display all the tokens at once: the domain list only says whether each account has a credential or not. An account's token is requested when someone copies it, and the request is recorded in the audit log (`dashboard_read_account_token`), with the value masked.

### Testing before saving

The test button opens a real connection, logs in, looks at the folders, and closes. It does not save anything, does not send anything, and leaves no trace in the mailbox.

It uses the same connection code as the rest of the server, so the message it outputs is the same one that would appear when reading the mailbox. And the password does not appear in the error message.

## The MCP routes

With accounts in the database, the server exposes three routes:

| Route | Scope |
| --- | --- |
| `/mcp` | The guide: the route catalog. And the default domain, if there is one. |
| `/mcp/<domain>` | The accounts of that domain. |
| `/mcp/<account>` | That account. |

The catalog is provided by `list_accounts`. An example:

```json
{
  "route": "/mcp",
  "scope": ["ada@corp.example.com"],
  "default_domain": "corp.example.com",
  "domains": [
    {"domain": "corp.example.com", "route": "/mcp/corp.example.com",
     "default": true, "accounts": ["ada@corp.example.com"]}
  ],
  "accounts": [
    {"account": "ada@corp.example.com", "route": "/mcp/ada@corp.example.com",
     "domain": "corp.example.com", "own_credential": true,
     "can_send": true, "can_mark": true, "can_delete": false, "can_draft": true,
     "can_send_direct": false}
  ]
}
```

The agent receives that list and knows where to go. The general route does **not** expose all mailboxes: to open one, it must be named.

## The tokens

There are three levels, and the most specific one takes precedence when presented:

| Level | Where it lives | Opens |
| --- | --- | --- |
| General | `MCP_BEARER_TOKEN` | All accounts |
| Domain | `domains.bearer` | The accounts of that domain |
| Account | `accounts.bearer` | That account |

The rule: **the credential must open the route**. An account's credential does not open a domain's route, even if the domain has only one account. A domain's credential does not open another domain's route.

The security model is **at the account level**: one account, one scope, one credential. The domain and general tokens are coverage upward, for whoever needs it.

### An account's effective token

The token the server accepts for an account is:

1. **its own**, if the account has its own credential;
2. **its domain's**, if it does not have one but its domain does.

The second rule is not a courtesy: the server opens an account's route with the credential of the domain it belongs to (`BearerAuth._permite` in `server.py`). That is why the panel can say that an account without its own credential "uses its domain's key" without being misleading.

If there is neither a token of its own nor a domain token, the account is opened only by the general bearer, and there is no token to copy.

The panel shows this with `credential_source` on each account in the list:

| `credential_source` | What it means |
| --- | --- |
| `cuenta` | The account has its own credential |
| `dominio` | It uses its domain's credential |
| `general` | There is no scoped credential: only the general one |

And the API that returns an account's current token is a read:

```
GET /api/accounts/{id}/credenciales
GET /api/accounts/{id}/credentials
```

Both routes are the same: same handler, same contract. The first is the panel's, in Spanish like the rest of the API; the second is the one used by the delivery of VYRA-33.

It returns `token`, `origen` and `has_token`, plus `name` and `url`: the full URL of the account's MCP is what gets pasted into a client. **It rotates nothing**: reading the current token does not invalidate the previous one. The value is not written to the audit log: the log only records the origin.

Renewing the token is a different operation, and it is separate:

```
POST /api/accounts/{id}/token
```

That one **rotates**: it generates a new token and invalidates the previous one. The copy button uses the read, never this one.

## The panel's theme

The panel can be shown in **light**, **dark**, or **system**. The choice is stored in the browser and survives a reload; with "system", the panel follows changes to the device's appearance without reloading.

The panel's colors are CSS variables (`--fondo`, `--texto`, `--borde`, `--acento`…). The light and dark themes only change the values of those variables: no rule sets a color directly. That way, switching theme leaves no part of the interface in the other theme's color.

The `data-tema` attribute on the `<html>` is either `claro` or `oscuro`. Under "system" it is **not** set: the `prefers-color-scheme` media query decides, which is why it can follow the device live.

## Permissions

The chain is the same as always, with one more level:

| | `MCP_ENABLE_SEND` | `allow_send` of the domain | `allow_send` of the account |
| --- | --- | --- | --- |
| 1 | `false` | whatever | whatever | **Off** |
| 2 | `true` | undefined | undefined | **On** |
| 3 | `true` | undefined | `false` | **Off** for that account |
| 4 | `true` | `false` | whatever | **Off** in the domain |

The global switch remains the master: off means nothing is allowed. The domain and the account are optional overrides.

### Direct sending

There is a second send permission, `allow_direct_send`, with its own global switch, `MCP_ENABLE_DIRECT_SEND`. It is independent of `allow_send`.

- **Sending with confirmation** (`allow_send`): `prepare_send` and then `send_message`. It requires an explicit order for each message.
- **Direct sending** (`allow_direct_send`): `send_message_direct` sends in a single call, with no per-message confirmation.

Direct sending exists for automated routines: an agent that extracts pending items from another system and sends the email without human intervention. The authorization is the one given in advance when it was enabled, and it is limited to the account (or domain) that has it permitted.

To prevent duplicate emails, the tool requires a `idempotency_key`: the same key with the same content does not send again. Use a stable key for each send, for example the identifier of the originating pending item.

If the SMTP server rejects the send, the key is released and the send can be retried. If the SMTP server does not respond, the email may have gone out: the key stays reserved in an uncertain state, and the server refuses to resend with it, so the message is not duplicated.

**Do not enable direct sending on an account that a person talks through.** Confirmation mode exists precisely for that case.

## Audit

Everything the panel does is recorded in the same JSONL file as the MCP tools, under its own names (`dashboard_add_account`, `dashboard_rotate_token`, `dashboard_test_imap`...). No bodies and no secrets: passwords and tokens are masked.

```bash
docker compose exec mcp python -c "print(open('/var/log/mcp-correo/audit.jsonl').read())"
```

## Exposing the panel

By default it listens on `127.0.0.1` and the compose file publishes the port on loopback. **The panel can see the passwords**: publishing it openly is a decision you need to mean.

If you do need to expose it, it's better behind Cloudflare Access than with the token alone.

## The database

A SQLite file, in WAL mode, with the passwords encrypted. The schema is versioned and migrations are applied at startup. The revision counter lives in the database, and it is what lets the server reload accounts without restarting: the panel writes, the server reads, and it notices.

To inspect it:

```bash
docker compose exec mcp python -c "import sqlite3; print(sqlite3.connect('/var/lib/mcp-correo/cuentas.db').execute('select id, name, is_default from domains').fetchall())"
```

The passwords are shown encrypted. On purpose.
