"""Endpoints para despacho, rotulación QR y logística de pedidos."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..deps import get_current_user, get_order_store, require_roles
from ..schemas import (
    EscanearDespachoRequest,
    EscanearDespachoResponse,
    ItemPedidoResponse,
    ListarPedidosResponse,
    PedidoDetalleResponse,
)
from ...orders_store import OrderStore, Pedido

router = APIRouter(prefix="/despacho", tags=["Despacho y Logística"])


def _pedido_a_detalle(pedido: Pedido, order_store: OrderStore) -> PedidoDetalleResponse:
    items_raw = order_store.obtener_items_pedido(pedido.id)
    items = [
        ItemPedidoResponse(codigo=it[0], descripcion=it[1], cantidad=it[2])
        for it in items_raw
    ]
    return PedidoDetalleResponse(
        id=pedido.id,
        nota_pedido=pedido.nota_pedido,
        numero_pedido=pedido.numero_pedido or "",
        cliente=pedido.cliente,
        bultos=pedido.bultos,
        logistica=pedido.logistica or "",
        armador=pedido.armador or "",
        estado_despacho=pedido.estado_despacho,
        created_at=pedido.created_at,
        despachado_at=pedido.despachado_at or "",
        despachado_por=pedido.despachado_por or "",
        entregado_at=pedido.entregado_at or "",
        entregado_por=pedido.entregado_por or "",
        items=items,
    )


@router.post(
    "/escanear",
    response_model=EscanearDespachoResponse,
    summary="Escanear rótulo QR o remito y actualizar estado de despacho",
)
async def escanear_despacho(
    req: EscanearDespachoRequest,
    order_store: OrderStore = Depends(get_order_store),
    user: Dict[str, Any] = Depends(require_roles("operador", "administrador")),
):
    """Procesa el escaneo de un código QR de bulto o número de remito.

    Avanza el pedido al siguiente estado logístico (Armado → Despachado → Entregado)
    o aplica el estado especificado, registrando el operario y la hora exacta.
    """
    usuario_operario = user.get("nombre") or user.get("username") or "operador"
    ok, mensaje, pedido = order_store.avanzar_estado_por_codigo(
        codigo_qr_o_remito=req.codigo,
        usuario=usuario_operario,
        nuevo_estado=req.nuevo_estado,
    )

    pedido_detalle: Optional[PedidoDetalleResponse] = None
    if pedido is not None:
        pedido_detalle = _pedido_a_detalle(pedido, order_store)

    return EscanearDespachoResponse(
        ok=ok,
        mensaje=mensaje,
        pedido=pedido_detalle,
    )


@router.get("/pedidos", response_model=ListarPedidosResponse, summary="Listar pedidos para despacho")
async def listar_pedidos(
    estado_despacho: Optional[str] = Query(None, description="Filtrar por estado: 'armado', 'despachado', 'entregado'"),
    limit: int = Query(50, ge=1, le=200, description="Cantidad máxima de pedidos a retornar"),
    order_store: OrderStore = Depends(get_order_store),
    _user: Dict[str, Any] = Depends(get_current_user),
):
    """Devuelve la lista de pedidos recientes o pendientes de despacho."""
    todos = order_store.listar_pedidos(limit=limit)
    if estado_despacho:
        filtro = estado_despacho.strip().lower()
        todos = [p for p in todos if p.estado_despacho.lower() == filtro]

    pedidos_det = [_pedido_a_detalle(p, order_store) for p in todos]
    return ListarPedidosResponse(total=len(pedidos_det), pedidos=pedidos_det)


@router.get("/pedidos/{nota_pedido}", response_model=PedidoDetalleResponse, summary="Obtener detalle de un pedido por remito")
async def obtener_pedido_por_remito(
    nota_pedido: str,
    order_store: OrderStore = Depends(get_order_store),
    _user: Dict[str, Any] = Depends(get_current_user),
):
    """Retorna los datos completos y la lista de artículos de un pedido por su número de remito."""
    pedido = order_store.buscar_pedido_por_nota(nota_pedido)
    if pedido is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontró ningún pedido con el remito '{nota_pedido}'.",
        )
    return _pedido_a_detalle(pedido, order_store)
