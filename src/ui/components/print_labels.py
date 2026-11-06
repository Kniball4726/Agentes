"""Módulo desacoplado para la emisión e impresión de rótulos térmicos y A4 de bultos."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from ...label_generator import (
    generar_etiquetas_bultos_pdf,
    generar_etiquetas_lote_pedidos_pdf,
    generar_etiquetas_termicas_pdf,
)
from ..user_preferences import obtener_preferencias_usuario


def listar_impresoras_sistema() -> list[str]:
    """Lista las impresoras instaladas en el sistema operativo Windows."""
    try:
        cmd = [
            "powershell",
            "-NoProfile",
            "-Command",
            "Get-CimInstance Win32_Printer | Select-Object -ExpandProperty Name",
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=6)
        if res.returncode == 0:
            lineas = [l.strip() for l in res.stdout.splitlines() if l.strip()]
            return sorted(lineas)
    except Exception:
        pass
    return []


def imprimir_directo_spooler(ruta_pdf: Path, impresora: str) -> bool:
    """Envía un archivo PDF a la cola de impresión de Windows de forma desatendida."""
    if not ruta_pdf.exists() or not impresora:
        return False
    try:
        cmd = [
            "powershell",
            "-NoProfile",
            "-Command",
            f"Start-Process -FilePath '{ruta_pdf.resolve()}' -Verb PrintTo -ArgumentList '\"{impresora}\"' -PassThru | Out-Null",
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return res.returncode == 0
    except Exception:
        return False


def imprimir_rotulos_termicos_pedido_ui(interfaz: Any, pedido: Any) -> None:
    """Genera e imprime el rótulo térmico individual para un pedido."""
    try:
        carpeta_rotulos = interfaz.menu.carpeta_descuentos / "Rotulos"
        ruta_pdf = generar_etiquetas_termicas_pdf(pedido, carpeta_rotulos)

        # Verificar si el usuario tiene configurada impresión directa a impresora térmica
        usuario = getattr(interfaz.usuario_actual, "username", "")
        prefs = obtener_preferencias_usuario(usuario) if usuario else {}
        impresora_termica = prefs.get("impresora_termica", "")
        modo_directo = bool(prefs.get("impresion_directa", False))

        if modo_directo and impresora_termica:
            exito = imprimir_directo_spooler(ruta_pdf, impresora_termica)
            if exito:
                interfaz.notificar(
                    f"✅ Rótulo térmico enviado a la impresora '{impresora_termica}' ({pedido.bultos} bultos)."
                )
                return

        interfaz.abrir_informe(ruta_especifica=ruta_pdf)
        interfaz.notificar(f"Rótulo térmico para {pedido.bultos} bulto(s) generado con éxito ({ruta_pdf.name}).")
    except Exception as error:
        interfaz.notificar(f"Error generando rótulo térmico: {error}")


def imprimir_rotulos_pedido_ui(interfaz: Any, pedido: Any, llenar_hoja: bool = False) -> None:
    """Genera e imprime las etiquetas de bulto estándar A4 para un pedido."""
    try:
        ruta_pdf = generar_etiquetas_bultos_pdf(pedido, interfaz.menu.carpeta_descuentos, llenar_hoja=llenar_hoja)
        interfaz.abrir_informe(ruta_especifica=ruta_pdf)
        interfaz.notificar(f"Rótulos para {pedido.bultos} bulto(s) generados con éxito ({ruta_pdf.name}).")
    except Exception as error:
        interfaz.notificar(f"Error generando rótulos de bulto:\n{error}")


def imprimir_rotulos_lote_ui(interfaz: Any, pedidos: list[Any], llenar_hoja: bool = False) -> None:
    """Genera e imprime en una sola planilla A4 el lote de rótulos de despacho."""
    try:
        pedidos_validos = [p for p in pedidos if getattr(p, "estado", "") != "anulado" and getattr(p, "bultos", 0) > 0]
        if not pedidos_validos:
            interfaz.notificar("No hay pedidos válidos con bultos para generar rótulos.")
            return
        ruta_pdf = generar_etiquetas_lote_pedidos_pdf(pedidos_validos, interfaz.menu.carpeta_descuentos, llenar_hoja=llenar_hoja)
        interfaz.abrir_informe(ruta_especifica=ruta_pdf)
        total_bultos = sum(p.bultos for p in pedidos_validos)
        interfaz.notificar(f"Rótulos para {len(pedidos_validos)} pedido(s) ({total_bultos} bultos) generados en A4 ({ruta_pdf.name}).")
    except Exception as error:
        interfaz.notificar(f"Error generando lote de rótulos:\n{error}")
