"""Helper modular para construir los reportes Operario (3 canales) y Administrador (suma total) de un cierre."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Sequence

from ....orders.models import clasificar_canal_pedido
from ....stock.reports_movements import (
    generar_reporte_descuento_operario_canales,
    generar_reporte_movimientos_estandar,
)


def _sintetizar_canales_desde_items(
    items_consolidados: dict[str, Any],
    pedidos_pendientes: Sequence[Any],
    order_store: Any,
) -> list[dict[str, Any]]:
    """Construye el desglose por canal usando OrderStore o, como respaldo, los pedidos recibidos."""
    if hasattr(order_store, "obtener_descuentos_operario_por_canal") and pedidos_pendientes:
        try:
            filas = order_store.obtener_descuentos_operario_por_canal(
                pedidos_ids=[p.id for p in pedidos_pendientes]
            )
            if filas:
                return filas
        except Exception:
            pass

    por_sku: dict[str, dict[str, Any]] = {}
    for p in pedidos_pendientes:
        canal = getattr(p, "canal_efectivo", "") or clasificar_canal_pedido(
            tipo_archivo=getattr(p, "tipo_archivo", ""),
            cliente=getattr(p, "cliente", ""),
            nombre_archivo=getattr(p, "nombre_archivo", ""),
            nota_pedido=getattr(p, "nota_pedido", ""),
            logistica=getattr(p, "logistica", ""),
            canal_explicito=getattr(p, "canal", ""),
        )
        items_db = order_store.obtener_items_pedido(p.id) if hasattr(order_store, "obtener_items_pedido") else []
        for cod, desc, cant in items_db:
            cod_s = str(cod or "").strip().upper()
            cant_i = int(cant or 0)
            if not cod_s or cant_i <= 0:
                continue
            entry = por_sku.setdefault(
                cod_s,
                {
                    "codigo": cod_s,
                    "descripcion": str(desc or "").strip(),
                    "mayoristas": 0,
                    "mercado_libre": 0,
                    "full": 0,
                    "canjes": 0,
                    "total": 0,
                    "remitos": [],
                },
            )
            if canal == "mercado_libre":
                entry["mercado_libre"] += cant_i
            elif canal == "full":
                entry["full"] += cant_i
            elif canal == "canje":
                entry["canjes"] += cant_i
            else:
                entry["mayoristas"] += cant_i
            entry["total"] += cant_i
            rem = str(getattr(p, "nota_pedido", "") or "").strip()
            if rem and rem not in entry["remitos"]:
                entry["remitos"].append(rem)

    if por_sku:
        return list(por_sku.values())

    return [
        {
            "codigo": cod,
            "descripcion": getattr(it, "descripcion", cod),
            "mayoristas": int(getattr(it, "cantidad_total", 0)),
            "mercado_libre": 0,
            "full": 0,
            "canjes": 0,
            "total": int(getattr(it, "cantidad_total", 0)),
            "remitos": list(getattr(it, "remitos_origen", []) or []),
        }
        for cod, it in items_consolidados.items()
        if int(getattr(it, "cantidad_total", 0)) > 0
    ]


def _sintetizar_resumen_admin_si_vacio(
    resumen_movs: dict[str, Any],
    descuentos_aplicados: Sequence[Any],
    mapa_orden: dict[str, int],
) -> dict[str, Any]:
    """Completa salidas desde `descuentos_aplicados` si la consulta temporal de movimientos llegó vacía."""
    if resumen_movs.get("salidas") or not descuentos_aplicados:
        return resumen_movs

    salidas = []
    for d in descuentos_aplicados:
        if int(getattr(d, "cantidad_descontada", 0)) <= 0:
            continue
        stock_f = int(getattr(d, "stock_nuevo", 0))
        estado = "AGOTADO" if stock_f <= 0 else ("QUIEBRE_INMINENTE" if stock_f <= 5 else "OPTIMO")
        salidas.append(
            {
                "code": d.codigo,
                "name": d.nombre_producto,
                "ubicacion": "",
                "display_order": mapa_orden.get(d.codigo, 999999),
                "stock_minimo": 5,
                "stock_maximo": 100,
                "stock_inicial": int(getattr(d, "stock_anterior", stock_f + d.cantidad_descontada)),
                "cantidad_salida": int(d.cantidad_descontada),
                "cantidad_ingreso": 0,
                "variacion_neta": -int(d.cantidad_descontada),
                "stock_cierre": stock_f,
                "origen_salida": "Descuento Cierre",
                "origen_ingreso": "-",
                "responsables": "Operario",
                "estado_inventario": estado,
            }
        )
    salidas.sort(key=lambda x: (x["display_order"], x["code"]))
    ingresos = list(resumen_movs.get("ingresos") or [])
    tot_sal = sum(x["cantidad_salida"] for x in salidas)
    tot_ing = sum(x["cantidad_ingreso"] for x in ingresos)
    return {
        "salidas": salidas,
        "ingresos": ingresos,
        "resumen_productos": salidas + ingresos,
        "kpis": {
            "skus_salida": len(salidas),
            "unidades_salida": tot_sal,
            "skus_ingreso": len(ingresos),
            "unidades_ingreso": tot_ing,
            "variacion_neta": tot_ing - tot_sal,
        },
    }


def generar_reportes_cierre_jornada(
    interfaz: Any,
    stock_mgr: Any,
    pedidos_pendientes: Sequence[Any],
    pedidos_doc: Sequence[Any],
    items_consolidados: dict[str, Any],
    reporte_simulado: Any,
    usr_cierre: str,
    fecha_desde: str,
    fecha_hasta: str,
    cierre_anterior_id: int | None,
) -> dict[str, Any]:
    """Genera los comprobantes PDF y Excel Operario (3 canales) y Admin (suma total por producto)."""
    carpeta = Path(interfaz.menu.carpeta_descuentos)
    carpeta.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    mapa_orden = {
        cod: idx
        for idx, (_, cod, _, _) in enumerate(getattr(stock_mgr, "filas_catalogo", []) or [])
    }

    resumen_movs: dict[str, Any] = {
        "salidas": [],
        "ingresos": [],
        "resumen_productos": [],
        "kpis": {"skus_salida": 0, "unidades_salida": 0, "skus_ingreso": 0, "unidades_ingreso": 0, "variacion_neta": 0},
    }
    product_store = getattr(stock_mgr, "product_store", None)
    if product_store and hasattr(product_store, "get_period_movements_summary"):
        try:
            resumen_movs = product_store.get_period_movements_summary(
                fecha_desde,
                fecha_hasta,
                order_by="catalog",
                strict_after_from=(cierre_anterior_id is not None),
            )
        except Exception:
            pass

    items_canal = _sintetizar_canales_desde_items(items_consolidados, pedidos_pendientes, interfaz.order_store)
    canales_por_sku = {it["codigo"]: it for it in items_canal}

    sin_coincidencia: list[tuple[str, str, str, str]] = []
    for doc in pedidos_doc:
        for desc_sc, mot_sc in getattr(doc, "descripciones_sin_coincidencia", []) or []:
            sin_coincidencia.append(("-", getattr(doc, "archivo", "-"), str(desc_sc), str(mot_sc)))

    pdf_operario = generar_reporte_descuento_operario_canales(
        items_canal=items_canal,
        carpeta_destino=carpeta,
        formato="pdf",
        usuario=usr_cierre,
        pedidos_procesados=pedidos_pendientes,
        ingresos_periodo=resumen_movs.get("ingresos"),
        sin_coincidencia=sin_coincidencia,
        mapa_orden_catalogo=mapa_orden,
        prefijo_archivo="Cierre_Descuento",
        titulo_documento="CIERRE DIARIO · DESCUENTOS POR CANAL",
        timestamp_sufijo=ts,
    )
    xls_operario = generar_reporte_descuento_operario_canales(
        items_canal=items_canal,
        carpeta_destino=carpeta,
        formato="xlsx",
        usuario=usr_cierre,
        pedidos_procesados=pedidos_pendientes,
        ingresos_periodo=resumen_movs.get("ingresos"),
        sin_coincidencia=sin_coincidencia,
        mapa_orden_catalogo=mapa_orden,
        prefijo_archivo="Cierre_Descuento",
        titulo_documento="CIERRE DIARIO · DESCUENTOS POR CANAL",
        timestamp_sufijo=ts,
    )

    resumen_admin = _sintetizar_resumen_admin_si_vacio(
        resumen_movs,
        getattr(reporte_simulado, "descuentos_aplicados", []) or [],
        mapa_orden,
    )
    admin_pdf = generar_reporte_movimientos_estandar(
        resumen_periodo=resumen_admin,
        carpeta_destino=carpeta,
        formato="pdf",
        usuario=usr_cierre,
        modo="cierre_admin",
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        pedidos_procesados=pedidos_pendientes,
        canales_por_sku=canales_por_sku,
        prefijo_archivo="Cierre_Admin_Consolidado",
        timestamp_sufijo=ts,
    )
    admin_xls = generar_reporte_movimientos_estandar(
        resumen_periodo=resumen_admin,
        carpeta_destino=carpeta,
        formato="xlsx",
        usuario=usr_cierre,
        modo="cierre_admin",
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        pedidos_procesados=pedidos_pendientes,
        canales_por_sku=canales_por_sku,
        prefijo_archivo="Cierre_Admin_Consolidado",
        timestamp_sufijo=ts,
    )

    return {
        "pdf_path": pdf_operario,
        "xls_path": xls_operario,
        "admin_pdf_path": admin_pdf,
        "admin_xls_path": admin_xls,
    }


def generar_reporte_admin_para_cierre(
    interfaz: Any,
    cierre_obj: Any,
    formato: str = "pdf",
) -> Path:
    """Reconstruye y genera bajo demanda el Reporte Consolidado Administrador para un cierre histórico."""
    from ....paths import application_root
    from ....products import ProductStore

    carpeta = Path(getattr(getattr(interfaz, "menu", None), "carpeta_descuentos", None) or (application_root() / "Descuentos"))
    order_store = interfaz.order_store
    peds = order_store.obtener_pedidos_por_cierre(cierre_obj.id)
    fecha_desde, fecha_hasta, cierre_ant_id = order_store.obtener_ventana_ultimo_cierre(cierre_id=cierre_obj.id)

    product_store = getattr(getattr(interfaz, "stock_manager", None), "product_store", None)
    if product_store is None:
        ruta_db = getattr(interfaz, "ruta_base_datos", None) or getattr(getattr(interfaz, "menu", None), "ruta_base_datos", None)
        if ruta_db and Path(ruta_db).exists():
            product_store = ProductStore(Path(ruta_db))
        else:
            db_default = application_root() / "data" / "productos.sqlite3"
            if db_default.exists():
                product_store = ProductStore(db_default)

    resumen_movs: dict[str, Any] = {
        "salidas": [],
        "ingresos": [],
        "resumen_productos": [],
        "kpis": {"skus_salida": 0, "unidades_salida": 0, "skus_ingreso": 0, "unidades_ingreso": 0, "variacion_neta": 0},
    }
    if product_store and hasattr(product_store, "get_period_movements_summary"):
        resumen_movs = product_store.get_period_movements_summary(
            fecha_desde,
            fecha_hasta,
            order_by="catalog",
            strict_after_from=(cierre_ant_id is not None),
        )

    items_canal = order_store.obtener_descuentos_operario_por_canal(cierre_id=cierre_obj.id)
    canales_por_sku = {it["codigo"]: it for it in items_canal}

    # Si no hubo entradas directas en stock_movements (ej. pruebas sintéticas solo con pedidos),
    # reconstruir la suma total por producto desde los pedidos sellados en ese cierre.
    if not resumen_movs.get("salidas") and items_canal:
        salidas_synth = [
            {
                "code": it["codigo"],
                "name": it["descripcion"],
                "ubicacion": "",
                "display_order": idx,
                "stock_minimo": 5,
                "stock_maximo": 100,
                "stock_inicial": int(it["total"]),
                "cantidad_salida": int(it["total"]),
                "cantidad_ingreso": 0,
                "variacion_neta": -int(it["total"]),
                "stock_cierre": 0,
                "origen_salida": ", ".join(it.get("remitos") or []) or "Cierre",
                "origen_ingreso": "-",
                "responsables": cierre_obj.usuario,
                "estado_inventario": "OPTIMO",
            }
            for idx, it in enumerate(items_canal)
        ]
        tot_sal = sum(s["cantidad_salida"] for s in salidas_synth)
        resumen_movs = {
            "salidas": salidas_synth,
            "ingresos": list(resumen_movs.get("ingresos") or []),
            "resumen_productos": salidas_synth,
            "kpis": {
                "skus_salida": len(salidas_synth),
                "unidades_salida": tot_sal,
                "skus_ingreso": int(resumen_movs.get("kpis", {}).get("skus_ingreso", 0)),
                "unidades_ingreso": int(resumen_movs.get("kpis", {}).get("unidades_ingreso", 0)),
                "variacion_neta": int(resumen_movs.get("kpis", {}).get("unidades_ingreso", 0)) - tot_sal,
            },
        }

    usr_admin = getattr(getattr(interfaz, "usuario_actual", None), "username", None) or "Administrador"
    return generar_reporte_movimientos_estandar(
        resumen_periodo=resumen_movs,
        carpeta_destino=carpeta,
        formato=formato,
        usuario=usr_admin,
        modo="cierre_admin",
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        pedidos_procesados=peds,
        canales_por_sku=canales_por_sku,
        prefijo_archivo=f"Cierre_Admin_{cierre_obj.id}",
        cierre_id=cierre_obj.id,
    )
