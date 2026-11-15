"""Generadores estándar SQLite-Nativos de reportes de Salidas, Ingresos y Cierre Diario."""

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
from .reports_movements_canales import generar_reporte_descuento_operario_canales
from .reports_movements_common import (
    _construir_bloque_kpis_pdf,
    _construir_firmas_pdf,
    _construir_titulo_seccion_pdf,
    _escribir_seccion_excel,
    _estilo_estado_cell,
    _fmt_num,
    _ordenar_items_por_catalogo,
)

__all__ = [
    "_fmt_num",
    "_construir_bloque_kpis_pdf",
    "_construir_titulo_seccion_pdf",
    "_construir_firmas_pdf",
    "_escribir_seccion_excel",
    "_estilo_estado_cell",
    "_ordenar_items_por_catalogo",
    "generar_reporte_descuento_operario_canales",
    "generar_reporte_movimientos_estandar",
]


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
