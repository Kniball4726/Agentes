"""Generadores estándar SQLite-Nativos de reportes de Salidas, Ingresos y Cierre Diario."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Sequence

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

from .report_styles import (
    _BORDER_THIN,
    _FILL_HEADER,
    _FONT_BOLD,
    _FONT_HEADER,
    _autoajustar_columnas_excel,
    compilar_pdf_reporte,
    construir_tabla_zebra,
    crear_estilos_pdf,
    estilizar_fila_excel,
)


def _fmt_num(valor: int) -> str:
    return str(valor) if valor > 0 else "—"


def _construir_bloque_kpis_pdf(tarjetas: list[tuple[str, str]], st: dict[str, ParagraphStyle]) -> Table:
    """Construye una fila horizontal compacta de tarjetas KPI en PDF."""
    fila_titulos = [
        Paragraph(f"<b>{lbl}</b>", ParagraphStyle("KpiT", parent=st["sub"], fontSize=7.5, alignment=1, textColor=colors.HexColor("#475569")))
        for lbl, _ in tarjetas
    ]
    fila_valores = [
        Paragraph(f"<b>{val}</b>", ParagraphStyle("KpiV", parent=st["td_center"], fontSize=11, leading=13, textColor=colors.HexColor("#0f172a")))
        for _, val in tarjetas
    ]
    ancho_total = 18.6 * cm
    ancho_celda = ancho_total / max(1, len(tarjetas))
    tabla = Table([fila_titulos, fila_valores], colWidths=[ancho_celda] * len(tarjetas))
    tabla.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f1f5f9")),
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#cbd5e1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    return tabla


def _construir_titulo_seccion_pdf(texto: str, st: dict[str, ParagraphStyle]) -> Paragraph:
    estilo = ParagraphStyle(
        "SecMov",
        parent=st["titulo"],
        fontSize=11.5,
        leading=14,
        textColor=colors.HexColor("#1e293b"),
        spaceBefore=6,
        spaceAfter=4,
    )
    return Paragraph(texto, estilo)


def _construir_firmas_pdf(st: dict[str, ParagraphStyle]) -> Table:
    tabla = Table(
        [
            ["_______________________________", "_______________________________"],
            [
                Paragraph("Firma Operador / Armador", st["td_center"]),
                Paragraph("Control / Supervisión Administración", st["td_center"]),
            ],
        ],
        colWidths=[9.3 * cm, 9.3 * cm],
    )
    tabla.setStyle(
        TableStyle(
            [
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("TOPPADDING", (0, 0), (-1, 0), 18),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    return tabla


def _escribir_seccion_excel(
    ws: openpyxl.worksheet.worksheet.Worksheet,
    titulo_seccion: str,
    headers: list[str],
    filas: list[list[Any]],
    fila_totales: list[Any] | None = None,
) -> None:
    """Agrega un bloque titulado con encabezados, filas cebreadas y totales opcionales."""
    if ws.max_row > 1:
        ws.append([])
    ws.append([titulo_seccion])
    fila_sec = ws.max_row
    ws.cell(fila_sec, 1).font = Font(name="Calibri", size=11, bold=True, color="1E293B")
    ws.cell(fila_sec, 1).fill = PatternFill(start_color="E2E8F0", end_color="E2E8F0", fill_type="solid")

    ws.append(headers)
    fila_hdr = ws.max_row
    for c_idx in range(1, len(headers) + 1):
        celda = ws.cell(fila_hdr, c_idx)
        celda.fill = _FILL_HEADER
        celda.font = _FONT_HEADER
        celda.alignment = Alignment(horizontal="center", vertical="center")

    for idx_r, row_vals in enumerate(filas):
        ws.append(row_vals)
        estilizar_fila_excel(ws, ws.max_row, len(headers), idx_r % 2 == 1)

    if fila_totales:
        ws.append(fila_totales)
        r_tot = ws.max_row
        fill_tot = PatternFill(start_color="DBEAFE", end_color="DBEAFE", fill_type="solid")
        for c_idx in range(1, len(headers) + 1):
            celda = ws.cell(r_tot, c_idx)
            celda.font = _FONT_BOLD
            celda.border = _BORDER_THIN
            celda.fill = fill_tot


def _estilo_estado_cell(estado: str, st: dict[str, ParagraphStyle]) -> Paragraph:
    if estado == "AGOTADO":
        return Paragraph("AGOTADO", st["agotado"])
    if estado in ("QUIEBRE_INMINENTE", "CRITICO"):
        return Paragraph("QUIEBRE", st["critico"])
    if estado == "SOBRESTOCK":
        return Paragraph("SOBRESTOCK", st["td_center"])
    return Paragraph("OK", st["td_center"])


def _ordenar_items_por_catalogo(
    items: list[dict[str, Any]],
    mapa_orden_catalogo: dict[str, int] | None,
) -> list[dict[str, Any]]:
    if not mapa_orden_catalogo:
        return sorted(items, key=lambda x: str(x.get("codigo") or x.get("code") or ""))
    return sorted(
        items,
        key=lambda x: (
            mapa_orden_catalogo.get(str(x.get("codigo") or x.get("code") or ""), 999999),
            str(x.get("codigo") or x.get("code") or ""),
        ),
    )


def generar_reporte_descuento_operario_canales(
    items_canal: list[dict[str, Any]],
    carpeta_destino: Path,
    formato: str = "pdf",
    usuario: str = "Operador",
    pedidos_procesados: Sequence[Any] = (),
    ingresos_periodo: list[dict[str, Any]] | None = None,
    sin_coincidencia: list[tuple[str, str, str, str]] | None = None,
    mapa_orden_catalogo: dict[str, int] | None = None,
    prefijo_archivo: str = "Cierre_Descuento",
    titulo_documento: str = "REPORTE OPERATIVO DE DESCUENTOS POR CANAL",
    cierre_id: int | None = None,
    timestamp_sufijo: str | None = None,
) -> Path:
    """Genera el reporte de Operario discriminando Mayoristas, Mercado Libre y Full (solo con movimientos)."""
    carpeta_destino = Path(carpeta_destino)
    carpeta_destino.mkdir(parents=True, exist_ok=True)
    ahora = datetime.now()
    ts = timestamp_sufijo or ahora.strftime("%Y%m%d_%H%M%S")
    fecha_legible = ahora.strftime("%d/%m/%Y %H:%M")

    activos = [it for it in items_canal if int(it.get("total", 0)) > 0]
    ordenados = _ordenar_items_por_catalogo(activos, mapa_orden_catalogo)
    ingresos = _ordenar_items_por_catalogo(list(ingresos_periodo or []), mapa_orden_catalogo)

    tot_may = sum(int(x.get("mayoristas", 0)) for x in ordenados)
    tot_ml = sum(int(x.get("mercado_libre", 0)) for x in ordenados)
    tot_full = sum(int(x.get("full", 0)) for x in ordenados)
    tot_canj = sum(int(x.get("canjes", 0)) for x in ordenados)
    tot_ing = sum(int(x.get("cantidad_ingreso", 0)) for x in ingresos)

    lote_txt = f" · Lote/Cierre #{cierre_id}" if cierre_id else ""
    ext = "pdf" if formato.lower() == "pdf" else "xlsx"
    ruta_salida = carpeta_destino / f"{prefijo_archivo}_{ts}.{ext}"

    if ext == "xlsx":
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Descuentos por Canal"
        ws.append([titulo_documento])
        ws.cell(1, 1).font = Font(name="Calibri", size=14, bold=True, color="1E293B")
        ws.append([f"Emitido: {fecha_legible}{lote_txt} | Responsable: {usuario} | SKUs descontados: {len(ordenados)}"])

        filas_xl = [
            [
                x["codigo"],
                x["descripcion"],
                int(x.get("mayoristas", 0)),
                int(x.get("mercado_libre", 0)),
                int(x.get("full", 0)),
                int(x.get("canjes", 0)),
                ", ".join(x.get("remitos") or []) or "-",
            ]
            for x in ordenados
        ]
        _escribir_seccion_excel(
            ws,
            "DETALLE DE PRODUCTOS DESCONTADOS POR CANAL (SOLO CON MOVIMIENTO)",
            ["Código", "Descripción", "Mayoristas", "Mercado Libre", "Full", "Canjes/Otros", "Remitos / Lotes"],
            filas_xl or [["—", "Sin productos descontados en este lote.", 0, 0, 0, 0, "-"]],
            fila_totales=["TOTALES", f"{len(ordenados)} SKU(s)", tot_may, tot_ml, tot_full, tot_canj, f"Pedidos: {len(pedidos_procesados)}"] if ordenados else None,
        )

        if ingresos:
            filas_ing_xl = [
                [
                    x["code"],
                    x["name"],
                    x.get("origen_ingreso", "-"),
                    int(x.get("cantidad_ingreso", 0)),
                    int(x.get("stock_cierre", 0)),
                ]
                for x in ingresos
            ]
            _escribir_seccion_excel(
                ws,
                "INGRESOS REGISTRADOS EN LA JORNADA",
                ["Código", "Descripción", "Origen / Motivo", "Ingreso (+)", "Stock Resultante"],
                filas_ing_xl,
                fila_totales=["TOTALES", f"{len(ingresos)} SKU(s)", "-", tot_ing, ""],
            )

        if pedidos_procesados:
            filas_ped_xl = []
            for doc in pedidos_procesados:
                cli = getattr(doc, "cliente", "") or getattr(doc, "nombre_archivo", "")
                rem = getattr(doc, "nota_pedido", "") or getattr(doc, "numero_remito", "")
                log = getattr(doc, "logistica", "-")
                bul = getattr(doc, "bultos", 1)
                canal = getattr(doc, "canal_efectivo", "") if hasattr(doc, "canal_efectivo") else ""
                filas_ped_xl.append([canal.upper() or "-", cli, str(rem), log, bul])
            _escribir_seccion_excel(
                ws,
                "DOCUMENTOS Y PEDIDOS PROCESADOS",
                ["Canal", "Cliente", "N° Remito / Pedido", "Logística", "Bultos"],
                filas_ped_xl,
            )

        _autoajustar_columnas_excel(ws)
        wb.save(ruta_salida)
        wb.close()
        return ruta_salida

    # Renderizado PDF A4
    st = crear_estilos_pdf()
    subtitulo = f"Emitido: {fecha_legible}{lote_txt} | Responsable: <b>{usuario}</b> | Sólo artículos con movimiento"
    tarjetas = [
        ("SKUs Descontados", str(len(ordenados))),
        ("Mayoristas", str(tot_may)),
        ("Mercado Libre", str(tot_ml)),
        ("Mercado Full", str(tot_full)),
    ]
    if ingresos:
        tarjetas.append(("Ingresos (+)", f"+{tot_ing} ({len(ingresos)} SKUs)"))
    elif tot_canj > 0:
        tarjetas.append(("Canjes / Otros", str(tot_canj)))

    cuerpo: list[Any] = [_construir_bloque_kpis_pdf(tarjetas, st), Spacer(1, 0.35 * cm)]

    cuerpo.append(_construir_titulo_seccion_pdf("1. Productos Descontados por Canal", st))
    filas_pdf: list[list[Any]] = [[
        Paragraph("Código", st["th"]),
        Paragraph("Descripción", st["th"]),
        Paragraph("Mayoristas", st["th"]),
        Paragraph("Mercado Libre", st["th"]),
        Paragraph("Full", st["th"]),
        Paragraph("Remitos / Canjes", st["th"]),
    ]]
    if ordenados:
        for item in ordenados:
            rems = ", ".join(item.get("remitos") or []) or "-"
            canj = int(item.get("canjes", 0))
            if canj > 0:
                rems = f"[Canje: {canj}] {rems}".strip()
            filas_pdf.append([
                Paragraph(str(item["codigo"]), st["td_center"]),
                Paragraph(str(item["descripcion"])[:48], st["td"]),
                Paragraph(f"<b>{_fmt_num(int(item.get('mayoristas', 0)))}</b>", st["td_center"]),
                Paragraph(f"<b>{_fmt_num(int(item.get('mercado_libre', 0)))}</b>", st["td_center"]),
                Paragraph(f"<b>{_fmt_num(int(item.get('full', 0)))}</b>", st["td_center"]),
                Paragraph(rems[:38], st["td"]),
            ])
        filas_pdf.append([
            Paragraph("<b>TOTAL</b>", st["td_center"]),
            Paragraph(f"<b>{len(ordenados)} producto(s) descontados</b>", st["td"]),
            Paragraph(f"<b>{tot_may}</b>", st["td_center"]),
            Paragraph(f"<b>{tot_ml}</b>", st["td_center"]),
            Paragraph(f"<b>{tot_full}</b>", st["td_center"]),
            Paragraph(f"<b>Canjes: {tot_canj}</b>" if tot_canj else f"<b>{len(pedidos_procesados)} ped.</b>", st["td_center"]),
        ])
    else:
        filas_pdf.append([
            Paragraph("—", st["td_center"]),
            Paragraph("Sin salidas registradas en este lote.", st["td"]),
            Paragraph("0", st["td_center"]),
            Paragraph("0", st["td_center"]),
            Paragraph("0", st["td_center"]),
            Paragraph("-", st["td"]),
        ])

    cuerpo.append(construir_tabla_zebra(filas_pdf, [2.3 * cm, 6.2 * cm, 2.0 * cm, 2.3 * cm, 1.8 * cm, 4.0 * cm]))

    if ingresos:
        cuerpo.append(Spacer(1, 0.35 * cm))
        cuerpo.append(_construir_titulo_seccion_pdf("2. Ingresos de Mercadería en la Jornada", st))
        filas_ing: list[list[Any]] = [[
            Paragraph("Código", st["th"]),
            Paragraph("Descripción", st["th"]),
            Paragraph("Origen / Motivo", st["th"]),
            Paragraph("Ingreso (+)", st["th"]),
            Paragraph("Stock Final", st["th"]),
        ]]
        for item in ingresos:
            filas_ing.append([
                Paragraph(str(item["code"]), st["td_center"]),
                Paragraph(str(item["name"])[:50], st["td"]),
                Paragraph(str(item.get("origen_ingreso", "-"))[:36], st["td"]),
                Paragraph(f"<b>+{item['cantidad_ingreso']}</b>", st["td_center"]),
                Paragraph(str(item["stock_cierre"]), st["td_center"]),
            ])
        cuerpo.append(construir_tabla_zebra(filas_ing, [2.5 * cm, 6.8 * cm, 4.8 * cm, 2.2 * cm, 2.3 * cm]))

    if pedidos_procesados:
        cuerpo.append(Spacer(1, 0.35 * cm))
        cuerpo.append(_construir_titulo_seccion_pdf("Documentos / Pedidos Procesados", st))
        filas_docs: list[list[Any]] = [[
            Paragraph("Canal", st["th"]),
            Paragraph("Cliente", st["th"]),
            Paragraph("N° Remito / Pedido", st["th"]),
            Paragraph("Logística", st["th"]),
            Paragraph("Bultos", st["th"]),
        ]]
        for doc in pedidos_procesados:
            canal = getattr(doc, "canal_efectivo", "") if hasattr(doc, "canal_efectivo") else getattr(doc, "archivo", "")
            cli = getattr(doc, "cliente", "") or "-"
            rem = getattr(doc, "nota_pedido", "") or getattr(doc, "numero_remito", "-")
            log = getattr(doc, "logistica", "-")
            bul = getattr(doc, "bultos", 1)
            filas_docs.append([
                Paragraph(str(canal).upper()[:18], st["td_center"]),
                Paragraph(str(cli)[:40], st["td"]),
                Paragraph(str(rem)[:24], st["td_center"]),
                Paragraph(str(log)[:22], st["td_center"]),
                Paragraph(str(bul), st["td_center"]),
            ])
        cuerpo.append(construir_tabla_zebra(filas_docs, [2.8 * cm, 6.0 * cm, 4.0 * cm, 4.0 * cm, 1.8 * cm]))

    if sin_coincidencia:
        cuerpo.append(Spacer(1, 0.35 * cm))
        cuerpo.append(_construir_titulo_seccion_pdf("Incidencias · Productos Sin Coincidencia", st))
        filas_inc: list[list[Any]] = [[
            Paragraph("Código", st["th"]),
            Paragraph("Archivo / Pedido", st["th"]),
            Paragraph("Producto", st["th"]),
            Paragraph("Motivo", st["th"]),
        ]]
        for cod_i, arch_i, desc_i, mot_i in sin_coincidencia:
            filas_inc.append([
                Paragraph(str(cod_i or "-"), st["td_center"]),
                Paragraph(str(arch_i or "-")[:28], st["td"]),
                Paragraph(str(desc_i or "-")[:42], st["td"]),
                Paragraph(str(mot_i or "-")[:34], st["td"]),
            ])
        cuerpo.append(construir_tabla_zebra(filas_inc, [2.4 * cm, 4.2 * cm, 6.5 * cm, 5.5 * cm]))

    cuerpo.append(Spacer(1, 0.3 * cm))
    cuerpo.append(_construir_firmas_pdf(st))
    return compilar_pdf_reporte(
        ruta_salida=ruta_salida,
        titulo_doc=titulo_documento,
        subtitulo_html=subtitulo,
        titulo_canvas=f"StockAgent · {titulo_documento}",
        fecha_legible=fecha_legible,
        cuerpo_extra=cuerpo,
        st=st,
    )


def generar_reporte_movimientos_estandar(
    resumen_periodo: dict[str, Any],
    carpeta_destino: Path,
    formato: str = "pdf",
    usuario: str = "Administrador",
    modo: str = "ambos",
    fecha_desde: str = "",
    fecha_hasta: str = "",
    pedidos_procesados: Sequence[Any] = (),
    canales_por_sku: dict[str, dict[str, Any]] | None = None,
    prefijo_archivo: str = "Reporte_Movimientos",
    titulo_documento: str | None = None,
    cierre_id: int | None = None,
    timestamp_sufijo: str | None = None,
) -> Path:
    """Genera el reporte estándar de Salidas, Ingresos o Consolidado Administrador (suma total por SKU)."""
    carpeta_destino = Path(carpeta_destino)
    carpeta_destino.mkdir(parents=True, exist_ok=True)
    ahora = datetime.now()
    ts = timestamp_sufijo or ahora.strftime("%Y%m%d_%H%M%S")
    fecha_legible = ahora.strftime("%d/%m/%Y %H:%M")

    modo_clean = (modo or "ambos").strip().lower()
    salidas = list(resumen_periodo.get("salidas") or [])
    ingresos = list(resumen_periodo.get("ingresos") or [])
    kpis = dict(resumen_periodo.get("kpis") or {})

    if not titulo_documento:
        if modo_clean == "salidas":
            titulo_documento = "REPORTE ESTÁNDAR DE SALIDAS DE STOCK"
        elif modo_clean == "ingresos":
            titulo_documento = "REPORTE ESTÁNDAR DE INGRESOS DE STOCK"
        elif modo_clean == "cierre_admin":
            titulo_documento = "CIERRE DIARIO CONSOLIDADO · ADMINISTRACIÓN"
        else:
            titulo_documento = "REPORTE ESTÁNDAR DE MOVIMIENTOS (ENTRADAS Y SALIDAS)"

    incluir_salidas = modo_clean in ("salidas", "ambos", "cierre_admin")
    incluir_ingresos = modo_clean in ("ingresos", "ambos", "cierre_admin")
    lote_txt = f" | Cierre #{cierre_id}" if cierre_id else ""
    rango_txt = f"Período: {fecha_desde[:16]} al {fecha_hasta[:16]}" if (fecha_desde or fecha_hasta) else "Jornada Actual"
    ext = "pdf" if formato.lower() == "pdf" else "xlsx"
    ruta_salida = carpeta_destino / f"{prefijo_archivo}_{ts}.{ext}"

    def _etiqueta_origen_salida(item: dict[str, Any]) -> str:
        base = str(item.get("origen_salida") or "-")
        if canales_por_sku and item["code"] in canales_por_sku:
            ch = canales_por_sku[item["code"]]
            partes = []
            if ch.get("mayoristas"):
                partes.append(f"May:{ch['mayoristas']}")
            if ch.get("mercado_libre"):
                partes.append(f"ML:{ch['mercado_libre']}")
            if ch.get("full"):
                partes.append(f"Full:{ch['full']}")
            if ch.get("canjes"):
                partes.append(f"Canj:{ch['canjes']}")
            if partes:
                return " | ".join(partes)
        return base

    if ext == "xlsx":
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Movimientos Consolidados"
        ws.append([titulo_documento])
        ws.cell(1, 1).font = Font(name="Calibri", size=14, bold=True, color="1E293B")
        ws.append([f"{rango_txt}{lote_txt} | Emitido: {fecha_legible} | Generado por: {usuario}"])

        if incluir_salidas:
            filas_sal_xl = [
                [
                    s["code"],
                    s["name"],
                    _etiqueta_origen_salida(s),
                    int(s["stock_inicial"]),
                    -int(s["cantidad_salida"]),
                    int(s["stock_cierre"]),
                    s["estado_inventario"],
                ]
                for s in salidas
            ]
            _escribir_seccion_excel(
                ws,
                "SALIDAS CONSOLIDADAS POR PRODUCTO (SUMA TOTAL)",
                ["Código", "Descripción", "Origen / Desglose", "Stock Ini.", "Total Salida (-)", "Stock Cierre", "Estado"],
                filas_sal_xl or [["—", "Sin salidas en el período.", "-", 0, 0, 0, "-"]],
                fila_totales=["TOTAL", f"{len(salidas)} SKU(s)", "-", "", -int(kpis.get("unidades_salida", 0)), "", ""] if salidas else None,
            )

        if incluir_ingresos:
            filas_ing_xl = [
                [
                    ing["code"],
                    ing["name"],
                    ing.get("origen_ingreso", "-"),
                    int(ing["stock_inicial"]),
                    int(ing["cantidad_ingreso"]),
                    int(ing["stock_cierre"]),
                    ing.get("responsables", "-"),
                ]
                for ing in ingresos
            ]
            _escribir_seccion_excel(
                ws,
                "INGRESOS CONSOLIDADOS POR PRODUCTO",
                ["Código", "Descripción", "Origen / Motivo", "Stock Ini.", "Total Ingreso (+)", "Stock Cierre", "Responsable"],
                filas_ing_xl or [["—", "Sin ingresos en el período.", "-", 0, 0, 0, "-"]],
                fila_totales=["TOTAL", f"{len(ingresos)} SKU(s)", "-", "", int(kpis.get("unidades_ingreso", 0)), "", ""] if ingresos else None,
            )

        _autoajustar_columnas_excel(ws)
        wb.save(ruta_salida)
        wb.close()
        return ruta_salida

    st = crear_estilos_pdf()
    subtitulo = f"{rango_txt}{lote_txt} | Emitido: {fecha_legible} | Responsable: <b>{usuario}</b>"
    tarjetas: list[tuple[str, str]] = []
    if incluir_salidas:
        tarjetas.extend([
            ("SKUs con Salida", str(kpis.get("skus_salida", len(salidas)))),
            ("Unidades Salidas", str(kpis.get("unidades_salida", 0))),
        ])
    if incluir_ingresos:
        tarjetas.extend([
            ("SKUs con Ingreso", str(kpis.get("skus_ingreso", len(ingresos)))),
            ("Unidades Ingresadas", str(kpis.get("unidades_ingreso", 0))),
        ])
    if incluir_salidas and incluir_ingresos:
        neto = int(kpis.get("variacion_neta", 0))
        tarjetas.append(("Balance Neto", f"+{neto}" if neto > 0 else str(neto)))

    cuerpo: list[Any] = [_construir_bloque_kpis_pdf(tarjetas, st), Spacer(1, 0.35 * cm)]

    if incluir_salidas:
        cuerpo.append(_construir_titulo_seccion_pdf("1. Salidas Consolidadas por Producto (Suma Total)", st))
        filas_sal: list[list[Any]] = [[
            Paragraph("Código", st["th"]),
            Paragraph("Descripción", st["th"]),
            Paragraph("Origen / Canales", st["th"]),
            Paragraph("Stock Ini.", st["th"]),
            Paragraph("Total Salida", st["th"]),
            Paragraph("Stock Final", st["th"]),
            Paragraph("Estado", st["th"]),
        ]]
        if salidas:
            for item in salidas:
                filas_sal.append([
                    Paragraph(str(item["code"]), st["td_center"]),
                    Paragraph(str(item["name"])[:42], st["td"]),
                    Paragraph(_etiqueta_origen_salida(item)[:36], st["td"]),
                    Paragraph(str(item["stock_inicial"]), st["td_center"]),
                    Paragraph(f"<b>-{item['cantidad_salida']}</b>", st["td_center"]),
                    Paragraph(f"<b>{item['stock_cierre']}</b>", st["td_center"]),
                    _estilo_estado_cell(str(item["estado_inventario"]), st),
                ])
            filas_sal.append([
                Paragraph("<b>TOTAL</b>", st["td_center"]),
                Paragraph(f"<b>{len(salidas)} SKU(s) con egreso</b>", st["td"]),
                Paragraph("-", st["td_center"]),
                Paragraph("-", st["td_center"]),
                Paragraph(f"<b>-{sum(x['cantidad_salida'] for x in salidas)}</b>", st["td_center"]),
                Paragraph("-", st["td_center"]),
                Paragraph("-", st["td_center"]),
            ])
        else:
            filas_sal.append([
                Paragraph("—", st["td_center"]),
                Paragraph("No se registraron salidas en el período seleccionado.", st["td"]),
                Paragraph("-", st["td_center"]),
                Paragraph("0", st["td_center"]),
                Paragraph("0", st["td_center"]),
                Paragraph("0", st["td_center"]),
                Paragraph("-", st["td_center"]),
            ])
        cuerpo.append(construir_tabla_zebra(filas_sal, [2.1 * cm, 5.2 * cm, 4.1 * cm, 1.7 * cm, 1.8 * cm, 1.8 * cm, 1.9 * cm]))

    if incluir_ingresos:
        if incluir_salidas:
            cuerpo.append(Spacer(1, 0.35 * cm))
        num_sec = "2." if incluir_salidas else "1."
        cuerpo.append(_construir_titulo_seccion_pdf(f"{num_sec} Ingresos de Mercadería por Producto", st))
        filas_ing: list[list[Any]] = [[
            Paragraph("Código", st["th"]),
            Paragraph("Descripción", st["th"]),
            Paragraph("Origen / Motivo", st["th"]),
            Paragraph("Stock Ini.", st["th"]),
            Paragraph("Ingreso (+)", st["th"]),
            Paragraph("Stock Final", st["th"]),
            Paragraph("Responsable", st["th"]),
        ]]
        if ingresos:
            for item in ingresos:
                filas_ing.append([
                    Paragraph(str(item["code"]), st["td_center"]),
                    Paragraph(str(item["name"])[:42], st["td"]),
                    Paragraph(str(item.get("origen_ingreso", "-"))[:36], st["td"]),
                    Paragraph(str(item["stock_inicial"]), st["td_center"]),
                    Paragraph(f"<b>+{item['cantidad_ingreso']}</b>", st["td_center"]),
                    Paragraph(f"<b>{item['stock_cierre']}</b>", st["td_center"]),
                    Paragraph(str(item.get("responsables", "-"))[:20], st["td_center"]),
                ])
            filas_ing.append([
                Paragraph("<b>TOTAL</b>", st["td_center"]),
                Paragraph(f"<b>{len(ingresos)} SKU(s) con ingreso</b>", st["td"]),
                Paragraph("-", st["td_center"]),
                Paragraph("-", st["td_center"]),
                Paragraph(f"<b>+{sum(x['cantidad_ingreso'] for x in ingresos)}</b>", st["td_center"]),
                Paragraph("-", st["td_center"]),
                Paragraph("-", st["td_center"]),
            ])
        else:
            filas_ing.append([
                Paragraph("—", st["td_center"]),
                Paragraph("No se registraron ingresos en el período seleccionado.", st["td"]),
                Paragraph("-", st["td_center"]),
                Paragraph("0", st["td_center"]),
                Paragraph("0", st["td_center"]),
                Paragraph("0", st["td_center"]),
                Paragraph("-", st["td_center"]),
            ])
        cuerpo.append(construir_tabla_zebra(filas_ing, [2.1 * cm, 5.2 * cm, 4.1 * cm, 1.7 * cm, 1.8 * cm, 1.8 * cm, 1.9 * cm]))

    criticos_post = [s for s in salidas if s.get("estado_inventario") in ("AGOTADO", "QUIEBRE_INMINENTE")]
    if criticos_post:
        cuerpo.append(Spacer(1, 0.35 * cm))
        cuerpo.append(_construir_titulo_seccion_pdf("Alertas de Reposición Generadas en el Período", st))
        filas_al: list[list[Any]] = [[
            Paragraph("Código", st["th"]),
            Paragraph("Producto", st["th"]),
            Paragraph("Ubicación", st["th"]),
            Paragraph("Stock Final", st["th"]),
            Paragraph("Stock Mín.", st["th"]),
            Paragraph("Estado", st["th"]),
        ]]
        for item in criticos_post:
            filas_al.append([
                Paragraph(str(item["code"]), st["td_center"]),
                Paragraph(str(item["name"])[:50], st["td"]),
                Paragraph(str(item.get("ubicacion") or "-")[:16], st["td_center"]),
                Paragraph(f"<b>{item['stock_cierre']}</b>", st["td_center"]),
                Paragraph(str(item.get("stock_minimo", 5)), st["td_center"]),
                _estilo_estado_cell(str(item["estado_inventario"]), st),
            ])
        cuerpo.append(construir_tabla_zebra(filas_al, [2.3 * cm, 7.6 * cm, 2.5 * cm, 2.0 * cm, 2.0 * cm, 2.2 * cm]))

    cuerpo.append(Spacer(1, 0.3 * cm))
    cuerpo.append(_construir_firmas_pdf(st))
    return compilar_pdf_reporte(
        ruta_salida=ruta_salida,
        titulo_doc=titulo_documento,
        subtitulo_html=subtitulo,
        titulo_canvas=f"StockAgent · {titulo_documento}",
        fecha_legible=fecha_legible,
        cuerpo_extra=cuerpo,
        st=st,
    )
