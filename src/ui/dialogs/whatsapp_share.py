"""Utilidades de compartición por WhatsApp Web para informes y estado de pedidos."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import urllib.parse
import webbrowser

import flet as ft

from ...auth import USER_ROLES


def abrir_url_whatsapp(interfaz: Any, url: str) -> None:
    """Abre una URL de WhatsApp Web usando el navegador del cliente web o el SO."""
    es_web = bool(getattr(getattr(interfaz, "page", None), "web", False))
    if es_web and hasattr(interfaz, "abrir_url_en_navegador"):
        interfaz.abrir_url_en_navegador(url)
        return
    if not webbrowser.open(url):
        raise RuntimeError("No se pudo abrir WhatsApp Web.")


def compartir_whatsapp(
    interfaz: Any,
    _evento: ft.Event | None = None,
    ruta_especifica: Path | None = None,
) -> None:
    """Abre la carpeta del informe y redirige a WhatsApp Web."""
    if not interfaz.exigir_roles(*USER_ROLES):
        return
    ruta = ruta_especifica or interfaz.ruta_informe()
    if ruta is None:
        return
    try:
        if not bool(getattr(getattr(interfaz, "page", None), "web", False)):
            interfaz.abrir_carpeta_informe(ruta)
        abrir_url_whatsapp(interfaz, "https://web.whatsapp.com/")
    except (OSError, RuntimeError) as error:
        interfaz.notificar(f"No se pudo abrir WhatsApp o el archivo:\n{error}")


def construir_mensaje_whatsapp_pedido(pedido: Any) -> str:
    """Formatea el mensaje de estado del pedido listo para enviar por WhatsApp."""
    cliente = getattr(pedido, "cliente", "Cliente") or "Cliente"
    remito = getattr(pedido, "nota_pedido", "") or ""
    bultos = getattr(pedido, "bultos", 1) or 1
    logistica = getattr(pedido, "logistica", "") or "A convenir"
    guia = getattr(pedido, "numero_guia", "") or ""

    lineas = [
        f"Hola *{cliente}*, te informamos el estado de tu pedido:",
        f"📋 *Remito:* {remito}",
        f"📦 *Bultos preparados:* {bultos}",
        f"🚚 *Logística / Transporte:* {logistica}",
    ]
    if guia:
        lineas.append(f"🔖 *N° de Guía:* {guia}")
    lineas.append("\n_StockAgent - Control de Inventario y Despachos_")
    return "\n".join(lineas)


def compartir_whatsapp_pedido(interfaz: Any, pedido: Any, telefono: str = "") -> None:
    """Abre WhatsApp Web con un mensaje preformateado con el estado del remito y bultos."""
    if not interfaz.exigir_roles(*USER_ROLES):
        return
    texto_encoded = urllib.parse.quote(construir_mensaje_whatsapp_pedido(pedido))
    tel_clean = "".join(c for c in str(telefono) if c.isdigit())
    if tel_clean:
        url = f"https://web.whatsapp.com/send?phone={tel_clean}&text={texto_encoded}"
    else:
        url = f"https://web.whatsapp.com/send?text={texto_encoded}"

    try:
        abrir_url_whatsapp(interfaz, url)
    except Exception as error:
        interfaz.notificar(f"No se pudo abrir WhatsApp:\n{error}")
