"""Endpoints para conteo físico e inventario móvil en vivo."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException, status

from ..deps import get_current_user, get_stock_manager, require_roles
from ..schemas import (
    ConteoInventarioRequest,
    InventarioItemComparativa,
    InventarioResultadoResponse,
)
from ...stock_manager import StockManager

router = APIRouter(prefix="/inventario", tags=["Inventario en Vivo"])


@router.post("/comparar-preliminar", summary="Previsualizar comparativa de conteo físico sin guardar")
async def comparar_preliminar(
    req: ConteoInventarioRequest,
    stock_manager: StockManager = Depends(get_stock_manager),
    _user: Dict[str, Any] = Depends(require_roles("operador", "administrador")),
):
    """Permite al teléfono ver el balance preliminar (faltantes / sobrantes) antes de cerrar."""
    if not req.conteo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debe incluir al menos un producto contado en el diccionario.",
        )

    comparativa_raw = stock_manager.comparar_stock_fisico(req.conteo)
    items: List[InventarioItemComparativa] = []
    coinciden = 0
    faltantes = 0
    sobrantes = 0

    for item in comparativa_raw:
        dif = int(item.get("diferencia", 0))
        en_cat = bool(item.get("en_catalogo", True))
        if not en_cat:
            estado = "NO_CATALOGADO"
        elif dif == 0:
            estado = "COINCIDE"
            coinciden += 1
        elif dif < 0:
            estado = "FALTANTE"
            faltantes += 1
        else:
            estado = "SOBRANTE"
            sobrantes += 1

        items.append(
            InventarioItemComparativa(
                codigo=str(item.get("codigo", "")),
                nombre=str(item.get("nombre", "")),
                stock_sistema=int(item.get("stock_sistema", 0)),
                stock_fisico=int(item.get("stock_fisico", 0)),
                diferencia=dif,
                estado=estado,
            )
        )

    return {
        "total_items": len(items),
        "coinciden": coinciden,
        "faltantes": faltantes,
        "sobrantes": sobrantes,
        "items": items,
    }


@router.post(
    "/finalizar",
    response_model=InventarioResultadoResponse,
    summary="Finalizar relevamiento de inventario físico y generar reporte",
)
async def finalizar_inventario(
    req: ConteoInventarioRequest,
    stock_manager: StockManager = Depends(get_stock_manager),
    user: Dict[str, Any] = Depends(require_roles("operador", "administrador")),
):
    """Cierra el relevamiento físico escaneado desde el teléfono.

    Actualiza el stock físico en la base de datos, genera el archivo Excel de
    comparativa para la administración y registra la notificación en el sistema.
    """
    if not req.conteo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El conteo está vacío. Escanee al menos un producto antes de finalizar.",
        )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nombre_archivo = req.nombre_archivo or f"Inventario_Movil_{timestamp}.xlsx"
    usuario_operario = user.get("nombre") or user.get("username") or "operador"

    try:
        ruta_doc, comparativa_raw = stock_manager.procesar_stock_fisico(
            conteo_fisico=req.conteo,
            usuario=usuario_operario,
            nombre_archivo=nombre_archivo,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al procesar el inventario físico: {e}",
        )

    items: List[InventarioItemComparativa] = []
    coinciden = 0
    faltantes = 0
    sobrantes = 0

    for item in comparativa_raw:
        dif = int(item.get("diferencia", 0))
        en_cat = bool(item.get("en_catalogo", True))
        if not en_cat:
            estado = "NO_CATALOGADO"
        elif dif == 0:
            estado = "COINCIDE"
            coinciden += 1
        elif dif < 0:
            estado = "FALTANTE"
            faltantes += 1
        else:
            estado = "SOBRANTE"
            sobrantes += 1

        items.append(
            InventarioItemComparativa(
                codigo=str(item.get("codigo", "")),
                nombre=str(item.get("nombre", "")),
                stock_sistema=int(item.get("stock_sistema", 0)),
                stock_fisico=int(item.get("stock_fisico", 0)),
                diferencia=dif,
                estado=estado,
            )
        )

    return InventarioResultadoResponse(
        ok=True,
        mensaje="Relevamiento de inventario registrado y procesado exitosamente.",
        total_items=len(items),
        coinciden=coinciden,
        faltantes=faltantes,
        sobrantes=sobrantes,
        archivo_generado=ruta_doc.name if ruta_doc else None,
        comparativa=items,
    )
