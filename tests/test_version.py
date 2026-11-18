"""The version must match everywhere.

The number appears in three places: version.py (the source of truth),
pyproject.toml (required by the format), and the image label. If any
of them falls behind, the deployment and documentation report the wrong version.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from audit import AuditLog
from server import create_app
from tests.ayuda import ajustes
from version import __version__

ROOT = Path(__file__).resolve().parents[1]


def test_la_version_sigue_semver() -> None:
    assert re.fullmatch(r"\d+\.\d+\.\d+", __version__), __version__


def test_pyproject_dice_la_misma_version() -> None:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert data["project"]["version"] == __version__


def test_la_etiqueta_de_la_imagen_dice_la_misma_version() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    match = re.search(r"ARG MCP_VERSION=(\S+)", dockerfile)
    assert match, "El Dockerfile debería declarar ARG MCP_VERSION"
    assert match.group(1) == __version__


def test_el_handshake_mcp_dice_la_version(tmp_path: Path) -> None:
    """The client sees the version in initialize, without exposing it on /health."""
    settings = ajustes()
    audit = AuditLog(tmp_path / "audit.jsonl")
    application, _runtime = create_app(
        settings, {}, "token-de-prueba-0123456789abcdef", audit=audit
    )
    with TestClient(application, base_url="http://127.0.0.1:8765") as http:
        response = http.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1"},
                },
            },
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
                "Authorization": "Bearer token-de-prueba-0123456789abcdef",
            },
        )
    assert response.status_code == 200, response.text
    assert response.json()["result"]["serverInfo"]["version"] == __version__


def test_health_no_revela_la_version(tmp_path: Path) -> None:
    """/health requires no token and must not reveal the version to callers."""
    settings = ajustes()
    audit = AuditLog(tmp_path / "audit.jsonl")
    application, _runtime = create_app(
        settings, {}, "token-de-prueba-0123456789abcdef", audit=audit
    )
    with TestClient(application, base_url="http://127.0.0.1:8765") as http:
        response = http.get("/health")
    assert response.status_code == 200
    assert __version__ not in response.text


def test_el_banner_de_arranque_se_ve(tmp_path: Path) -> None:
    """Startup messages must actually be logged.

    They used to appear as a side effect of the SDK configuring the root
    logger with its own format when constructing MCPServer. If the SDK
    changed, the banner changed with it or disappeared.
    """
    import subprocess
    import sys

    from tests.fakes import entorno_de_subproceso

    env = entorno_de_subproceso(
        ROOT,
        MCP_BEARER_TOKEN="token-de-prueba-0123456789abcdef",
        MCP_AUDIT_LOG=str(tmp_path / "audit.jsonl"),
    )
    completed = subprocess.run(
        [sys.executable, "-c", "import server"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    salida = completed.stdout + completed.stderr
    assert "Servidor listo:" in salida, salida
    assert "Configuración: " in salida, salida
    assert f"mailproxy-mcp {__version__}" in salida, salida
    # Include the level prefix, as in uvicorn logs.
    assert "INFO     Servidor listo:" in salida, salida


@pytest.mark.parametrize("fichero", ["README.md", "docs/configuration.md"])
def test_la_documentacion_no_contradice_la_version(fichero: str) -> None:
    """If the README mentions a specific version, it must be the current one."""
    text = (ROOT / fichero).read_text(encoding="utf-8")
    for mentioned in set(re.findall(r"\bv?(\d+\.\d+\.\d+)\b", text)):
        if mentioned in {"0.2.0", "1.0.0"}:
            assert mentioned == __version__, f"{fichero} menciona {mentioned}"


def _bloque_de_publicar(fichero: Path) -> list[str]:
    """Return the sed and git commands from the publishing code block.

    Scope the scan to the section. Scanning the entire README could pick up
    an unrelated sed command, such as a rotation example or a maintenance
    script, and fail the synchronization test even if the block stayed the same.

    The heading varies by file and language: Publishing or Publicar in
    AGENTS.md, Versioning or Versionado in the README. The section ends at
    the next heading of the same level.
    """
    lineas = fichero.read_text(encoding="utf-8").splitlines()
    inicio = None
    for numero, linea in enumerate(lineas):
        if linea.startswith("## ") and (
            any(
                palabra in linea.lower()
                for palabra in ("publicar", "versionado", "publishing", "versioning")
            )
        ):
            inicio = numero
            break
    assert inicio is not None, f"{fichero.name}: no está la sección de publicar"
    dentro: list[str] = []
    en_bloque = False
    for linea in lineas[inicio + 1 :]:
        if linea.startswith("## "):
            break
        if linea.startswith("```bash"):
            en_bloque = True
            continue
        if en_bloque and linea.startswith("```"):
            break
        if en_bloque:
            dentro.append(linea)
    return [linea for linea in dentro if linea.startswith(("sed -i ", "git commit ", "git tag "))]


def _patron_de_sed(linea: str) -> str:
    """Return the left-hand side of a sed substitution, the pattern.

    The pattern must match the current version. If it targets another
    version, the command changes nothing and the published version still
    reports the previous one.

    Capture the sed delimiter (slash, pipe, or quote) so the backreference
    finds the closing delimiter. A non-capturing group would make the
    backreference point at the wrong group and return an empty pattern.
    A test that checks an empty list always passes.
    """
    coincidencia = re.search(r"s(['\"/|])(.*?)\1", linea)
    return coincidencia.group(2) if coincidencia else ""


def _sustitucion_de_sed(linea: str) -> str:
    """Return the right-hand side of a sed substitution, the replacement."""
    coincidencia = re.search(r"s(['\"/|])(.*?)\1(.*?)\1", linea)
    return coincidencia.group(3) if coincidencia else ""


def _versiones(texto: str) -> set[str]:
    """Extract version numbers with or without escaped dots."""
    encontradas = re.findall(r"(\d+(?:\\?\.)?\d+(?:\\?\.)?\d+)", texto)
    return {v.replace("\\", "") for v in encontradas}


def test_los_dos_bloques_de_publicar_apuntan_al_mismo_numero() -> None:
    """The README and AGENTS.md must publish the same version.

    In 2.1.0, the README block was updated while AGENTS.md still pointed
    to an older version. Following AGENTS.md published an older version,
    and the sed commands in the documentation matched nothing.

    Compare every command in the block, including git commit and git tag.
    The tag determines what gets published.
    """
    readme = _bloque_de_publicar(ROOT / "README.md")
    agentes = _bloque_de_publicar(ROOT / "AGENTS.md")
    assert readme and agentes, "Uno de los dos bloques de publicar no está"
    assert readme == agentes, (
        "Los bloques de publicar divergen:\n"
        "README.md:\n  " + "\n  ".join(readme) + "\n"
        "AGENTS.md:\n  " + "\n  ".join(agentes)
    )


def test_cada_sed_del_bloque_usa_la_version_actual_como_patron() -> None:
    """Every sed command must use the current version in its pattern.

    Each command replaces the current version with the next one. A pattern
    targeting another version changes nothing, so the published version
    still reports the previous one.

    Check each line individually. Combining their matches can hide an error
    if even one command uses the right version.

    Fail if the pattern cannot be extracted. A test that iterates over an
    empty list always passes.
    """
    lineas = [
        linea for linea in _bloque_de_publicar(ROOT / "README.md") if linea.startswith("sed -i ")
    ]
    assert lineas, "El bloque de publicar no tiene ningún sed"
    vistas = 0
    for linea in lineas:
        patron = _patron_de_sed(linea)
        assert patron, f"No se ha podido sacar el patrón de {linea!r}"
        versiones = _versiones(patron)
        if not versiones:
            # The wildcard pattern (.*) replaces any value and
            # therefore contains no version number.
            continue
        vistas += 1
        assert versiones == {__version__}, (
            f"El patrón de esta línea no es la versión actual ({__version__}): "
            f"{versiones} en {linea!r}"
        )
    assert vistas >= 2, (
        f"Solo {vistas} líneas del bloque llevan la versión en el patrón: "
        "el test no está mirando lo que dice mirar."
    )


def test_el_bloque_de_publicar_etiqueta_la_version_siguiente() -> None:
    """The tag and commit must name the next version.

    If the git tag points elsewhere, the workflow aborts. The tag must
    match the version written by the sed commands, even when the tag and
    commit already agree with each other.
    """
    lineas = _bloque_de_publicar(ROOT / "README.md")
    etiquetas = set()
    for linea in lineas:
        coincidencia = re.search(r"git tag v(\d+\.\d+\.\d+)", linea)
        if coincidencia:
            etiquetas.add(coincidencia.group(1))
    commits = set()
    for linea in lineas:
        coincidencia = re.search(r'git commit -am "version (\d+\.\d+\.\d+)"', linea)
        if coincidencia:
            commits.add(coincidencia.group(1))
    assert etiquetas, "El bloque no dice qué etiqueta se publica"
    assert commits, "El bloque no dice con qué commit se publica"
    assert etiquetas == commits, (
        f"La etiqueta ({etiquetas}) y el commit ({commits}) no son la misma versión."
    )
    # That version must also be the one the block writes.
    escritas = set()
    for linea in lineas:
        patron = _patron_de_sed(linea)
        sustitucion = _sustitucion_de_sed(linea)
        if "__version__" in patron:
            escritas |= _versiones(sustitucion)
    assert escritas, "No se ha podido sacar la versión que escribe el bloque"
    assert etiquetas == escritas, (
        f"La etiqueta ({etiquetas}) no es la versión que escribe el bloque ({escritas})."
    )
    assert __version__ not in etiquetas, (
        f"La etiqueta es la versión actual ({__version__}): ya está publicada."
    )
