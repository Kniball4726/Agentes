"""Gestión y persistencia de preferencias de interfaz por usuario."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..paths import application_root


def _ruta_preferencias() -> Path:
    return application_root() / "data" / "preferencias_ui.json"


def obtener_preferencias_usuario(username: str) -> dict[str, Any]:
    """Carga las preferencias persistentes de UI para un usuario determinado."""
    ruta = _ruta_preferencias()
    if ruta.exists():
        try:
            with open(ruta, "r", encoding="utf-8") as f:
                data = json.load(f)
                return dict(data.get(username, {}) or {})
        except Exception:
            pass
    return {}


def guardar_preferencia_usuario(username: str, clave: str, valor: Any) -> None:
    """Guarda una clave de preferencia específica para un usuario determinado."""
    ruta = _ruta_preferencias()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    try:
        data: dict[str, Any] = {}
        if ruta.exists():
            try:
                with open(ruta, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = {}
        if username not in data:
            data[username] = {}
        data[username][clave] = valor
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception:
        pass
