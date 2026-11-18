# AGENTS.md

Read these project rules before working on **mailproxy-mcp**.

## Overview

This [MCP](https://modelcontextprotocol.io) server gives an AI assistant access
to third-party IMAP/SMTP mailboxes. Reads are available within the authorized
scope. Writes require an explicit instruction from the operator and use
two-step confirmation with a single-use `confirmation_id`.

The reference deployment uses **Portainer + Cloudflare Tunnel** and takes
all server configuration from environment variables.

```
Cliente MCP ──HTTPS──▶ Cloudflare ──▶ cloudflared ──▶ mailproxy-mcp ──▶ IMAP/SMTP
```

## Project rules

Each rule addresses an observed failure.

### 1. Configure the server through environment variables

Configure the server with `MCP_*` variables. There is no configuration file,
TOML, account configuration in the environment, or separate list to maintain.

```
MCP_BEARER_TOKEN=el-secreto-del-cliente-mcp
MCP_DASHBOARD_KEY=la-clave-que-cifra-las-contrasenas
MCP_DASHBOARD_TOKEN=la-credencial-del-panel
```

The dashboard manages accounts in the database. Avoid adding
`MCP_ACCOUNT_*` variables: their presence in Compose or `.env.example` would
lead users to expect that they configure accounts.

The dashboard and database are always required. Startup stops if
`MCP_DASHBOARD_KEY` or `MCP_DASHBOARD_TOKEN` is missing. Put the database on a
volume so it can be written to from a read-only container and survive restarts.

### 2. Fail early with an actionable message

An invalid value **stops startup** with an explicit error.

- A switch accepts only `true`, `false`, `1`, and `0`. `MCP_ENABLE_SEND=yes`
  produces an error.
- An explicit limit of `0` must reach the validator and be rejected.
- Reject line breaks in values used in headers.

Syntax errors in a TOML file surface when the file is read. Invalid environment
values can otherwise silently disable a tool and go unnoticed for weeks.
**A configuration error must identify its cause.**

### 3. Give each rule one implementation

When the same concept appears twice, move it into a shared module and import
it. For example, `write_capabilities` uses the same rules to decide which tools
to register as `MailboxWriter._gated` uses to authorize individual operations.
Duplicated rules can diverge over time.

### 4. Use fictitious data in the repository

The repository is public. Use fictitious domains, email addresses, machine
hostnames, and IPs.

`tests/test_ficticio.py` checks every commit for email addresses on non-reserved
domains, non-reserved domains, and personal information. Use `example.com`,
`example.org`, `example.net`, and `*.test` for examples (RFC 2606 and 6761).

The check has caught real leaks three times. Keep it strict.

### 5. Keep documentation in sync with the code

Update the documentation when the code changes. Tests verify that:

- `.env.example` lists every variable the code recognizes.
- Compose declares every fixed server variable.
- `version.py`, `pyproject.toml`, and the image tag agree.

Outdated instructions waste time for anyone who relies on them.

Tool descriptions and responses are part of the contract. Record changes to
tool names or arguments in the CHANGELOG and explain the required client
action in the deployment section.

### 6. Keep secrets out of the image and Git

Supply deployment secrets through the environment. The image must contain
no tokens or passwords. `.gitignore` excludes `.env`. Track `.env.example`
with fictitious values.

## Code map

| File | Responsibility |
| --- | --- |
| `server.py` | `MCPServer`, bearer authentication, account routing, and tool registration |
| `config.py` | Environment variables, capabilities, limits, and validation |
| `scope.py` | Request scope, which determines which accounts a call can access |
| `audit.py` | JSONL per call, excluding bodies and credentials |
| `mail/imap.py` | Reads (`EXAMINE`, `BODY.PEEK`) and centralized isolation |
| `mail/mutate.py` | Writes: marking, deleting, drafting, and sending |
| `mail/confirm.py` | In-memory single-use `confirmation_id` and daily quota |
| `mail/compose.py` | Message construction and header escaping |
| `mail/readonly.py` | Proxy that blocks writes on read paths |
| `store/db.py` | Database schema, migrations, and revision counter |
| `store/crypto.py` | Password encryption with the key stored outside the database |
| `store/store.py` | Domain, account, and token operations |
| `store/accounts.py` | Static or database-backed account source, with reload support |
| `store/direct_send.py` | Direct-send idempotency keys and fingerprints in the database |
| `dashboard/app.py` | Dashboard routes, session, and CSRF protection |
| `dashboard/api.py` | Dashboard handlers, including the connection test |
| `dashboard/ui.py` | Dashboard UI and login |
| `docker/rotate_audit.py` | JSONL audit log rotation |
| `docker/healthcheck.py` | Health probe for MCP and the dashboard when available |
| `tests/ayuda.py` | Server settings and fictitious test accounts |
| `tests/test_nombres_de_campos.py` | Checks that MCP field names avoid credential patterns |

## Routes and permissions

**Routes.** The route defines the scope. The bearer token authorizes it.

| Route | Accepted credentials | Scope |
| --- | --- | --- |
| `/mcp` | `MCP_BEARER_TOKEN` | Route catalog and default domain |
| `/mcp/<domain>` | Global or domain credential | Accounts in that domain |
| `/mcp/<account>` | Global, account, or owning domain credential | One account |

`<account>` can be the email address, account `NAME`, or index. `<domain>`
is the domain name. An account token is valid only on its own account route.
The general route accepts only the global token. A credential used outside
its authorized routes receives 403.

`MailService._account()` is the single enforcement point for isolation.
Scope is carried in a `ContextVar` (`scope.py`) because SDK tools are
synchronous and run in a thread pool.

**Write permissions.** The global switch controls availability and supplies
the default. A domain can restrict it, and an account can supply its own
setting within those limits. Unset values are inherited.

| Global | Domain | Account | Result |
| --- | --- | --- | --- |
| `false` | Any | Any | Disabled |
| `true` | Unset | Unset | Enabled by inheritance |
| `true` | Unset | `true` | Enabled |
| `true` | Unset | `false` | Disabled for that account |
| `true` | `false` | Any | Disabled for the domain |

**Direct sending is a separate capability** with its own switch
(`MCP_ENABLE_DIRECT_SEND`) and permission (`allow_direct_send`). An account
can enable either or both send modes independently of `send`. Direct sending
uses prior authorization without per-message confirmation. Database-backed
idempotency makes retries safe.

## Development workflow

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/pytest
```

Tests use IMAP and SMTP doubles and need neither network access nor a real
mailbox.

**Verify in a clean clone with a new virtual environment.** Local runs and
CI can behave differently.

```bash
# The diff is regenerated AFTER the fixes: the clone has to validate the
# code that is going to be merged, not the previous one.
git add -A && git diff --cached > /tmp/revision.diff
set -e
TMP=$(mktemp -d); git clone . "$TMP/ci"; cd "$TMP/ci"
# If the change is not committed, apply it (with --index).
# If it is already committed, the clone carries it: do not apply anything.
git apply --index /tmp/revision.diff
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt
.venv/bin/ruff format --check . && .venv/bin/ruff check .
.venv/bin/pytest
PYTHONSAFEPATH=1 .venv/bin/pytest    # the Actions environment
```

**The clone must contain the change.** A clone starts at the latest commit.
For an uncommitted change, apply its diff with `--index` so new files are
tracked. For a committed change, clone the commit and skip the patch.
Use `set -e` to stop on a failed `git apply`. Results obtained after a failed
patch would apply to the old code.

**Use `ruff format --check` for verification.** `ruff format` rewrites files.
A successful check after a rewrite can conceal a formatting violation in
the original tree.

**Use a real clone with its `.git` directory.** Copies made with `rsync` or
`cp` lack repository metadata. The fictitious-data detector needs
`git ls-files` and otherwise fails with `returned non-zero exit status 128`.

A clean clone catches three problems:

- The fictitious-data detector ignores untracked files because it uses
  `git ls-files`.
- A fresh install exposes dependencies your local `.venv` may still have
  even though `requirements.txt` no longer declares them.
- `PYTHONSAFEPATH` in Actions leaves the working directory off `sys.path`.
  Subprocess imports can therefore fail only in CI.

Run the formatting check before the lint check after each edit. Formatting
can affect lint outcomes. During editing, `ruff format` formats the files.
During verification, `ruff format --check` checks the files as they are.

Before accepting a change:

1. **Test the image.** `tests/test_docker.py` assembles the files copied by
   the Dockerfile and starts the server from that directory. Tests run from
   the repository can pass even when the image is missing a module.
2. **Check first-time setup.** Verify that missing variables produce startup
   messages that explain how to fix them.
3. **Update `.env.example` and Compose when a variable changes.** Tests
   check the names. Verify the defaults as well.
4. **Add regression coverage for every defect you fix manually.** Confirm
   that the test fails without the fix.
5. **Keep the UI and API in sync.** `tests/test_interfaz_api.py` compares
   JavaScript calls with the application's routes. A misspelled route can
   leave a button inert without a visible error.

## Pitfalls

Each of these caused a broken release.

- **A module missing from the image.** `scope.py` was missing from the
  Dockerfile's `COPY`, so the container could not start. Tests from the
  repository passed because the file was present there. The image layout
  test reproduces the container's file set.
- **Two modules implementing different versions of the same rule.** The
  entrypoint still read `MCP_ACCOUNTS` after the schema switched to indexed
  discovery. The entrypoint was removed. Configure the server through the
  environment and manage accounts in the database.
- **An error message listing settings that are already correct.** The
  marking error listed `MCP_ENABLE_MARK=true` and
  `MCP_ACCOUNT_ALLOW_MARK_<N>=true` even when the global value was already
  set. Report only missing settings.
- **imapclient's `logout()` already closes the socket.** A subsequent
  `shutdown()` attempts a second close and adds an error to every request log.
- **An account default overriding a global setting.** `MCP_SMTP_SECURITY`
  had no effect while the account always set the mode. A default at the
  more specific layer can override the documented global setting.
- **`Bcc` in the copy in Sent.** The SMTP message omitted `Bcc` but the
  stored copy still included it. Remove it before `APPEND`.
- **Display names in headers.** An unescaped comma can split an address
  in two. Escape display names with `formataddr` and reject CRLF when
  loading header values.
- **A required argument already determined by the route.** The `account`
  argument was required even on `/mcp/<account>`, where the route identifies
  the account. The model had to guess the key.
- **A stale account snapshot.** Accounts added in the dashboard were
  invisible to `/mcp`. Use a reloadable source and check its revision
  counter in the database on every request. A cache without invalidation
  makes dashboard edits appear ineffective.
- **A credential with excessive scope.** Enforce isolation by route type.
  An account credential must never open a domain route, even if the
  domain currently contains only that account. Filtering the returned
  accounts alone would allow that access.
- **The general route exposing every mailbox.** Keep `/mcp` as the entry
  point for the route catalog and the default domain, if configured.
- **Two simultaneous account sources.** v2 made the database the only
  account source and removed environment-based accounts. Multiple sources
  could cause missing tools or inexplicable changes to accounts.
- **A database without persistence.** Put the database on the data volume.
  Without it, the read-only container either prevents writes or loses the
  database on restart. A test checks the mount.
- **A silent UI failure.** A misspelled JavaScript route, an inert button,
  or a label missing `for=` can leave a broken feature on a page that still
  loads. `tests/test_interfaz_api.py` checks the UI against the API.
- **A form that exposes the data model.** The form asked for the same email
  three times because the route identifier, label, and login are separate
  fields in the model. Put unusual overrides under advanced options.
- **An edit breaking an existing route.** The route alias identifies the
  account in `/mcp`. Preserve it on edits. Overwriting it with the email
  address silently breaks existing clients.
- **An explicit `0` treated as unset.** The pattern `int(valor) or 100`
  silently fell back to the default for an explicit zero. `_env_int_or()`
  and `_env_float_or()` distinguish unset variables from explicit values
  so the validator can reject zero. Preserve that distinction for every
  explicitly supplied invalid value.
- **Use reserved domains in examples.** The reserved domains are
  `example.com`, `example.org`, `example.net`, `*.test`, `*.invalid`, and
  `*.localhost`. Using a non-reserved equivalent slipped through twice.
- **A field name preventing delivery of its value.** Paperclip redacts tool
  response fields with names such as `token`, `secret`, `password`, `api_key`,
  and `bearer`. `validateToolContent` delivers the redacted result. The agent
  received `***REDACTED***` for `confirm_token` and could not complete the
  send. Use `confirmation_id` with a `cfm_` prefix to avoid credential
  patterns. `tests/test_nombres_de_campos.py` checks MCP field names and
  values. The ID requires the account's bearer token and works once, for
  one operation on one account, within ten minutes.
- **A tool response is a text block containing JSON.** The platform also
  redacts text, so `"confirm_token": "..."` can be redacted inside the block.
  Run the pattern against the response text when checking whether a value
  survives redaction.
- **The MCP client caches the tool catalog.** Renaming an argument leads
  to a validation failure when the client sends the old name. When a tool
  contract changes, tell users to refresh the catalog and record this in
  the deployment section of the CHANGELOG.
- **Write responses that omit identifiers.** `send_message` returned
  `sent: true` and `copy_in_sent: true` without `message_id` or `sent_uid`.
  Clients had to guess the folder and search criteria, and a misspelled
  query could make the copy appear missing. A write that creates readable
  data must return the information needed to retrieve it.
- **Single-call tools cannot rely on a second call.** Paperclip could
  call the preparation tool but could not pass the `confirmation_id` to
  a second call. `send_message_direct` sends in one call with prior
  authorization. It is opt-in with its own global switch
  (`MCP_ENABLE_DIRECT_SEND`) and permission (`allow_direct_send`). Store
  idempotency in the database so a restart cannot cause a duplicate send.
- **An argument containing `key` can be redacted.** Paperclip uses field
  names to identify credentials. `idempotency_key` contains `key`, but
  `tests/test_nombres_de_campos.py` ensures it does not match the secret
  pattern. The name is part of the contract. The audit log redacts its value.
- **An explicit SMTP rejection and no SMTP reply have different retry
  semantics.** A rejection means the message was not sent. A lost reply
  leaves delivery uncertain. `mail/smtp_out.py` releases the idempotency
  key for explicit rejections (`SMTPRecipientsRefused` or
  `SMTPResponseException`) and keeps it reserved on `SmtpUncertain`.
  Model rejection in the SMTP double with a server response. A generic
  `SMTPException` tests the uncertain outcome and can pass for the wrong reason.
- **Idempotency keys require content fingerprints.** The key identifies
  the send and the fingerprint identifies its content. The fingerprint
  lets the server reject reuse of a key with a different body, which
  would otherwise return the earlier result and leave the new message unsent.
- **A test database can persist on disk.** `conftest.py` sets
  `MCP_DASHBOARD_DB` in a temporary directory. A stale test file can
  still exist between runs. After a schema change, reading an old row can
  raise `IndexError: No item with that key`. Remove the stale test database
  or use a fresh filename when the schema changes.
- **Always write the schema version after migration.** The v1-to-v2
  migration wrote `schema_version` only if the row was absent. A migrated
  database whose row still said `1` reran the migration on every startup.
  Construct a v1 database with accounts and a version row to verify that
  migration records the new version. `prepare()` on a new database does not
  exercise the existing row.
- **Adding a column to an existing database requires `ALTER TABLE`.**
  `CREATE TABLE` affects only new databases. `allow_direct_send` was added
  to `_SCHEMA_V1` while `_SCHEMA_V2` only created `direct_sends`, causing
  `IndexError: No item with that key` when reading an existing row. Treat
  v1 as historical and add columns in migrations with `ALTER TABLE`.
- **The version number can outpace the schema.** A migration that fails
  partway can leave a database with a new version and incomplete changes.
  A version-only guard skips it at subsequent startups. Inspect actual
  columns with `PRAGMA table_info` and make the migration idempotent.
  Test with a partial database containing the new table and version but
  missing the column.
- **A test iterating over an empty list always passes.** The IMAP double
  used `input_schema` while the test read `inputSchema`. `getattr` returned
  `None` and the test checked no names. Assert that the schema and names
  exist, and revert the fix temporarily to confirm that the test fails.
- **The IMAP double must implement the criteria the code uses.**
  The double ignored `HEADER Message-ID` and matched every message.
  Model the server's behavior so the test checks the intended condition.

## Publishing

The version is defined in `version.py`. To release a new version:

```bash
sed -i 's/__version__ = ".*"/__version__ = "2.4.1"/' version.py
sed -i 's/^version = ".*"/version = "2.4.1"/' pyproject.toml
sed -i 's/ARG MCP_VERSION=.*/ARG MCP_VERSION=2.4.1/' Dockerfile
sed -i 's/mailproxy-mcp 2\.4\.0 |/mailproxy-mcp 2.4.1 |/' docs/configuration.md
sed -i 's|mailproxy-mcp:2\.4\.0|mailproxy-mcp:2.4.1|' README.md
git commit -am "version 2.4.1"
git tag v2.4.1 && git push origin v2.4.1
```

The documentation `sed` commands are required. Tests check that the
documentation refers to the current version. Update the patterns on each bump
to match the current version.

Each `sed` command must match text. The `mailproxy-mcp X.Y.Z |` signature
exists only in the configuration reference. Searching another file silently
leaves the signature unchanged.

On macOS, `sed -i` needs an empty suffix: `sed -i '' 's/.../.../'`.
Without it, `sed` treats the script as a filename and fails.

The example publishes the **next** version. Use the current version in the
search patterns, or the substitutions will leave the old version in place.
Keep the two blocks in the README and this file in sync. Updating only one
can publish an older version or leave the documentation stale.

The tag starts `.github/workflows/release.yml`, which runs the tests, publishes
the image to GHCR, and creates the Release. Publication requires passing tests.
The broken 1.1.0 never reached the registry because a test caught a real email
address in the CHANGELOG.

The workflow extracts the matching version section from the CHANGELOG and
combines it with image details to create the Release body. GitHub's automatic
notes missed changes and the warning about images published without local
testing. If the section is missing, the workflow warns and continues because
the image has already been published by then.

v2.0.1 was published on 2026-10-28 from commit `bc2657b` with tag `v2.0.1`.
The image was published as `ghcr.io/davidneyra2804/mcp-correo:2.0.1` and
`latest`. Docker was unavailable on the publishing machine, so the image
was never started or tested locally. v2.0.0 was published on 2026-10-27
from commit `d7ebf0c` with tag `v2.0.0` and image
`ghcr.io/davidneyra2804/mcp-correo:2.0.0` and `latest`.

**The repository was renamed to `mailproxy-mcp` on 2026-11-17.** The image
uses `ghcr.io/${{ github.repository }}`, so the registry package follows
the repository name. Versions before 2.4.0 remain under
`ghcr.io/davidneyra2804/mcp-correo`. GHCR keeps the existing package under
that name and does not redirect it. Versions 2.4.0 and later use
`ghcr.io/davidneyra2804/mailproxy-mcp`. Deployments with `MCP_IMAGE` pinned to
the former path must update it and redeploy to use the new image.

Preserve the HKDF salt and `info` in `store/crypto.py`, the
`KEY_CHECK_PLAINTEXT` marker in `store/store.py` and `store/db.py`, and the
paths `/var/lib/mcp-correo` and `/var/log/mcp-correo`. The first three
values derive or verify the encryption key for account passwords. Changing
them would prevent an existing deployment from decrypting its database.
The paths are Docker volume mounts. Changing them would make the
container start with an empty database.

The image targets **`linux/amd64` only**. The workflow does not include
`setup-qemu` or `platforms`. On arm64, build locally or add multi-platform
support to the workflow.

### Test the release image

The publishing machine lacks Docker, so it does not start the tagged image
locally. `tests/test_docker.py` simulates the Dockerfile's `COPY` and starts
the server with the copied files. It catches missing modules. Image builds,
container permissions, and volume behavior require a real container test.

Schema changes need special attention. Migrations run at startup and must
work with an existing database mounted at `/var/lib/mcp-correo`. The suite
covers migration from a v1 test database. A deployed database needs separate
verification.

Before releasing a schema change, start the image with a volume containing a
database from the previous version and verify the migration. If Docker is
unavailable, record the gap in the commit and Release so users know before
redeploying.

### Verify the release

A successful workflow alone does not show that the image is available.
If `gh` is unavailable, check the API:

```bash
# The workflows triggered by the tag
curl -s "https://api.github.com/repos/<repo>/actions/runs?per_page=5" \
  | python3 -c "import json,sys; [print(r['name'], r['status'], r['conclusion']) for r in json.load(sys.stdin)['workflow_runs'][:5]]"

# The Release
curl -s "https://api.github.com/repos/<repo>/releases/tags/v2.0.0"

# The image tags, with an anonymous read-only token
TOKEN=$(curl -s "https://ghcr.io/token?scope=repository:<repo>:pull&service=ghcr.io" \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['token'])")
curl -s -H "Authorization: Bearer $TOKEN" \
  "https://ghcr.io/v2/<repo>/tags/list"

# The version OCI label, reading the published manifest
curl -s -H "Authorization: Bearer $TOKEN" \
  -H "Accept: application/vnd.oci.image.index.v1+json" \
  "https://ghcr.io/v2/<repo>/manifests/2.0.0"
```

Verify that the published `org.opencontainers.image.version` label matches
`version.py` and that the entrypoint is current. The manifest is an image
index. Follow its `linux/amd64` manifest, get `config.digest`, and read that
blob. The entrypoint is in `config.Entrypoint`.

The workflow composes the Release body so it need not be edited by hand.
Re-running the tag with `git tag -f` and `git push --force origin vX.Y.Z`
also republishes the image.

## Review

**Run the `revision` skill after implementing a change and before committing
or pushing.** The rule is not optional for behavioral changes and is included
here because this file is injected into every session. Prose and comments
that leave behavior unchanged are exempt.

A migration once omitted a required `ALTER TABLE` and the clean-clone check
was skipped even though this file already required both checks. A reviewer
with fresh context checks that the required validations were performed.

1. Prepare the complete diff with `git add -A` and `git diff --cached` so
   the reviewer sees new files.
2. **Run tests and lint** and pass their output to the reviewer.
3. Start a reviewer with fresh context. The reviewer reads the diff and
   the supplied output and reasons about them.
4. Verify findings before making fixes.
5. The primary agent tests in a **clean clone** and verifies that **each new
   test fails without the fix**.
6. Run one review. The primary agent decides whether to **repeat** it: a
   review is not a cycle.
7. Report what was reviewed, which findings were confirmed, and what remains
   unverified.

The review budget is **ten minutes**. Early reviews took between 5 and 66
minutes, largely due to cloning, installing environments, building mutation
harnesses, and researching OpenCode. The reviewer uses the existing tree
and supplied outputs. The primary agent performs mutations, as required
by the skill. Platform research is outside the review scope.

The reviewer works in the existing tree with editing, writing, patching,
shell access, subagent launches, and Code Mode denied. A shell command allowlist
would still allow writes through arguments such as `ruff check --fix`,
`git diff --output=`, and `pytest --junit-xml=`. The primary agent supplies
the completed test output.

OpenCode's own actions, such as creating a worktree or moving a session,
are outside those denials and do not edit project files.

The review supplements tests and focuses on severe problems. It can assess
only the code and evidence supplied. If the reviewer and primary agent use
the same model, they can share blind spots.

## Before merging to `main`

- [ ] Run `revision` and address confirmed findings.
- [ ] Run tests locally and in a clean clone.
- [ ] Start the image with `docker compose -f docker-compose.yml -f docker-compose.local.yml up --build`.
- [ ] Run the smoke test with `python herramientas/humo.py`.
- [ ] Confirm that documentation matches the code.
- [ ] Verify that the tree contains only fictitious example data.
- [ ] For configuration changes, update `.env.example`, Compose,
      `docs/configuration.md`, and the CHANGELOG.
- [ ] For changes to argument or response key names, document the catalog
      refresh in the deployment section of the CHANGELOG.
- [ ] For route changes, update `deploy/nginx-mcp.conf`. An exact
      `location = /mcp` match returns 404 on account and domain routes.
- [ ] For dashboard changes, update `docs/dashboard.md` and the README
      with the new workflow.
- [ ] For schema changes, test migration from the previous version and
      confirm that startup succeeds with an old database.
- [ ] For new columns, include an `ALTER TABLE` for existing databases.
      `CREATE TABLE` applies only to new databases.

**If Docker is unavailable, say so in the commit and Release.**
`tests/test_docker.py` simulates the Dockerfile's `COPY` and starts the
server from that copy, which catches missing modules. Verifying the image
build, container permissions, and the data volume requires a Docker run.

## Pending work

- **Multi-platform images.** Published images target `linux/amd64`. On
  arm64, build locally or add `setup-qemu` and `platforms` to the workflow.
