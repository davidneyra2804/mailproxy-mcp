# Visual validation — VYRA-34

The effective token and the light/dark/system theme on the buttons that copy the MCP URL and each account's token.

## What was there

The basis of this work is VYRA-32 (`4992f46`), which already had the two copy buttons. Two things were missing, and neither was "touching up":

**The effective token.** VYRA-32 read `cuenta.bearer` and nothing else. An account without its own credential returned an empty token, so the button could not copy anything. The interface text ("this account has no token of its own: it uses its domain's") described a behavior the backend did not fulfill.

**The theme.** The panel was dark-mode only: `:root` declared `color-scheme: dark`, and there was neither a selector nor a `prefers-color-scheme`.

## The finding about VYRA-25

The assignment assumes that VYRA-25 already implemented light/dark/system in `feat/panel-modo-oscuro-acordeon`, commit `867637a`. **That commit does not contain the theme.** It is the fix for action alignment and menu visibility: four files, `panel.css` (+5 −1), `panel.js`, a document, and a test file.

VYRA-25's theme work was in another commit, `869a460`, on the isolated branch `work/VYRA-25` in Atenea. That commit **never reached `main`**: VYRA-26 integrated only the patch from `3049666` (the menu alignment), and VYRA-28 merged `867637a`.

Checked in the repository, not assumed:

```
git log --all -S "prefers-color-scheme" -- dashboard/static/panel.css   # sin resultados
git show main:dashboard/static/panel.css | grep color-scheme             # solo "dark"
```

That is to say: **there was no theme support to reuse**. The task says "reuse only the selector/persistence and required theme styles," assuming they exist. They did not exist, so they had to be implemented. That is why the "before" only has screenshots in dark mode: that panel could not be seen in light mode, and no "before light" screenshot has been invented.

## What was implemented

### The theme

- **Selector** in the header: Light / Dark / System, with `aria-pressed` to indicate which one is active.
- **Persistence** in `localStorage` (`mailproxy-mcp-tema`). The attribute is applied in the head of the HTML, before painting, so there is no flash of the wrong theme.
- **"System"** sets no attribute: the media query governs. The panel follows the device **live**, with the listener from `change` in `matchMedia`.
- The colors that depended on the theme were hard-coded in 17 rules. They are now variables (`--texto-acento`, `--borde-ok`, `--cabecera-fondo`, `--degradado-bienvenida`…), so the two themes differ only in the values of `:root`. A test guards this: no literal color may remain outside the variables (printing, which always uses white, is the only exception).
- The browser `theme-color` accompanies the theme: it is what is seen in the browser bar on mobile.

The menu and the domain order were not touched: VYRA-25 fixed them, and they are accepted.

### The effective token

With the delivery of VYRA-33 (Apolo), the route returns the **effective** token: the account's own, or its domain's, and `origen` says which one.

- The interface **distinguishes the three cases**: `cuenta` (own token), `dominio` (inherited), and `general` (no token to copy).
- A label in the row says "Domain token" when the token is inherited, and "Only with the general token" when there is no token to copy. It only appears when there is something to clarify: an account with its own token keeps the row clean.
- The error text is now accurate. The previous one ("it uses its domain's") was false with the new backend: the domain token **is** copyable. The `general` case is stated honestly instead of promising a copy that would not work.
- The `title` and `aria-label` of the button explain where that account's token comes from, before anything is clicked.

### A bug found along the way

Each button scheduled its return to the normal state with its own `setTimeout`, without canceling the previous one. Copying twice in a row made the first copy's timer **erase the confirmation of the second**: the button went back to its original text while the second copy had in fact been made. The user saw that nothing had been copied, and what had been copied was correct. Now each button stores its timer and cancels the previous one.

## Verification

### Tests

- `pytest`: **358 passing** (301 before VYRA-32, plus 57 from this work).
- `ruff check`: no findings. `ruff format --check`: 81 files, all
  formatted correctly.
- **Clean clone** with its own environment: 358 passing, and also with
  `PYTHONSAFEPATH=1` (the Actions environment, where import failures only appear in CI).

### Real browser

Chromium with Playwright, with the actual dashboard running against a dummy
database. Desktop viewport `1440×1000` and mobile viewport `390×844`.

| Check | Result |
|---|---|
| The dashboard loads and renders the accounts | ok |
| Dark background by default | `rgb(12, 16, 23)` |
| Three theme options, "system" selected | ok |
| The light background differs from the dark one | `rgb(244, 246, 251)` |
| The choice persists after reloading | ok |
| Copy token: the clipboard holds the account's token | ok |
| Copy URL: the clipboard holds the full URL | `https://mcp.example.com/mcp/ada@corp.example.com` |
| **Account without its own token: the domain token is copied** | `token-del-dominio-0123456789abcdef` |
| The row says "Domain token" | ok |
| An account with its own token has no label | ok |
| **Account without any token: the row warns, and does not say "Copied"** | ok |
| The warning says it only opens with the general token | ok |
| The clipboard was not touched in that case | ok |
| The copy button is reachable with Tab | ok |
| Visible focus with the keyboard | ok |
| Enter also copies | ok |
| **Clipboard failure: does not say "Copied", warns, and shows the value** | ok |
| The warning is `role="status"` and `aria-live="polite"` | ok |
| In "system" there is no attribute and the device decides | ok |
| The dashboard follows the device **live**, without reloading | ok |
| With a manually chosen theme, the device no longer decides | ok |
| JavaScript errors in the console | none |

The account without its own token was checked **against the real MCP server**:
the token the dashboard returns is the one `BearerAuth._permite` accepts for
opening that route. It is not enough that the token is returned.

## Screenshots

In `docs/screenshots-vyra34/`:

**Before** (base `4992f46`, dark mode only — there is no "before in light" because that dashboard could not be viewed in light mode):
- `vyra34-before-dark-desktop.png`
- `vyra34-before-dark-mobile.png`

**After:**
- `vyra34-light-desktop.png`
- `vyra34-light-mobile.png`
- `vyra34-dark-desktop.png`
- `vyra34-dark-mobile.png`

**"Copied" state:**
- `vyra34-copied-light-desktop.png`
- `vyra34-copied-dark-desktop.png`

All screenshots were reviewed with vision: the text is readable in both themes, the buttons do not overflow on mobile, and the two source badges are distinguishable.

## Limits and residual risk

- **No push, PR, merge, or deployment has been done.** The branch is local.
- **The route returns the token in plain text** to anyone with a dashboard session. This is
  what David accepted in VYRA-32 and what the assignment requested, and the token
  was already stored in plain text in the database (the password is still encrypted
  with `MCP_DASHBOARD_KEY`). If the security model changes in the future
  (hashed tokens), that route would stop being possible without reviewing the design.
- **The clipboard failure shows the token on the page itself**, which is
  what the requirement asked for as the fallback. On a shared computer
  this leaves the token visible; it is a risk accepted by the requirement.
- **The Docker image has not been verified**: there is no Docker on this machine. There are no new Python modules beyond `rutas.py` (which VYRA-32 already included) and no new dependencies — `requirements.txt` and
  `requirements-dev.txt` are unchanged — so the `COPY` of the `Dockerfile`
  only adds `rutas.py`, which without it the image would start without that module.
  The change has not been built or run in Docker.
- Browser validation covers Chromium and the two viewports
  indicated. It does not cover other browsers, other zoom levels, or other assistive
  technologies.
- The VYRA-33 backend was integrated **as delivered by Apolo**
  (commit `a82f074` on its branch). The code review of that part belongs to Apolo; here it was
  verified that the interface consumes what it exposes correctly.
