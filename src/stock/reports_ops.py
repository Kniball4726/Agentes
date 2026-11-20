"""Generadores de reportes operativos de despachos por logística y cierres de jornada."""

from __future__ import annotations

from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any

from openpyxl.styles import Alignment
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph

from ..core.sanitize_utils import sanitizar_fila_excel
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


def generar_reporte_pedidos_despacho(
    order_store: Any,
    carpeta_destino: Path,
    formato: str = "pdf",
    usuario: str = "Sistema",
    filtro_transporte: str | None = None,
    limite: int = 500,
) -> Path:
    """Genera informe consolidado de despachos y pedidos procesados."""
    carpeta_destino.mkdir(parents=True, exist_ok=True)
    dt = datetime.now()
    stamp = dt.strftime("%Y%m%d_%H%M%S")
    fecha_legible = dt.strftime("%d/%m/%Y %H:%M")

    try:
        pedidos = order_store.listar_pedidos(limit=limite)
    except Exception:
        pedidos = []

    if filtro_transporte and filtro_transporte.strip():
        filtro_norm = filtro_transporte.strip().lower()
        pedidos = [p for p in pedidos if (getattr(p, "logistica", "") or "").strip().lower() == filtro_norm]

    total_pedidos = len(pedidos)
    total_bultos = sum(int(getattr(p, "bultos", 0) or 0) for p in pedidos)

    if formato.lower() in ("excel", "xlsx"):
        ruta_salida = carpeta_destino / f"Reporte_Despacho_Pedidos_{stamp}.xlsx"
        headers = ["Nota de Pedido", "Cliente", "Transporte / Logística", "Bultos", "Armador", "Estado", "Fecha"]
        wb, ws = crear_hoja_reporte_excel(
            "Despacho Pedidos",
            "STOCKAGENT · REPORTE CONSOLIDADO DE DESPACHO Y PEDIDOS",
            f"Fecha de emisión: {fecha_legible} | Generado por: {usuario} | Total pedidos: {total_pedidos} | Total bultos: {total_bultos}",
            headers,
        )
        for idx, p in enumerate(pedidos, start=5):
            fill_actual = _FILL_ZEBRA if idx % 2 == 0 else _FILL_WHITE
            f_str = str(getattr(p, "created_at", "") or getattr(p, "fecha", ""))[:16]
            ws.append(sanitizar_fila_excel([
                getattr(p, "nota_pedido", ""),
                getattr(p, "cliente", "") or "-",
                getattr(p, "logistica", "") or "-",
                int(getattr(p, "bultos", 0) or 0),
                getattr(p, "armador", "") or "-",
                getattr(p, "estado_despacho", "") or "-",
                f_str,
            ]))
            for c_idx in range(1, 8):
                c = ws.cell(idx, c_idx)
                c.fill = fill_actual
                c.font = _FONT_BODY
                c.border = _BORDER_THIN
                if c_idx == 4:
                    c.alignment = Alignment(horizontal="right")
                    c.font = _FONT_BOLD
                elif c_idx in (1, 3, 5, 6, 7):
                    c.alignment = Alignment(horizontal="center")
        _autoajustar_columnas_excel(ws)
        wb.save(str(ruta_salida))
        return ruta_salida

    ruta_salida = carpeta_destino / f"Reporte_Despacho_Pedidos_{stamp}.pdf"
    st = crear_estilos_pdf()
    headers_pdf = [Paragraph(t, st["th"]) for t in ("Remito / NP", "Cliente", "Transporte", "Bultos", "Armador", "Fecha")]
    filas_pdf = [headers_pdf]
    for p in pedidos:
        f_str = str(getattr(p, "created_at", "") or getattr(p, "fecha", ""))[:16]
        filas_pdf.append([
            Paragraph(escape(str(getattr(p, "nota_pedido", ""))), st["td_center"]),
            Paragraph(escape(str(getattr(p, "cliente", "") or "-")), st["td"]),
            Paragraph(escape(str(getattr(p, "logistica", "") or "-")), st["td_center"]),
            Paragraph(str(getattr(p, "bultos", 0) or 0), st["td_right"]),
            Paragraph(escape(str(getattr(p, "armador", "") or "-")), st["td_center"]),
            Paragraph(f_str, st["td_center"]),
        ])

    tabla = construir_tabla_zebra(filas_pdf, [2.6 * cm, 5.4 * cm, 3.2 * cm, 1.6 * cm, 2.6 * cm, 3.0 * cm])
    return compilar_pdf_reporte(
        ruta_salida,
        "StockAgent · Reporte Consolidado de Despacho",
        f"Emitido el {fecha_legible} · Total Pedidos: <b>{total_pedidos}</b> · Total Bultos: <b>{total_bultos}</b>",
        "StockAgent · Reporte de Despacho",
        fecha_legible,
        [tabla],
        st,
    )


def generar_reporte_cierres_historicos(
    order_store: Any,
    carpeta_destino: Path,
    formato: str = "pdf",
    usuario: str = "Sistema",
    limite: int = 100,
) -> Path:
    """Genera informe consolidado de todos los cierres de jornada ejecutados."""
    carpeta_destino.mkdir(parents=True, exist_ok=True)
    dt = datetime.now()
    stamp = dt.strftime("%Y%m%d_%H%M%S")
    fecha_legible = dt.strftime("%d/%m/%Y %H:%M")

    try:
        cierres = order_store.listar_cierres(limit=limite)
    except Exception:
        cierres = []

    if formato.lower() in ("excel", "xlsx"):
        ruta_salida = carpeta_destino / f"Reporte_Cierres_Jornada_{stamp}.xlsx"
        headers = ["Cierre #", "Fecha y Hora", "Total Pedidos", "Total Bultos", "Operador Responsable", "Archivo Informe"]
        wb, ws = crear_hoja_reporte_excel(
            "Cierres Históricos",
            "STOCKAGENT · HISTORIAL DE CIERRES DE JORNADA",
            f"Fecha de emisión: {fecha_legible} | Generado por: {usuario} | Total cierres auditados: {len(cierres)}",
            headers,
        )
        for idx, c in enumerate(cierres, start=5):
            fill_actual = _FILL_ZEBRA if idx % 2 == 0 else _FILL_WHITE
            f_cie = str(getattr(c, "created_at", "") or getattr(c, "fecha_hora", ""))[:19]
            cant_ped = int(getattr(c, "cantidad_pedidos", 0) or getattr(c, "total_pedidos", 0) or 0)
            art_tot = int(getattr(c, "articulos_totales", 0) or getattr(c, "total_bultos", 0) or 0)
            op = getattr(c, "usuario", "") or getattr(c, "operador", "") or "-"
            arch = getattr(c, "archivo_pdf", "") or getattr(c, "archivo_informe", "") or "-"
            ws.append(sanitizar_fila_excel([getattr(c, "id", idx), f_cie, cant_ped, art_tot, op, arch]))
            for c_idx in range(1, 7):
                cell_c = ws.cell(idx, c_idx)
                cell_c.fill = fill_actual
                cell_c.font = _FONT_BODY
                cell_c.border = _BORDER_THIN
                if c_idx in (3, 4):
                    cell_c.alignment = Alignment(horizontal="right")
                elif c_idx in (1, 2, 5):
                    cell_c.alignment = Alignment(horizontal="center")
        _autoajustar_columnas_excel(ws)
        wb.save(str(ruta_salida))
        return ruta_salida

    ruta_salida = carpeta_destino / f"Reporte_Cierres_Jornada_{stamp}.pdf"
    st = crear_estilos_pdf()
    headers_pdf = [Paragraph(t, st["th"]) for t in ("Cierre #", "Fecha y Hora", "Pedidos", "Bultos", "Operador / Archivo")]
    filas_pdf = [headers_pdf]
    for c in cierres:
        f_cie = str(getattr(c, "created_at", "") or getattr(c, "fecha_hora", ""))[:19]
        cant_ped = str(getattr(c, "cantidad_pedidos", 0) or getattr(c, "total_pedidos", 0) or 0)
        art_tot = str(getattr(c, "articulos_totales", 0) or getattr(c, "total_bultos", 0) or 0)
        op = getattr(c, "usuario", "") or getattr(c, "operador", "") or "-"
        arch = getattr(c, "archivo_pdf", "") or getattr(c, "archivo_informe", "") or "-"
        filas_pdf.append([
            Paragraph(f"#{getattr(c, 'id', '')}", st["td_center"]),
            Paragraph(f_cie, st["td_center"]),
            Paragraph(cant_ped, st["td_right"]),
            Paragraph(art_tot, st["td_right"]),
            Paragraph(f"<b>{escape(str(op))}</b><br/>{escape(str(arch))}", st["td"]),
        ])

    tabla = construir_tabla_zebra(filas_pdf, [2.0 * cm, 4.4 * cm, 2.6 * cm, 2.6 * cm, 6.8 * cm])
    return compilar_pdf_reporte(
        ruta_salida,
        "StockAgent · Historial de Cierres de Jornada",
        f"Emitido el {fecha_legible} · Total cierres registrados: <b>{len(cierres)}</b>",
        "StockAgent · Cierres de Jornada",
        fecha_legible,
        [tabla],
        st,
    )
