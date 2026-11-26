"""Módulo de ejecución para el Cierre de Mercado (Mercado Libre y Mercado Full) para pickers."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from ....consolidator import ItemConsolidado
from ....parsers.remito_parser import ItemRemito, ResultadoRemito, normalizar_codigo
from .._shared import resolve_stock_manager

logger = logging.getLogger("stockagent.ui.cierre_mercado")


def _resolver_sm_cls(interfaz: Any = None):
    return resolve_stock_manager(interfaz)


def ejecutar_tarea_cierre_mercado(
    interfaz: Any,
    pedidos_seleccionados: list[Any],
    tipo_mercado: str = "TODOS",
) -> dict[str, Any]:
    """Ejecuta el cálculo consolidado del lote de mercado, genera el PDF/Excel y sella los pedidos."""
    if not pedidos_seleccionados:
        raise ValueError("No hay pedidos seleccionados para cerrar mercado.")

    pedidos_ids = [p.id for p in pedidos_seleccionados]
    items_raw = interfaz.order_store.obtener_items_mercado_pendientes(pedidos_ids)
    items_consolidados: dict[str, ItemConsolidado] = {}

    for cod, desc, cant, remitos in items_raw:
        cod_n = normalizar_codigo(cod)
        if cod_n not in items_consolidados:
            items_consolidados[cod_n] = ItemConsolidado(
                codigo=cod_n,
                descripcion=desc,
                cantidad_total=cant,
                remitos_origen=list(remitos),
            )
        else:
            items_consolidados[cod_n].cantidad_total += cant
            for rem in remitos:
                if rem not in items_consolidados[cod_n].remitos_origen:
                    items_consolidados[cod_n].remitos_origen.append(rem)

    # Si algún pedido no tenía items en pedido_items por ser legacy, intentar recuperar de items_db o archivo
    if not items_consolidados:
        for p in pedidos_seleccionados:
            items_db = interfaz.order_store.obtener_items_pedido(p.id) if hasattr(interfaz.order_store, "obtener_items_pedido") else []
            for cod, desc, cant in items_db:
                cod_n = normalizar_codigo(cod)
                if cod_n not in items_consolidados:
                    items_consolidados[cod_n] = ItemConsolidado(
                        codigo=cod_n,
                        descripcion=desc,
                        cantidad_total=cant,
                        remitos_origen=[p.nota_pedido],
                    )
                else:
                    items_consolidados[cod_n].cantidad_total += cant
                    if p.nota_pedido not in items_consolidados[cod_n].remitos_origen:
                        items_consolidados[cod_n].remitos_origen.append(p.nota_pedido)

    sm_cls = _resolver_sm_cls(interfaz)
    stock_mgr = sm_cls(ruta_excel_base=interfaz.menu.ruta_excel_base)

    pedidos_doc: list[ResultadoRemito] = []
    for p in pedidos_seleccionados:
        items_db = interfaz.order_store.obtener_items_pedido(p.id) if hasattr(interfaz.order_store, "obtener_items_pedido") else []
        items_p = [
            ItemRemito(codigo=normalizar_codigo(cod), descripcion=desc, cantidad=cant, origen_remito=p.nota_pedido)
            for cod, desc, cant in items_db
        ]
        pedidos_doc.append(
            ResultadoRemito(
                archivo=p.nombre_archivo,
                numero_remito=p.nota_pedido,
                fecha=p.created_at[:10] if len(p.created_at) >= 10 else "",
                cliente=p.cliente,
                articulos_declarados=p.articulos_descontados,
                articulos_extraidos=p.articulos_descontados,
                items=items_p,
                descripciones_sin_coincidencia=[],
                verificacion_ok=True,
            )
        )

    prefijo = f"Cierre_Mercado_{tipo_mercado}" if tipo_mercado != "TODOS" else "Cierre_Mercado"
    rep = stock_mgr.aplicar_descuentos(
        items_consolidados=items_consolidados,
        carpeta_destino=interfaz.menu.carpeta_descuentos,
        pedidos_procesados=pedidos_doc,
        guardar_archivo=True,
        prefijo_archivo=prefijo,
        descuento_ya_aplicado=True,
    )

    pdf_path = Path(rep.archivo_pdf) if rep.archivo_pdf else None
    xls_path = Path(rep.archivo_guardado) if rep.archivo_guardado else None
    usr = interfaz.usuario_actual.username if interfaz.usuario_actual else "Picker"

    # En ejecuciones reales (no mockeadas), generar comprobante compacto solo con artículos descontados
    if (
        hasattr(interfaz.order_store, "obtener_descuentos_operario_por_canal")
        and pdf_path
        and pdf_path.exists()
    ):
        try:
            from ....stock.reports_movements import generar_reporte_descuento_operario_canales

            items_canal = interfaz.order_store.obtener_descuentos_operario_por_canal(
                pedidos_ids=pedidos_ids
            )
            mapa_orden = {
                cod: idx
                for idx, (_, cod, _, _) in enumerate(getattr(stock_mgr, "filas_catalogo", []) or [])
            }
            pdf_gen = generar_reporte_descuento_operario_canales(
                items_canal=items_canal,
                carpeta_destino=interfaz.menu.carpeta_descuentos,
                formato="pdf",
                usuario=usr,
                pedidos_procesados=pedidos_seleccionados,
                mapa_orden_catalogo=mapa_orden,
                prefijo_archivo=prefijo,
                titulo_documento=f"CIERRE DE MERCADO · {tipo_mercado.replace('_', ' ')}",
            )
            xls_gen = generar_reporte_descuento_operario_canales(
                items_canal=items_canal,
                carpeta_destino=interfaz.menu.carpeta_descuentos,
                formato="xlsx",
                usuario=usr,
                pedidos_procesados=pedidos_seleccionados,
                mapa_orden_catalogo=mapa_orden,
                prefijo_archivo=prefijo,
                titulo_documento=f"CIERRE DE MERCADO · {tipo_mercado.replace('_', ' ')}",
            )
            if pdf_gen != pdf_path:
                pdf_path.unlink(missing_ok=True)
            if xls_path and xls_path.exists() and xls_gen != xls_path:
                xls_path.unlink(missing_ok=True)
            pdf_path, xls_path = pdf_gen, xls_gen
        except Exception:
            pass

    total_arts = sum(it.cantidad_total for it in items_consolidados.values())
    resumen_p = f"{len(pedidos_seleccionados)} pedidos ({total_arts} un.)"

    cierre_m_id = interfaz.order_store.registrar_cierre_mercado(
        usuario=usr,
        tipo_mercado=tipo_mercado,
        pedidos_ids=pedidos_ids,
        articulos_totales=total_arts,
        resumen_pedidos=resumen_p,
        archivo_pdf=pdf_path.name if pdf_path else "",
        archivo_excel=xls_path.name if xls_path else "",
    )

    # Notificación colaborativa interna
    if hasattr(interfaz, "sincronizar_sesiones"):
        try:
            interfaz.sincronizar_sesiones(
                aviso_colaborativo=f"📦 {usr} cerró tanda de Mercado #{cierre_m_id} ({resumen_p})"
            )
        except Exception:
            pass

    return {
        "cierre_id": cierre_m_id,
        "pdf_path": pdf_path,
        "xls_path": xls_path,
        "resumen": resumen_p,
        "total_articulos": total_arts,
    }
