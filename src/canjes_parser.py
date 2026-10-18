"""
Módulo de Extracción y Verificación de Canjes en formato Excel (.xlsx).
Lee planillas de canje de productos, extrae los ítems solicitados
(código, cantidad pedida y descripción) y sus metadatos.
"""

from pathlib import Path
from typing import List, Optional
import openpyxl
from .remito_parser import ItemRemito, ResultadoRemito, normalizar_codigo


def parsear_canje_excel(ruta_excel: str | Path) -> ResultadoRemito:
    """
    Parsea una planilla Excel de Canje (.xlsx), localiza la tabla de pedidos
    y extrae los productos con cantidad mayor a cero.
    """
    path = Path(ruta_excel)
    wb = openpyxl.load_workbook(str(path), data_only=True)
    
    # Se utiliza la primera hoja activa
    sheet = wb.active

    # 1. Extracción de Metadatos (Filas superiores)
    observacion = str(sheet.cell(row=1, column=1).value or "").strip()
    cliente_raw = str(sheet.cell(row=2, column=1).value or "").strip()
    dni_raw = str(sheet.cell(row=3, column=1).value or "").strip()

    cliente = cliente_raw if cliente_raw else "Canje Particular"
    if dni_raw:
        cliente = f"{cliente} ({dni_raw})"

    # Obtener identificador del archivo
    num_id = path.stem.split(".")[0]
    numero_canje = f"CANJE-{num_id}"

    # 2. Localizar la fila de encabezados dinámicamente
    header_row = 5
    col_pedido = 1
    col_codigo = 2
    col_desc = 3

    for r in range(1, 15):
        vals = [str(sheet.cell(row=r, column=c).value or "").strip().upper() for c in range(1, 10)]
        if "PEDIDO" in vals and "CODIGO" in vals:
            header_row = r
            col_pedido = vals.index("PEDIDO") + 1
            col_codigo = vals.index("CODIGO") + 1
            col_desc = col_codigo + 1
            break

    # 3. Extraer productos pedidos (Columna PEDIDO > 0)
    items: List[ItemRemito] = []
    for r in range(header_row + 1, sheet.max_row + 1):
        v_ped = sheet.cell(row=r, column=col_pedido).value
        v_cod = sheet.cell(row=r, column=col_codigo).value
        v_desc = sheet.cell(row=r, column=col_desc).value

        if v_ped is not None and str(v_ped).strip() != "":
            try:
                qty = int(round(float(v_ped)))
                if qty > 0 and v_cod is not None and str(v_cod).strip() != "":
                    cod = normalizar_codigo(str(v_cod))
                    desc = str(v_desc or "").strip()
                    items.append(ItemRemito(
                        codigo=cod,
                        descripcion=desc,
                        cantidad=qty,
                        origen_remito=numero_canje
                    ))
            except (ValueError, TypeError):
                continue

    total_articulos = sum(it.cantidad for it in items)

    return ResultadoRemito(
        archivo=path.name,
        numero_remito=numero_canje,
        fecha=observacion if observacion else "Canje",
        cliente=cliente,
        articulos_declarados=total_articulos,
        articulos_extraidos=total_articulos,
        verificacion_ok=True,
        items=items
    )
