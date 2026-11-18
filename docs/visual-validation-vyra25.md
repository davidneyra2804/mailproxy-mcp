# Visual validation — VYRA-25

## Findings and changes

- Original capture from the parent task: the primary domain was rendered after the secondary one. The render now places the domain marked `default` first; when it is changed and the page is reloaded, the new primary remains first.
- Original capture from the parent task: the options menu was clipped or overlapped the content. The updated fixture shows the menu outside the clipping area and without covering the row's controls.
- Review capture for VYRA-25: “Add account”, “Edit” and “…” were at different heights. The margin of `1.2rem` intended for the dialog's native `<menu>` element also reached the buttons with class `.menu`. That rule was limited to `dialog menu`; Playwright measured identical vertical centers for the three controls on desktop and mobile.
- Visual inspection also showed that the mathematical character `⋯` was not visible in the environment's font. It was replaced with the horizontal ellipsis `…`, which appears in the later captures.

## Verification

- Browser: Chromium headless with Playwright, desktop viewport `1440×1000` and mobile viewport `390×844`.
- The page under test contains the actual HTML, CSS and JavaScript from the VYRA-25 branch. API routes were intercepted within the browser and answered with a fictitious fixture (`vyrts.com` primary and `vyrgs.com` secondary); no backend or real data was connected.
- Playwright checked light/dark/system modes, persistence on reload, live tracking of `prefers-color-scheme`, initial order and order after changing the primary/reloading, opening options with Enter, closing with Escape and focus return, accessible name, visible focus, and absence of JavaScript errors.
- Vertical center measurements for “Add account”, “Edit” and “…”: desktop `520.6 px` for the three controls (spread `0 px`); mobile `708 px` for the three (spread `0 px`). The options button measures `44×44 px` and the visible focus has an outline of `2 px`.
- Visual inspection of captures after the changes: text readable in light and dark themes; controls aligned; no row overlap in the two viewports.
- Repository tests in the isolated VYRA-25 clone: `295 passed` (`/tmp/vyra25-pyenv/bin/pytest -q`). `git diff --check` without errors.

## Follow-up captures

Four captures taken in Chromium are attached to the issue: desktop light/dark and mobile light/dark. The capture reported by the user remains attached to the original comment for comparison.

## Limits and residual risk

The API was simulated with a fixture: these tests do not verify data persistence or backend changes. The inspection covers the indicated viewports only, not all scales, browsers or assistive technologies.

## Integration into the Orion branch

Commit `3049666d27cae6f5c5c70ca6d444252186ed1fe9` was integrated into `feat/panel-modo-oscuro-acordeon` (see [VYRA-26](/VYRA/issues/VYRA-26)). The patch was applied on top of that branch: the dialog rule changed from `.menu` to `dialog menu`, and the options button changed from `⋯` to `…`.

The two assertions of the accessibility contract were added to `tests/test_accesibilidad_panel.py`, the file that in this branch holds the panel's structural contract for CSS and JavaScript. In the isolated VYRA-25 clone that file did not exist, and the assertions were placed in `tests/test_interfaz.py`.

The branch is integrated and not deployed: no image has been built or published, and no backend, API or data has been touched.
