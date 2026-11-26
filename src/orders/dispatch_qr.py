"""Parsing puro de payloads QR de rótulos y construcción de respuestas de escaneo de despacho."""

from __future__ import annotations

import re
from typing import Any

from .models import Pedido


def extraer_remito_de_codigo(texto: str) -> str:
    """Extrae el número de remito de un payload QR o texto escaneado."""
    limpio = (texto or "").strip()
    coincidencia = re.search(r"REMITO:\s*([^|]+)", limpio, re.IGNORECASE)
    return coincidencia.group(1).strip() if coincidencia else limpio


def extraer_datos_qr_despacho(texto: str) -> dict[str, Any]:
    """Extrae remito, índice de bulto y total de bultos de un código QR de rótulo o texto plano."""
    limpio = (texto or "").strip()
    remito = extraer_remito_de_codigo(limpio)
    bulto_num: int | None = None
    total_bultos: int | None = None
    coinc_bulto = re.search(r"BULTOS?:\s*(\d+)\s*/\s*(\d+)", limpio, re.IGNORECASE)
    if coinc_bulto:
        try:
            bulto_num = int(coinc_bulto.group(1))
            total_bultos = int(coinc_bulto.group(2))
        except ValueError:
            bulto_num = None
            total_bultos = None
    return {
        "remito": remito,
        "bulto_num": bulto_num,
        "total_bultos": total_bultos,
    }


def construir_respuesta_escaneo(
    *,
    ok: bool,
    mensaje: str,
    pedido: Pedido | None = None,
    bultos_escaneados: list[int] | None = None,
    bultos_esperados: int = 0,
    completado: bool = False,
    duplicado: bool = False,
    requiere_confirmacion_bultos: bool = False,
) -> dict[str, Any]:
    """Construye el payload estándar de respuesta para un escaneo QR de despacho."""
    return {
        "ok": ok,
        "completado": completado,
        "duplicado": duplicado,
        "requiere_confirmacion_bultos": requiere_confirmacion_bultos,
        "mensaje": mensaje,
        "pedido": pedido,
        "bultos_escaneados": bultos_escaneados if bultos_escaneados is not None else [],
        "bultos_esperados": bultos_esperados,
    }
