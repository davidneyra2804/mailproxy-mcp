"""Normalización de los argumentos que un cliente MCP entrega como texto.

Un cliente MCP no siempre entrega los argumentos en el tipo que declara el
esquema. Los puentes que validan el esquema sin coerción —el de OpenMausBot
entre ellos— rechazan un `limit: 20` que llega como `"20"`, y una lista de
uid que llega como `"21055,21051"`. El cliente no tiene la culpa de nada de
esto, pero el trabajo tampoco se puede quedar sin hacer.

Este módulo es el único sitio donde se normaliza: a partir de aquí los
valores ya están en su tipo final (`list[int]`, `int`, `bool`, `list[str]`).

Un valor que no se entiende **no** se descarta en silencio: se rechaza con un
error que dice qué se recibió y qué formas validas hay. Un uid que se pierde
es un correo que el agente creía haber marcado y que sigue sin marcar, y eso
no se ve.
"""

from __future__ import annotations

import json
import re
from typing import Any

from mail.errors import MailError

#: Un entero escrito a mano, con signo opcional.
_ENTERO = re.compile(r"[+-]?\d+")

#: Las formas de texto que se entienden como «sí» y como «no».
_SI = frozenset({"true", "1", "yes", "si", "sí"})
_NO = frozenset({"false", "0", "no"})


def normalize_uids(valor: Any, nombre: str = "uids") -> list[int]:
    """Normaliza una lista de uid a `list[int]`.

    Valen la lista de enteros, la lista con sus números escritos
    (`["21055","21051"]`), el texto JSON (`"[21055,21051]"`), la lista
    separada por comas (`"21055,21051"`) y el número suelto (`"21055"`). Los
    uid repetidos se quedan una vez: contarlos dos veces no marca dos veces.
    """
    if isinstance(valor, str):
        texto = valor.strip()
        if not texto:
            raise MailError("Indica al menos un uid.")
        if texto.startswith("["):
            datos = _json(texto, nombre)
            if not isinstance(datos, list):
                raise _uids_invalidos(valor, nombre)
            return _uids_de_lista(datos, nombre)
        partes = [parte.strip() for parte in texto.split(",")]
        if any(not parte for parte in partes):
            raise _uids_invalidos(valor, nombre)
        return _uids_de_lista(partes, nombre)
    if isinstance(valor, list | tuple):
        return _uids_de_lista(list(valor), nombre)
    raise _uids_invalidos(valor, nombre)


def normalize_int(valor: Any, nombre: str = "limit") -> int:
    """Normaliza un entero, venga como número o escrito como texto."""
    numero = _entero(valor)
    if numero is None:
        raise MailError(f"{nombre} debe ser un entero. Se recibió: {valor!r}.")
    return numero


def normalize_bool(valor: Any, nombre: str = "unseen") -> bool:
    """Normaliza un booleano, venga como booleano o escrito como texto.

    Se entienden `true`, `1`, `yes` y `si` como sí, y `false`, `0` y `no`
    como no. Cualquier otra cosa se rechaza: adivinar un interruptor es
    peor que fallar.
    """
    if isinstance(valor, bool):
        return valor
    if isinstance(valor, str):
        texto = valor.strip().lower()
        if texto in _SI:
            return True
        if texto in _NO:
            return False
    raise MailError(f"{nombre} debe ser true o false. Se recibió: {valor!r}.")


def normalize_text_list(valor: Any, nombre: str = "to") -> list[str]:
    """Normaliza una lista de textos (destinatarios) a `list[str]`.

    Valen la lista, el texto JSON (`'["ana@example.com"]'`) y la lista
    separada por comas (`"ana@example.com,luis@example.com"`). Un texto con
    comas solo se parte si todas las partes parecen direcciones: un nombre
    visible (`"Doe, John <john@example.com>"`) es una sola dirección y se
    respeta intacto.
    """
    if isinstance(valor, str):
        texto = valor.strip()
        if not texto:
            raise MailError(f"Indica al menos un elemento en {nombre}.")
        if texto.startswith("["):
            datos = _json(texto, nombre)
            if not isinstance(datos, list):
                raise _textos_invalidos(valor, nombre)
            valores = datos
        else:
            partes = [parte.strip() for parte in texto.split(",")]
            valores = partes if all("@" in parte for parte in partes) else [texto]
    elif isinstance(valor, list | tuple):
        valores = list(valor)
    else:
        raise _textos_invalidos(valor, nombre)
    limpio: list[str] = []
    for item in valores:
        if not isinstance(item, str):
            raise _textos_invalidos(valor, nombre)
        texto = item.strip()
        if texto:
            limpio.append(texto)
    if not limpio:
        raise MailError(f"Indica al menos un elemento en {nombre}.")
    return limpio


def normalize_objects(valor: Any, nombre: str = "attachments") -> list[dict[str, str]] | None:
    """Normaliza una lista de objetos (adjuntos) a `list[dict[str, str]]`.

    Vale la lista y el texto JSON con la misma lista dentro. `None` se
    devuelve tal cual: son adjuntos opcionales.
    """
    if valor is None:
        return None
    if isinstance(valor, str):
        datos = _json(valor.strip(), nombre)
    elif isinstance(valor, list | tuple):
        datos = list(valor)
    else:
        raise _objetos_invalidos(valor, nombre)
    if not isinstance(datos, list):
        raise _objetos_invalidos(valor, nombre)
    limpio: list[dict[str, str]] = []
    for item in datos:
        if not isinstance(item, dict):
            raise _objetos_invalidos(valor, nombre)
        limpio.append({str(clave): str(contenido) for clave, contenido in item.items()})
    return limpio


def _entero(valor: Any) -> int | None:
    """El entero que vale `valor`, o `None` si no vale ninguno."""
    if isinstance(valor, bool):
        return None
    if isinstance(valor, int):
        return valor
    if isinstance(valor, str) and _ENTERO.fullmatch(valor.strip()):
        return int(valor.strip())
    return None


def _uids_de_lista(valores: list[Any], nombre: str) -> list[int]:
    """Los uid de una lista, sin repetir y en orden."""
    if not valores:
        raise MailError("Indica al menos un uid.")
    limpio: list[int] = []
    for valor in valores:
        numero = _entero(valor)
        if numero is None or numero < 1:
            raise MailError(
                f"{nombre} debe ser un entero mayor o igual que 1. Se recibió: {valor!r}."
            )
        if numero not in limpio:
            limpio.append(numero)
    return limpio


def _json(texto: str, nombre: str) -> Any:
    """El JSON de un texto, o un error que dice qué se recibió."""
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        raise MailError(f"{nombre} no es un texto JSON válido. Se recibió: {texto!r}.") from None


def _uids_invalidos(valor: Any, nombre: str) -> MailError:
    return MailError(
        f"{nombre} no es una lista de uid. Se recibió: {valor!r}. "
        'Valen: [21055, 21051], "[21055,21051]", "21055,21051" o "21055".'
    )


def _textos_invalidos(valor: Any, nombre: str) -> MailError:
    return MailError(
        f"{nombre} no es una lista de textos. Se recibió: {valor!r}. "
        'Valen: ["ana@example.com"], "ana@example.com" o "ana@example.com,luis@example.com".'
    )


def _objetos_invalidos(valor: Any, nombre: str) -> MailError:
    return MailError(
        f"{nombre} no es una lista de objetos. Se recibió: {valor!r}. "
        'Vale una lista, o su texto JSON: [{"filename": "a.txt", "content": "..."}].'
    )
