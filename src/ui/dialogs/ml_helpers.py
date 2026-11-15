"""Helpers de documento y rótulos para el descuento de Mercado Libre."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import flet as ft

from ..theme import ROJO
from ...orders import calcular_hash_archivo

try:
    from docx import Document
except ImportError:
    Document = None


def generar_docx_respaldo_escaner(
    ruta_doc: Path,
    nota_ml: str,
    cliente_ml: str,
    armador_nom: str,
    total_unidades: int,
    items_pedido_store: list[tuple[str, str, int]],
) -> str:
    """Genera un archivo DOCX de respaldo del paquete escaneado y devuelve su hash SHA-256."""
    try:
        if Document is not None:
            doc = Document()
            doc.add_heading("Mercado Libre · Despacho Escáner en Vivo", level=1)
            p_meta = doc.add_paragraph()
            p_meta.add_run("Identificador / Guía: ").bold = True
            p_meta.add_run(f"{nota_ml}\n")
            p_meta.add_run("Cliente / Comprador: ").bold = True
            p_meta.add_run(f"{cliente_ml}\n")
            p_meta.add_run("Armador: ").bold = True
            p_meta.add_run(f"{armador_nom}\n")
            p_meta.add_run("Fecha: ").bold = True
            p_meta.add_run(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            p_meta.add_run("Total de unidades: ").bold = True
            p_meta.add_run(f"{total_unidades} unidades\n")

            tabla = doc.add_table(rows=1, cols=3)
            tabla.style = "Table Grid"
            hdr = tabla.rows[0].cells
            hdr[0].text = "Código (SKU)"
            hdr[1].text = "Descripción"
            hdr[2].text = "Cant."
            for cod_i, nom_i, cant_i in items_pedido_store:
                row = tabla.add_row().cells
                row[0].text = str(cod_i)
                row[1].text = str(nom_i)
                row[2].text = str(cant_i)
            doc.save(str(ruta_doc))
        else:
            ruta_doc.write_text(
                f"ML {nota_ml}\nCliente: {cliente_ml}\nTotal: {total_unidades}\n",
                encoding="utf-8",
            )
        return calcular_hash_archivo(ruta_doc)
    except Exception:
        return ""


def mostrar_prompt_rotulo_ml(
    interfaz: Any,
    ped_creado: Any,
    nota_ml: str,
    cliente_ml: str,
    bultos_val: int,
    resumen_items: str,
) -> None:
    """Muestra el diálogo opcional de impresión de rótulo A4 o térmico tras descontar el paquete."""
    if not (hasattr(interfaz, "imprimir_rotulos_pedido") and ped_creado):
        return
    try:
        def imprimir_a4(_e):
            interfaz.page.pop_dialog()
            interfaz.imprimir_rotulos_pedido(ped_creado)

        def imprimir_termico(_e):
            interfaz.page.pop_dialog()
            if hasattr(interfaz, "imprimir_rotulos_termicos_pedido"):
                interfaz.imprimir_rotulos_termicos_pedido(ped_creado)
            else:
                interfaz.imprimir_rotulos_pedido(ped_creado)

        dialogo_prompt = ft.AlertDialog(
            modal=True,
            title=ft.Row([ft.Icon(ft.Icons.CHECK_CIRCLE, color=ft.Colors.GREEN_400), ft.Text("Paquete ML Descontado")]),
            content=ft.Container(
                width=420,
                content=ft.Column(
                    [
                        ft.Text(f"Paquete #{nota_ml} registrado con éxito.", size=13, weight=ft.FontWeight.W_500),
                        ft.Text(f"• Comprador: {cliente_ml} · Bultos: {bultos_val}", size=12, color=interfaz.secundario),
                        ft.Text(f"• Descuento: {resumen_items} en tiempo real.", size=12, color=ft.Colors.GREEN_400),
                        ft.Divider(height=10),
                        ft.Text("¿Deseas imprimir el rótulo para el paquete?", size=12, color=interfaz.texto),
                    ],
                    tight=True,
                    spacing=6,
                ),
            ),
            actions=[
                ft.Button("Rótulo A4", icon=ft.Icons.PRINT, bgcolor=ROJO, color=ft.Colors.WHITE, on_click=imprimir_a4),
                ft.Button("Rótulo Térmico", icon=ft.Icons.LABEL, bgcolor=ft.Colors.PURPLE_700, color=ft.Colors.WHITE, on_click=imprimir_termico),
                interfaz.boton_dialogo("Omitir", lambda _e: interfaz.page.pop_dialog()),
            ],
        )
        interfaz.page.show_dialog(dialogo_prompt)
    except Exception:
        pass
