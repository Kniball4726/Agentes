"""Módulo de consolidación y optimización de Ola de Picking (Wave Picking)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .models import Pedido


def consolidar_ola_picking(
    order_store: Any,
    pedidos: list[Pedido],
    product_store: Any | None = None,
) -> list[dict[str, Any]]:
    """
    Consolida múltiples pedidos en una ola de preparación optimizada.
    Agrupa unidades totales por SKU y ordena los artículos según su ubicación
    física en el almacén (pasillo/estantería) para minimizar el recorrido del picker.
    """
    if not pedidos:
        return []

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
                if product_store is not None:
                    try:
                        p_info = product_store.get_product(cod_limpio)
                        if p_info:
                            ubic = str(p_info.get("ubicacion", "") or "").strip()
                    except Exception:
                        ubic = ""

                mapa_items[cod_limpio] = {
                    "codigo": cod_limpio,
                    "descripcion": desc or cod_limpio,
                    "total_unidades": 0,
                    "ubicacion": ubic,
                    "pedidos": [],
                }

            mapa_items[cod_limpio]["total_unidades"] += int(cant)
            mapa_items[cod_limpio]["pedidos"].append({
                "pedido_id": ped.id,
                "nota_pedido": ped.nota_pedido,
                "cliente": ped.cliente,
                "cantidad": int(cant),
            })

    # Ordenar primero por si tiene ubicación física conocida, luego por pasillo/ubicación y finalmente por código
    lista_consolidada = list(mapa_items.values())
    lista_consolidada.sort(key=lambda x: (x["ubicacion"] == "", x["ubicacion"], x["codigo"]))
    return lista_consolidada
