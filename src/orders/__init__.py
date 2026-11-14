"""Módulo de gestión de pedidos, clientes, cierres de jornada, auditoría y concurrencia."""

from .models import (
    LOGISTICA_OPCIONES,
    ESTADOS_DESPACHO,
    _COLUMNAS_DESPACHO,
    calcular_hash_archivo,
    Cliente,
    CierreJornada,
    CierreMercado,
    RegistroAuditoria,
    Pedido,
    MensajeChat,
)
from ..core.exceptions import (
    OrderStoreError,
    OrderNotFoundError,
    OrderValidationError,
    OrderConcurrencyError,
)
from .schema import inicializar_esquema_pedidos
from .client_repo import ClientRepositoryMixin
from .chat_repo import ChatRepositoryMixin
from .concurrency_repo import ConcurrencyRepositoryMixin
from .audit_repo import AuditRepositoryMixin
from .closure_repo import ClosureRepositoryMixin
from .dispatch_repo import DispatchRepositoryMixin
from .store import OrderStore

__all__ = [
    "LOGISTICA_OPCIONES",
    "ESTADOS_DESPACHO",
    "_COLUMNAS_DESPACHO",
    "calcular_hash_archivo",
    "inicializar_esquema_pedidos",
    "OrderStoreError",
    "OrderNotFoundError",
    "OrderValidationError",
    "OrderConcurrencyError",
    "Cliente",
    "CierreJornada",
    "CierreMercado",
    "RegistroAuditoria",
    "Pedido",
    "MensajeChat",
    "ClientRepositoryMixin",
    "ChatRepositoryMixin",
    "ConcurrencyRepositoryMixin",
    "AuditRepositoryMixin",
    "ClosureRepositoryMixin",
    "DispatchRepositoryMixin",
    "OrderStore",
]
