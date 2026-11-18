"""Keep real data out of this public repository.

The project is deployed with real configuration. A real domain, email
address, or hostname in the documentation, examples, or tests would be
published by mistake.

These tests permit only the domains reserved by RFC 2606 and RFC 6761
and the short list of public services the project mentions deliberately.

The repository's own addresses (github.com and ghcr.io) identify the
project itself. A public repository necessarily has an owner.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

#: Domains reserved for documentation by RFC 2606 and RFC 6761.
RESERVADOS_EXACTOS = frozenset(
    {"example.com", "example.org", "example.net", "example", "test", "invalid", "localhost"}
)
RESERVADOS_SUFIJOS = (
    ".example.com",
    ".example.org",
    ".example.net",
    ".example",
    ".test",
    ".invalid",
    ".localhost",
)

#: Public services the project mentions deliberately.
PERMITIDOS = frozenset(
    {
        "github.com",
        "ghcr.io",
        "modelcontextprotocol.io",
        "semver.org",
        "keepachangelog.com",
        "portainer.io",
        "developers.cloudflare.com",
        "jsonrpc.org",
        "opensource.org",
        "creativecommons.org",
        "ietf.org",
        "python.org",
        "pypi.org",
        "docker.io",
        # The favicon format requires this SVG namespace. The project
        # makes no connections to this domain.
        "www.w3.org",
        "localhost",
        "ip6.me",
    }
)

#: Domains allowed as suffixes of subdomains.
SUFIJOS_PERMITIDOS = (
    "github.com",
    "githubusercontent.com",
    "githubassets.com",
)

_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
#: Lowercase domain with a plausible TLD. The TLD filter skips Python
#: paths such as imaplib.IMAP4.error and filenames such as
#: docker-compose.local.yml. The negative lookahead skips Python
#: attribute access that resembles a domain, such as logger.info(.
_DOMINIO = re.compile(
    r"\b(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
    r"(?:com|net|org|io|dev|app|cloud|me|info|biz|xyz|site|online|tech|co|uk|de|fr|it|nl|pt|br|ar|mx|cat|test|invalid|example|es|eu|ai)\b"
    r"(?!\s*\()"
)

#: Personal identifiers that must stay out of the repository.
RASTROS_PERSONALES = (
    "gmail.com",
    "MacBook-Pro",
    "vyrtech",
)


def _ficheros_versionados() -> list[Path]:
    """Return only Git-tracked files, excluding .venv and untracked files."""
    listado = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    return [ROOT / nombre for nombre in listado if (ROOT / nombre).is_file()]


def _texto() -> dict[Path, str]:
    return {
        path: path.read_text(encoding="utf-8", errors="ignore") for path in _ficheros_versionados()
    }


def _reservado(dominio: str) -> bool:
    return dominio in RESERVADOS_EXACTOS or any(
        dominio.endswith(sufijo) for sufijo in RESERVADOS_SUFIJOS
    )


def _sospechoso(dominio: str) -> bool:
    """Decide whether this domain-like string warrants a check.

    Strings with at least three labels are usually real domains. With
    two labels, Python attribute access such as self.app or logger.info
    looks similar. Check those only if the name contains a hyphen or digit,
    which helps distinguish real domains from ordinary words.
    """
    etiquetas = dominio.split(".")
    if len(etiquetas) >= 3:
        return True
    nombre = etiquetas[0]
    return "-" in nombre or any(caracter.isdigit() for caracter in nombre)


def test_todo_correo_usa_un_dominio_reservado() -> None:
    """example.com and example.org are reserved for documentation."""
    malos: list[str] = []
    for path, text in _texto().items():
        for correo in _EMAIL.findall(text):
            dominio = correo.rsplit("@", 1)[1].lower()
            if not _reservado(dominio):
                malos.append(f"{path.relative_to(ROOT)}: {correo}")
    assert not malos, "Correos que no son de dominio reservado:\n  " + "\n  ".join(malos)


def test_todo_dominio_es_reservado_o_esta_permitido() -> None:
    """The documentation must contain no real domains."""
    malos: list[str] = []
    for path, text in _texto().items():
        for dominio in _DOMINIO.findall(text):
            dominio = dominio.lower()
            if _reservado(dominio) or dominio in PERMITIDOS:
                continue
            if any(dominio.endswith(f".{sufijo}") for sufijo in SUFIJOS_PERMITIDOS):
                continue
            if not _sospechoso(dominio):
                continue
            malos.append(f"{path.relative_to(ROOT)}: {dominio}")
    assert not malos, "Dominios que no son de documentación:\n  " + "\n  ".join(sorted(set(malos)))


def test_no_hay_rastros_personales_en_el_arbol() -> None:
    """The tree must contain no personal email addresses or hostnames.

    Exclude this file because it contains the strings it searches for.
    """
    malos: list[str] = []
    for path, text in _texto().items():
        if path == Path(__file__).resolve():
            continue
        for rastro in RASTROS_PERSONALES:
            if rastro in text:
                malos.append(f"{path.relative_to(ROOT)}: {rastro}")
    assert not malos, "Rastros personales:\n  " + "\n  ".join(malos)


@pytest.mark.parametrize(
    "fichero",
    ["README.md", "CHANGELOG.md", "docs/configuration.md", "docs/deployment-portainer.md"],
)
def test_la_documentacion_no_tiene_dominios_reales(fichero: str) -> None:
    """Check the most-read files separately as a precaution."""
    text = (ROOT / fichero).read_text(encoding="utf-8")
    for dominio in _DOMINIO.findall(text):
        dominio = dominio.lower()
        if _reservado(dominio) or dominio in PERMITIDOS:
            continue
        if any(dominio.endswith(f".{sufijo}") for sufijo in SUFIJOS_PERMITIDOS):
            continue
        if not _sospechoso(dominio):
            continue
        raise AssertionError(f"{fichero}: {dominio}")
