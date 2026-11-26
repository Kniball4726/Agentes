"""
Módulo para parsear remitos / pedidos de fábrica (ingreso de stock).
Soporta archivos Excel (.xlsx, .xls) y PDF con detalles de productos y cantidades recibidas.
"""

from pathlib import Path
from typing import Dict, List, Tuple
import xlrd
from .remito_parser import normalizar_codigo, parsear_remito
from .safe_loader import MAX_EXCEL_COLS, MAX_EXCEL_ROWS, cargar_workbook_seguro, validar_xls_seguro


def parsear_pedido_fabrica_excel(ruta_excel: str | Path) -> Tuple[Dict[str, int], List[Tuple[str, str, int]]]:
    """
    Parsea una planilla Excel (.xlsx o .xls) con columnas de Código (o COD) y Cantidad (o UNIDADES/STOCK/INGRESO).
    Si no encuentra encabezados específicos, busca columnas numéricas donde la primera sea el código y la segunda la cantidad.
    
    Retorna:
        - items_dict: Dict[codigo, cantidad_total] consolidado.
        - detalle: List[(codigo, descripcion, cantidad)]
    """
    path = Path(ruta_excel)
    items_crudos: List[Tuple[str, str, int]] = []

    if path.suffix.lower() == ".xls":
        libro = xlrd.open_workbook(file_contents=validar_xls_seguro(path))
        hoja = libro.sheet_by_index(0)
        max_cols_xls = min(hoja.ncols, MAX_EXCEL_COLS)
        max_rows_xls = min(hoja.nrows, MAX_EXCEL_ROWS)
        
        # Detectar columnas
        col_cod = -1
        col_desc = -1
        col_cant = -1
        fila_inicio = 0
        
        for r in range(min(15, max_rows_xls)):
            fila_vals = [str(hoja.cell_value(r, c)).strip().upper() for c in range(max_cols_xls)]
            for c, val in enumerate(fila_vals):
                if any(k in val for k in ["CODIGO", "COD", "ARTICULO", "CÓDIGO"]) and col_cod == -1:
                    col_cod = c
                elif any(k in val for k in ["DESCRIPCION", "PRODUCTO", "DETALLE", "NOMBRE"]) and col_desc == -1:
                    col_desc = c
                elif any(k in val for k in ["CANTIDAD", "CANT", "UNIDADES", "INGRESO", "STOCK", "PEDIDO"]) and col_cant == -1:
                    col_cant = c
            if col_cod != -1 and col_cant != -1:
                fila_inicio = r + 1
                break

        if col_cod == -1 or col_cant == -1:
            col_cod = 0
            col_desc = 1 if max_cols_xls > 2 else -1
            col_cant = 2 if max_cols_xls > 2 else 1
            fila_inicio = 0

        for r in range(fila_inicio, max_rows_xls):
            val_cod = hoja.cell_value(r, col_cod)
            val_cant = hoja.cell_value(r, col_cant)
            val_desc = hoja.cell_value(r, col_desc) if col_desc != -1 else ""
            if val_cod is None or str(val_cod).strip() == "":
                continue
            cod = normalizar_codigo(str(val_cod))
            try:
                cant = int(float(val_cant))
            except (ValueError, TypeError):
                continue
            if cant > 0:
                items_crudos.append((cod, str(val_desc).strip(), cant))

    else:
        wb = cargar_workbook_seguro(path, data_only=True)
        try:
            hoja = wb.active
            if hoja is None:
                return {}, []

            max_cols_xlsx = min(hoja.max_column or 0, MAX_EXCEL_COLS)
            max_rows_xlsx = min(hoja.max_row or 0, MAX_EXCEL_ROWS)

            col_cod = -1
            col_desc = -1
            col_cant = -1
            fila_inicio = 1

            for r in range(1, min(16, max_rows_xlsx + 1)):
                fila_vals = [str(hoja.cell(r, c).value or "").strip().upper() for c in range(1, max_cols_xlsx + 1)]
                for idx, val in enumerate(fila_vals):
                    c = idx + 1
                    if any(k in val for k in ["CODIGO", "COD", "ARTICULO", "CÓDIGO"]) and col_cod == -1:
                        col_cod = c
                    elif any(k in val for k in ["DESCRIPCION", "PRODUCTO", "DETALLE", "NOMBRE"]) and col_desc == -1:
                        col_desc = c
                    elif any(k in val for k in ["CANTIDAD", "CANT", "UNIDADES", "INGRESO", "STOCK", "PEDIDO"]) and col_cant == -1:
                        col_cant = c
                if col_cod != -1 and col_cant != -1:
                    fila_inicio = r + 1
                    break

            if col_cod == -1 or col_cant == -1:
                col_cod = 1
                col_desc = 2 if max_cols_xlsx > 2 else -1
                col_cant = 3 if max_cols_xlsx > 2 else 2
                fila_inicio = 1

            for r in range(fila_inicio, max_rows_xlsx + 1):
                val_cod = hoja.cell(r, col_cod).value
                val_cant = hoja.cell(r, col_cant).value
                val_desc = hoja.cell(r, col_desc).value if col_desc != -1 else ""
                if val_cod is None or str(val_cod).strip() == "":
                    continue
                cod = normalizar_codigo(str(val_cod))
                try:
                    cant = int(float(val_cant))
                except (ValueError, TypeError):
                    continue
                if cant > 0:
                    items_crudos.append((cod, str(val_desc).strip(), cant))
        finally:
            wb.close()

    consolidado: Dict[str, int] = {}
    for cod, _, cant in items_crudos:
        consolidado[cod] = consolidado.get(cod, 0) + cant

    return consolidado, items_crudos


def parsear_pedido_fabrica_pdf(ruta_pdf: str | Path) -> Tuple[Dict[str, int], List[Tuple[str, str, int]]]:
    """
    Parsea un remito PDF de fábrica utilizando el parser de remitos existente.
    """
    resultado = parsear_remito(ruta_pdf)
    items_crudos: List[Tuple[str, str, int]] = []
    consolidado: Dict[str, int] = {}

    for it in resultado.items:
        cod = normalizar_codigo(it.codigo)
        items_crudos.append((cod, it.descripcion, it.cantidad))
        consolidado[cod] = consolidado.get(cod, 0) + it.cantidad

    return consolidado, items_crudos


def parsear_archivo_fabrica(ruta_archivo: str | Path) -> Tuple[Dict[str, int], List[Tuple[str, str, int]]]:
    """
    Detecta automáticamente la extensión (.xlsx, .xls, .pdf) y parsea el archivo de ingreso de fábrica.
    """
    path = Path(ruta_archivo)
    sufijo = path.suffix.lower()
    if sufijo in (".xlsx", ".xls"):
        return parsear_pedido_fabrica_excel(path)
    elif sufijo == ".pdf":
        return parsear_pedido_fabrica_pdf(path)
    else:
        raise ValueError(f"Formato no soportado para pedidos de fábrica: {sufijo}. Use Excel (.xlsx, .xls) o PDF (.pdf).")
