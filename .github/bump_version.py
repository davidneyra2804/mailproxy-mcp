"""Apply the 2.5.0 version bump.

Temporary helper for the release branch: it is deleted by the workflow that
runs it, so it never reaches main. It does exactly what the publishing
section of README.md and AGENTS.md describes, plus the CHANGELOG entry.
"""

from __future__ import annotations

import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
OLD = "2.4.0"
NEW = "2.5.0"
NEXT = "2.6.0"

SECTION = """## [2.5.0] — 2026-11-18

The documentation is now in English. The project is published for a wider
audience, and the docs were the last part still written in Spanish.

### Changed

- **The whole documentation is in English**: the README, `AGENTS.md`, this
  CHANGELOG, the guides under `docs/` and the deployment layer (the Compose
  files, `deploy/`, the workflows, the `Dockerfile` and `.env.example`).

- **The guides under `docs/` have English file names now.** `configuracion.md`
  is `configuration.md`, `despliegue-portainer.md` is
  `deployment-portainer.md`, `despliegue-systemd.md` is
  `deployment-systemd.md`, `despliegue-tunel-cloudflare.md` is
  `deployment-cloudflare-tunnel.md`, `seguridad.md` is `security.md`,
  `validacion-visual-vyra25.md` is `visual-validation-vyra25.md` and
  `validacion-visual-vyra34.md` is `visual-validation-vyra34.md`. The
  screenshots moved to `docs/screenshots-vyra34/`. The links inside the
  repository were updated, but a link from outside to the old names no
  longer resolves.

- **The tests check the English wording.** They used to look for Spanish
  sentences, so after the translation they would have passed for the wrong
  reason. Each one now checks the English text with the same strength:
  putting a line back in Spanish makes the test fail.

### Unchanged

- **The runtime logs stay in Spanish** ("Servidor listo:", "Configuración:").
  They are runtime output and they are quoted verbatim in this CHANGELOG.

- **The encrypted data is not affected.** The HKDF salt, the
  `KEY_CHECK_PLAINTEXT` marker and the `/var/lib/mcp-correo` and
  `/var/log/mcp-correo` paths keep their names on purpose: changing them
  would leave the database undecryptable or empty.

"""


def edit(path: str, old: str, new: str) -> None:
    file = ROOT / path
    text = file.read_text(encoding="utf-8")
    assert old in text, f"{path}: no match for {old!r}"
    file.write_text(text.replace(old, new), encoding="utf-8")


def publishing_block() -> list[str]:
    """The commands that publish the next version.

    The pattern has to name the current version: the tests check it.
    """

    pattern = NEW.replace(".", r"\.")
    return [
        f"""sed -i 's/__version__ = ".*"/__version__ = "{NEXT}"/' version.py""",
        f"""sed -i 's/^version = ".*"/version = "{NEXT}"/' pyproject.toml""",
        f"""sed -i 's/ARG MCP_VERSION=.*/ARG MCP_VERSION={NEXT}/' Dockerfile""",
        f"""sed -i 's/mailproxy-mcp {pattern} |/mailproxy-mcp {NEXT} |/' docs/configuration.md""",
        f"""sed -i 's|mailproxy-mcp:{pattern}|mailproxy-mcp:{NEXT}|' README.md""",
        f"""git commit -am "version {NEXT}\"""",
        f"""git tag v{NEXT} && git push origin v{NEXT}""",
    ]


def replace_block(path: str, headings: tuple[str, ...]) -> None:
    """Rewrite the publishing block of a file, keeping its comment lines."""

    file = ROOT / path
    lines = file.read_text(encoding="utf-8").splitlines()
    start = None
    for number, line in enumerate(lines):
        if line.startswith("## ") and any(word in line.lower() for word in headings):
            start = number
            break
    assert start is not None, path
    begin = None
    for number in range(start + 1, len(lines)):
        if lines[number].startswith("```bash"):
            begin = number
            break
    assert begin is not None, path
    end = begin + 1
    while not lines[end].startswith("```"):
        end += 1
    comments = [line for line in lines[begin + 1 : end] if line.startswith("#")]
    lines[begin + 1 : end] = comments + publishing_block()
    file.write_text("\n".join(lines) + "\n", encoding="utf-8")


def changelog() -> None:
    file = ROOT / "CHANGELOG.md"
    text = file.read_text(encoding="utf-8")
    assert "## [2.5.0]" not in text, "the section already exists"
    text = text.replace("## [Unpublished]\n", "## [Unpublished]\n\n" + SECTION, 1)
    older = f"[{OLD}]: https://github.com/davidneyra2804/mailproxy-mcp/releases/tag/v{OLD}"
    newer = f"[{NEW}]: https://github.com/davidneyra2804/mailproxy-mcp/releases/tag/v{NEW}"
    assert older in text
    text = text.replace(older, newer + "\n" + older, 1)
    file.write_text(text, encoding="utf-8")


edit("version.py", f'__version__ = "{OLD}"', f'__version__ = "{NEW}"')
edit("pyproject.toml", f'version = "{OLD}"', f'version = "{NEW}"')
edit("Dockerfile", f"ARG MCP_VERSION={OLD}", f"ARG MCP_VERSION={NEW}")
edit(
    "docs/configuration.md",
    f"mailproxy-mcp {OLD} | [Home](../README.md)",
    f"mailproxy-mcp {NEW} | [Home](../README.md)",
)
edit(
    "README.md",
    f"MCP_IMAGE=ghcr.io/davidneyra2804/mailproxy-mcp:{OLD}",
    f"MCP_IMAGE=ghcr.io/davidneyra2804/mailproxy-mcp:{NEW}",
)
replace_block("README.md", ("versioning", "versionado"))
replace_block("AGENTS.md", ("publishing", "publicar"))
changelog()
print("bump 2.5.0 applied")
