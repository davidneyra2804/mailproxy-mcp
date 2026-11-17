"""Los argumentos que un cliente entrega escritos en vez de tipados.

Un puente MCP puede entregar los argumentos en su tipo o escritos: un
`limit: 20` que llega como `"20"`, una lista de uid que llega como
`"21055,21051"`. Con el tipo cerrado, esas llamadas morían antes de llegar
al servidor y el trabajo se quedaba sin hacer.

Estas pruebas fijan dos cosas:

- el normalizador entiende las formas textuales y rechaza lo que no
  entiende, diciendo qué recibió,
- las tools aceptan las dos formas, y el esquema publicado lo dice.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from mail.errors import MailError
from mail.normalize import (
    normalize_bool,
    normalize_int,
    normalize_objects,
    normalize_text_list,
    normalize_uids,
)
from tests.test_writes import Rig


def _json(resultado: object) -> dict:
    assert getattr(resultado, "is_error", False) is False
    return json.loads(resultado.content[0].text)  # type: ignore[attr-defined]


# --- el normalizador ---------------------------------------------------------


def test_uids_desde_una_lista() -> None:
    assert normalize_uids([21055, 21051]) == [21055, 21051]


def test_uids_desde_texto_json() -> None:
    assert normalize_uids("[21055, 21051]") == [21055, 21051]


def test_uids_desde_una_lista_separada_por_comas() -> None:
    assert normalize_uids("21055,21051") == [21055, 21051]
    assert normalize_uids(" 21055 , 21051 ") == [21055, 21051]


def test_uids_desde_un_solo_numero() -> None:
    assert normalize_uids("21055") == [21055]


def test_un_uid_repetido_se_queda_una_vez() -> None:
    assert normalize_uids("21055,21055") == [21055]
    assert normalize_uids([21055, 21055]) == [21055]


def test_una_lista_de_uid_vacia_se_rechaza() -> None:
    with pytest.raises(MailError, match="Indica al menos un uid"):
        normalize_uids("")
    with pytest.raises(MailError, match="Indica al menos un uid"):
        normalize_uids([])


def test_un_uid_invalido_se_rechaza_diciendo_que_se_recibio() -> None:
    with pytest.raises(MailError, match="'abc'"):
        normalize_uids("abc")
    with pytest.raises(MailError, match="12.5"):
        normalize_uids(12.5)


def test_un_uid_cero_o_negativo_se_rechaza() -> None:
    with pytest.raises(MailError, match="mayor o igual que 1"):
        normalize_uids("0")
    with pytest.raises(MailError, match="mayor o igual que 1"):
        normalize_uids([-3])


def test_un_texto_json_roto_no_se_adivina() -> None:
    with pytest.raises(MailError, match="no es un texto JSON válido"):
        normalize_uids("[21055,")


def test_entero_acepta_numero_y_texto() -> None:
    assert normalize_int(20, "limit") == 20
    assert normalize_int("20", "limit") == 20
    assert normalize_int(" 20 ", "limit") == 20


def test_entero_invalido_se_rechaza() -> None:
    with pytest.raises(MailError, match="limit debe ser un entero"):
        normalize_int("muchos", "limit")
    with pytest.raises(MailError, match="limit debe ser un entero"):
        normalize_int(True, "limit")


def test_booleano_acepta_las_formas_de_texto() -> None:
    for texto in ("true", "TRUE", "1", "yes", "si"):
        assert normalize_bool(texto, "unseen") is True
    for texto in ("false", "0", "no"):
        assert normalize_bool(texto, "unseen") is False
    assert normalize_bool(True, "unseen") is True
    assert normalize_bool(False, "unseen") is False


def test_un_booleano_que_no_se_entiende_se_rechaza() -> None:
    with pytest.raises(MailError, match="unseen debe ser true o false"):
        normalize_bool("quiza", "unseen")


def test_lista_de_textos_desde_lista_texto_json_y_csv() -> None:
    assert normalize_text_list(["ana@example.com"], "to") == ["ana@example.com"]
    assert normalize_text_list('["ana@example.com"]', "to") == ["ana@example.com"]
    assert normalize_text_list("ana@example.com,luis@example.com", "to") == [
        "ana@example.com",
        "luis@example.com",
    ]


def test_un_nombre_visible_con_coma_no_se_parte() -> None:
    texto = "Doe, John <john@example.com>"
    assert normalize_text_list(texto, "to") == [texto]


def test_una_lista_de_textos_vacia_se_rechaza() -> None:
    with pytest.raises(MailError, match="Indica al menos un elemento en to"):
        normalize_text_list("", "to")


def test_objetos_desde_lista_y_desde_texto() -> None:
    lista = [{"filename": "nota.txt", "content_base64": "MTIz"}]
    assert normalize_objects(lista, "attachments") == lista
    assert normalize_objects(
        '[{"filename": "nota.txt", "content_base64": "MTIz"}]', "attachments"
    ) == (lista)
    assert normalize_objects(None, "attachments") is None


def test_objetos_invalidos_se_rechazan() -> None:
    with pytest.raises(MailError, match="attachments no es un texto JSON válido"):
        normalize_objects("no es json", "attachments")
    with pytest.raises(MailError, match="attachments no es una lista de objetos"):
        normalize_objects('{"filename": "nota.txt"}', "attachments")


# --- las tools ---------------------------------------------------------------


def test_marcar_leido_acepta_los_uid_como_texto(tmp_path: Path) -> None:
    rig = Rig(tmp_path)

    async def run() -> None:
        desde_csv = _json(
            await rig.mcp.call_tool("mark_read", {"account": "principal", "uids": "10,13"})
        )
        assert desde_csv["uids"] == [10, 13]
        desde_json = _json(
            await rig.mcp.call_tool("mark_unread", {"account": "principal", "uids": "[11, 12]"})
        )
        assert desde_json["uids"] == [11, 12]
        suelto = _json(await rig.mcp.call_tool("mark_read", {"account": "principal", "uids": "10"}))
        assert suelto["uids"] == [10]

    asyncio.run(run())
    inbox = rig.fake.folders["INBOX"].messages
    assert b"\\Seen" in inbox[10].flags
    assert b"\\Seen" in inbox[13].flags
    assert b"\\Seen" not in inbox[11].flags
    assert b"\\Seen" not in inbox[12].flags


def test_marcar_leido_sigue_exigiendo_los_uid(tmp_path: Path) -> None:
    rig = Rig(tmp_path)

    async def run() -> None:
        with pytest.raises(ToolError):
            await rig.mcp.call_tool("mark_read", {"account": "principal"})
        with pytest.raises(ToolError, match="Indica al menos un uid"):
            await rig.mcp.call_tool("mark_read", {"account": "principal", "uids": ""})

    asyncio.run(run())


def test_preparar_el_borrado_acepta_los_uid_como_texto(tmp_path: Path) -> None:
    rig = Rig(tmp_path)

    async def run() -> None:
        preparado = _json(
            await rig.mcp.call_tool(
                "prepare_delete",
                {"account": "principal", "uids": "10", "permanent": "false"},
            )
        )
        assert preparado["uids"] == [10]
        assert preparado["permanent"] is False

    asyncio.run(run())


def test_listar_mensajes_acepta_limit_y_unseen_como_texto(tmp_path: Path) -> None:
    rig = Rig(tmp_path)

    async def run() -> None:
        listado = _json(
            await rig.mcp.call_tool(
                "list_messages",
                {"account": "principal", "limit": "2", "unseen": "true"},
            )
        )
        assert len(listado["messages"]) == 2
        assert all(not item.get("seen") for item in listado["messages"])

    asyncio.run(run())


def test_una_forma_textual_que_no_se_entiende_se_rechaza(tmp_path: Path) -> None:
    rig = Rig(tmp_path)

    async def run() -> None:
        with pytest.raises(ToolError, match="mayor o igual que 1"):
            await rig.mcp.call_tool("mark_read", {"account": "principal", "uids": "abc"})
        with pytest.raises(ToolError, match="limit debe ser un entero"):
            await rig.mcp.call_tool("list_messages", {"account": "principal", "limit": "muchos"})

    asyncio.run(run())


# --- el esquema publicado ----------------------------------------------------


def test_el_esquema_publicado_admite_las_formas_textuales(tmp_path: Path) -> None:
    rig = Rig(tmp_path)

    async def run() -> None:
        tools = {tool.name: tool for tool in await rig.mcp.list_tools()}
        uids = tools["mark_read"].input_schema["properties"]["uids"]
        assert {rama.get("type") for rama in uids["anyOf"]} == {"array", "string"}
        assert "uids" in tools["mark_read"].input_schema["required"]
        limit = tools["list_messages"].input_schema["properties"]["limit"]
        assert {rama.get("type") for rama in limit["anyOf"]} == {"integer", "string"}
        unseen = tools["list_messages"].input_schema["properties"]["unseen"]
        assert {rama.get("type") for rama in unseen["anyOf"]} == {"boolean", "string"}

    asyncio.run(run())


def test_el_esquema_publicado_sigue_siendo_valido(tmp_path: Path) -> None:
    rig = Rig(tmp_path)

    async def run() -> None:
        for tool in await rig.mcp.list_tools():
            schema = tool.input_schema
            assert schema.get("type") == "object", tool.name
            properties = schema.get("properties", {})
            for nombre, pieza in properties.items():
                assert "type" in pieza or "anyOf" in pieza, f"{tool.name}.{nombre}"
            for nombre in schema.get("required", []):
                assert nombre in properties, f"{tool.name}.{nombre}"

    asyncio.run(run())
