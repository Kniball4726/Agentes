"""Utilidades de red, portapapeles e imágenes con badges para System Tray."""

from __future__ import annotations

import socket
import subprocess
import sys
from pathlib import Path
from typing import Optional

from ..logger_config import configurar_logging
from ..paths import application_root

logger = configurar_logging()

ESTADO_INICIANDO = "iniciando"
ESTADO_ONLINE = "online"
ESTADO_CLIENTE = "cliente_conectado"
ESTADO_ERROR = "error"
ESTADO_DETENIDO = "detenido"

TEXTOS_ESTADO = {
    ESTADO_INICIANDO: "🟡 Iniciando...",
    ESTADO_ONLINE: "🟢 En línea",
    ESTADO_CLIENTE: "🔵 Dispositivo conectado",
    ESTADO_ERROR: "🔴 Desconectado / Error",
    ESTADO_DETENIDO: "⚪ Detenido",
}

COLORES_BADGE = {
    ESTADO_INICIANDO: (234, 179, 8, 255),
    ESTADO_ONLINE: (34, 197, 94, 255),
    ESTADO_CLIENTE: (59, 130, 246, 255),
    ESTADO_ERROR: (239, 68, 68, 255),
    ESTADO_DETENIDO: (156, 163, 175, 255),
}


def _obtener_ip_local() -> str:
    """Devuelve la dirección IP del equipo en la red local (LAN)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(0.2)
            s.connect(("8.8.8.8", 80))
            return str(s.getsockname()[0])
    except Exception:
        try:
            return str(socket.gethostbyname(socket.gethostname()))
        except Exception:
            return "127.0.0.1"


def _obtener_ip_tailscale() -> Optional[str]:
    """Busca una dirección IPv4 de Tailscale asignada a la máquina (100.64.0.0/10)."""
    try:
        host = socket.gethostname()
        for item in socket.getaddrinfo(host, None, socket.AF_INET):
            ip = item[4][0]
            if ip.startswith("100."):
                partes = [int(p) for p in ip.split(".") if p.isdigit()]
                if len(partes) == 4 and 64 <= partes[1] <= 127:
                    return ip
    except Exception:
        pass
    return None


def _copiar_al_portapapeles(texto: str) -> bool:
    """Copia una cadena de texto al portapapeles nativo de Windows."""
    try:
        subprocess.run(
            "clip",
            input=texto.encode("utf-16"),
            shell=True,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except Exception as exc:
        logger.warning("No se pudo copiar al portapapeles: %s", exc)
        return False


def _buscar_icono_base() -> Optional[Path]:
    """Busca la imagen base del logotipo para el icono de la bandeja."""
    candidatos = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        p = Path(meipass)
        candidatos.extend([
            p / "src" / "img" / "ultratech.png",
            p / "assets" / "favicon.png",
            p / "assets" / "icons" / "icon-192.png",
        ])

    app_root = application_root()
    candidatos.extend([
        app_root / "src" / "img" / "ultratech.png",
        app_root / "assets" / "favicon.png",
        app_root / "assets" / "icons" / "icon-192.png",
        Path(__file__).resolve().parent.parent / "img" / "ultratech.png",
    ])

    for ruta in candidatos:
        if ruta.is_file():
            return ruta
    return None


def describir_dispositivo(agente: str) -> str:
    """Devuelve un nombre legible del dispositivo a partir del User-Agent."""
    ua = (agente or "").lower()
    if "android" in ua:
        return "Celular Android"
    if "iphone" in ua:
        return "iPhone"
    if "ipad" in ua:
        return "iPad"
    if "windows" in ua:
        return "PC Windows"
    if "macintosh" in ua or "mac os" in ua:
        return "Mac"
    if "linux" in ua:
        return "Equipo Linux"
    if "dart" in ua or "okhttp" in ua:
        return "App móvil StockAgent"
    return "Dispositivo"


def generar_imagen_estado(estado: str):
    """Genera el ícono PIL 64x64 con el badge circular del estado actual."""
    try:
        from PIL import Image, ImageDraw

        ruta_base = _buscar_icono_base()
        if ruta_base and ruta_base.exists():
            base = Image.open(ruta_base).convert("RGBA").resize((64, 64), Image.Resampling.LANCZOS)
        else:
            base = Image.new("RGBA", (64, 64), color=(0, 0, 0, 0))
            draw_bg = ImageDraw.Draw(base)
            draw_bg.rounded_rectangle(
                (4, 4, 60, 60),
                radius=12,
                fill=(30, 41, 59, 255),
                outline=(71, 85, 105, 255),
                width=2,
            )

        draw = ImageDraw.Draw(base)
        color_badge = COLORES_BADGE.get(estado, COLORES_BADGE[ESTADO_INICIANDO])
        draw.ellipse((36, 36, 64, 64), fill=(255, 255, 255, 255))
        draw.ellipse((38, 38, 62, 62), fill=color_badge)
        if estado == ESTADO_CLIENTE:
            draw.line(
                [(44, 50), (49, 55), (57, 43)],
                fill=(255, 255, 255, 255),
                width=3,
                joint="curve",
            )
        return base
    except Exception as exc:
        logger.error("Error al generar imagen para System Tray: %s", exc)
        try:
            from PIL import Image
            return Image.new("RGBA", (16, 16), color=(34, 197, 94, 255))
        except Exception:
            return None
