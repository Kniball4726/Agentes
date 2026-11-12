"""Fachada de compatibilidad hacia atrás para el subsistema de pedidos y clientes.

Re-exporta las entidades, constantes y el motor `OrderStore` desde el nuevo paquete
modularizado `src.orders`.
"""

from .orders import (
    LOGISTICA_OPCIONES,
    ESTADOS_DESPACHO,
    _COLUMNAS_DESPACHO,
    calcular_hash_archivo,
    OrderStoreError,
    OrderNotFoundError,
    OrderValidationError,
    OrderConcurrencyError,
    Cliente,
    CierreJornada,
    RegistroAuditoria,
    Pedido,
    MensajeChat,
    OrderStore,
)

__all__ = [
    "LOGISTICA_OPCIONES",
    "ESTADOS_DESPACHO",
    "_COLUMNAS_DESPACHO",
    "calcular_hash_archivo",
    "OrderStoreError",
    "OrderNotFoundError",
    "OrderValidationError",
    "OrderConcurrencyError",
    "Cliente",
    "CierreJornada",
    "RegistroAuditoria",
    "Pedido",
    "MensajeChat",
    "OrderStore",
]
