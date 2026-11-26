"""Modelos Pydantic para validación y serialización de la API REST."""

from __future__ import annotations

from typing import Dict, List, Optional
from pydantic import BaseModel, Field


# ==========================================
# Autenticación y Usuarios
# ==========================================

class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=120, description="Nombre de usuario o correo electrónico")
    password: str = Field(..., min_length=1, max_length=256, description="Contraseña del usuario")


class ApiKeyCreateRequest(BaseModel):
    client_name: str = Field(..., min_length=1, max_length=100, description="Nombre del cliente o ERP externo")
    role: str = Field("operador", min_length=1, max_length=32, description="Rol asignado a la clave API")


class UsuarioResponse(BaseModel):
    id: int
    username: str
    role: str
    nombre: str
    email: Optional[str] = None


class LoginResponse(BaseModel):
    ok: bool
    token: Optional[str] = None
    user: Optional[UsuarioResponse] = None
    message: str


# ==========================================
# Catálogo de Productos y Stock
# ==========================================

class ProductoItemResponse(BaseModel):
    code: str
    name: str
    stock: int
    stock_fisico: Optional[int] = 0
    stock_minimo: Optional[int] = 0
    stock_maximo: Optional[int] = 0
    cod_barras: Optional[str] = ""
    ubicacion: Optional[str] = ""
    active: bool = True


class BuscarProductosResponse(BaseModel):
    total: int
    productos: List[ProductoItemResponse]


class ActualizarUbicacionRequest(BaseModel):
    ubicacion: str = Field(..., max_length=80, description="Ubicación física en el depósito (ej: A-02-3)")


class AsociarBarcodeRequest(BaseModel):
    cod_barras: str = Field(..., min_length=1, max_length=128, description="Código de barras EAN-13, Code-128 o QR")


# ==========================================
# Relevamiento de Inventario en Vivo
# ==========================================

class ConteoInventarioRequest(BaseModel):
    conteo: Dict[str, int] = Field(..., max_length=5000, description="Diccionario {codigo_o_sku: cantidad_contada}")
    nombre_archivo: Optional[str] = Field(None, max_length=160, description="Nombre opcional del archivo comparativo")


class InventarioItemComparativa(BaseModel):
    codigo: str
    nombre: str
    stock_sistema: int
    stock_fisico: int
    diferencia: int
    estado: str  # 'COINCIDE', 'FALTANTE', 'SOBRANTE', 'NO_CATALOGADO'


class InventarioResultadoResponse(BaseModel):
    ok: bool
    mensaje: str
    total_items: int
    coinciden: int
    faltantes: int
    sobrantes: int
    archivo_generado: Optional[str] = None
    comparativa: List[InventarioItemComparativa] = []


# ==========================================
# Despacho y Logística de Pedidos
# ==========================================

class ItemPedidoResponse(BaseModel):
    codigo: str
    descripcion: str
    cantidad: int


class PedidoDetalleResponse(BaseModel):
    id: int
    nota_pedido: str
    numero_pedido: Optional[str] = ""
    cliente: str
    bultos: int
    logistica: Optional[str] = ""
    armador: Optional[str] = ""
    estado_despacho: str
    created_at: str
    despachado_at: Optional[str] = ""
    despachado_por: Optional[str] = ""
    entregado_at: Optional[str] = ""
    entregado_por: Optional[str] = ""
    items: List[ItemPedidoResponse] = []


class EscanearDespachoRequest(BaseModel):
    codigo: str = Field(..., min_length=1, max_length=256, description="Texto del código QR escaneado o número de remito")
    nuevo_estado: Optional[str] = Field(
        None,
        max_length=32,
        description="Estado destino forzado: 'armado', 'despachado', 'entregado'. Si no se indica, avanza al siguiente.",
    )


class EscanearDespachoResponse(BaseModel):
    ok: bool
    mensaje: str
    pedido: Optional[PedidoDetalleResponse] = None


class EscanearLoteRequest(BaseModel):
    items: List[EscanearDespachoRequest] = Field(..., max_length=500, description="Lista de escaneos acumulados offline")


class EscanearLoteResponse(BaseModel):
    ok: bool
    total_procesados: int
    exitosos: int
    fallidos: int
    resultados: List[EscanearDespachoResponse]


class ListarPedidosResponse(BaseModel):
    total: int
    pedidos: List[PedidoDetalleResponse]


# ==========================================
# Sistema y Telemetría
# ==========================================

class EstadoSistemaResponse(BaseModel):
    ok: bool
    version: str
    servidor_hora: str
    ip_local: str
    sesiones_activas: int
    modo_conexion: str
