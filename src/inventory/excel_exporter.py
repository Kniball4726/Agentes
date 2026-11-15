"""Exportador modular del catálogo SQLite hacia formato Excel (.xlsx).

Permite volcar el estado completo del inventario desde SQLite a un archivo Excel
con reemplazo atómico, formato profesional y pestaña secundaria para inactivos.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Optional

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

from .template_sync import _reemplazar_atomicamente

if TYPE_CHECKING:
    from ..products import ProductStore

logger = logging.getLogger(__name__)


def exportar_catalogo_a_excel(
    product_store: ProductStore,
    ruta_destino: Path,
    nombre_hoja: str = "Stock",
    incluir_inactivos_hoja_separada: bool = True,
) -> int:
    """Genera o actualiza un archivo Excel con los productos activos e inactivos de SQLite.

    Retorna la cantidad total de productos activos exportados.
    """
    ruta_destino = Path(ruta_destino)
    ruta_destino.parent.mkdir(parents=True, exist_ok=True)

    todos_los_productos = product_store.list_products(solo_activos=False)
    activos = [p for p in todos_los_productos if int(p["active"]) == 1]
    inactivos = [p for p in todos_los_productos if int(p["active"]) == 0]

    libro = openpyxl.Workbook()
    # Hoja principal de stock activo
    hoja_activos = libro.active
    hoja_activos.title = nombre_hoja

    # Estilos
    fuente_encabezado_principal = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    fuente_columnas = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
    fuente_datos = Font(name="Calibri", size=10)
    relleno_encabezado = PatternFill(start_color="1F497D", end_color="1F497D", fill_type="solid")
    relleno_columnas = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
    alineacion_centro = Alignment(horizontal="center", vertical="center")
    alineacion_derecha = Alignment(horizontal="right", vertical="center")
    alineacion_izquierda = Alignment(horizontal="left", vertical="center")
    borde_fino = Border(
        left=Side(style="thin", color="D9D9D9"),
        right=Side(style="thin", color="D9D9D9"),
        top=Side(style="thin", color="D9D9D9"),
        bottom=Side(style="thin", color="D9D9D9"),
    )

    # Encabezados fila 1 y fila 3 (compatibles con el formato histórico de Productos.xlsx)
    hoja_activos.cell(1, 1, "Codigo").font = Font(name="Calibri", size=11, bold=True)
    hoja_activos.cell(1, 2, "Productos").font = Font(name="Calibri", size=11, bold=True)
    hoja_activos.cell(1, 3, "Descuento").font = Font(name="Calibri", size=11, bold=True)

    # Fila 3 encabezados de columnas operativas
    cols_encabezado = [
        (1, "Codigo", alineacion_centro),
        (2, "Productos / Descripción", alineacion_izquierda),
        (3, "Stock Inicial", alineacion_derecha),
        (4, "Descuento", alineacion_centro),
        (5, "Stock Final", alineacion_derecha),
    ]
    for col_idx, texto, alineacion in cols_encabezado:
        celda = hoja_activos.cell(3, col_idx, texto)
        celda.font = fuente_columnas
        celda.fill = relleno_columnas
        celda.alignment = alineacion

    fila_actual = 4
    for prod in activos:
        cod_raw = str(prod["code"]).strip()
        cod_val = int(cod_raw) if cod_raw.isdigit() else cod_raw
        nom_val = str(prod["name"]).strip()
        stk_val = int(prod["stock"])

        c_cod = hoja_activos.cell(fila_actual, 1, cod_val)
        c_cod.alignment = alineacion_centro
        c_cod.font = fuente_datos
        c_cod.border = borde_fino

        c_nom = hoja_activos.cell(fila_actual, 2, nom_val)
        c_nom.alignment = alineacion_izquierda
        c_nom.font = fuente_datos
        c_nom.border = borde_fino

        c_stk_ini = hoja_activos.cell(fila_actual, 3, stk_val)
        c_stk_ini.alignment = alineacion_derecha
        c_stk_ini.font = fuente_datos
        c_stk_ini.number_format = "#,##0"
        c_stk_ini.border = borde_fino

        c_desc = hoja_activos.cell(fila_actual, 4, None)
        c_desc.border = borde_fino

        c_stk_fin = hoja_activos.cell(fila_actual, 5, stk_val)
        c_stk_fin.alignment = alineacion_derecha
        c_stk_fin.font = fuente_datos
        c_stk_fin.number_format = "#,##0"
        c_stk_fin.border = borde_fino

        fila_actual += 1

    # Ajustar anchos de columnas
    hoja_activos.column_dimensions["A"].width = 14
    hoja_activos.column_dimensions["B"].width = 46
    hoja_activos.column_dimensions["C"].width = 15
    hoja_activos.column_dimensions["D"].width = 14
    hoja_activos.column_dimensions["E"].width = 15

    # Hoja de inactivos (opcional)
    if incluir_inactivos_hoja_separada and inactivos:
        hoja_inactivos = libro.create_sheet(title="Inactivos")
        hoja_inactivos.cell(1, 1, f"Catálogo de Productos Inactivos / Descontinuados ({len(inactivos)} productos)").font = Font(name="Calibri", size=11, bold=True, color="7F7F7F")
        encabezados_inact = ["Código SKU", "Descripción / Nombre", "Último Stock", "Código de Barras", "Ubicación"]
        relleno_inact = PatternFill(start_color="7F7F7F", end_color="7F7F7F", fill_type="solid")
        for c_i, nom_c in enumerate(encabezados_inact, start=1):
            c_h = hoja_inactivos.cell(3, c_i, nom_c)
            c_h.font = fuente_columnas
            c_h.fill = relleno_inact
            c_h.alignment = alineacion_centro

        f_inact = 4
        for prod in inactivos:
            cod_raw = str(prod["code"]).strip()
            cod_val = int(cod_raw) if cod_raw.isdigit() else cod_raw
            hoja_inactivos.cell(f_inact, 1, cod_val).alignment = alineacion_centro
            hoja_inactivos.cell(f_inact, 2, str(prod["name"]).strip())
            hoja_inactivos.cell(f_inact, 3, int(prod["stock"])).alignment = alineacion_derecha
            hoja_inactivos.cell(f_inact, 4, str(prod["cod_barras"] or "-")).alignment = alineacion_centro
            hoja_inactivos.cell(f_inact, 5, str(prod["ubicacion"] or "-")).alignment = alineacion_centro
            f_inact += 1

        hoja_inactivos.column_dimensions["A"].width = 14
        hoja_inactivos.column_dimensions["B"].width = 46
        hoja_inactivos.column_dimensions["C"].width = 15
        hoja_inactivos.column_dimensions["D"].width = 18
        hoja_inactivos.column_dimensions["E"].width = 15

    # Guardado atómico
    _reemplazar_atomicamente(ruta_destino, lambda p: libro.save(str(p)))
    libro.close()
    return len(activos)
