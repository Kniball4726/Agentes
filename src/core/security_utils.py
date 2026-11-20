"""Utilidades centralizadas de seguridad para rutas, nombres de archivo y URLs."""

from __future__ import annotations

import os
from pathlib import Path
import re
from typing import Iterable
import urllib.parse

_RE_COMPONENTE_INVALIDO = re.compile(r"[^A-Za-z0-9._-]+")
_RE_IMPRESORA_INSEGURA = re.compile(r"[\x00-\x1f\x7f\"'`$;|&<>{}]")
_NOMBRES_RESERVADOS_WIN = frozenset(
    {
        "con",
        "prn",
        "aux",
        "nul",
        *(f"com{i}" for i in range(1, 10)),
        *(f"lpt{i}" for i in range(1, 10)),
    }
)


def sanitizar_componente_archivo(
    valor: str,
    fallback: str = "archivo",
    max_len: int = 120,
) -> str:
    """Sanitiza un fragmento de nombre de archivo contra Path Traversal y caracteres inválidos."""
    bruto = str(valor or "").strip().replace("\\", "/")
    base = bruto.split("/")[-1]
    limpio = _RE_COMPONENTE_INVALIDO.sub("_", base).strip("._-")
    if not limpio or limpio.lower() in _NOMBRES_RESERVADOS_WIN:
        limpio = fallback
    return limpio[: max(1, int(max_len))]


def resolver_ruta_confinada(base_dir: Path, nombre_relativo: str) -> Path:
    """Resuelve una ruta relativa garantizando confinamiento estricto dentro de `base_dir`."""
    base_res = Path(base_dir).resolve()
    rel = str(nombre_relativo or "").strip()
    if not rel:
        raise ValueError("Ruta relativa vacía.")
    destino = (base_res / rel).resolve()
    if not destino.is_relative_to(base_res):
        raise ValueError("La ruta solicitada escapa del directorio permitido.")
    return destino


def ruta_en_directorios_permitidos(ruta: Path, directorios: Iterable[Path]) -> bool:
    """Verifica si `ruta` resuelta se encuentra dentro de alguno de los directorios permitidos."""
    try:
        ruta_res = Path(ruta).resolve()
    except OSError:
        return False
    for directorio in directorios:
        try:
            if ruta_res.is_relative_to(Path(directorio).resolve()):
                return True
        except (OSError, ValueError):
            continue
    return False


def es_ruta_unc_o_sistema(ruta_str: str) -> bool:
    """Detecta rutas de red UNC (`\\\\host\\recurso`) o directorios críticos del sistema operativo."""
    texto = str(ruta_str or "").strip()
    if not texto:
        return False
    if texto.startswith("\\\\") or texto.startswith("//"):
        return True
    normalizada = texto.replace("/", "\\").lower()
    if normalizada.startswith("\\\\?\\unc\\"):
        return True
    rutas_sistema = (
        os.environ.get("SystemRoot", r"C:\Windows"),
        os.environ.get("ProgramFiles", r"C:\Program Files"),
        os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
    )
    try:
        resuelta = Path(texto).resolve()
    except OSError:
        return True
    for dir_sis in rutas_sistema:
        if not dir_sis:
            continue
        try:
            if resuelta.is_relative_to(Path(dir_sis).resolve()):
                return True
        except (OSError, ValueError):
            continue
    return False


def validar_nombre_impresora_seguro(impresora: str) -> str:
    """Valida que un nombre de impresora no contenga metacaracteres de shell ni de control."""
    limpia = str(impresora or "").strip()
    if not limpia or len(limpia) > 256:
        raise ValueError("Nombre de impresora vacío o demasiado largo.")
    if _RE_IMPRESORA_INSEGURA.search(limpia):
        raise ValueError("El nombre de impresora contiene caracteres no permitidos.")
    return limpia


def es_url_navegable_segura(url: str) -> bool:
    """Autoriza solo rutas relativas `/` o URLs `http://`/`https://` con host válido."""
    limpia = str(url or "").strip()
    if not limpia or any(ord(c) < 32 for c in limpia):
        return False
    if limpia.startswith("/") and not limpia.startswith("//"):
        return True
    parsed = urllib.parse.urlparse(limpia)
    return parsed.scheme.lower() in ("http", "https") and bool(parsed.netloc)
