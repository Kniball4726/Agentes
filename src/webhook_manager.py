"""Gestor de Webhooks salientes para notificación y automatización de eventos."""

from __future__ import annotations

import json
import logging
import os
import threading
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any
import uuid

from . import secretos
from .core.environment import resolver_data_dir_para_raiz
from .core.network_security import (
    NoRedirectHandler,
    crear_contexto_tls_estricto,
    firmar_payload_hmac,
    validar_url_externa_segura,
)
from .paths import application_root

logger = logging.getLogger(__name__)

EVENTOS_DISPONIBLES: tuple[str, ...] = (
    "QUIEBRE_STOCK",
    "CIERRE_JORNADA",
    "MOVIMIENTO_RAPIDO",
)


def _ruta_webhooks() -> Path:
    return resolver_data_dir_para_raiz(application_root()) / "webhooks.json"


def _permitir_lan_webhooks() -> bool:
    return os.environ.get("STOCKAGENT_ALLOW_LAN_WEBHOOKS", "0").strip() == "1"


def obtener_webhooks() -> list[dict[str, Any]]:
    """Carga la lista de webhooks configurados desde el almacenamiento JSON."""
    ruta = _ruta_webhooks()
    if ruta.exists():
        try:
            with open(ruta, encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except Exception as e:
            logger.warning("Error al leer webhooks: %s", e)
    return []


def _validar_url_webhook(url: str, *, resolver_dns: bool = False) -> str:
    return validar_url_externa_segura(
        url,
        resolver_dns=resolver_dns,
        permitir_lan_privada=_permitir_lan_webhooks(),
    )


def guardar_webhook(
    url: str,
    eventos: list[str] | None = None,
    descripcion: str = "",
    activo: bool = True,
    secreto: str = "",
) -> dict[str, Any]:
    """Registra o actualiza una suscripción de webhook."""
    url_valida = _validar_url_webhook(url, resolver_dns=False)
    ruta = _ruta_webhooks()
    ruta.parent.mkdir(parents=True, exist_ok=True)

    webhooks = obtener_webhooks()
    webhook_id = str(uuid.uuid4())[:8]

    eventos_filtrados = [
        ev for ev in (eventos or list(EVENTOS_DISPONIBLES))
        if ev in EVENTOS_DISPONIBLES
    ]

    secreto_limpio = str(secreto or "").strip()
    item = {
        "id": webhook_id,
        "url": url_valida,
        "descripcion": descripcion.strip(),
        "eventos": eventos_filtrados or list(EVENTOS_DISPONIBLES),
        "activo": activo,
        "secreto": secretos.cifrar(secreto_limpio) if secreto_limpio else "",
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


def _resolver_secreto_webhook(item: dict[str, Any] | None = None) -> str:
    raw = str((item or {}).get("secreto", "") or "").strip()
    if raw:
        try:
            return secretos.descifrar(raw)
        except secretos.SecretoError:
            return ""
    return os.environ.get("STOCKAGENT_WEBHOOK_SECRET", "").strip()


def probar_webhook(url: str, secreto: str = "") -> tuple[bool, str]:
    """Envía un payload de prueba (Ping) al endpoint especificado y reporta el resultado."""
    payload = {
        "event": "PING_TEST",
        "timestamp": datetime.now().isoformat(sep=" ", timespec="seconds"),
        "mensaje": "Prueba de conectividad desde StockAgent Webhook Dispatcher",
        "sistema": "StockAgent 2026",
    }
    return _enviar_http(url, payload, secreto=secreto or os.environ.get("STOCKAGENT_WEBHOOK_SECRET", "").strip())


def despachar_evento_webhook(evento: str, datos: dict[str, Any]) -> None:
    """Despacha un evento a todos los webhooks activos suscritos en un hilo en segundo plano."""
    webhooks = obtener_webhooks()
    destinos = [
        (w["url"], _resolver_secreto_webhook(w)) for w in webhooks
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
        for url, sec in destinos:
            _enviar_http(url, payload, secreto=sec)

    threading.Thread(target=_worker, daemon=True).start()


def _enviar_http(url: str, payload: dict[str, Any], *, secreto: str = "") -> tuple[bool, str]:
    """Envía un payload JSON mediante HTTP/HTTPS POST sin redirecciones, con anti-SSRF y firma HMAC."""
    try:
        url_valida = _validar_url_webhook(url, resolver_dns=True)
        data_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": "StockAgent-Webhook/1.0",
            **firmar_payload_hmac(data_bytes, secreto),
        }
        req = urllib.request.Request(
            url_valida,
            data=data_bytes,
            headers=headers,
            method="POST",
        )
        opener = urllib.request.build_opener(
            NoRedirectHandler(),
            urllib.request.HTTPSHandler(context=crear_contexto_tls_estricto()),
        )
        with opener.open(req, timeout=8) as resp:
            codigo = resp.getcode()
            if 200 <= codigo < 300:
                return True, f"HTTP {codigo} OK"
            return False, f"HTTP {codigo}"
    except urllib.error.HTTPError as he:
        return False, f"HTTP {he.code}: {he.reason}"
    except Exception as ex:
        return False, f"Error: {ex}"
