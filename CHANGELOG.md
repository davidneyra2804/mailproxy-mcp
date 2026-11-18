# Changelog

All notable changes to mailproxy-mcp.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
versioning follows [SemVer](https://semver.org/lang/en/).

## [Unpublished]

## [2.4.0] — 2026-11-17

The repository is named `mailproxy-mcp`. It used to be called `mcp-correo`, and the
name was in the wrong place: the project is not only about corporate email,
but an MCP server for mailboxes that is deployed as a mail proxy. With the
new name, the repository and the image say the same thing as the service they
give access to.

### Changed

- **The repository, the Python package, and the MCP server are named
  `mailproxy-mcp`.** The server name in the MCP handshake changes from
  `mcp-correo` to `mailproxy-mcp`. Clients that point to it by URL are not
  affected: the name is only forwarded in the `initialize`.

- **The image is published at a different GHCR path.** The image is built as
  `ghcr.io/${{ github.repository }}`, so the registry package is the one
  for the repository, and **GHCR does not rename packages or support
  redirects**. Versions up to 2.3.0 remain at
  `ghcr.io/davidneyra2804/mcp-correo:<version>`, unchanged; 2.4.0 and
  later are published at `ghcr.io/davidneyra2804/mailproxy-mcp:<version>`. If
  you have `MCP_IMAGE` pinned to the old path, it keeps working: the image
  does not move. To change it, you must update the variable and redeploy.

### Removed

- **The name `mcp-correo` is removed from the code, the documentation, and the
  deployment**: in the Python package name, the MCP server name, the container
  names, the systemd unit (`deploy/mailproxy-mcp.service`), and the systemd deployment paths
  (`/opt/mailproxy-mcp`, `/etc/mailproxy-mcp`).

### Fixed

- **Data is not touched.** Three things keep the previous name on purpose,
  because changing them breaks a running installation:

  - The salt and the HKDF `info` in `store/crypto.py`: they derive the key
    used to encrypt the account passwords. Changing them leaves the database
    undecryptable.
  - The `KEY_CHECK_PLAINTEXT` marker of `store/store.py` and `store/db.py`:
    it is the encrypted value that verifies the dashboard key matches this
    database.
  - The `/var/lib/mcp-correo` and `/var/log/mcp-correo` paths: they are the mount points
    of the Docker volumes. If they change, the container starts with an empty
    database and the dashboard would show zero accounts.

## [2.3.0] — 2026-11-17

Tool arguments are also accepted as strings: the MCP bridge delivers numbers
as text, and the calls were failing before reaching the server.

### Changed

- **Tool arguments are also accepted as strings.** An MCP client may deliver an
  argument in its type or as a string: `limit: 20` or
  `"20"`, `uids: [21055]` or `"21055,21051"`. With a strict type, those
  calls failed in the client's bridge, before reaching the server, and the
  work was never done.

  The OpenMausBot MCP bridge (the one used by the mail team) validates each
  tool's arguments against the schema published by the server, using Ajv
  **without coercion** (`server/mcp-schema-validator.ts`): an argument that
  arrives as text is rejected with "must be integer" or "must be boolean", and
  the call does not leave the bridge. The bridge for connected apps does adjust
  types (`server/connector-arguments.ts`); the one for MCP tools does not. The
  root fix belongs to that bridge: if the validator coerced, the server would
  receive the `20` as a number and this improvement would not have been
  needed. Until then, the server accepts both forms.

  Through the generic MCP path (`mcp_call_tool`), the bridge converts to text
  every argument that is not text, including those inside an array: `uids: [21055]` arrives as `["21055"]` and the validator
  rejects it with "uids.0: must be integer". For that reason, the array branch
  declares `items` as a union of integer and string, and the string form
  is declared for all affected types, not only for numbers.

  What each argument accepts now:

  | Argument | Forms |
  | --- | --- |
  | `uids` (`mark_read`, `mark_unread`, `prepare_delete`) | `[21055, 21051]`, `["21055", "21051"]`, `"[21055,21051]"`, `"21055,21051"`, `"21055"` |
  | `uid`, `index`, `limit`, `max_chars` | `20` or `"20"` |
  | `unseen`, `permanent` | `true`/`false` or `"true"`/`"false"`/`"1"`/`"0"` |
  | `to`, `cc`, `bcc` | `["ana@example.com"]` or `"ana@example.com"` |
  | `attachments` | `[{"filename": "nota.txt", ...}]` or its JSON text |

A value that is not understood is **not** silently discarded: it is rejected with an error that states what was received and which valid forms exist. Marking an email that was not marked, without notice, is worse than failing.

Argument names do not change, and the existing types remain valid: a client that already knows the catalog keeps working without refreshing it. What changes is the published schema, which now declares the union (`anyOf`) so that the client can see the new forms.

### Deployment

- You need to **refresh the tools catalog** in the MCP client: the published schema changes, because the affected types now declare the union (`anyOf`) between the type and its textual form. The **names** of the arguments and of the response keys do not change, so a client with the old catalog keeps working.
- The image has been published **without being built or tested locally**: the publishing machine does not have Docker. `tests/test_docker.py` checks that the modules that must go into the image are present, but not that the image builds, nor that the container permissions are correct, nor that the data volume works.
- The image is published **only for `linux/amd64`**: the workflow does not include `setup-qemu` or `platforms`. On an arm64 host it must be built locally.

## [2.2.0] — 2026-11-05

The accounts panel is usable again: "Cancel" closes the dialog and the three-dot menu no longer gets clipped.

### Added

- **Buttons to copy each account's MCP URL and token.** In the panel, each account has two new buttons:

  - **Copy URL** puts the full URL of that account on the clipboard, using the public host (`https://mcp.example.com/mcp/ada@corp.example.com`), ready to paste into an MCP client.
  - **Copy token** puts that account's **current** access token on the clipboard. It does not renew it: the operation is a read, and the copied token remains valid on the account's path.

  Both buttons are truly `<button>`, with `aria-label` and `title`, work with the keyboard and have a visible focus. When copying, the button confirms with "Copied" and the panel notice (which is `role="status"`) announces it to screen readers. If the clipboard is not available, the panel does **not** say "Copied": it shows a warning and displays the value so it can be copied manually.

  The URL and token are requested from a new panel route, `GET /api/accounts/{id}/credenciales` (also in English as `/api/accounts/{id}/credentials`). **The security model does not change**: the token was already stored in plaintext in the database and is now read. The password remains encrypted with `MCP_DASHBOARD_KEY`, and the domain list still does not show any token: it only says where the token that opens each account comes from. The read is audited (`dashboard_read_account_credentials`), with the value masked: only the source goes to the audit log.

  The contract for the MCP routes moves to its own module (`rutas.py`), which both the server and the panel use: this way the URL that is copied cannot drift from the one the server accepts.

- **An account's current token, without rotating it.** The panel read returns the token the server actually accepts for that account: its own if it has one, and its domain's token if not. It is a read: it does not rotate, does not invalidate the previous one, and does not change the security model.

  The account list now carries `credential_source` (`cuenta`, `dominio` or `general`) so the interface does not promise a copy that will not work, and `own_credential` to state whether that token is the account's own or inherited from the domain.

  Previously, the panel only said whether an account had its own credential (`has_credential`), which was false for an account that opened through its domain: the account worked while the panel said it did not. Now `has_credential` answers "is there any token that opens this account", and `own_credential` keeps the previous meaning. Both names are those of the MCP surface (`list_accounts`).

- **The panel can be viewed in light, dark, or system mode.** A theme selector in the header offers three options, and the choice persists after reloading. In "system" mode, the panel follows the device's appearance changes live, without reloading.

### Changed

- **The administration panel is redesigned.** Only the interface: neither the API, the backend, nor the `/mcp/...` routes change.

  - **Dark mode** by default, with a blue accent and good contrast.
  - **Accordion per domain**: only the primary one opens by default, and the one that opens is the one the API marks as primary, not one pinned in the frontend. The header shows the name, the number of accounts, and the label "Primary" / "Secondary".
  - **Reorganized actions**: day-to-day actions are visible; actions that break something (renewing the password, deactivating, deleting) go in a "⋯" menu with a separator, a warning that they cannot be undone, and danger styling.
  - **Custom confirmations** instead of `confirm()`: a title per action, Escape cancels, and clicking outside cancels. When closed, focus returns to the control that opened it.
  - **Clear texts** and an explanation for each action (`title` and `aria-label`).
  - **Custom title and favicon**: "VYR Mail Hub · Panel".
  - **Responsive**: tested at 390px, with no horizontal overflow.

  And with the accessibility pattern requested by the CTO's review:

  - The accordion trigger (`summary`) contains only text. The buttons and the menu sit in their own row, outside it: inside, they would be nested controls within the trigger.
  - That row is outside the `details`, so it is visible with the domain closed. Putting it inside hid it, and then it was not possible to add an account to a closed domain.
  - The "⋯" menu is a WAI-ARIA *menu button* pattern: `aria-haspopup="menu"`, `role="menu"` and `role="menuitem"`, arrow-key navigation, Home and End, and Escape that closes the menu and returns focus to the trigger.
  - The menu items carry `tabindex="-1"`: they are removed from the sequential Tab order, as the pattern requires. Tab and Shift+Tab leave the menu, close it, and move focus to the next or previous control on the page. Without that, the destination depended on how the browser recalculated focus when the list was hidden.
  - The calculation of that destination includes the `summary`, which are native accordion controls and receive focus via Tab: otherwise, leaving a menu skipped the next domain's header. And if there is no control in that direction, focus returns to the trigger, instead of staying on the menu item that was just hidden.
  - `aria-expanded` resets when an option is chosen, not only when closed with Escape.
  - The `document` listeners are a single set for all menus, instead of one per menu: otherwise they accumulated with each repaint.
  - The account list does not depend on `:has()`: if the browser does not support it, the list is always shown. Showing extra accounts is preferable to showing none. The accordion state is also stored in the `data-abierto` attribute of the block.

- **The review has a budget: ten minutes.** The first reviews took between 5 and 66 minutes, and the time was not spent reviewing: it went to **over-verifying** (cloning, installing a fresh environment, building mutation-testing harnesses, and investigating the platform). Now:

  - the reviewer **does not run anything**: the main agent passes it the output of the tests and the linter, and it reads, reasons, and reports. It has no shell, editing and subagent launching are denied, and Code Mode too. A command allowlist **is not defensible**: any subcommand with a write argument slips through (`ruff check
    --fix`, `git diff --output=`, `pytest --junit-xml=`);
  - the **clean clone** and the check that **the new test fails without the fix** are done by the main agent, which has them in seconds;
  - the **repetition** is at the main agent's discretion: one review, not a cycle.

And the reviewer's prompt has been trimmed: it looks for serious problems, not an exhaustive audit.

## [2.1.0] — 2026-10-29

The **direct send** for automated routines, and the tool that prevents accepting an implementation without reviewing it.

### Added

- **Opt-in direct send for automated routines.** The tool `send_message_direct` sends the message in **a single call**, without `confirmation_id` and without human confirmation per message. It exists for agents that work in the background: in Paperclip, an agent that extracts pending items from Trello and sends the email calls it once, and the platform doesn't let it make the second call of the two-step flow.

  The mode is off by default and independent of the normal send:

  | | Global switch | Domain/account permission |
  | --- | --- | --- |
  | Send with confirmation | `MCP_ENABLE_SEND` | `allow_send` |
  | Direct send | `MCP_ENABLE_DIRECT_SEND` | `allow_direct_send` |

  The tool requires `idempotency_key`: a stable key per send. The same key with the same content **does not send again**; it returns the previous result with `duplicate: true`. The same key with different content is rejected. The keys live in the database, so they survive a restart and a retry does not duplicate the email.

  The database schema moves to version 2, with the table `direct_sends`. The migration is applied at startup.

  SMTP failures are distinguished: a **rejection** releases the key and allows a retry; a **lack of response** leaves the key in an uncertain state, because the email may have gone out, and the server refuses to resend it with that key.

  This deliberately changes the security model: on an account with direct send, the server does **not** require confirmation per message. The authorization is the one given in advance, and it is advisable to limit it to the account the routine uses.

### Fixed

- **The migration adds the missing column.** v2 added the permission `allow_direct_send` to `domains` and `accounts`, but the migration only created the table `direct_sends`: the column had been added to the `CREATE TABLE` of v1, and that only affects **new** databases. A running v1 database migrated without the column, and the server crashed at startup with `IndexError: No item with that key` when reading the accounts.

  Now the migration performs the `ALTER TABLE` that was missing, and the check is **idempotent and does not depend on the version number**: it inspects the actual table. This also repairs databases that were left half-done (marked as the new version but without the column), which is what happened in the deployment that failed.

- **The schema version is written when migrating.** The migration wrote `schema_version` only if the row did not exist. A database that migrated applied the changes but kept marking the previous version, so the migration was reapplied on every startup. Now it is always written.

- **"Cancel" now closes the account dialog.** The form in the dialog ("Add account" and "Edit account") has required email and password fields. With the form empty, field validation blocked form submission, so the `submit` event never fired and the `method="dialog"` did not close anything: the dialog stayed open, with the fields marked in red, with no way out. Clicking "Cancel" did not close the modal.

  Now the button carries `formnovalidate`, and closing is handled in the `submit` handler instead of relying on native submission. "Cancel" closes the dialog without saving anything, without validation errors, and without sending anything to the server. "Save changes" still validates: an invalid email or password is an error, and nothing is saved.

- **The three-dot menu is no longer clipped.** The block for each domain clips its content with `overflow: hidden`, so that the accordion doesn't overflow its edges. The more-options menu hangs from an account, which is inside that block, so it was also being clipped: when the account was near the bottom edge, the last entry—"Delete account"—disappeared and could not be clicked.

The menu moves to `position: fixed`, which no ancestor clips, and its
  position is calculated by the script when it opens: below the button and flush against its
  right edge, and upward if it doesn't fit below. When scrolling or resizing
  the window, it is repositioned so that it does not end up misaligned.

- **Browser checks that are installable.** The tools
  in `herramientas/` that open Chromium (the theme one and the account modal one)
  need Playwright, which was not declared anywhere:
  anyone following the `AGENTS.md` flow ran into a
  `ModuleNotFoundError` without knowing why.

  Now the dependencies of those tools are kept separate, in
  `requirements-browser.txt`. **They were not** added to
  `requirements-dev.txt` on purpose: the test suite does not use them, and
  they would slow down every install, CI included. The installer
  is down to two lines, in the header of each tool and in
  `docs/dashboard.md`.

### Documentation

- **Automatic review before accepting anything as good.** The skill
  `revision` (`.opencode/skills/revision/`) launches a reviewer subagent
  with clean context when an implementation is finished, before the commit and
  the push. The reviewer is the `reviewer` agent
  (`.opencode/agents/reviewer.md`), which **cannot use the edit tools**: the guarantee does not depend on the prompt asking for it. (It can
  use the shell, which it needs to clone and run tests, but it always works
  in a disposable clone.)

  The reviewer works in a separate clone, checks the change
  **by running it** (tests, a clean clone with real dependencies, and that the
  new test fails without the fix) and checks the change against the list of
  pitfalls in `AGENTS.md`. The main agent verifies its findings
  before fixing them, and repeats the review if the fix changed the
  code.

  The rule that makes it mandatory is in `AGENTS.md`, which is injected
  into every session: it does not depend on the model "remembering."

  It exists because the last two implementations were accepted as good without
  running validations that `AGENTS.md` itself already required: a migration
  without `ALTER TABLE` and a clean clone not done. The skill was corrected
  several times with the reviewer's help before it was ready: it found,
  among other things, that the fake-data detector gave false positives on
  the new untracked files.

- **`tests/test_revision.py`.** The skill monitors itself: that the
  frontmatter is valid YAML, that the prompt's markers match
  those of the skill, that the reference file exists at the path it states,
  that the agent cannot edit, that the skill and `AGENTS.md` do not
  contradict each other, and that no words in another language slip in.

- **The lessons from this version are recorded in `AGENTS.md`.** Fourteen
  new pitfalls, each with its story. Six concern the client contract:
  the name of a field can keep the agent from ever receiving the value;
  a tool's response is text with JSON inside and is also redacted; the
  client caches the catalog of tools; a response without identifiers cannot be
  verified; a test that iterates over an empty list always passes; and the
  IMAP double has to know what the code uses, or the test passes for the wrong reason.

  The other eight come from this work: a tool that is called once must not
  depend on the second one; an argument name with `key` can end up
  shadowed; a rejection and a lack of response are not the same; an
  idempotency key needs a fingerprint, not just a key; a test database
  stays on disk; the schema version is always written, not only when it is missing;
  **adding a column is not
  changing `CREATE TABLE`**; and the version number can lie.

### Deployment

- **The database migrates itself on startup.** The schema moves to
  version 2. There is no need to touch the database by hand and **accounts are not
  lost**: the migration adds the missing column and checks the columns against the actual table,
  so it also repairs databases that were left half-finished with a new version recorded and changes not applied.
  The log states which columns were added; if startup fails,
  the error says whether the database is read-only or locked.
- You need to **refresh the tool catalog** in the MCP client: `send_message_direct` is added and a new permission appears in the panel. A client with the old catalog keeps working with the previous tools.
- To use direct sending: `MCP_ENABLE_DIRECT_SEND=true` in the environment
  (and in the compose file), and `allow_direct_send` in the panel, on the domain or on
  the specific account.
- In Paperclip, the agent policy must allow `send_message_direct`
  without interactive approval: the server no longer asks for confirmation, but the
  client may have it configured on its own.
- **The image was published without being built or tested locally**: the
  publishing machine does not have Docker. `tests/test_docker.py` checks
  that the modules that must go into the image are present, but not that
  the image builds, nor that the container permissions are
  correct, nor that the data volume works.
- **The image is only published for `linux/amd64`**: the workflow does not include
  `setup-qemu` or `platforms`. On an arm64 host it must be built
  locally.

## [2.0.1] — 2026-10-27

Fix of the write tools' contract and the confirmation flow,
with two real incidents along the way.

### Fixed

- **`confirm_token` is renamed to `confirmation_id`.** The agent could not read the value from the preparation and could not complete the send. The cause
  was in Paperclip: it masks by **name** the fields of a tool response that "look like credentials" (`token`, `secret`, `password`, `api_key`,
  `bearer`...), and **the masked value is the one the agent receives**, not the original. `confirm_token` fell into that pattern, so the agent received
  `***REDACTED***` instead of the identifier. `confirmation_id` does not match, and the
  value arrives intact.

  `confirmation_id` is not a credential: without the account's bearer it is useless, it is only valid for one operation, in one account, and for ten
  minutes. Its value now carries a `cfm_` prefix so that it also does not have the form of any provider's key.

  This is a contract change: the argument of `send_message` and `delete_message`
  is now called `confirmation_id`, and the response of `prepare_send` and
  `prepare_delete` returns that field. Clients that read the schema dynamically will not notice; those that had it hard-coded will.

- **A `confirmation_id` that arrives masked says that it arrived masked.** Before, the error was "unknown or already used," which did not distinguish a bad identifier from one that never arrived. Now the message says that the platform redacted it and that the preparation must be repeated.

### Added

- **The send says how to locate the message.** `send_message` returns
  `message_id` and `sent_uid`, in addition to `sent_folder`. `create_draft` returns
  `message_id` and `draft_uid`. Based on a real diagnosis: the send
  returned `copy_in_sent: true` and `sent: true`, but the
  subsequent searches in the Sent folder returned zero messages and the report had no way to verify the copy, because the response carried no identifier. With `message_id` and `sent_uid`, the message is located without guessing the folder or the criterion.
- **`search_messages` accepts `message_id`.** It is the deterministic way to
  find a specific message whose identifier is known, and the one used to locate the copy of a send. It accepts the Message-ID with or
  without angle brackets.
- **`list_accounts` states `sent_folder` and `drafts_folder`** for each account. The
  guide said where each mailbox is, but not in which folder the copy of Sent items is stored: the agent had to guess the name and ended up searching in a folder that was not the right one.
- **`tests/test_nombres_de_campos.py`.** No field name on the MCP surface may match a secret pattern, and the value of the
  `confirmation_id` may not have the form of a known credential. The test was verified by reverting the name: it fails, which is what it should do.

  It covers the three things that happened in production: that the `confirmation_id`
  survives the platform's redaction (its regex is applied to the actual response), that a client with the old catalog receives an actionable error and not the one for the masked value, and that the send and draft responses also have no keys that get masked.

### Changed

- **The send and delete flow is explained in three layers.** The agent
  called `prepare_send`, believed the email had been sent, and did not know it had to call `send_message` afterwards. Now the contract is stated in the server instructions (step by step), in the description of each tool
  (`prepare_send` says that it does not send and which is the next call;
  `send_message` says where the `confirmation_id` comes from), and in the preparation response. One cannot rely on the client passing along the server's general instructions.
- **The preparation response carries explicit status.** `prepare_send`
  and `prepare_delete` return `status: "prepared"`, `sent: false` or
  `deleted: false`, and `next_tool` with the tool that follows. The second call
  returns `status: "sent"` or `status: "deleted"`. The status no longer depends on the model inferring the sequence from a text.
- **The warnings say what to do next.** The preparation warning no longer merely prohibits calling `send_message` or `delete_message` too early:
  it states that the operation has not been executed, that the preview must be shown, that the explicit order must be awaited, and then the following tool must be called with the returned `confirmation_id`. It also warns that the `confirmation_id` expires,
  and that, if it is missing or did not arrive legibly, the preparation must be repeated instead of inventing it.

The security model does not change: the explicit instruction from whoever operates the assistant is still required, and `confirmation_id` remains single-use, bound to the account and the operation.

### Deployment

When deploying this, you must **refresh the connection's catalog** in the MCP client: the argument name for `send_message` and `delete_message` has changed, and a client with the old catalog keeps sending `confirm_token`, which the server rejects with a validation error. It can be recovered by reading the schema again, but it is better not to get there.

The image was published **without being built or tested locally**: the publishing machine has no Docker. `tests/test_docker.py` checks that the modules that must go into the image are present, but not that the image builds, nor the container's permissions, nor that the data volume works. The image is released only for `linux/amd64`.

## [1.0.0] — 2026-10-26

First stable release. The goal remains the same: for an AI assistant to be able to work with third-party IMAP/SMTP mailboxes without the agent needing outbound access to IMAP or SMTP, and without being able to write without an explicit instruction from whoever operates it.

### Added

- **Configuration via environment variables only.** Each server setting has its own variable `MCP_*`. Accounts are declared numbered: `MCP_ACCOUNT_<CAMPO>_<N>`. Precedence: environment > `accounts.toml` > defaults.
- **Per-account routes.** `/mcp` exposes all mailboxes with the global bearer. `/mcp/<cuenta>` exposes just one, identified by its email address, its `NAME`, or its number, and can be authenticated with its own credential (`MCP_ACCOUNT_BEARER_<N>`) that is not valid on any other route.
- **Isolation at a single point.** `MailService._account` is the only place where the scope of the request is checked, so no tool can touch an account outside its route.
- **Deployment with Portainer.** `docker-compose.yml` mounts no configuration file: everything comes through variables. Overlays for Cloudflare Tunnel (`docker-compose.tunnel.yml`), for Caddy with its own TLS (`docker-compose.proxy.yml`), and for local development (`docker-compose.local.yml`).
- **Cloudflare Tunnel.** `cloudflared` reaches the container through the Compose network; there is no need to open any port on the host or add Caddy.
- **Versioning.** `version.py` is the source of truth; a test keeps it in sync with `pyproject.toml` and with the image tag, and the version appears in the MCP handshake. The `vX.Y.Z` tags publish the image to GHCR and create the Release.

### Security

- Mandatory bearer compared against `hmac.compare_digest`; without it, the process does not start.
- The write switches only accept `true`, `false`, `1` and `0`: a misspelled value aborts startup instead of silently staying off.
- Per-account credentials cannot be repeated or match the global one.
- JSONL audit per call, without bodies or credentials. If it cannot be written, the tool does not mutate the mailbox nor issue a token.

## [1.0.1] — 2026-10-26

Fixes from a full audit of the project.

### Fixed

- **The project did not configure logging.** Messages came out because the SDK configures the root logger as a side effect when building the MCP server, using its own format. If the SDK changed, the startup banner went with it. It is now configured before anything else, with the same format as uvicorn.
- **`MCP_SMTP_SECURITY` did nothing** for environment-defined accounts: the account always set the mode, so the global one was dead code. Now the account only sets it if it specifies `SMTP_USE_SSL`, and the default port follows the mode (465 for `ssl`, 587 for `starttls`).
- **Blind recipients were left in the Sent copy.** The same message carried `Bcc` over SMTP and had no `Bcc` when saved.
- **`MCP_CONFIG` pointing to a nonexistent file prevented startup**, even when accounts were defined via environment. It happened in the systemd deployment.
- **`/mcp/0` resolved to an arbitrary account** of the `accounts.toml`.
- **`find_unanswered` asserted a criterion it had not verified** when it could not open the Sent folder. It now says so.
- **The audit rotator died with a traceback** in a restart loop if a size was not a number. And a quoted `"password"` key slipped into the generated TOML.

### Consistency

- The entrypoint no longer decides whether there are accounts: it only prepares the file. It used to be where the schema discrepancies appeared.
- The capability map, the folder limit, and the list of headers now live in a single place.
- `tests/test_ficticio.py` prevents a domain, an email address, or a personal trace from slipping into the repository.

### Documentation

- "It exposes nothing on its own" was false: it publishes `127.0.0.1:8765`.
- "The process starts and warns" was false: it aborts.
- Server variables that nobody documented: `MCP_CONFIG`,
  `MCP_ALLOW_NONLOCAL_BIND`, `MCP_ACCOUNTS_TOML*`, `MCP_GENERATED_CONFIG`,
  `CADDY_*`, `CLOUDFLARED_VERSION`.
- The nginx in the systemd deployment did not serve the routes per account.

[1.0.1]: https://github.com/davidneyra2804/mailproxy-mcp/releases/tag/v1.0.1
## [1.0.2] — 2026-10-26

### Fixed

- **The `Dockerfile` did not copy `scope.py` into the image.** The module came with
  the per-account routes and was left out of the `COPY`. The image did not start:
  `ModuleNotFoundError: No module named 'scope'`. The local tests passed
  because they run from the repository, where the file does exist.

### Tests

- One test builds a directory with **exactly what the Dockerfile copies** and
  starts the server from there. If a module or a file is left out of
  the image, it shows up.
- Another checks that the list of modules the app imports matches the
  one in `COPY`.

[1.0.2]: https://github.com/davidneyra2804/mailproxy-mcp/releases/tag/v1.0.2
[1.0.1]: https://github.com/davidneyra2804/mailproxy-mcp/releases/tag/v1.0.1
## [1.0.3] — 2026-10-26

### Fixed

- **The `audit-rotate` container stayed "unhealthy" forever.** The
  `HEALTHCHECK` in the image expects an HTTP server on port 8765, and this
  service does not serve HTTP: it is a loop that watches the file. It failed with
  *Connection refused* on every attempt. Now the service disables the inherited healthcheck.
- **The rotator said nothing on startup.** Since it only printed when it rotated
  something, and that takes an hour, the log came out empty and the container seemed
  stopped. Now it says what it is watching.

### Tests

- One checks that only the server service inherits the `HEALTHCHECK` from
  the image: the others have to disable it.

[1.0.3]: https://github.com/davidneyra2804/mailproxy-mcp/releases/tag/v1.0.3
[1.0.2]: https://github.com/davidneyra2804/mailproxy-mcp/releases/tag/v1.0.2
[1.0.1]: https://github.com/davidneyra2804/mailproxy-mcp/releases/tag/v1.0.1
## [1.0.4] — 2026-10-26

### Fixed

- **The 421 "Invalid Host header" did not say where the problem came from.** With a
  Cloudflare tunnel, the most common cause is that `MCP_ALLOWED_HOSTS` is
  defined and does not include the public hostname: the explicit list **replaces**
  the one derived from `MCP_PUBLIC_HOST`, and the `Host` that the tunnel forwards is
  left out. The response now says where to look, without leaking the list of
  allowed hosts.
- **Startup warns if `MCP_PUBLIC_HOST` is not in `allowed_hosts`.** And the startup
  log now states which hosts and origins are allowed, so they do not have to be
  inferred.

### Tests

- The 421 includes the hint and does not leak the allowed hosts.
- The startup warning fires when the public host is left out of the
  list, and does not fire when it is inside it.

[1.0.4]: https://github.com/davidneyra2804/mailproxy-mcp/releases/tag/v1.0.4
[1.0.3]: https://github.com/davidneyra2804/mailproxy-mcp/releases/tag/v1.0.3
[1.0.2]: https://github.com/davidneyra2804/mailproxy-mcp/releases/tag/v1.0.2
[1.0.1]: https://github.com/davidneyra2804/mailproxy-mcp/releases/tag/v1.0.1
## [1.0.5] — 2026-10-26

### Diagnostics

- **The log says which `Host` arrived and which ones are accepted.** With a tunnel, the culprit
  may be that the `Host` Cloudflare forwards is not the public hostname (for example, if the route has a different *HTTP Host Header*), or that
  the host list does not include it. With one log line, you can tell which of
  the two it is.
- **The 421 response includes the `Host` received.** The caller already knows
  its own, and it is the missing clue.

[1.0.5]: https://github.com/davidneyra2804/mailproxy-mcp/releases/tag/v1.0.5
[1.0.4]: https://github.com/davidneyra2804/mailproxy-mcp/releases/tag/v1.0.4
[1.0.3]: https://github.com/davidneyra2804/mailproxy-mcp/releases/tag/v1.0.3
[1.0.2]: https://github.com/davidneyra2804/mailproxy-mcp/releases/tag/v1.0.2
[1.0.1]: https://github.com/davidneyra2804/mailproxy-mcp/releases/tag/v1.0.1
## [1.0.6] — 2026-10-26

### Diagnostics

- **Startup says why a write capability is turned off.** Enabling
  `MCP_ENABLE_MARK` is not enough: the account also needs
  `MCP_ACCOUNT_ALLOW_MARK_<N>=true`. With only one of the two, the tool
  does not appear in `tools/list` and there was no way to tell why.

  ```
  INFO     Servidor listo: 1 cuentas, escucha 0.0.0.0:8765, escritura=ninguna
  INFO     Por qué están apagadas: marcado necesita MCP_ENABLE_MARK=true y
           MCP_ACCOUNT_ALLOW_MARK_<N>=true en la cuenta
  ```

- `list_accounts` documents that `can_send`, `can_mark`, `can_delete` and
  `can_draft` reflect the two doors.

[1.0.6]: https://github.com/davidneyra2804/mailproxy-mcp/releases/tag/v1.0.6
[1.0.5]: https://github.com/davidneyra2804/mailproxy-mcp/releases/tag/v1.0.5
[1.0.4]: https://github.com/davidneyra2804/mailproxy-mcp/releases/tag/v1.0.4
[1.0.3]: https://github.com/davidneyra2804/mailproxy-mcp/releases/tag/v1.0.3
[1.0.2]: https://github.com/davidneyra2804/mailproxy-mcp/releases/tag/v1.0.2
[1.0.1]: https://github.com/davidneyra2804/mailproxy-mcp/releases/tag/v1.0.1
## [1.0.7] — 2026-10-26

### Fixed

- **The `account` argument of the tools was required even on a single-account route.** On `/mcp/<cuenta>` the route already fixes the account, but the model also had to know the key and pass it. If it did not, pydantic rejected the call before it reached the code: `Tool 'list_messages' rejected arguments: ['account']`.

  Now `account` is optional in all tools. If the route exposes a single account, that one is used. If it exposes several, the account must be specified, and the error says which ones are available: *"Specify the account. On this route there are: ..."*.
- **Noise in the log when closing the IMAP connection.** `logout()` already closes the socket, so the `shutdown()` afterwards was a double close that always failed and wrote *"Could not close the IMAP socket for ..."* on every request. Now the explicit close is only done if `logout()` fails.

### Documentation

- The per-account routes and the optional argument, explained in the README and the configuration guide.

[1.0.7]: https://github.com/davidneyra2804/mailproxy-mcp/releases/tag/v1.0.7
[1.0.6]: https://github.com/davidneyra2804/mailproxy-mcp/releases/tag/v1.0.6
[1.0.5]: https://github.com/davidneyra2804/mailproxy-mcp/releases/tag/v1.0.5
[1.0.4]: https://github.com/davidneyra2804/mailproxy-mcp/releases/tag/v1.0.4
[1.0.3]: https://github.com/davidneyra2804/mailproxy-mcp/releases/tag/v1.0.3
[1.0.2]: https://github.com/davidneyra2804/mailproxy-mcp/releases/tag/v1.0.2
[1.0.1]: https://github.com/davidneyra2804/mailproxy-mcp/releases/tag/v1.0.1
## [1.0.8] — 2026-10-26

### Fixed

- **Startup listed both variables of a capability even when the global one was already set.** It said *"marcado needs `MCP_ENABLE_MARK=true` and `MCP_ACCOUNT_ALLOW_MARK_<N>=true`"*, and with the global already at `true` that leads you to doubt the one that is already correct. Now each capability states **only what is missing**, and when it is the per-account permission, it includes a copyable example:

  ```
  INFO     Por qué están apagadas: marcado: falta MCP_ACCOUNT_ALLOW_MARK_<N>=true
           en la cuenta (por ejemplo, MCP_ACCOUNT_ALLOW_MARK_1=true)
  ```

[1.0.8]: https://github.com/davidneyra2804/mailproxy-mcp/releases/tag/v1.0.8
[1.0.7]: https://github.com/davidneyra2804/mailproxy-mcp/releases/tag/v1.0.7
[1.0.6]: https://github.com/davidneyra2804/mailproxy-mcp/releases/tag/v1.0.6
[1.0.5]: https://github.com/davidneyra2804/mailproxy-mcp/releases/tag/v1.0.5
[1.0.4]: https://github.com/davidneyra2804/mailproxy-mcp/releases/tag/v1.0.4
[1.0.3]: https://github.com/davidneyra2804/mailproxy-mcp/releases/tag/v1.0.3
[1.0.2]: https://github.com/davidneyra2804/mailproxy-mcp/releases/tag/v1.0.2
[1.0.1]: https://github.com/davidneyra2804/mailproxy-mcp/releases/tag/v1.0.1
## [1.0.9] — 2026-10-26

### Changed

- **The per-account write permission is an optional override, not a second switch.** Before, both were required: the global one (`MCP_ENABLE_MARK=true`) and the account's permission (`MCP_ACCOUNT_ALLOW_MARK_<N>=true`). Enabling a capability took two changes in two places, and the symptom (the tool not appearing) did not say which one was missing.

  Now the global setting is the master and also the default:

  | Global | Account permission | Result |
  | --- | --- | --- |
  | `false` | whatever | off: the global wins |
  | `true` | unset | on: the account inherits it |
  | `true` | `true` | on |
  | `true` | `false` | off for that account: the account wins |

  The per-account override still works to exclude one account without turning off the whole capability.

  **This also changes the `accounts.toml`**: an account without `allow_send` now inherits the global `enable_send`, instead of being off.

### Added

- `write_capabilities_detail` distinguishes the two reasons a capability may be off: the global setting is missing, or all accounts have it set to `false`.

[1.0.9]: https://github.com/davidneyra2804/mailproxy-mcp/releases/tag/v1.0.9
[1.0.8]: https://github.com/davidneyra2804/mailproxy-mcp/releases/tag/v1.0.8
[1.0.7]: https://github.com/davidneyra2804/mailproxy-mcp/releases/tag/v1.0.7
[1.0.6]: https://github.com/davidneyra2804/mailproxy-mcp/releases/tag/v1.0.6
[1.0.5]: https://github.com/davidneyra2804/mailproxy-mcp/releases/tag/v1.0.5
[1.0.4]: https://github.com/davidneyra2804/mailproxy-mcp/releases/tag/v1.0.4
[1.0.3]: https://github.com/davidneyra2804/mailproxy-mcp/releases/tag/v1.0.3
[1.0.2]: https://github.com/davidneyra2804/mailproxy-mcp/releases/tag/v1.0.2
[1.0.1]: https://github.com/davidneyra2804/mailproxy-mcp/releases/tag/v1.0.1
## [1.1.0] — 2026-10-26

### Added

- **Visible sender name: `MCP_ACCOUNT_SENDER_<N>`.** The `From` header of outgoing emails contained only the address, so the recipient saw the account name without the domain. With this variable:

  ```bash
  MCP_ACCOUNT_SENDER_1=Ada Lovelace
  ```

  the `From` becomes `Ada Lovelace <ada@corp.example.com>`, and in the `accounts.toml` it is called `sender`.

  The name is escaped according to RFC 5322 rules: if it contains a comma or quotes, it is quoted so it does not split the address in two. A line break is rejected when the configuration is loaded, not when sending: it would end up in a header and would allow injecting a real `Bcc`. The SMTP envelope still carries the bare address.

### Documentation

- `SENDER` in the account fields list, in the `.env.example`, and in the
  `accounts.toml` example.

[1.1.0]: https://github.com/davidneyra2804/mailproxy-mcp/releases/tag/v1.1.0
[1.0.9]: https://github.com/davidneyra2804/mailproxy-mcp/releases/tag/v1.0.9
[1.0.8]: https://github.com/davidneyra2804/mailproxy-mcp/releases/tag/v1.0.8
[1.0.7]: https://github.com/davidneyra2804/mailproxy-mcp/releases/tag/v1.0.7
[1.0.6]: https://github.com/davidneyra2804/mailproxy-mcp/releases/tag/v1.0.6
[1.0.5]: https://github.com/davidneyra2804/mailproxy-mcp/releases/tag/v1.0.5
[1.0.4]: https://github.com/davidneyra2804/mailproxy-mcp/releases/tag/v1.0.4
[1.0.3]: https://github.com/davidneyra2804/mailproxy-mcp/releases/tag/v1.0.3
[1.0.2]: https://github.com/davidneyra2804/mailproxy-mcp/releases/tag/v1.0.2
[1.0.1]: https://github.com/davidneyra2804/mailproxy-mcp/releases/tag/v1.0.1
[1.0.0]: https://github.com/davidneyra2804/mailproxy-mcp/releases/tag/v1.0.0

## [2.0.0] — 2026-10-26

A control panel on a second port, and mail accounts stored in a
database instead of environment variables. **The routes contract
changes**, which is why this is a major version.

### Added

- **Control panel on its own port.** A second HTTP surface, in the same
  process and on another port, to register domains and accounts without
  touching the deployment. It has its own credential (`MCP_DASHBOARD_TOKEN`),
  its own signed session, and its own anti-CSRF layer. **It cannot read or
  write a mailbox**: it only manages configuration and tests connections.
- **Accounts in a SQLite database.** The database is the **only** source
  of accounts. There are no `MCP_ACCOUNT_<CAMPO>_<N>` variables or configuration file:
  accounts are created in the panel, and a new installation starts empty.
- **Accounts per domain.** A domain groups accounts and gives them a default
  IMAP and SMTP server, permissions, and their own credential. The
  permission chain gains one level: global → domain → account.
- **Real-time exposure.** An account created in the panel is available at
  its `/mcp/<cuenta>` route on the next request. No restart needed. The
  revision counter lives in the database, so it works the same within one
  process or across two.
- **Per-domain route: `/mcp/<dominio>`.** Opens the domain's accounts, using the
  domain credential or the general one.
- **Per-domain token and per-account token**, generated and rotated from the
  panel. They are shown only once.
- **Test button.** Validates the IMAP connection (and SMTP) with the
  just-entered password, before saving. It uses the same code as the rest of
  the server, so the message is the same one you would get when reading the
  mailbox.
- **Passwords encrypted at rest**, with AES-GCM and a key that is **not**
  stored in the database (`MCP_DASHBOARD_KEY`). On startup, the server checks that
  the key matches the database and, if it doesn't, stops and says so.
- **Panel audit log.** Everything done in the panel is recorded in the same
  JSONL as the tools, under its own name and without secrets.

### Changed

- **The panel and the database are no longer optional.** They are how
  accounts are managed. `MCP_DASHBOARD_KEY` and `MCP_DASHBOARD_TOKEN` are required, and if either
  is missing, startup stops and says which one. `MCP_DASHBOARD_DB` is the file path,
  not a switch: by default it is `cuentas.db`, and in the container it is on
  the data volume.
- **`MCP_ACCOUNTS` is removed.** The list of account indexes was unnecessary:
  indexes are discovered automatically. Additionally, with the list, a
  mismatch aborted startup for something that was not a configuration error.
- **`/mcp` no longer exposes all accounts.** It becomes the entry point:
  the guide (the route catalog) and, if there is one, the domain marked as
  default. To open a mailbox, you must name the account or the domain.
  `list_accounts` returns the catalog, with the route for each account and each
  domain.
- **The credential must open the route.** `MCP_BEARER_TOKEN` is the general bearer
  token. A domain's token opens its domain route and its accounts' routes; an
  account's token opens only its own. An account credential on `/mcp/<dominio>`
  returns 403, even if the domain has only one account.
- **The list of write tools depends on the global switch**, not on the
  accounts: the list is set at startup, and accounts can change afterward.
  The per-account permission is still checked on each call, which is where it
  is checked anyway.
- **No accounts is no longer a startup error.** The panel creates them.
- **File-based and per-account variable configuration is removed.**
  `accounts.toml`, `MCP_CONFIG`, `MCP_ACCOUNTS_TOML`, `MCP_ACCOUNTS_TOML_B64`
  and `MCP_GENERATED_CONFIG` are no longer read, and with them all the `MCP_ACCOUNT_<CAMPO>_<N>`
  variables. The server configuration remains **entirely** based on
  `MCP_*` variables, one per field. The `entrypoint` in the container, which
  only generated the TOML, is removed: the image runs the server directly.
- **The startup text states where the configuration comes from.** It is
  always environment variables, and the panel says so when the database is
  empty.

### Fixed

- **The panel could die silently.** It ran `bind` in its thread: if the
  port was in use, the thread died, the log said "Panel running", and
  the process stayed alive **without a panel**. With the panel mandatory, that is a
  broken process. Now the socket is opened in the main thread and, if it
  cannot be opened, the process stops and says so.

### Security

- The panel listens on `127.0.0.1` and its port is published on loopback.
- The panel session is a cookie signed with HMAC, `HttpOnly` and
  `SameSite=Strict`, with expiration.
- Requests that change anything require the `X-MCP-Dashboard` header:
  a form from another site cannot set a custom header.
- The API never returns a password. When reading an account, it shows whether
  the account has a password, not which one it is.
- The database lives on a volume. Without it, the container is read-only and
  accounts are lost on every restart.

[2.4.0]: https://github.com/davidneyra2804/mailproxy-mcp/releases/tag/v2.4.0
[2.0.0]: https://github.com/davidneyra2804/mailproxy-mcp/releases/tag/v2.0.0
