"""Módulo de sincronización y generación de reportes con plantillas Excel."""

from __future__ import annotations

import unicodedata
from copy import copy
from pathlib import Path
from typing import List, Optional, Tuple

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

from ..core.sanitize_utils import sanitizar_celda_excel
from openpyxl.utils import get_column_letter

from ..parsers.remito_parser import ResultadoRemito
from ..stock.reports import copiar_estilo_fila


def normalizar_encabezado(valor: object) -> str:
    """Normaliza un encabezado de celda quitando acentos y espacios superfluos."""
    texto = unicodedata.normalize("NFKD", str(valor or ""))
    return "".join(caracter for caracter in texto if not unicodedata.combining(caracter)).strip().upper()


def detectar_esquema(sheet: openpyxl.worksheet.worksheet.Worksheet) -> dict[str, int | None]:
    """Detecta las columnas de código, nombre y stocks en una hoja Excel."""
    encabezados_codigo = {"CODIGO", "COD"}
    encabezados_nombre = {"PRODUCTO", "PRODUCTOS", "DESCRIPCION", "ARTICULO"}
    fila_encabezados = None
    columnas: dict[str, int] = {}
    filas_stock: list[int] = []
    col_stock_inicial: int | None = None
    col_descuento: int | None = None
    col_stock_final: int | None = None

    for fila in range(1, min(sheet.max_row, 14) + 1):
        fila_actual: dict[str, int] = {}
        for columna in range(1, sheet.max_column + 1):
            valor = normalizar_encabezado(sheet.cell(fila, columna).value)
            if valor in encabezados_codigo:
                fila_actual["codigo"] = columna
            elif valor in encabezados_nombre:
                fila_actual["nombre"] = columna
            elif valor == "STOCK INICIAL":
                col_stock_inicial = columna
                filas_stock.append(fila)
            elif valor == "DESCUENTO":
                col_descuento = columna
                filas_stock.append(fila)
            elif valor == "STOCK FINAL":
                col_stock_final = columna
                filas_stock.append(fila)

        if "codigo" in fila_actual and "nombre" in fila_actual:
            fila_encabezados = fila
            columnas = fila_actual

    if fila_encabezados is None:
        return {
            "col_codigo": 1,
            "col_nombre": 2,
            "col_stock": 3,
            "col_stock_inicial": None,
            "col_descuento": None,
            "col_stock_final": None,
            "fila_inicio_datos": 3,
        }

    return {
        "col_codigo": columnas["codigo"],
        "col_nombre": columnas["nombre"],
        "col_stock": col_stock_inicial or 3,
        "col_stock_inicial": col_stock_inicial,
        "col_descuento": col_descuento,
        "col_stock_final": col_stock_final,
        "fila_inicio_datos": max(3, fila_encabezados + 1, *(fila + 1 for fila in filas_stock)),
    }


def leer_stock(
    sheet: openpyxl.worksheet.worksheet.Worksheet,
    fila: int,
    col_stock_final: int | None,
    col_stock_inicial: int | None,
    col_stock: int,
) -> int:
    """Lee el valor numérico de stock de una fila en la hoja de cálculo."""
    columnas_stock = [col_stock_final, col_stock_inicial or col_stock]
    for columna in columnas_stock:
        if columna is None:
            continue
        valor = sheet.cell(row=fila, column=columna).value
        if valor is None or not str(valor).strip():
            continue
        try:
            return int(round(float(str(valor).replace(",", "."))))
        except (ValueError, TypeError):
            continue
    return 0


def _crear_plantilla_virtual(nombre_hoja: str) -> openpyxl.Workbook:
    """Construye una plantilla estilizada en memoria cuando no existe `Productos.xlsx`."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = (nombre_hoja or "Stock")[:31]
    ws.column_dimensions["A"].width = 14
    ws.column_dimensions["B"].width = 48
    ws.column_dimensions["C"].width = 22
    ws.column_dimensions["D"].width = 22
    ws["A1"] = "CODIGO"
    ws["B1"] = "PRODUCTOS"
    ws["C1"] = "DESCUENTO"
    ws["B3"] = "PRODUCTOS"
    ws["C3"] = "DESCUENTO"
    fuente_base = Font(name="Arial", size=9)
    borde_base = Border(
        left=Side(style="thin", color="E2E8F0"),
        right=Side(style="thin", color="E2E8F0"),
        top=Side(style="thin", color="E2E8F0"),
        bottom=Side(style="thin", color="E2E8F0"),
    )
    for fila in (1, 2, 3, 4):
        for col in range(1, 5):
            celda = ws.cell(fila, col)
            celda.font = copy(fuente_base)
            celda.border = copy(borde_base)
    return wb


def crear_informe_desde_plantilla(
    ruta_excel_base: Optional[Path],
    nombre_hoja: str,
    col_codigo: int,
    col_nombre: int,
    col_descuento: int | None,
    col_stock: int,
    col_stock_inicial: int | None,
    fila_inicio_datos: int,
    cantidad_descuentos: int,
    unidades_descontadas: int,
    fecha_generacion: str,
    filas_productos: List[Tuple[int, str, Optional[int], str, Optional[int]]],
    pedidos_descontados: List[ResultadoRemito],
    productos_sin_coincidencia: List[Tuple[str, str, str, str]],
) -> Tuple[openpyxl.Workbook, openpyxl.worksheet.worksheet.Worksheet]:
    """Genera el libro de Excel para el informe usando la plantilla si existe o estilos en memoria."""
    if ruta_excel_base and Path(ruta_excel_base).exists():
        libro_plantilla = openpyxl.load_workbook(ruta_excel_base)
    else:
        libro_plantilla = _crear_plantilla_virtual(nombre_hoja)
    hoja_plantilla = (
        libro_plantilla[nombre_hoja]
        if nombre_hoja in libro_plantilla.sheetnames
        else libro_plantilla.active
    )
    libro_salida = openpyxl.Workbook()
    hoja_salida = libro_salida.active
    hoja_salida.title = hoja_plantilla.title[:31]
    hoja_salida.sheet_view.showGridLines = hoja_plantilla.sheet_view.showGridLines
    hoja_salida.page_setup.orientation = "portrait"
    hoja_salida.page_setup.paperSize = hoja_salida.PAPERSIZE_A4
    hoja_salida.page_setup.fitToWidth = 1
    hoja_salida.page_setup.fitToHeight = 0
    hoja_salida.sheet_properties.pageSetUpPr.fitToPage = True
    margen_cm = 2 / 2.54
    hoja_salida.page_margins.left = margen_cm
    hoja_salida.page_margins.right = margen_cm
    hoja_salida.page_margins.top = margen_cm
    hoja_salida.page_margins.bottom = margen_cm
    hoja_salida.freeze_panes = "A4"

    def copiar_estilo(origen, destino) -> None:
        if not origen.has_style:
            return
        destino.font = copy(origen.font)
        destino.fill = copy(origen.fill)
        destino.border = copy(origen.border)
        destino.alignment = copy(origen.alignment)
        destino.number_format = origen.number_format
        destino.protection = copy(origen.protection)

    def aplicar_encabezado(fila: int, color_fondo: str, cantidad_columnas: int = 4) -> None:
        for columna in range(1, cantidad_columnas + 1):
            celda = hoja_salida.cell(fila, columna)
            celda.fill = PatternFill("solid", fgColor=color_fondo)
            celda.font = Font(name="Arial", size=9, bold=True, color="17365D")
            celda.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            celda.border = Border(bottom=Side(style="thin", color="D9E2F3"))

    def aplicar_titulo_seccion(fila: int, color_fondo: str) -> None:
        celda = hoja_salida.cell(fila, 1)
        celda.fill = PatternFill("solid", fgColor=color_fondo)
        celda.font = Font(name="Arial", size=11, bold=True, color="17365D")
        celda.alignment = Alignment(vertical="center", wrap_text=True)

    columnas_plantilla = (
        col_codigo,
        col_nombre,
        col_descuento or col_stock,
    )
    for columna_salida, columna_plantilla in enumerate(columnas_plantilla, start=1):
        letra_salida = get_column_letter(columna_salida)
        letra_plantilla = get_column_letter(columna_plantilla)
        dimension = hoja_plantilla.column_dimensions[letra_plantilla]
        ancho = dimension.width
        if columna_salida == 3:
            ancho = max(ancho or 0, 22)
        hoja_salida.column_dimensions[letra_salida].width = ancho
        hoja_salida.column_dimensions[letra_salida].hidden = dimension.hidden

    for fila in range(1, 4):
        hoja_salida.row_dimensions[fila].height = hoja_plantilla.row_dimensions[fila].height
        for columna_salida, columna_plantilla in enumerate(columnas_plantilla, start=1):
            origen = hoja_plantilla.cell(fila, columna_plantilla)
            destino = hoja_salida.cell(fila, columna_salida)
            copiar_estilo(origen, destino)

    for encabezado in ("A1:A2", "B1:B2", "C1:D2"):
        hoja_salida.merge_cells(encabezado)
    hoja_salida["A1"] = hoja_plantilla.cell(1, col_codigo).value or "CODIGO"
    hoja_salida["B1"] = hoja_plantilla.cell(1, col_nombre).value or "PRODUCTOS"
    hoja_salida["C1"] = f"FECHA: {fecha_generacion}"
    aplicar_encabezado(1, "D9EAF7", 3)
    hoja_salida["D1"].fill = PatternFill("solid", fgColor="D9EAF7")
    hoja_salida["D1"].border = Border(bottom=Side(style="thin", color="D9E2F3"))

    encabezado_productos = hoja_plantilla.cell(3, col_nombre).value
    hoja_salida["B3"] = (
        encabezado_productos
        if col_stock_inicial is not None and encabezado_productos
        else "PRODUCTOS"
    )
    hoja_salida["C3"] = "DESCUENTO"
    hoja_salida["C3"].number_format = "@"
    aplicar_encabezado(3, "D9EAF7", 3)
    hoja_salida.row_dimensions[1].height = 48
    hoja_salida.row_dimensions[2].height = 10
    hoja_salida.row_dimensions[3].height = 24

    fila_estilo_producto = min(
        max(fila_inicio_datos, 1),
        max(hoja_plantilla.max_row, 1),
    )
    for fila_salida, producto in enumerate(filas_productos, start=4):
        fila_original, codigo, unidades, nombre, descuento = producto
        fila_estilo = (
            fila_original
            if 0 < fila_original <= hoja_plantilla.max_row
            else fila_estilo_producto
        )
        hoja_salida.row_dimensions[fila_salida].height = hoja_plantilla.row_dimensions[fila_estilo].height
        for columna_salida, columna_plantilla in enumerate(columnas_plantilla, start=1):
            origen = hoja_plantilla.cell(fila_estilo, columna_plantilla)
            destino = hoja_salida.cell(fila_salida, columna_salida)
            copiar_estilo(origen, destino)
        codigo_salida = int(codigo) if codigo.isdigit() else sanitizar_celda_excel(codigo)
        hoja_salida.cell(fila_salida, 1, codigo_salida)
        hoja_salida.cell(fila_salida, 2, sanitizar_celda_excel(nombre))
        if descuento is not None:
            hoja_salida.cell(fila_salida, 3, descuento).number_format = "0"

    fila_actual = 4 + len(filas_productos)
    hoja_salida.cell(fila_actual, 2, "TOTAL CÓDIGOS DE PRODUCTO DESCONTADOS:")
    hoja_salida.cell(fila_actual, 3, cantidad_descuentos)
    _copiar_estilo_fila_helper(
        hoja_plantilla, hoja_salida, 3, fila_actual, 3,
        col_codigo, col_nombre, col_descuento or col_stock, col_stock
    )
    for columna in range(1, 4):
        celda = hoja_salida.cell(fila_actual, columna)
        celda.fill = PatternFill("solid", fgColor="D9EAF7")
        celda.font = Font(name="Arial", size=10, bold=True, color="17365D")
        celda.alignment = Alignment(vertical="center", wrap_text=True)
    fila_actual += 1
    hoja_salida.cell(fila_actual, 2, "TOTAL UNIDADES DESCONTADAS:")
    hoja_salida.cell(fila_actual, 3, unidades_descontadas)
    _copiar_estilo_fila_helper(
        hoja_plantilla, hoja_salida, 3, fila_actual, 3,
        col_codigo, col_nombre, col_descuento or col_stock, col_stock
    )
    for columna in range(1, 4):
        celda = hoja_salida.cell(fila_actual, columna)
        celda.fill = PatternFill("solid", fgColor="D9EAF7")
        celda.font = Font(name="Arial", size=10, bold=True, color="17365D")
        celda.alignment = Alignment(vertical="center", wrap_text=True)
    fila_actual += 1
    hoja_salida.merge_cells(start_row=fila_actual, start_column=1, end_row=fila_actual, end_column=4)
    hoja_salida.cell(fila_actual, 1, "PEDIDOS CON PRODUCTOS DESCONTADOS")
    _copiar_estilo_fila_helper(
        hoja_plantilla, hoja_salida, 3, fila_actual, 4,
        col_codigo, col_nombre, col_descuento or col_stock, col_stock
    )
    aplicar_titulo_seccion(fila_actual, "EAF0F6")
    fila_actual += 1
    for columna, titulo in enumerate(("TIPO", "CLIENTE", "N° REMITO / PEDIDO"), start=1):
        hoja_salida.cell(fila_actual, columna, titulo)
    _copiar_estilo_fila_helper(
        hoja_plantilla, hoja_salida, 3, fila_actual, 4,
        col_codigo, col_nombre, col_descuento or col_stock, col_stock
    )
    aplicar_encabezado(fila_actual, "D9EAF7")
    if pedidos_descontados:
        for documento in pedidos_descontados:
            fila_actual += 1
            if documento.archivo.lower().endswith(".pdf"):
                tipo = "Remito Mayorista"
            elif documento.archivo.lower().endswith(".docx"):
                tipo = "Mercado Libre"
            else:
                tipo = "Canje"
            for columna, valor in enumerate((tipo, documento.cliente, str(documento.numero_remito)), start=1):
                hoja_salida.cell(fila_actual, columna, sanitizar_celda_excel(valor))
            _copiar_estilo_fila_helper(
                hoja_plantilla, hoja_salida, fila_estilo_producto, fila_actual, 4,
                col_codigo, col_nombre, col_descuento or col_stock, col_stock
            )
    else:
        fila_actual += 1
        hoja_salida.merge_cells(start_row=fila_actual, start_column=1, end_row=fila_actual, end_column=4)
        hoja_salida.cell(fila_actual, 1, "No hubo pedidos con productos descontados.")
        _copiar_estilo_fila_helper(
            hoja_plantilla, hoja_salida, fila_estilo_producto, fila_actual, 4,
            col_codigo, col_nombre, col_descuento or col_stock, col_stock
        )
    fila_actual += 1

    if productos_sin_coincidencia:
        hoja_salida.merge_cells(start_row=fila_actual, start_column=1, end_row=fila_actual, end_column=4)
        hoja_salida.cell(fila_actual, 1, "PRODUCTOS NO DESCONTADOS - SIN COINCIDENCIA")
        _copiar_estilo_fila_helper(
            hoja_plantilla, hoja_salida, 3, fila_actual, 4,
            col_codigo, col_nombre, col_descuento or col_stock, col_stock
        )
        aplicar_titulo_seccion(fila_actual, "FCE4D6")
        fila_actual += 1
        for columna, titulo in enumerate(("CÓDIGO", "ARCHIVO / PEDIDO", "PRODUCTO / DESCRIPCIÓN", "MOTIVO"), start=1):
            hoja_salida.cell(fila_actual, columna, titulo)
        _copiar_estilo_fila_helper(
            hoja_plantilla, hoja_salida, 3, fila_actual, 4,
            col_codigo, col_nombre, col_descuento or col_stock, col_stock
        )
        aplicar_encabezado(fila_actual, "D9EAF7")
        for codigo, archivo, descripcion, motivo in productos_sin_coincidencia:
            fila_actual += 1
            hoja_salida.cell(fila_actual, 1, sanitizar_celda_excel(codigo))
            hoja_salida.cell(fila_actual, 2, sanitizar_celda_excel(archivo))
            hoja_salida.cell(fila_actual, 3, sanitizar_celda_excel(descripcion))
            hoja_salida.cell(fila_actual, 4, sanitizar_celda_excel(motivo))
            _copiar_estilo_fila_helper(
                hoja_plantilla, hoja_salida, fila_estilo_producto, fila_actual, 4,
                col_codigo, col_nombre, col_descuento or col_stock, col_stock
            )

    libro_plantilla.close()
    hoja_salida.print_area = f"A1:D{max(3, fila_actual)}"
    return libro_salida, hoja_salida


def _copiar_estilo_fila_helper(
    hoja_plantilla,
    hoja_salida,
    fila_plantilla: int,
    fila_salida: int,
    cantidad_columnas: int,
    col_codigo: int,
    col_nombre: int,
    col_descuento: int,
    col_stock_final: int,
) -> None:
    columnas_plantilla = (
        col_codigo,
        col_nombre,
        col_descuento,
        col_stock_final,
    )
    copiar_estilo_fila(
        hoja_plantilla=hoja_plantilla,
        hoja_salida=hoja_salida,
        fila_plantilla=fila_plantilla,
        fila_salida=fila_salida,
        cantidad_columnas=cantidad_columnas,
        columnas_plantilla=columnas_plantilla,
    )
