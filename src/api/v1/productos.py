"""Endpoints para consulta y actualización de productos y stock."""

from __future__ import annotations

import sqlite3
from typing import Any, Callable, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..deps import get_product_store, require_roles
from ..schemas import (
    ActualizarUbicacionRequest,
    AsignarUbicacionRequest,
    AsociarBarcodeRequest,
    BuscarProductosResponse,
    ConsolidarReservaRequest,
    ConsumirLotesFefoRequest,
    CrearReservaRequest,
    LiberarReservaRequest,
    ProductoItemResponse,
    RegistrarLoteRequest,
    TransferirUbicacionRequest,
)
from ...core.exceptions import InsufficientStockError, ProductNotFoundError
from ...products import ProductStore

router = APIRouter(prefix="/productos", tags=["Productos y Stock"])


def _ejecutar_operacion_deposito(fn: Callable[[], Any]) -> Any:
    """Ejecuta una operación de repositorio traduciendo errores de dominio a códigos HTTP."""
    try:
        return fn()
    except InsufficientStockError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ProductNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


def _row_to_producto(row: sqlite3.Row, stock_reservado: int = 0) -> ProductoItemResponse:
    keys = row.keys()
    stock_actual = int(row["stock"])
    res_norm = max(0, int(stock_reservado))
    return ProductoItemResponse(
        code=str(row["code"]).strip(),
        name=str(row["name"]).strip(),
        stock=stock_actual,
        stock_fisico=int(row["stock_fisico"]) if "stock_fisico" in keys and row["stock_fisico"] is not None else 0,
        stock_reservado=res_norm,
        stock_disponible=max(0, stock_actual - res_norm),
        stock_minimo=int(row["stock_minimo"]) if "stock_minimo" in keys and row["stock_minimo"] is not None else 0,
        stock_maximo=int(row["stock_maximo"]) if "stock_maximo" in keys and row["stock_maximo"] is not None else 0,
        cod_barras=str(row["cod_barras"]).strip() if "cod_barras" in keys and row["cod_barras"] else "",
        ubicacion=str(row["ubicacion"]).strip() if "ubicacion" in keys and row["ubicacion"] else "",
        active=bool(row["active"]) if "active" in keys else True,
    )


@router.get("/buscar", response_model=BuscarProductosResponse, summary="Buscar productos por texto o código")
async def buscar_productos(
    q: str = Query("", description="Término de búsqueda (nombre, código interno o código de barras)"),
    limit: int = Query(50, ge=1, le=200, description="Cantidad máxima de resultados"),
    product_store: ProductStore = Depends(get_product_store),
    _user: Dict[str, Any] = Depends(require_roles("operador", "administrador", "picker", "consulta")),
):
    """Busca productos en el catálogo por coincidencia de texto, SKU o código de barras."""
    termino = q.strip()
    if termino:
        rows = product_store.buscar_productos(termino, limite=limit)
    else:
        rows = product_store.list_products()[:limit]

    cods = [str(r["code"]).strip() for r in rows]
    mapa_reservas = product_store.obtener_mapa_reservas_activas(cods) if cods else {}
    items = [_row_to_producto(r, stock_reservado=mapa_reservas.get(str(r["code"]).strip(), 0)) for r in rows]
    return BuscarProductosResponse(total=len(items), productos=items)


@router.get("/reservas", summary="Listar reservas de stock activas o históricas")
async def listar_reservas(
    estado: Optional[str] = Query("activa", description="activa | consolidada | liberada"),
    referencia_tipo: Optional[str] = Query(None, description="Tipo de referencia (ej: ola_picking)"),
    referencia_id: Optional[str] = Query(None, description="Identificador de referencia"),
    codigo: Optional[str] = Query(None, description="Filtrar por código SKU"),
    product_store: ProductStore = Depends(get_product_store),
    _user: Dict[str, Any] = Depends(require_roles("operador", "administrador", "picker", "consulta")),
):
    """Lista las reservas de inventario separando stock comprometido en picking de stock libre."""
    reservas = _ejecutar_operacion_deposito(
        lambda: product_store.listar_reservas(
            estado=estado,
            referencia_tipo=referencia_tipo,
            referencia_id=referencia_id,
            product_code=codigo,
        )
    )
    return {"ok": True, "total": len(reservas), "reservas": reservas}


@router.post("/reservas", summary="Reservar stock contra disponibilidad neta")
async def crear_reserva_stock(
    req: CrearReservaRequest,
    product_store: ProductStore = Depends(get_product_store),
    user: Dict[str, Any] = Depends(require_roles("operador", "administrador", "picker")),
):
    """Bloquea stock disponible para evitar sobre-asignación concurrente durante picking."""
    usuario = str(user.get("username", "api") or "api")
    pares = [(it.codigo, it.cantidad) for it in req.items]
    resultado = _ejecutar_operacion_deposito(
        lambda: product_store.reservar_stock(
            pares,
            referencia_id=req.referencia_id,
            referencia_tipo=req.referencia_tipo,
            usuario=usuario,
            nota=req.nota,
            asignar_fefo=req.asignar_fefo,
            permitir_parcial=req.permitir_parcial,
            expires_at=req.expires_at,
        )
    )
    return {"ok": True, **resultado}


@router.post("/reservas/consolidar", summary="Consolidar reserva de stock")
async def consolidar_reserva_stock(
    req: ConsolidarReservaRequest,
    product_store: ProductStore = Depends(get_product_store),
    user: Dict[str, Any] = Depends(require_roles("operador", "administrador", "picker")),
):
    """Consolida reservas activas descontando opcionalmente el stock físico y lotes FEFO."""
    usuario = str(user.get("username", "api") or "api")
    resultado = _ejecutar_operacion_deposito(
        lambda: product_store.consolidar_reserva(
            referencia_id=req.referencia_id,
            referencia_tipo=req.referencia_tipo,
            product_code=req.codigo,
            descontar_stock=req.descontar_stock,
            usuario=usuario,
            detalle=req.detalle,
        )
    )
    return {"ok": True, **resultado}


@router.post("/reservas/liberar", summary="Liberar reservas activas")
async def liberar_reserva_stock(
    req: LiberarReservaRequest,
    product_store: ProductStore = Depends(get_product_store),
    _user: Dict[str, Any] = Depends(require_roles("operador", "administrador", "picker")),
):
    """Libera reservas activas devolviendo inmediatamente unidades al saldo disponible."""
    resultado = _ejecutar_operacion_deposito(
        lambda: product_store.liberar_reserva(
            referencia_id=req.referencia_id,
            referencia_tipo=req.referencia_tipo,
            product_code=req.codigo,
            motivo=req.motivo,
        )
    )
    return {"ok": True, **resultado}


@router.get("/lotes/proximos-vencer", summary="Alertas de lotes próximos a vencer o vencidos (FEFO)")
async def listar_lotes_proximos_vencer(
    dias: int = Query(30, ge=0, le=3650, description="Ventana de días hacia adelante"),
    incluir_vencidos: bool = Query(True, description="Incluir lotes ya vencidos con saldo"),
    product_store: ProductStore = Depends(get_product_store),
    _user: Dict[str, Any] = Depends(require_roles("operador", "administrador", "picker", "consulta")),
):
    """Lista lotes ordenados por fecha de vencimiento próxima para control FEFO."""
    alertas = product_store.listar_lotes_proximos_vencer(
        dias=dias,
        incluir_vencidos=incluir_vencidos,
        solo_con_stock=True,
    )
    return {"ok": True, "total": len(alertas), "lotes": alertas}


@router.get("/{codigo_o_barcode}", response_model=ProductoItemResponse, summary="Obtener producto por SKU o Código de Barras")
async def obtener_producto(
    codigo_o_barcode: str,
    product_store: ProductStore = Depends(get_product_store),
    _user: Dict[str, Any] = Depends(require_roles("operador", "administrador", "picker", "consulta")),
):
    """Localiza un producto de forma inmediata por su código de barras escaneado o su SKU."""
    prod = product_store.find_product_by_code_or_barcode(codigo_o_barcode)
    if prod is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Producto '{codigo_o_barcode}' no encontrado en el catálogo.",
        )
    cod = str(prod["code"]).strip()
    reservado = product_store.obtener_mapa_reservas_activas([cod]).get(cod, 0)
    return _row_to_producto(prod, stock_reservado=reservado)


@router.put("/{codigo}/ubicacion", summary="Actualizar ubicación física de estantería")
async def actualizar_ubicacion(
    codigo: str,
    req: ActualizarUbicacionRequest,
    product_store: ProductStore = Depends(get_product_store),
    _user: Dict[str, Any] = Depends(require_roles("operador", "administrador")),
):
    """Asigna o modifica la ubicación física de un producto en el depósito (ej: A-01-2)."""
    ok = product_store.actualizar_ubicacion(codigo, req.ubicacion)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se pudo actualizar la ubicación: el producto '{codigo}' no existe.",
        )
    return {
        "ok": True,
        "codigo": codigo.strip().upper(),
        "ubicacion": req.ubicacion.strip().upper(),
        "mensaje": f"Ubicación actualizada a '{req.ubicacion.strip().upper()}'.",
    }


@router.put("/{codigo}/codigo-barras", summary="Asociar código de barras a un producto")
async def asociar_codigo_barras(
    codigo: str,
    req: AsociarBarcodeRequest,
    product_store: ProductStore = Depends(get_product_store),
    _user: Dict[str, Any] = Depends(require_roles("operador", "administrador")),
):
    """Asocia un código de barras (EAN-13, QR) escaneado con la cámara a un SKU existente."""
    prod = product_store.get_product(codigo)
    if prod is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"El producto con código '{codigo}' no existe en el catálogo.",
        )

    product_store.set_product_barcode(codigo, req.cod_barras)
    return {
        "ok": True,
        "codigo": codigo.strip(),
        "cod_barras": req.cod_barras.strip(),
        "mensaje": f"Código de barras '{req.cod_barras}' vinculado exitosamente a {codigo}.",
    }


@router.get("/{codigo}/stock", summary="Consulta rápida de saldo de inventario (B2B / ERP / API Key)")
async def obtener_stock_producto(
    codigo: str,
    product_store: ProductStore = Depends(get_product_store),
    _user: Dict[str, Any] = Depends(require_roles("operador", "administrador", "picker", "consulta")),
):
    """Retorna el saldo de inventario disponible y reservado para un SKU específico."""
    prod = product_store.find_product_by_code_or_barcode(codigo)
    if prod is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Producto '{codigo}' no encontrado.",
        )
    cod = str(prod["code"]).strip()
    resumen = product_store.obtener_resumen_stock_disponible(cod)
    return {
        "ok": True,
        "code": cod,
        "codigo": cod,
        "name": str(prod["name"]).strip(),
        "nombre": str(prod["name"]).strip(),
        "stock": int(prod["stock"]),
        "stock_reservado": int(resumen["stock_reservado"]),
        "stock_disponible": int(resumen["stock_disponible"]),
        "stock_minimo": int(prod["stock_minimo"]) if "stock_minimo" in prod.keys() else 0,
        "active": bool(prod["active"]) if "active" in prod.keys() else True,
    }


@router.get("/{codigo}/ubicaciones", summary="Listar ubicaciones multi-zona de un SKU")
async def listar_ubicaciones_producto(
    codigo: str,
    product_store: ProductStore = Depends(get_product_store),
    _user: Dict[str, Any] = Depends(require_roles("operador", "administrador", "picker", "consulta")),
):
    """Retorna resumen de stock y todas las zonas (`picking`, `pulmon`, `pallet`) del SKU."""
    resumen = _ejecutar_operacion_deposito(
        lambda: product_store.obtener_resumen_stock_disponible(codigo.strip())
    )
    ubicaciones = product_store.listar_ubicaciones_producto(resumen["product_code"])
    return {"ok": True, **resumen, "ubicaciones": ubicaciones}


@router.post("/{codigo}/ubicaciones", summary="Asignar o actualizar ubicación multi-zona")
async def asignar_ubicacion_producto(
    codigo: str,
    req: AsignarUbicacionRequest,
    product_store: ProductStore = Depends(get_product_store),
    _user: Dict[str, Any] = Depends(require_roles("operador", "administrador")),
):
    """Registra o actualiza una ubicación (`picking`, `pulmon`, `pallet`, etc.) para el SKU."""
    ubic = _ejecutar_operacion_deposito(
        lambda: product_store.asignar_ubicacion_producto(
            codigo.strip(),
            req.ubicacion,
            tipo_zona=req.tipo_zona,
            stock=req.stock,
            capacidad_max=req.capacidad_max,
            es_principal=req.es_principal,
        )
    )
    return {"ok": True, "ubicacion": ubic}


@router.post("/{codigo}/ubicaciones/transferir", summary="Transferir stock entre ubicaciones internas")
async def transferir_ubicacion_producto(
    codigo: str,
    req: TransferirUbicacionRequest,
    product_store: ProductStore = Depends(get_product_store),
    _user: Dict[str, Any] = Depends(require_roles("operador", "administrador", "picker")),
):
    """Traslada existencias entre bins del mismo SKU (ej. reposición `pulmon` -> `picking`)."""
    resultado = _ejecutar_operacion_deposito(
        lambda: product_store.transferir_entre_ubicaciones(
            codigo.strip(),
            req.origen,
            req.destino,
            req.cantidad,
            destino_zona=req.destino_zona,
            crear_destino=req.crear_destino,
        )
    )
    return {"ok": True, **resultado}


@router.get("/{codigo}/lotes", summary="Listar lotes de un SKU en orden FEFO")
async def listar_lotes_producto(
    codigo: str,
    solo_disponibles: bool = Query(False, description="Solo lotes activos con stock > 0"),
    ubicacion: Optional[str] = Query(None, description="Filtrar por ubicación específica"),
    product_store: ProductStore = Depends(get_product_store),
    _user: Dict[str, Any] = Depends(require_roles("operador", "administrador", "picker", "consulta")),
):
    """Lista lotes ordenados FEFO (próximos a vencer primero)."""
    resumen = _ejecutar_operacion_deposito(
        lambda: product_store.obtener_resumen_stock_disponible(codigo.strip())
    )
    lotes = product_store.listar_lotes_fefo(
        resumen["product_code"],
        solo_disponibles=solo_disponibles,
        ubicacion=ubicacion,
    )
    return {"ok": True, "product_code": resumen["product_code"], "total": len(lotes), "lotes": lotes}


@router.post("/{codigo}/lotes", summary="Registrar o actualizar lote con vencimiento FEFO")
async def registrar_lote_producto(
    codigo: str,
    req: RegistrarLoteRequest,
    product_store: ProductStore = Depends(get_product_store),
    _user: Dict[str, Any] = Depends(require_roles("operador", "administrador")),
):
    """Crea o actualiza un lote con fecha de vencimiento (`YYYY-MM-DD`) y ubicación."""
    lote = _ejecutar_operacion_deposito(
        lambda: product_store.registrar_lote(
            codigo.strip(),
            req.lote,
            req.cantidad,
            fecha_vencimiento=req.fecha_vencimiento,
            ubicacion=req.ubicacion,
            estado=req.estado,
            notas=req.notas,
            sumar_si_existe=req.sumar_si_existe,
        )
    )
    return {"ok": True, "lote": lote}


@router.post("/{codigo}/lotes/consumir-fefo", summary="Consumir unidades por regla FEFO")
async def consumir_lotes_fefo_producto(
    codigo: str,
    req: ConsumirLotesFefoRequest,
    product_store: ProductStore = Depends(get_product_store),
    user: Dict[str, Any] = Depends(require_roles("operador", "administrador", "picker")),
):
    """Consume stock siguiendo estricto orden FEFO (primer vencimiento, primera salida)."""
    usuario = str(user.get("username", "api") or "api")
    resultado = _ejecutar_operacion_deposito(
        lambda: product_store.consumir_lotes_fefo(
            codigo.strip(),
            req.cantidad,
            ubicacion=req.ubicacion,
            permitir_parcial=req.permitir_parcial,
            incluir_vencidos=req.incluir_vencidos,
            descontar_stock_producto=req.descontar_stock_producto,
            usuario=usuario,
            detalle=req.detalle,
        )
    )
    return {"ok": True, **resultado}
