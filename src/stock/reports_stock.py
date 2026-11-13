"""Generadores de reportes operativos de inventario: Stock Crítico y Catálogo Completo."""

from __future__ import annotations

from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any

from openpyxl.styles import Alignment, Font
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

from .report_styles import (
    _BORDER_THIN,
    _FILL_WHITE,
    _FILL_ZEBRA,
    _FONT_BODY,
    _FONT_BOLD,
    _autoajustar_columnas_excel,
    compilar_pdf_reporte,
    construir_tabla_zebra,
    crear_estilos_pdf,
    crear_hoja_reporte_excel,
)


def _obtener_items_criticos(product_store: Any) -> list[Any]:
    try:
        return product_store.get_replenishment_analysis(solo_criticos=True)
    except Exception:
        items: list[dict[str, Any]] = []
        try:
            for p in product_store.list_products():
                stk = int(p["stock"]) if hasattr(p, "keys") else int(getattr(p, "stock", 0))
                min_stk = int(p["min_stock"]) if "min_stock" in p.keys() else 10
                if stk <= min_stk:
                    items.append({
                        "code": p["code"],
                        "name": p["name"],
                        "stock": stk,
                        "min_stock": min_stk,
                        "target_stock": min_stk * 2,
                        "suggested_order": max((min_stk * 2) - stk, 0),
                        "status": "CRITICAL" if stk > 0 else "OUT_OF_STOCK",
                        "ubicacion": p["ubicacion"] if "ubicacion" in p.keys() else "",
                    })
        except Exception:
            return []
        return items


def generar_reporte_stock_critico(
    product_store: Any,
    carpeta_destino: Path,
    formato: str = "pdf",
    usuario: str = "Sistema",
) -> Path:
    """Genera informe de productos agotados o por debajo del stock mínimo."""
    carpeta_destino.mkdir(parents=True, exist_ok=True)
    dt = datetime.now()
    stamp = dt.strftime("%Y%m%d_%H%M%S")
    fecha_legible = dt.strftime("%d/%m/%Y %H:%M")
    items = _obtener_items_criticos(product_store)

    if formato.lower() in ("excel", "xlsx"):
        ruta_salida = carpeta_destino / f"Reporte_Stock_Critico_{stamp}.xlsx"
        headers = ["Código", "Descripción del Producto", "Ubicación", "Stock Actual", "Stock Mínimo", "Sugerido Reponer", "Estado"]
        wb, ws = crear_hoja_reporte_excel(
            "Stock Crítico",
            "STOCKAGENT · REPORTE DE STOCK CRÍTICO Y REPOSICIÓN",
            f"Fecha de emisión: {fecha_legible} | Generado por: {usuario} | Total productos en alerta: {len(items)}",
            headers,
        )
        for idx, it in enumerate(items, start=5):
            stk = int(it.get("stock", 0))
            estado = "AGOTADO" if stk <= 0 else "CRÍTICO"
            fill_actual = _FILL_ZEBRA if idx % 2 == 0 else _FILL_WHITE
            fila = [
                it.get("code", ""),
                it.get("name", ""),
                it.get("ubicacion", "") or "-",
                stk,
                int(it.get("min_stock", 0)),
                int(it.get("suggested_order", 0)),
                estado,
            ]
            ws.append(fila)
            for c_idx in range(1, len(fila) + 1):
                c = ws.cell(idx, c_idx)
                c.fill = fill_actual
                c.font = _FONT_BODY
                c.border = _BORDER_THIN
                if c_idx in (4, 5, 6):
                    c.alignment = Alignment(horizontal="right")
                elif c_idx == 7:
                    c.alignment = Alignment(horizontal="center")
                    c.font = Font(name="Calibri", size=10, bold=True, color="DC2626" if estado == "AGOTADO" else "D97706")
        _autoajustar_columnas_excel(ws)
        wb.save(str(ruta_salida))
        return ruta_salida

    ruta_salida = carpeta_destino / f"Reporte_Stock_Critico_{stamp}.pdf"
    st = crear_estilos_pdf()
    agotados_cnt = sum(1 for it in items if int(it.get("stock", 0)) <= 0)
    criticos_cnt = len(items) - agotados_cnt

    t_resumen = Table(
        [[
            Paragraph(f"<b>Total en Alerta:</b> {len(items)}", st["td_center"]),
            Paragraph(f"<b>Agotados (Stock 0):</b> {agotados_cnt}", st["agotado"]),
            Paragraph(f"<b>Bajo Mínimo:</b> {criticos_cnt}", st["critico"]),
        ]],
        colWidths=[6 * cm, 6 * cm, 6 * cm],
    )
    t_resumen.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f1f5f9")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))

    headers_pdf = [
        Paragraph(tit, st["th"])
        for tit in ("Código", "Descripción", "Ubicación", "Actual", "Mínimo", "Sugerido", "Estado")
    ]
    filas_pdf = [headers_pdf]
    if not items:
        filas_pdf.append([Paragraph("No hay productos en quiebre ni bajo stock crítico.", st["td_center"]), "", "", "", "", "", ""])
    else:
        for it in items:
            stk = int(it.get("stock", 0))
            is_agotado = stk <= 0
            filas_pdf.append([
                Paragraph(escape(str(it.get("code", ""))), st["td_center"]),
                Paragraph(escape(str(it.get("name", ""))), st["td"]),
                Paragraph(escape(str(it.get("ubicacion", "") or "-")), st["td_center"]),
                Paragraph(str(stk), st["td_right"]),
                Paragraph(str(it.get("min_stock", 0)), st["td_right"]),
                Paragraph(str(it.get("suggested_order", 0)), st["td_right"]),
                Paragraph("AGOTADO" if is_agotado else "CRÍTICO", st["agotado"] if is_agotado else st["critico"]),
            ])

    tabla = construir_tabla_zebra(filas_pdf, [2.2 * cm, 6.8 * cm, 2.0 * cm, 2.0 * cm, 2.0 * cm, 2.0 * cm, 1.8 * cm])
    return compilar_pdf_reporte(
        ruta_salida,
        "StockAgent · Reporte de Stock Crítico y Reposición",
        f"Emitido el {fecha_legible} · Generado por: <b>{escape(usuario)}</b>",
        "StockAgent · Reporte de Stock Crítico",
        fecha_legible,
        [t_resumen, Spacer(1, 0.5 * cm), tabla],
        st,
    )


def _extraer_campos_producto(p: Any) -> tuple[str, str, str, str, int, bool]:
    has_keys = hasattr(p, "keys")
    keys_p = set(p.keys()) if has_keys else set()
    cod = p["code"] if has_keys else getattr(p, "code", "")
    nom = p["name"] if has_keys else getattr(p, "name", "")
    bar = (p["cod_barras"] if "cod_barras" in keys_p and p["cod_barras"] else "") or (
        p["barcode"] if "barcode" in keys_p else ""
    )
    ubi = p["ubicacion"] if "ubicacion" in keys_p else ""
    stk = int(p["stock"]) if has_keys else int(getattr(p, "stock", 0))
    act = bool(p["active"]) if "active" in keys_p else True
    return str(cod), str(nom), str(bar), str(ubi), stk, act


def generar_reporte_catalogo_stock(
    product_store: Any,
    carpeta_destino: Path,
    formato: str = "pdf",
    usuario: str = "Sistema",
) -> Path:
    """Genera inventario general con existencias, código de barras y ubicaciones."""
    carpeta_destino.mkdir(parents=True, exist_ok=True)
    dt = datetime.now()
    stamp = dt.strftime("%Y%m%d_%H%M%S")
    fecha_legible = dt.strftime("%d/%m/%Y %H:%M")

    try:
        prods = product_store.list_products()
    except Exception:
        prods = []

    if formato.lower() in ("excel", "xlsx"):
        ruta_salida = carpeta_destino / f"Reporte_Catalogo_Inventario_{stamp}.xlsx"
        headers = ["Código", "Descripción", "Código de Barras", "Ubicación", "Stock Actual", "Estado"]
        wb, ws = crear_hoja_reporte_excel(
            "Catálogo Stock",
            "STOCKAGENT · INVENTARIO Y CATÁLOGO DE PRODUCTOS",
            f"Fecha de emisión: {fecha_legible} | Generado por: {usuario} | Total referencias: {len(prods)}",
            headers,
        )
        for idx, p in enumerate(prods, start=5):
            cod, nom, bar, ubi, stk, act = _extraer_campos_producto(p)
            fill_actual = _FILL_ZEBRA if idx % 2 == 0 else _FILL_WHITE
            ws.append([cod, nom, bar or "-", ubi or "-", stk, "Activo" if act else "Inactivo"])
            for c_idx in range(1, 7):
                c = ws.cell(idx, c_idx)
                c.fill = fill_actual
                c.font = _FONT_BODY
                c.border = _BORDER_THIN
                if c_idx == 5:
                    c.alignment = Alignment(horizontal="right")
                    c.font = _FONT_BOLD
                elif c_idx in (1, 3, 4, 6):
                    c.alignment = Alignment(horizontal="center")
        _autoajustar_columnas_excel(ws)
        wb.save(str(ruta_salida))
        return ruta_salida

    ruta_salida = carpeta_destino / f"Reporte_Catalogo_Inventario_{stamp}.pdf"
    st = crear_estilos_pdf()
    headers_pdf = [Paragraph(t, st["th"]) for t in ("Código", "Descripción", "Cód. Barras", "Ubicación", "Stock")]
    filas_pdf = [headers_pdf]
    for p in prods:
        cod, nom, bar, ubi, stk, _ = _extraer_campos_producto(p)
        filas_pdf.append([
            Paragraph(escape(cod), st["td_center"]),
            Paragraph(escape(nom), st["td"]),
            Paragraph(escape(bar or "-"), st["td_center"]),
            Paragraph(escape(ubi or "-"), st["td_center"]),
            Paragraph(str(stk), st["td_right"]),
        ])

    tabla = construir_tabla_zebra(filas_pdf, [2.2 * cm, 8.0 * cm, 3.2 * cm, 2.4 * cm, 2.6 * cm])
    return compilar_pdf_reporte(
        ruta_salida,
        "StockAgent · Catálogo Completo de Inventario",
        f"Emitido el {fecha_legible} · Total referencias: <b>{len(prods)}</b> · Operador: <b>{escape(usuario)}</b>",
        "StockAgent · Catálogo e Inventario",
        fecha_legible,
        [tabla],
        st,
    )
