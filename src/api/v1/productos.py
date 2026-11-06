"""Endpoints para consulta y actualización de productos y stock."""

from __future__ import annotations

import sqlite3
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..deps import get_current_user, get_product_store, require_roles
from ..schemas import (
    ActualizarUbicacionRequest,
    AsociarBarcodeRequest,
    BuscarProductosResponse,
    ProductoItemResponse,
)
from ...product_store import ProductStore

router = APIRouter(prefix="/productos", tags=["Productos y Stock"])


def _row_to_producto(row: sqlite3.Row) -> ProductoItemResponse:
    keys = row.keys()
    return ProductoItemResponse(
        code=str(row["code"]).strip(),
        name=str(row["name"]).strip(),
        stock=int(row["stock"]),
        stock_fisico=int(row["stock_fisico"]) if "stock_fisico" in keys and row["stock_fisico"] is not None else 0,
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
    _user: Dict[str, Any] = Depends(get_current_user),
):
    """Busca productos en el catálogo por coincidencia de texto, SKU o código de barras."""
    termino = q.strip()
    if termino:
        rows = product_store.buscar_productos(termino, limite=limit)
    else:
        rows = product_store.list_products()[:limit]

    items = [_row_to_producto(r) for r in rows]
    return BuscarProductosResponse(total=len(items), productos=items)


@router.get("/{codigo_o_barcode}", response_model=ProductoItemResponse, summary="Obtener producto por SKU o Código de Barras")
async def obtener_producto(
    codigo_o_barcode: str,
    product_store: ProductStore = Depends(get_product_store),
    _user: Dict[str, Any] = Depends(get_current_user),
):
    """Localiza un producto de forma inmediata por su código de barras escaneado o su SKU."""
    prod = product_store.find_product_by_code_or_barcode(codigo_o_barcode)
    if prod is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Producto '{codigo_o_barcode}' no encontrado en el catálogo.",
        )
    return _row_to_producto(prod)


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
    _user: Dict[str, Any] = Depends(get_current_user),
):
    """Retorna el saldo de inventario disponible para un SKU específico."""
    prod = product_store.find_product_by_code_or_barcode(codigo)
    if prod is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Producto '{codigo}' no encontrado.",
        )
    return {
        "ok": True,
        "code": str(prod["code"]).strip(),
        "codigo": str(prod["code"]).strip(),
        "name": str(prod["name"]).strip(),
        "nombre": str(prod["name"]).strip(),
        "stock": int(prod["stock"]),
        "stock_minimo": int(prod["stock_minimo"]) if "stock_minimo" in prod.keys() else 0,
        "active": bool(prod["active"]) if "active" in prod.keys() else True,
    }
