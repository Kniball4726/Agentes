"""Generador del reporte operativo de descuentos discriminado por canales (Mayoristas, ML y Full)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Sequence

import openpyxl
from openpyxl.styles import Font
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, Spacer

from .report_styles import (
    _autoajustar_columnas_excel,
    compilar_pdf_reporte,
    construir_tabla_zebra,
    crear_estilos_pdf,
)
from .reports_movements_common import (
    _construir_bloque_kpis_pdf,
    _construir_firmas_pdf,
    _construir_titulo_seccion_pdf,
    _escribir_seccion_excel,
    _fmt_num,
    _ordenar_items_por_catalogo,
)


def _renderizar_canales_excel(
    *,
    ruta_salida: Path,
    titulo_documento: str,
    fecha_legible: str,
    lote_txt: str,
    usuario: str,
    ordenados: list[dict[str, Any]],
    ingresos: list[dict[str, Any]],
    pedidos_procesados: Sequence[Any],
    totales: tuple[int, int, int, int, int],
) -> Path:
    tot_may, tot_ml, tot_full, tot_canj, tot_ing = totales
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
        fila_totales=(
            ["TOTALES", f"{len(ordenados)} SKU(s)", tot_may, tot_ml, tot_full, tot_canj, f"Pedidos: {len(pedidos_procesados)}"]
            if ordenados
            else None
        ),
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
        return _renderizar_canales_excel(
            ruta_salida=ruta_salida,
            titulo_documento=titulo_documento,
            fecha_legible=fecha_legible,
            lote_txt=lote_txt,
            usuario=usuario,
            ordenados=ordenados,
            ingresos=ingresos,
            pedidos_procesados=pedidos_procesados,
            totales=(tot_may, tot_ml, tot_full, tot_canj, tot_ing),
        )

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
