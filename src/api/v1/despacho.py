"""Endpoints para despacho, rotulación QR y logística de pedidos."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from ..deps import get_current_user, get_order_store, get_product_store, require_roles
from ..schemas import (
    EscanearDespachoRequest,
    EscanearDespachoResponse,
    EscanearLoteRequest,
    EscanearLoteResponse,
    ItemPedidoResponse,
    ListarPedidosResponse,
    PedidoDetalleResponse,
)
from ...core.stock_order_tx import consolidar_reserva_pedido_si_existe
from ...orders import OrderStore, Pedido

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


def _procesar_escaneo_por_rol(
    order_store: OrderStore,
    codigo: str,
    nuevo_estado: Optional[str],
    user: Dict[str, Any],
) -> tuple[bool, str, Optional[Pedido]]:
    """Aplica la lógica de escaneo según el rol: `despachador` verifica bultos y solo pasa a `despachado`."""
    rol = str(user.get("role", "")).strip().lower()
    usuario_operario = user.get("nombre") or user.get("username") or (rol or "operador")
    if rol == "despachador":
        if nuevo_estado and nuevo_estado.strip().lower() != "despachado":
            return (
                False,
                "El rol despachador solo tiene permiso para pasar pedidos al estado 'despachado'.",
                None,
            )
        res = order_store.registrar_escaneo_bulto_despacho(
            codigo_qr_o_remito=codigo,
            usuario=usuario_operario,
        )
        return bool(res["ok"]), str(res["mensaje"]), res["pedido"]

    puede_retroceder = rol in ("administrador", "master")
    return order_store.avanzar_estado_por_codigo(
        codigo_qr_o_remito=codigo,
        usuario=usuario_operario,
        nuevo_estado=nuevo_estado,
        permitir_retroceso=puede_retroceder,
    )


def _resolver_product_store_opcional(request: Request):
    """Resuelve `ProductStore` si está disponible en overrides o contexto sin fallar en tests aislados."""
    override = request.app.dependency_overrides.get(get_product_store)
    if callable(override):
        try:
            return override()
        except Exception:
            return None
    try:
        return get_product_store()
    except Exception:
        return None


def _consolidar_reserva_al_despachar(
    request: Request,
    ok: bool,
    pedido: Optional[Pedido],
    user: Dict[str, Any],
) -> None:
    """Consolida automáticamente reservas activas del pedido cuando alcanza estado `despachado`."""
    if not ok or pedido is None:
        return
    if str(getattr(pedido, "estado_despacho", "")).strip().lower() != "despachado":
        return
    p_store = _resolver_product_store_opcional(request)
    if p_store is None:
        return
    usuario = str(user.get("username") or user.get("nombre") or "despacho")
    try:
        consolidar_reserva_pedido_si_existe(
            p_store,
            pedido.nota_pedido,
            usuario=usuario,
            detalle=f"Despacho móvil/API pedido #{pedido.nota_pedido}",
        )
    except Exception:
        pass


@router.post(
    "/escanear",
    response_model=EscanearDespachoResponse,
    summary="Escanear rótulo QR o remito y actualizar estado de despacho",
)
async def escanear_despacho(
    req: EscanearDespachoRequest,
    request: Request,
    order_store: OrderStore = Depends(get_order_store),
    user: Dict[str, Any] = Depends(require_roles("operador", "administrador", "despachador")),
):
    """Procesa el escaneo de un código QR de bulto o número de remito.

    Para el rol `despachador`, verifica bulto por bulto y únicamente cambia de `armado` → `despachado`.
    """
    ok, mensaje, pedido = _procesar_escaneo_por_rol(
        order_store=order_store,
        codigo=req.codigo,
        nuevo_estado=req.nuevo_estado,
        user=user,
    )
    _consolidar_reserva_al_despachar(request, ok, pedido, user)

    pedido_detalle: Optional[PedidoDetalleResponse] = None
    if pedido is not None:
        pedido_detalle = _pedido_a_detalle(pedido, order_store)

    return EscanearDespachoResponse(
        ok=ok,
        mensaje=mensaje,
        pedido=pedido_detalle,
    )


@router.post(
    "/escanear-lote",
    response_model=EscanearLoteResponse,
    summary="Procesar lote sincronizado de escaneos acumulados offline",
)
async def escanear_despacho_lote(
    req: EscanearLoteRequest,
    request: Request,
    order_store: OrderStore = Depends(get_order_store),
    user: Dict[str, Any] = Depends(require_roles("operador", "administrador", "despachador")),
):
    """Procesa un lote de escaneos acumulados en cola offline durante microcortes Wi-Fi."""
    resultados: List[EscanearDespachoResponse] = []
    exitosos = 0
    fallidos = 0

    for item in req.items:
        ok, mensaje, pedido = _procesar_escaneo_por_rol(
            order_store=order_store,
            codigo=item.codigo,
            nuevo_estado=item.nuevo_estado,
            user=user,
        )
        _consolidar_reserva_al_despachar(request, ok, pedido, user)
        det: Optional[PedidoDetalleResponse] = None
        if pedido is not None:
            det = _pedido_a_detalle(pedido, order_store)
        if ok:
            exitosos += 1
        else:
            fallidos += 1
        resultados.append(EscanearDespachoResponse(ok=ok, mensaje=mensaje, pedido=det))

    return EscanearLoteResponse(
        ok=True,
        total_procesados=len(req.items),
        exitosos=exitosos,
        fallidos=fallidos,
        resultados=resultados,
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
