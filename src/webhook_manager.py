"""Gestor de Webhooks salientes para notificación y automatización de eventos."""

from __future__ import annotations

import json
import logging
import threading
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any
import uuid

from .paths import application_root

logger = logging.getLogger(__name__)

EVENTOS_DISPONIBLES: tuple[str, ...] = (
    "QUIEBRE_STOCK",
    "CIERRE_JORNADA",
    "MOVIMIENTO_RAPIDO",
)


def _ruta_webhooks() -> Path:
    return application_root() / "data" / "webhooks.json"


def obtener_webhooks() -> list[dict[str, Any]]:
    """Carga la lista de webhooks configurados desde el almacenamiento JSON."""
    ruta = _ruta_webhooks()
    if ruta.exists():
        try:
            with open(ruta, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except Exception as e:
            logger.warning("Error al leer webhooks: %s", e)
    return []


def guardar_webhook(
    url: str,
    eventos: list[str] | None = None,
    descripcion: str = "",
    activo: bool = True,
) -> dict[str, Any]:
    """Registra o actualiza una suscripción de webhook."""
    ruta = _ruta_webhooks()
    ruta.parent.mkdir(parents=True, exist_ok=True)

    webhooks = obtener_webhooks()
    webhook_id = str(uuid.uuid4())[:8]

    eventos_filtrados = [
        ev for ev in (eventos or list(EVENTOS_DISPONIBLES))
        if ev in EVENTOS_DISPONIBLES
    ]

    item = {
        "id": webhook_id,
        "url": url.strip(),
        "descripcion": descripcion.strip(),
        "eventos": eventos_filtrados or list(EVENTOS_DISPONIBLES),
        "activo": activo,
        "created_at": datetime.now().isoformat(sep=" ", timespec="seconds"),
        "ultimo_envio": "",
        "ultimo_estado": "",
    }

    webhooks.append(item)
    try:
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(webhooks, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error("Error al guardar webhooks: %s", e)

    return item


def eliminar_webhook(webhook_id: str) -> bool:
    """Elimina un webhook por su ID."""
    ruta = _ruta_webhooks()
    webhooks = obtener_webhooks()
    inicial = len(webhooks)
    webhooks = [w for w in webhooks if w.get("id") != webhook_id]
    if len(webhooks) == inicial:
        return False

    try:
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(webhooks, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        logger.error("Error al eliminar webhook: %s", e)
        return False


def probar_webhook(url: str) -> tuple[bool, str]:
    """Envía un payload de prueba (Ping) al endpoint especificado y reporta el resultado."""
    payload = {
        "event": "PING_TEST",
        "timestamp": datetime.now().isoformat(sep=" ", timespec="seconds"),
        "mensaje": "Prueba de conectividad desde StockAgent Webhook Dispatcher",
        "sistema": "StockAgent 2026",
    }
    return _enviar_http(url, payload)


def despachar_evento_webhook(evento: str, datos: dict[str, Any]) -> None:
    """Despacha un evento a todos los webhooks activos suscritos en un hilo en segundo plano."""
    webhooks = obtener_webhooks()
    destinos = [
        w["url"] for w in webhooks
        if w.get("activo", True) and evento in w.get("eventos", [])
    ]
    if not destinos:
        return

    payload = {
        "event": evento,
        "timestamp": datetime.now().isoformat(sep=" ", timespec="seconds"),
        "data": datos,
    }

    # Despachar asíncronamente en background sin bloquear la UI ni transacciones
    def _worker():
        for url in destinos:
            _enviar_http(url, payload)

    threading.Thread(target=_worker, daemon=True).start()


def _enviar_http(url: str, payload: dict[str, Any]) -> tuple[bool, str]:
    """Envía un payload JSON mediante HTTP POST con timeout estricto."""
    try:
        data_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data_bytes,
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "User-Agent": "StockAgent-Webhook/1.0",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            codigo = resp.getcode()
            if 200 <= codigo < 300:
                return True, f"HTTP {codigo} OK"
            return False, f"HTTP {codigo}"
    except urllib.error.HTTPError as he:
        return False, f"HTTP {he.code}: {he.reason}"
    except Exception as ex:
        return False, f"Error: {ex}"
