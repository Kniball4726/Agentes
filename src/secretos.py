"""Protección de secretos (contraseñas SMTP, etc.) para que no queden en texto plano en disco.

- En Windows se usa DPAPI (``CryptProtectData``): el secreto queda atado al usuario de Windows
  que ejecuta la aplicación y no requiere gestionar claves.
- En otros sistemas se usa Fernet con una clave local generada automáticamente en
  ``data/.clave_secretos`` (permisos restringidos cuando el sistema lo permite).

Los valores cifrados se guardan con el prefijo ``enc:`` para poder distinguirlos de valores
heredados en texto plano (que se migran automáticamente al volver a guardar).
"""

from __future__ import annotations

import base64
import ctypes
import os
import sys
from ctypes import wintypes
from pathlib import Path

from .paths import application_root

PREFIJO = "enc:"
_PREFIJO_DPAPI = "dpapi:"
_PREFIJO_FERNET = "fernet:"


class SecretoError(Exception):
    """No fue posible cifrar o descifrar el secreto."""


class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _dpapi(datos: bytes, cifrar: bool) -> bytes:
    crypt32 = ctypes.windll.crypt32  # type: ignore[attr-defined]
    kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
    buffer = ctypes.create_string_buffer(datos, len(datos))
    entrada = _DataBlob(len(datos), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char)))
    salida = _DataBlob()
    funcion = crypt32.CryptProtectData if cifrar else crypt32.CryptUnprotectData
    exito = funcion(
        ctypes.byref(entrada), None, None, None, None, 0x01, ctypes.byref(salida)
    )  # 0x01 = CRYPTPROTECT_UI_FORBIDDEN
    if not exito:
        raise SecretoError("DPAPI no pudo procesar el secreto (¿otro usuario de Windows?).")
    try:
        return ctypes.string_at(salida.pbData, salida.cbData)
    finally:
        kernel32.LocalFree(salida.pbData)


def _fernet():
    from cryptography.fernet import Fernet

    ruta = application_root() / "data" / ".clave_secretos"
    ruta.parent.mkdir(parents=True, exist_ok=True)
    if not ruta.exists():
        ruta.write_bytes(Fernet.generate_key())
        try:
            os.chmod(ruta, 0o600)
        except OSError:
            pass
    return Fernet(ruta.read_bytes())


def esta_cifrado(valor: str) -> bool:
    return isinstance(valor, str) and valor.startswith(PREFIJO)


def cifrar(texto: str) -> str:
    """Devuelve el texto cifrado con prefijo ``enc:``; cadena vacía se mantiene vacía."""
    if not texto:
        return ""
    if esta_cifrado(texto):
        return texto
    datos = texto.encode("utf-8")
    if sys.platform == "win32":
        return PREFIJO + _PREFIJO_DPAPI + base64.b64encode(_dpapi(datos, True)).decode("ascii")
    return PREFIJO + _PREFIJO_FERNET + _fernet().encrypt(datos).decode("ascii")


def descifrar(valor: str) -> str:
    """Descifra un valor ``enc:...``; los valores sin prefijo se devuelven tal cual (legado)."""
    if not valor:
        return ""
    if not esta_cifrado(valor):
        return valor
    cuerpo = valor[len(PREFIJO):]
    try:
        if cuerpo.startswith(_PREFIJO_DPAPI):
            crudo = base64.b64decode(cuerpo[len(_PREFIJO_DPAPI):])
            return _dpapi(crudo, False).decode("utf-8")
        if cuerpo.startswith(_PREFIJO_FERNET):
            return _fernet().decrypt(cuerpo[len(_PREFIJO_FERNET):].encode("ascii")).decode("utf-8")
    except SecretoError:
        raise
    except Exception as error:  # noqa: BLE001
        raise SecretoError(f"No se pudo descifrar el secreto: {error}") from error
    raise SecretoError("Formato de secreto desconocido.")
