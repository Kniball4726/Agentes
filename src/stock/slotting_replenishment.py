"""Análisis de multi-ubicación y reposición inteligente a picking priorizada por FEFO."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def _es_coleccion_real(valor: Any, tipo: type) -> bool:
    return isinstance(valor, tipo)


@dataclass
class UbicacionProducto:
    """Representa una ubicación asignada a un SKU dentro del depósito."""

    product_code: str
    ubicacion: str
    tipo_zona: str
    stock: int
    capacidad_max: int = 0
    es_principal: bool = False


@dataclass
class LoteStock:
    """Representa un lote de inventario con fecha de vencimiento para control FEFO."""

    id: int
    product_code: str
    lote: str
    ubicacion: str
    fecha_vencimiento: str
    stock: int
    estado: str
    dias_para_vencer: int | None = None
    vencido: bool = False


@dataclass
class SugerenciaReposicionPicking:
    """Sugerencia de traslado interno (ej. pulmón/pallet -> picking) optimizada por FEFO."""

    product_code: str
    product_name: str
    ubicacion_origen: str
    zona_origen: str
    ubicacion_destino: str
    cantidad_sugerida: int
    stock_picking_actual: int
    stock_reserva_origen: int
    prioridad: str
    motivo: str
    lote_fefo: str = ""
    fecha_vencimiento_fefo: str = ""


def _catalogo_activos_por_codigo(product_store: Any) -> dict[str, dict[str, Any]]:
    if product_store is None or not hasattr(product_store, "list_products"):
        return {}
    try:
        rows = product_store.list_products(active_only=True)
    except TypeError:
        rows = product_store.list_products()
    except Exception:
        return {}
    if not isinstance(rows, (list, tuple)):
        return {}
    mapa: dict[str, dict[str, Any]] = {}
    for row in rows:
        try:
            cod = str(row["code"]).strip()
            mapa[cod] = {
                "code": cod,
                "name": str(row["name"] or cod).strip(),
                "stock": int(row["stock"] or 0),
                "stock_minimo": int(row["stock_minimo"] or 5) if "stock_minimo" in row.keys() else 5,
                "stock_maximo": int(row["stock_maximo"] or 20) if "stock_maximo" in row.keys() else 20,
                "ubicacion": str(row["ubicacion"] or "").strip(),
            }
        except Exception:
            continue
    return mapa


def generar_sugerencias_reposicion_picking(
    product_store: Any,
    dias_alerta_vencimiento: int = 30,
    stock_picking_objetivo: int | None = None,
) -> list[SugerenciaReposicionPicking]:
    """Detecta SKUs con picking bajo/vacío o lotes próximos a vencer en pulmón/pallet."""
    if product_store is None or not hasattr(product_store, "listar_ubicaciones_mapa"):
        return []
    mapa_ubic = product_store.listar_ubicaciones_mapa(solo_activos=True)
    if not _es_coleccion_real(mapa_ubic, dict):
        return []

    catalogo = _catalogo_activos_por_codigo(product_store)
    sugerencias: list[SugerenciaReposicionPicking] = []

    for cod, ubicaciones in mapa_ubic.items():
        if not ubicaciones:
            continue
        p_meta = catalogo.get(cod, {})
        nombre = p_meta.get("name", cod)
        stock_min = max(1, int(p_meta.get("stock_minimo", 5)))
        stock_max = max(stock_min, int(p_meta.get("stock_maximo", stock_min * 2)))

        picks = [u for u in ubicaciones if u.get("tipo_zona") == "picking"]
        destino = picks[0] if picks else ubicaciones[0]
        if destino.get("tipo_zona") not in ("picking",):
            continue

        reservas_origen = [
            u
            for u in ubicaciones
            if u.get("tipo_zona") in ("pulmon", "pallet", "recepcion")
            and int(u.get("stock", 0)) > 0
            and u.get("ubicacion") != destino.get("ubicacion")
        ]
        if not reservas_origen:
            continue

        lotes_activos: list[dict[str, Any]] = []
        if hasattr(product_store, "listar_lotes_fefo"):
            cand_lotes = product_store.listar_lotes_fefo(cod, solo_disponibles=True)
            if _es_coleccion_real(cand_lotes, list):
                lotes_activos = [l for l in cand_lotes if not l.get("vencido", False)]

        cap_dest = int(destino.get("capacidad_max") or 0)
        objetivo_dest = stock_picking_objetivo or (cap_dest if cap_dest > 0 else min(stock_max, stock_min * 2))
        objetivo_dest = max(stock_min, int(objetivo_dest))
        stock_pick = int(destino.get("stock", 0))
        necesita_cantidad = stock_pick <= stock_min

        # Elegir origen priorizando si existe lote FEFO próximo a vencer en reserva
        origen_elegido = max(reservas_origen, key=lambda u: int(u.get("stock", 0)))
        lote_codigo = ""
        lote_fv = ""
        alerta_fefo = False
        for lote in lotes_activos:
            ubic_lote = str(lote.get("ubicacion") or "").upper()
            match = next((u for u in reservas_origen if u.get("ubicacion") == ubic_lote), None)
            if match is not None:
                origen_elegido = match
                lote_codigo = str(lote.get("lote") or "")
                lote_fv = str(lote.get("fecha_vencimiento") or "")
                dias_v = lote.get("dias_para_vencer")
                if dias_v is not None and dias_v <= dias_alerta_vencimiento:
                    alerta_fefo = True
                break

        if not necesita_cantidad and not alerta_fefo:
            continue

        stock_orig = int(origen_elegido.get("stock", 0))
        deficit = max(1, objetivo_dest - stock_pick) if necesita_cantidad else min(stock_orig, stock_min)
        cantidad_sug = min(stock_orig, deficit)
        if cantidad_sug <= 0:
            continue

        if stock_pick == 0 or alerta_fefo:
            prioridad = "URGENTE"
        elif stock_pick <= stock_min:
            prioridad = "ALTA"
        else:
            prioridad = "MEDIA"

        if alerta_fefo and stock_pick > 0:
            motivo = f"Priorizar rotación FEFO lote {lote_codigo} (vence {lote_fv})"
        elif stock_pick == 0:
            motivo = f"Quiebre en picking ({destino['ubicacion']} en 0 u.) con stock en {origen_elegido['tipo_zona']}"
        else:
            motivo = f"Picking bajo umbral ({stock_pick}/{stock_min} u.)"

        sugerencias.append(
            SugerenciaReposicionPicking(
                product_code=cod,
                product_name=nombre,
                ubicacion_origen=str(origen_elegido["ubicacion"]),
                zona_origen=str(origen_elegido["tipo_zona"]),
                ubicacion_destino=str(destino["ubicacion"]),
                cantidad_sugerida=cantidad_sug,
                stock_picking_actual=stock_pick,
                stock_reserva_origen=stock_orig,
                prioridad=prioridad,
                motivo=motivo,
                lote_fefo=lote_codigo,
                fecha_vencimiento_fefo=lote_fv,
            )
        )

    orden_prio = {"URGENTE": 0, "ALTA": 1, "MEDIA": 2}
    sugerencias.sort(
        key=lambda s: (
            orden_prio.get(s.prioridad, 9),
            s.fecha_vencimiento_fefo or "9999-12-31",
            -s.cantidad_sugerida,
            s.product_code,
        )
    )
    return sugerencias


def analizar_ubicaciones_sku(product_store: Any, code: str) -> dict[str, Any]:
    """Consolida saldo disponible, ubicaciones por zona y lotes FEFO de un SKU."""
    resumen = product_store.obtener_resumen_stock_disponible(code)
    ubicaciones = product_store.listar_ubicaciones_producto(code)
    lotes = product_store.listar_lotes_fefo(code, solo_disponibles=False)
    resumen["ubicaciones"] = ubicaciones
    resumen["lotes_fefo"] = lotes
    return resumen
