"""Router principal unificado de la API REST v1 para StockAgent."""

from __future__ import annotations

from fastapi import APIRouter

from .auth import router as auth_router
from .productos import router as productos_router
from .inventario import router as inventario_router
from .despacho import router as despacho_router
from .sistema import router as sistema_router

api_v1_router = APIRouter(prefix="/api/v1")

api_v1_router.include_router(sistema_router)
api_v1_router.include_router(auth_router)
api_v1_router.include_router(productos_router)
api_v1_router.include_router(inventario_router)
api_v1_router.include_router(despacho_router)
