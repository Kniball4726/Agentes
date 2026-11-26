"""Módulo de consolidación y optimización de Ola de Picking (Wave Picking)."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .models import Pedido


def _leer_campo(obj: Any, campo: str, default: Any = "") -> Any:
    """Extrae un campo de forma segura desde `dict` o `sqlite3.Row`."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        val = obj.get(campo, default)
        return default if val is None else val
    try:
        val = obj[campo]
        return default if val is None else val
    except (KeyError, IndexError, TypeError):
        return default


def _entero_seguro(valor: Any, default: int = 0) -> int:
    """Convierte a `int` ignorando objetos mock o valores no numéricos."""
    if isinstance(valor, bool):
        return int(valor)
    if isinstance(valor, (int, float, str)):
        try:
            return int(valor)
        except (TypeError, ValueError):
            return default
    return default


def consolidar_ola_picking(
    order_store: Any,
    pedidos: list[Pedido],
    product_store: Any | None = None,
) -> list[dict[str, Any]]:
    """
    Consolida múltiples pedidos en una ola de preparación optimizada.
    Agrupa unidades totales por SKU, enriquece con disponibilidad neta (físico vs reservado),
    multi-ubicación y lotes FEFO, y ordena por pasillo/ubicación para minimizar recorrido.
    """
    if not pedidos:
        return []

    mapa_ubicaciones_lote: dict[str, list[dict[str, Any]]] = {}
    if product_store is not None and hasattr(product_store, "listar_ubicaciones_mapa"):
        try:
            cand_mapa = product_store.listar_ubicaciones_mapa(solo_activos=True)
            if isinstance(cand_mapa, dict):
                mapa_ubicaciones_lote = cand_mapa
        except Exception:
            mapa_ubicaciones_lote = {}

    mapa_items: dict[str, dict[str, Any]] = {}

    for ped in pedidos:
        if getattr(ped, "estado", "") == "anulado":
            continue
        items = order_store.obtener_items_pedido(ped.id)
        for cod, desc, cant in items:
            cod_limpio = str(cod).strip().upper()
            if not cod_limpio:
                continue
            if cod_limpio not in mapa_items:
                ubic = ""
                stock_fisico = 0
                lotes_fefo: list[dict[str, Any]] = []
                ubicaciones_sku = list(mapa_ubicaciones_lote.get(cod_limpio, []))

                if product_store is not None:
                    try:
                        p_info = product_store.get_product(cod_limpio)
                        if p_info:
                            ubic_val = _leer_campo(p_info, "ubicacion", "")
                            if isinstance(ubic_val, str):
                                ubic = ubic_val.strip()
                            stock_fisico = max(0, _entero_seguro(_leer_campo(p_info, "stock", 0)))
                    except Exception:
                        ubic = ""
                        stock_fisico = 0

                    if not ubic and ubicaciones_sku:
                        ubic = str(ubicaciones_sku[0].get("ubicacion", "") or "").strip()

                    if hasattr(product_store, "listar_lotes_fefo"):
                        try:
                            cand_lotes = product_store.listar_lotes_fefo(
                                cod_limpio, solo_disponibles=True
                            )
                            if isinstance(cand_lotes, list):
                                lotes_fefo = cand_lotes
                        except Exception:
                            lotes_fefo = []

                lotes_vigentes = [l for l in lotes_fefo if not l.get("vencido", False)]
                primer_lote = lotes_vigentes[0] if lotes_vigentes else (lotes_fefo[0] if lotes_fefo else None)

                mapa_items[cod_limpio] = {
                    "codigo": cod_limpio,
                    "descripcion": desc or cod_limpio,
                    "total_unidades": 0,
                    "ubicacion": ubic,
                    "ubicaciones": ubicaciones_sku,
                    "stock_fisico": stock_fisico,
                    "stock_reservado": 0,
                    "stock_disponible": stock_fisico,
                    "lotes_fefo": lotes_fefo,
                    "lote_sugerido": str(primer_lote.get("lote", "") or "") if primer_lote else "",
                    "vencimiento_sugerido": str(primer_lote.get("fecha_vencimiento", "") or "") if primer_lote else "",
                    "pedidos": [],
                }

            mapa_items[cod_limpio]["total_unidades"] += int(cant)
            mapa_items[cod_limpio]["pedidos"].append({
                "pedido_id": ped.id,
                "nota_pedido": ped.nota_pedido,
                "cliente": ped.cliente,
                "cantidad": int(cant),
            })

    if product_store is not None and mapa_items and hasattr(product_store, "obtener_mapa_reservas_activas"):
        try:
            mapa_res = product_store.obtener_mapa_reservas_activas(list(mapa_items.keys()))
            if isinstance(mapa_res, dict):
                for cod, item in mapa_items.items():
                    res_sku = max(0, _entero_seguro(mapa_res.get(cod, 0)))
                    item["stock_reservado"] = res_sku
                    item["stock_disponible"] = max(0, item["stock_fisico"] - res_sku)
        except Exception:
            pass

    # Ordenar primero por si tiene ubicación física conocida, luego por pasillo/ubicación y finalmente por código
    lista_consolidada = list(mapa_items.values())
    lista_consolidada.sort(key=lambda x: (x["ubicacion"] == "", x["ubicacion"], x["codigo"]))
    return lista_consolidada


def generar_referencia_ola(
    pedidos: list[Pedido],
    referencia_id: str | None = None,
) -> str:
    """Genera un identificador trazable y determinista/único para una ola de picking."""
    if referencia_id and str(referencia_id).strip():
        return str(referencia_id).strip()
    ids = sorted({int(p.id) for p in pedidos if getattr(p, "id", None) is not None})
    sello = datetime.now().strftime("%Y%m%d-%H%M%S")
    sufijo = "-".join(str(i) for i in ids[:5]) or "0"
    if len(ids) > 5:
        sufijo += f"-plus{len(ids) - 5}"
    return f"OLA-{sello}-{sufijo}"


def crear_y_reservar_ola_picking(
    order_store: Any,
    pedidos: list[Pedido],
    product_store: Any,
    referencia_id: str | None = None,
    usuario: str = "sistema",
    nota: str = "",
    permitir_parcial: bool = False,
) -> dict[str, Any]:
    """Consolida una ola y bloquea atómicamente el stock disponible requerido."""
    if product_store is None:
        raise ValueError("Se requiere `product_store` para reservar el stock de la ola.")
    items_ola = consolidar_ola_picking(order_store, pedidos, product_store=product_store)
    ref = generar_referencia_ola(pedidos, referencia_id=referencia_id)
    pares = [(it["codigo"], int(it["total_unidades"])) for it in items_ola]
    nota_final = (nota or f"Ola picking ({len(pedidos)} pedidos)").strip()
    resultado_reserva = product_store.reservar_stock(
        pares,
        referencia_id=ref,
        referencia_tipo="ola_picking",
        usuario=usuario,
        nota=nota_final,
        asignar_fefo=True,
        permitir_parcial=permitir_parcial,
    )
    items_actualizados = consolidar_ola_picking(order_store, pedidos, product_store=product_store)
    return {
        "referencia_id": ref,
        "referencia_tipo": "ola_picking",
        "items": items_actualizados,
        "reserva": resultado_reserva,
    }


def consolidar_y_despachar_ola_picking(
    product_store: Any,
    referencia_id: str,
    descontar_stock: bool = True,
    usuario: str = "sistema",
    detalle: str = "",
) -> dict[str, Any]:
    """Consolida las reservas de una ola al momento del despacho definitivo."""
    return product_store.consolidar_reserva(
        referencia_id=referencia_id,
        referencia_tipo="ola_picking",
        descontar_stock=descontar_stock,
        usuario=usuario,
        detalle=detalle or f"Despacho ola picking {referencia_id}",
    )


def liberar_ola_picking(
    product_store: Any,
    referencia_id: str,
    motivo: str = "",
) -> dict[str, Any]:
    """Libera las reservas activas de una ola cancelada o reprogramada."""
    return product_store.liberar_reserva(
        referencia_id=referencia_id,
        referencia_tipo="ola_picking",
        motivo=motivo,
    )
