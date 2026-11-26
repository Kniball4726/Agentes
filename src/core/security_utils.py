"""Utilidades centralizadas de seguridad para rutas, nombres de archivo y URLs."""

from __future__ import annotations

import ntpath
import os
from pathlib import Path, PureWindowsPath
import posixpath
import re
import sys
from typing import Iterable
import urllib.parse

_RE_COMPONENTE_INVALIDO = re.compile(r"[^A-Za-z0-9._-]+")
_RE_IMPRESORA_INSEGURA = re.compile(r"[\x00-\x1f\x7f\"'`$;|&<>{}]")
_RUTAS_SISTEMA_POSIX = (
    "/etc",
    "/bin",
    "/sbin",
    "/usr",
    "/boot",
    "/sys",
    "/proc",
    "/dev",
    "/lib",
    "/lib64",
    "/root",
    "/var/log",
    "/var/lib",
    "/var/run",
)
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
    rel_norm = rel.replace("\\", "/")
    win_rel = PureWindowsPath(rel)
    if rel_norm.startswith("/") or win_rel.is_absolute() or bool(win_rel.drive):
        raise ValueError("La ruta solicitada escapa del directorio permitido.")
    destino = (base_res / rel_norm).resolve()
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


def _normalizar_ruta_windows(ruta_str: str) -> str:
    """Normaliza una ruta estilo Windows de forma independiente del sistema anfitrión."""
    return ntpath.normpath(ruta_str.replace("/", "\\")).lower()


def _es_ruta_sistema_windows(ruta_str: str) -> bool:
    """Evalúa si una ruta con formato Windows apunta a directorios críticos del SO."""
    normalizada = _normalizar_ruta_windows(ruta_str)
    rutas_win = (
        r"C:\Windows",
        r"C:\Program Files",
        r"C:\Program Files (x86)",
        os.environ.get("SystemRoot", ""),
        os.environ.get("ProgramFiles", ""),
        os.environ.get("ProgramFiles(x86)", ""),
    )
    for dir_sis in rutas_win:
        if not dir_sis:
            continue
        sis_norm = _normalizar_ruta_windows(dir_sis)
        if not ntpath.splitdrive(sis_norm)[0]:
            continue
        prefijo = sis_norm if sis_norm.endswith("\\") else f"{sis_norm}\\"
        if normalizada == sis_norm or normalizada.startswith(prefijo):
            return True
    return False


def _es_ruta_sistema_posix(ruta_posix: str) -> bool:
    """Evalúa si una ruta POSIX apunta a directorios críticos del sistema Linux/Unix."""
    norm = posixpath.normpath(ruta_posix)
    if not norm.startswith("/"):
        return False
    return any(norm == dir_sis or norm.startswith(f"{dir_sis}/") for dir_sis in _RUTAS_SISTEMA_POSIX)


def _es_host_windows() -> bool:
    return sys.platform == "win32" and os.name == "nt"


def es_ruta_unc_o_sistema(ruta_str: str) -> bool:
    """Detecta rutas de red UNC (`\\\\host\\recurso`) o directorios críticos Windows/POSIX."""
    texto = str(ruta_str or "").strip()
    if not texto:
        return False
    if texto.startswith("\\\\") or texto.startswith("//"):
        return True
    normalizada_win = texto.replace("/", "\\").lower()
    if normalizada_win.startswith("\\\\?\\unc\\"):
        return True

    host_windows = _es_host_windows()
    unidad_win, _ = ntpath.splitdrive(normalizada_win)
    if unidad_win:
        if _es_ruta_sistema_windows(texto):
            return True
        # En POSIX una cadena con unidad Windows (`D:\Backups`) no existe localmente.
        if not host_windows:
            return False

    if texto.startswith("/") and _es_ruta_sistema_posix(texto):
        return True

    try:
        resuelta = Path(texto).resolve()
    except OSError:
        return True

    if host_windows:
        return _es_ruta_sistema_windows(str(resuelta))
    return _es_ruta_sistema_posix(resuelta.as_posix())


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
