"""Módulo desacoplado para la emisión e impresión de rótulos térmicos y A4 de bultos."""

from __future__ import annotations
from typing import Any
from ...label_generator import (
    generar_etiquetas_bultos_pdf,
    generar_etiquetas_lote_pedidos_pdf,
    generar_etiquetas_termicas_pdf,
)


def imprimir_rotulos_termicos_pedido_ui(interfaz: Any, pedido: Any) -> None:
    """Genera e imprime el rótulo térmico individual para un pedido."""
    try:
        carpeta_rotulos = interfaz.menu.carpeta_descuentos / "Rotulos"
        ruta_pdf = generar_etiquetas_termicas_pdf(pedido, carpeta_rotulos)
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
