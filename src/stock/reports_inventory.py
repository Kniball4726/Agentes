"""Generadores de reportes imprimibles de Toma de Inventario y Auditoría Física."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, Spacer

from .report_styles import (
    _autoajustar_columnas_excel,
    compilar_pdf_reporte,
    construir_tabla_zebra,
    crear_estilos_pdf,
    crear_hoja_reporte_excel,
    estilizar_fila_excel,
)


def generar_reporte_planilla_conteo_fisico(
    product_store: Any,
    carpeta_destino: Path,
    formato: str = "pdf",
    usuario: str = "Operador",
    conteo_ciego: bool = True,
    filtro_ubicacion: str = "",
) -> Path:
    """Genera una planilla imprimible para recuento físico en depósito ordenada por ubicación."""
    carpeta_destino = Path(carpeta_destino)
    carpeta_destino.mkdir(parents=True, exist_ok=True)
    productos = list(product_store.list_products(solo_activos=True) or [])
    ubic_clean = (filtro_ubicacion or "").strip().lower()
    if ubic_clean:
        productos = [
            p for p in productos
            if ubic_clean in str(p["ubicacion"] if "ubicacion" in p.keys() else "").lower()
        ]
    productos.sort(
        key=lambda p: (
            str(p["ubicacion"] if "ubicacion" in p.keys() and p["ubicacion"] else "ZZZ"),
            int(p["display_order"] if "display_order" in p.keys() and p["display_order"] is not None else 999999),
            str(p["code"]),
        )
    )

    ahora = datetime.now()
    ts = ahora.strftime("%Y%m%d_%H%M%S")
    fecha_legible = ahora.strftime("%d/%m/%Y %H:%M")
    modo_txt = "Conteo Ciego (sin stock digital)" if conteo_ciego else "Conteo Guiado (con stock sistema)"
    ext = "pdf" if formato.lower() == "pdf" else "xlsx"
    ruta_salida = carpeta_destino / f"Planilla_Conteo_Fisico_{ts}.{ext}"

    if ext == "xlsx":
        headers = (
            ["Ubicación", "Código", "Descripción", "Cód. Barras", "Conteo Físico", "Observaciones"]
            if conteo_ciego
            else ["Ubicación", "Código", "Descripción", "Cód. Barras", "Stock Sistema", "Conteo Físico", "Diferencia"]
        )
        wb, ws = crear_hoja_reporte_excel(
            "Conteo Físico",
            "PLANILLA DE TOMA DE INVENTARIO FÍSICO",
            f"Emitido: {fecha_legible} | {modo_txt} | Artículos: {len(productos)} | Resp: {usuario}",
            headers,
        )
        for idx, p in enumerate(productos):
            ubic = (p["ubicacion"] if "ubicacion" in p.keys() else "") or "-"
            cod_b = (p["cod_barras"] if "cod_barras" in p.keys() else "") or "-"
            if conteo_ciego:
                ws.append([ubic, p["code"], p["name"], cod_b, "", ""])
            else:
                ws.append([ubic, p["code"], p["name"], cod_b, int(p["stock"]), "", ""])
            estilizar_fila_excel(ws, ws.max_row, len(headers), idx % 2 == 1)
        _autoajustar_columnas_excel(ws)
        wb.save(ruta_salida)
        wb.close()
        return ruta_salida

    st = crear_estilos_pdf()
    subtitulo = f"Emitido: {fecha_legible} | <b>{modo_txt}</b> | Total SKUs: {len(productos)} | Resp: <b>{usuario}</b>"

    if conteo_ciego:
        headers_pdf = ["Ubic.", "Código", "Descripción", "Cód. Barras", "Conteo", "Obs."]
        widths = [2.0 * cm, 2.3 * cm, 7.2 * cm, 2.9 * cm, 2.0 * cm, 2.2 * cm]
    else:
        headers_pdf = ["Ubic.", "Código", "Descripción", "Sistema", "Conteo", "Dif."]
        widths = [2.0 * cm, 2.3 * cm, 8.1 * cm, 2.0 * cm, 2.1 * cm, 2.1 * cm]

    filas: list[list[Any]] = [[Paragraph(h, st["th"]) for h in headers_pdf]]
    for p in productos:
        ubic = (p["ubicacion"] if "ubicacion" in p.keys() else "") or "-"
        cod_b = (p["cod_barras"] if "cod_barras" in p.keys() else "") or "-"
        if conteo_ciego:
            filas.append([
                Paragraph(str(ubic)[:12], st["td_center"]),
                Paragraph(str(p["code"]), st["td_center"]),
                Paragraph(str(p["name"])[:52], st["td"]),
                Paragraph(str(cod_b)[:16], st["td_center"]),
                Paragraph("_______", st["td_center"]),
                Paragraph("", st["td"]),
            ])
        else:
            filas.append([
                Paragraph(str(ubic)[:12], st["td_center"]),
                Paragraph(str(p["code"]), st["td_center"]),
                Paragraph(str(p["name"])[:56], st["td"]),
                Paragraph(str(p["stock"]), st["td_center"]),
                Paragraph("_______", st["td_center"]),
                Paragraph("_____", st["td_center"]),
            ])

    return compilar_pdf_reporte(
        ruta_salida=ruta_salida,
        titulo_doc="PLANILLA DE TOMA DE INVENTARIO FÍSICO",
        subtitulo_html=subtitulo,
        titulo_canvas="StockAgent · Planilla de Conteo Físico",
        fecha_legible=fecha_legible,
        cuerpo_extra=[construir_tabla_zebra(filas, widths)],
        st=st,
    )


def generar_reporte_auditoria_inventario_fisico(
    product_store: Any,
    carpeta_destino: Path,
    formato: str = "pdf",
    usuario: str = "Administrador",
) -> Path:
    """Genera el informe comparativo Digital vs. Físico del último relevamiento cargado."""
    carpeta_destino = Path(carpeta_destino)
    carpeta_destino.mkdir(parents=True, exist_ok=True)
    cabecera, detalles = product_store.get_latest_physical_inventory()
    filas_det = list(detalles or [])

    ahora = datetime.now()
    ts = ahora.strftime("%Y%m%d_%H%M%S")
    fecha_legible = ahora.strftime("%d/%m/%Y %H:%M")
    ext = "pdf" if formato.lower() == "pdf" else "xlsx"
    ruta_salida = carpeta_destino / f"Auditoria_Inventario_Fisico_{ts}.{ext}"

    if cabecera is not None:
        meta_txt = (
            f"Relevamiento #{cabecera['id']} ({str(cabecera['fecha'])[:16]}) | "
            f"Relevados: {cabecera['total_relevados']} | Con diferencia: {cabecera['total_diferencias']}"
        )
    else:
        meta_txt = "Sin relevamientos físicos registrados aún."

    if ext == "xlsx":
        headers = ["Código", "Descripción", "Stock Digital", "Stock Físico", "Diferencia", "Estado"]
        wb, ws = crear_hoja_reporte_excel(
            "Auditoría Física",
            "AUDITORÍA DE INVENTARIO FÍSICO VS DIGITAL",
            f"Emitido: {fecha_legible} | {meta_txt} | Generado por: {usuario}",
            headers,
        )
        for idx, d in enumerate(filas_det):
            ws.append([
                d["product_code"],
                d["product_name"],
                int(d["stock_digital"]),
                int(d["stock_fisico"]),
                int(d["diferencia"]),
                d["estado"],
            ])
            estilizar_fila_excel(ws, ws.max_row, len(headers), idx % 2 == 1)
        if not filas_det:
            ws.append(["—", "No existen detalles de conteo físico registrados.", 0, 0, 0, "-"])
        _autoajustar_columnas_excel(ws)
        wb.save(ruta_salida)
        wb.close()
        return ruta_salida

    st = crear_estilos_pdf()
    subtitulo = f"Emitido: {fecha_legible} | {meta_txt} | Resp: <b>{usuario}</b>"
    filas_pdf: list[list[Any]] = [[
        Paragraph("Código", st["th"]),
        Paragraph("Producto", st["th"]),
        Paragraph("Digital", st["th"]),
        Paragraph("Físico", st["th"]),
        Paragraph("Diferencia", st["th"]),
        Paragraph("Estado", st["th"]),
    ]]
    if filas_det:
        for d in filas_det:
            dif = int(d["diferencia"] or 0)
            dif_txt = f"+{dif}" if dif > 0 else str(dif)
            est_cell = Paragraph(
                f"<b>{d['estado']}</b>",
                st["agotado"] if dif < 0 else (st["critico"] if dif > 0 else st["td_center"]),
            )
            filas_pdf.append([
                Paragraph(str(d["product_code"]), st["td_center"]),
                Paragraph(str(d["product_name"])[:50], st["td"]),
                Paragraph(str(d["stock_digital"]), st["td_center"]),
                Paragraph(str(d["stock_fisico"]), st["td_center"]),
                Paragraph(f"<b>{dif_txt}</b>", st["td_center"]),
                est_cell,
            ])
    else:
        filas_pdf.append([
            Paragraph("—", st["td_center"]),
            Paragraph("Aún no se cargó ningún inventario físico.", st["td"]),
            Paragraph("0", st["td_center"]),
            Paragraph("0", st["td_center"]),
            Paragraph("0", st["td_center"]),
            Paragraph("-", st["td_center"]),
        ])

    return compilar_pdf_reporte(
        ruta_salida=ruta_salida,
        titulo_doc="AUDITORÍA DE INVENTARIO FÍSICO",
        subtitulo_html=subtitulo,
        titulo_canvas="StockAgent · Auditoría de Inventario Físico",
        fecha_legible=fecha_legible,
        cuerpo_extra=[Spacer(1, 0.2 * cm), construir_tabla_zebra(filas_pdf, [2.3 * cm, 7.6 * cm, 2.0 * cm, 2.0 * cm, 2.2 * cm, 2.5 * cm])],
        st=st,
    )
