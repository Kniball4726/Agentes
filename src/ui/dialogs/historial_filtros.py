"""Funciones puras de filtrado, paginación y agrupación para historial de pedidos."""

from __future__ import annotations

from typing import Sequence

from ...orders import Pedido
from .historial_cards import _coincide_pedido


def filtrar_y_ordenar_pedidos(
    pedidos: Sequence[Pedido],
    *,
    filtro_rapido: str = "todos",
    termino: str = "",
    hoy_str: str = "",
) -> list[Pedido]:
    """Filtra pedidos por filtro rápido y texto libre, ordenados más recientes primero."""
    candidatos: list[Pedido] = []
    for p in pedidos:
        if filtro_rapido == "hoy" and not (p.created_at and p.created_at.startswith(hoy_str)):
            continue
        if filtro_rapido == "pendientes" and (
            getattr(p, "cierre_id", None) is not None or getattr(p, "estado", "") == "anulado"
        ):
            continue
        if filtro_rapido == "despachados" and getattr(p, "estado_despacho", "") != "despachado":
            continue
        if _coincide_pedido(p, termino):
            candidatos.append(p)

    candidatos.sort(key=lambda x: (x.created_at or "", x.id), reverse=True)
    return candidatos


def paginar_pedidos(
    pedidos: Sequence[Pedido],
    pagina_actual: int,
    tamano_pagina: int,
) -> tuple[list[Pedido], int, int, int, int]:
    """Calcula la porción de página segura y metadatos `(pagina_items, pagina_segura, total_paginas, inicio_idx, fin_idx)`."""
    total_items = len(pedidos)
    tam = max(1, int(tamano_pagina or 25))
    total_paginas = max(1, (total_items + tam - 1) // tam)
    pagina_segura = max(1, min(int(pagina_actual or 1), total_paginas))
    inicio_idx = (pagina_segura - 1) * tam
    fin_idx = min(inicio_idx + tam, total_items)
    return list(pedidos[inicio_idx:fin_idx]), pagina_segura, total_paginas, inicio_idx, fin_idx


def agrupar_pedidos_por_fecha(pedidos_pagina: Sequence[Pedido]) -> list[tuple[str, list[Pedido]]]:
    """Agrupa los pedidos visibles por fecha ISO descendente manteniendo orden reciente interno."""
    grupos: dict[str, list[Pedido]] = {}
    for p in pedidos_pagina:
        clave = p.created_at[:10] if p.created_at else "Sin fecha"
        grupos.setdefault(clave, []).append(p)

    claves_ordenadas = sorted(
        grupos.keys(),
        key=lambda d: ("0000-00-00" if d == "Sin fecha" else d),
        reverse=True,
    )
    resultado: list[tuple[str, list[Pedido]]] = []
    for f_clave in claves_ordenadas:
        lista_ordenada = sorted(grupos[f_clave], key=lambda x: (x.created_at or "", x.id), reverse=True)
        resultado.append((f_clave, lista_ordenada))
    return resultado
