"""Generadores de reportes analíticos de Kardex histórico por SKU y Ranking de Rotación."""

from __future__ import annotations

from datetime import datetime, timedelta
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


def generar_reporte_kardex_producto(
    product_store: Any,
    product_query: str,
    carpeta_destino: Path,
    formato: str = "pdf",
    usuario: str = "Operador",
    fecha_desde: str = "",
    fecha_hasta: str = "",
) -> Path:
    """Genera el libro mayor cronológico (Kardex) con saldos móviles para un artículo."""
    carpeta_destino = Path(carpeta_destino)
    carpeta_destino.mkdir(parents=True, exist_ok=True)
    kardex = product_store.get_product_kardex(
        product_query,
        date_from=fecha_desde,
        date_to=fecha_hasta,
    )
    producto = kardex.get("producto")
    movimientos = list(kardex.get("movimientos") or [])
    if producto is None:
        raise ValueError(f"No se encontró ningún producto que coincida con '{product_query}'.")

    ahora = datetime.now()
    ts = ahora.strftime("%Y%m%d_%H%M%S")
    fecha_legible = ahora.strftime("%d/%m/%Y %H:%M")
    cod_safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in str(producto["code"]))
    ext = "pdf" if formato.lower() == "pdf" else "xlsx"
    ruta_salida = carpeta_destino / f"Kardex_{cod_safe}_{ts}.{ext}"

    ubic = producto.get("ubicacion") or "-"
    meta = (
        f"Artículo: {producto['code']} · {producto['name']} | Stock Actual: {producto['stock']} "
        f"| Mín: {producto['stock_minimo']} | Ubicación: {ubic}"
    )

    if ext == "xlsx":
        headers = ["Fecha / Hora", "Tipo", "Detalle / Motivo", "Responsable", "Stock Ant.", "Entrada (+)", "Salida (-)", "Saldo Final"]
        wb, ws = crear_hoja_reporte_excel(
            "Kardex Producto",
            f"KARDEX DE MOVIMIENTOS · {producto['code']}",
            f"{meta} | Emitido: {fecha_legible} | Generado por: {usuario}",
            headers,
        )
        for idx, m in enumerate(movimientos):
            ws.append([
                m["fecha"].replace("T", " "),
                m["tipo"],
                m["detalle"] or "-",
                m["usuario"],
                int(m["stock_anterior"]),
                int(m["entrada"]),
                int(m["salida"]),
                int(m["stock_resultante"]),
            ])
            estilizar_fila_excel(ws, ws.max_row, len(headers), idx % 2 == 1)
        if not movimientos:
            ws.append(["—", "-", "Sin movimientos registrados en el rango.", "-", int(producto["stock"]), 0, 0, int(producto["stock"])])
        _autoajustar_columnas_excel(ws)
        wb.save(ruta_salida)
        wb.close()
        return ruta_salida

    st = crear_estilos_pdf()
    subtitulo = f"<b>{producto['code']}</b> — {producto['name']} | Stock Actual: <b>{producto['stock']}</b> | Ubic.: {ubic} | Emitido: {fecha_legible}"
    filas: list[list[Any]] = [[
        Paragraph("Fecha / Hora", st["th"]),
        Paragraph("Tipo", st["th"]),
        Paragraph("Detalle", st["th"]),
        Paragraph("Resp.", st["th"]),
        Paragraph("Ant.", st["th"]),
        Paragraph("Entr.", st["th"]),
        Paragraph("Sal.", st["th"]),
        Paragraph("Saldo", st["th"]),
    ]]
    if movimientos:
        for m in movimientos:
            filas.append([
                Paragraph(str(m["fecha"]).replace("T", " ")[:16], st["td_center"]),
                Paragraph(str(m["tipo"])[:18], st["td_center"]),
                Paragraph(str(m["detalle"] or "-")[:34], st["td"]),
                Paragraph(str(m["usuario"])[:14], st["td_center"]),
                Paragraph(str(m["stock_anterior"]), st["td_center"]),
                Paragraph(f"+{m['entrada']}" if m["entrada"] else "—", st["td_center"]),
                Paragraph(f"-{m['salida']}" if m["salida"] else "—", st["td_center"]),
                Paragraph(f"<b>{m['stock_resultante']}</b>", st["td_center"]),
            ])
    else:
        filas.append([
            Paragraph("—", st["td_center"]),
            Paragraph("-", st["td_center"]),
            Paragraph("Sin movimientos registrados en la ventana consultada.", st["td"]),
            Paragraph("-", st["td_center"]),
            Paragraph(str(producto["stock"]), st["td_center"]),
            Paragraph("0", st["td_center"]),
            Paragraph("0", st["td_center"]),
            Paragraph(str(producto["stock"]), st["td_center"]),
        ])

    return compilar_pdf_reporte(
        ruta_salida=ruta_salida,
        titulo_doc=f"KARDEX DE PRODUCTO · {producto['code']}",
        subtitulo_html=subtitulo,
        titulo_canvas=f"StockAgent · Kardex {producto['code']}",
        fecha_legible=fecha_legible,
        cuerpo_extra=[Spacer(1, 0.2 * cm), construir_tabla_zebra(filas, [2.7 * cm, 2.3 * cm, 4.7 * cm, 2.1 * cm, 1.5 * cm, 1.7 * cm, 1.7 * cm, 1.9 * cm])],
        st=st,
    )


def generar_reporte_rotacion_consumo(
    product_store: Any,
    carpeta_destino: Path,
    formato: str = "pdf",
    usuario: str = "Administrador",
    dias: int = 30,
    top_n: int = 60,
) -> Path:
    """Genera el ranking de consumo, velocidad diaria de salida y días estimados de cobertura."""
    carpeta_destino = Path(carpeta_destino)
    carpeta_destino.mkdir(parents=True, exist_ok=True)
    ahora = datetime.now()
    desde_dt = ahora - timedelta(days=max(1, int(dias)))
    ranking = list(
        product_store.get_rotation_ranking(
            date_from=desde_dt.strftime("%Y-%m-%dT00:00:00"),
            date_to=ahora.strftime("%Y-%m-%dT23:59:59"),
            dias_periodo=dias,
            top_n=top_n,
        )
        or []
    )

    ts = ahora.strftime("%Y%m%d_%H%M%S")
    fecha_legible = ahora.strftime("%d/%m/%Y %H:%M")
    ext = "pdf" if formato.lower() == "pdf" else "xlsx"
    ruta_salida = carpeta_destino / f"Rotacion_Consumo_{dias}d_{ts}.{ext}"

    if ext == "xlsx":
        headers = ["#", "Código", "Producto", "Ubicación", "Salidas Período", "Prom./Día", "Stock Actual", "Cobertura (días)"]
        wb, ws = crear_hoja_reporte_excel(
            "Rotación Stock",
            f"RANKING DE ROTACIÓN Y COBERTURA ({dias} DÍAS)",
            f"Emitido: {fecha_legible} | Top {len(ranking)} productos | Responsable: {usuario}",
            headers,
        )
        for idx, r in enumerate(ranking, start=1):
            cob = "SIN COBERTURA" if r["stock_actual"] <= 0 else (f"{r['cobertura_dias']} d." if r["cobertura_dias"] < 900 else "999+ d.")
            ws.append([idx, r["code"], r["name"], r["ubicacion"] or "-", r["total_salidas"], r["promedio_diario"], r["stock_actual"], cob])
            estilizar_fila_excel(ws, ws.max_row, len(headers), idx % 2 == 0)
        _autoajustar_columnas_excel(ws)
        wb.save(ruta_salida)
        wb.close()
        return ruta_salida

    st = crear_estilos_pdf()
    subtitulo = f"Ventana analizada: últimos <b>{dias} días</b> | Emitido: {fecha_legible} | Resp: <b>{usuario}</b>"
    filas: list[list[Any]] = [[
        Paragraph("#", st["th"]),
        Paragraph("Código", st["th"]),
        Paragraph("Descripción", st["th"]),
        Paragraph("Salidas", st["th"]),
        Paragraph("Prom/Día", st["th"]),
        Paragraph("Stock Act.", st["th"]),
        Paragraph("Cobertura", st["th"]),
    ]]
    if ranking:
        for idx, r in enumerate(ranking, start=1):
            cob_val = r["cobertura_dias"]
            if r["stock_actual"] <= 0:
                cob_cell = Paragraph("0 d. (AGOTADO)", st["agotado"])
            elif cob_val <= 7:
                cob_cell = Paragraph(f"{cob_val} d.", st["critico"])
            else:
                cob_cell = Paragraph(f"{cob_val} d." if cob_val < 900 else "999+ d.", st["td_center"])
            filas.append([
                Paragraph(str(idx), st["td_center"]),
                Paragraph(str(r["code"]), st["td_center"]),
                Paragraph(str(r["name"])[:48], st["td"]),
                Paragraph(f"<b>{r['total_salidas']}</b>", st["td_center"]),
                Paragraph(str(r["promedio_diario"]), st["td_center"]),
                Paragraph(str(r["stock_actual"]), st["td_center"]),
                cob_cell,
            ])
    else:
        filas.append([
            Paragraph("-", st["td_center"]),
            Paragraph("—", st["td_center"]),
            Paragraph("Sin salidas registradas en la ventana analizada.", st["td"]),
            Paragraph("0", st["td_center"]),
            Paragraph("0", st["td_center"]),
            Paragraph("-", st["td_center"]),
            Paragraph("-", st["td_center"]),
        ])

    return compilar_pdf_reporte(
        ruta_salida=ruta_salida,
        titulo_doc=f"RANKING DE ROTACIÓN Y COBERTURA ({dias} DÍAS)",
        subtitulo_html=subtitulo,
        titulo_canvas="StockAgent · Ranking de Rotación",
        fecha_legible=fecha_legible,
        cuerpo_extra=[Spacer(1, 0.2 * cm), construir_tabla_zebra(filas, [1.2 * cm, 2.3 * cm, 6.7 * cm, 2.0 * cm, 2.1 * cm, 2.1 * cm, 2.2 * cm])],
        st=st,
    )
