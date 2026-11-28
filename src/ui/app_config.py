"""Configuración global, constantes y utilidades de entorno para la interfaz Flet."""

from __future__ import annotations

import json
import os

from ..paths import application_root

PUERTO_WEB_DEFAULT = 8550


def _obtener_inactividad_max_minutos() -> int:
    """Lee el límite de inactividad en minutos desde la variable de entorno."""
    val = os.environ.get("STOCKAGENT_INACTIVIDAD_MINUTOS", "720")
    try:
        return int(val)
    except ValueError:
        return 720


# Tiempo de inactividad antes de cerrar sesión (por defecto 720 min = 12 h; 0 desactiva)
INACTIVIDAD_MAX_MINUTOS = _obtener_inactividad_max_minutos()


def obtener_correo_cierre_guardado() -> str:
    """Recupera los destinatarios guardados para el cierre de jornada."""
    cfg = application_root() / "data" / "config_notificaciones.json"
    if cfg.exists():
        try:
            with open(cfg, encoding="utf-8") as f:
                data = json.load(f)
                return str(data.get("correo_cierre", "") or "")
        except Exception:
            pass
    return ""


def guardar_correo_cierre(correo: str) -> None:
    """Guarda las direcciones de correo destinatarias del cierre."""
    cfg = application_root() / "data" / "config_notificaciones.json"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    try:
        data = {}
        if cfg.exists():
            with open(cfg, encoding="utf-8") as f:
                data = json.load(f)
        data["correo_cierre"] = correo.strip()
        with open(cfg, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass
