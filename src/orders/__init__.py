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
from .audit_repo import AuditRepository
from .channel_report_repo import ChannelReportRepository
from .chat_repo import ChatRepository
from .client_repo import ClientRepository
from .closure_repo import ClosureRepository
from .concurrency_repo import ConcurrencyRepository
from .dispatch_repo import DispatchRepository
from .factory_plan_repo import FactoryPlanRepository
from .full_plan_repo import FullPlanRepository
from .order_core_repo import OrderCoreRepository
from .stock_flow_repo import StockFlowRepository
from .picking_wave import (
    consolidar_ola_picking,
    consolidar_y_despachar_ola_picking,
    crear_y_reservar_ola_picking,
    generar_referencia_ola,
    liberar_ola_picking,
)
from .store import OrderStore

__all__ = [
    "LOGISTICA_OPCIONES",
    "ESTADOS_DESPACHO",
    "_COLUMNAS_DESPACHO",
    "calcular_hash_archivo",
    "inicializar_esquema_pedidos",
    "consolidar_ola_picking",
    "crear_y_reservar_ola_picking",
    "consolidar_y_despachar_ola_picking",
    "liberar_ola_picking",
    "generar_referencia_ola",
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
    "AuditRepository",
    "ChannelReportRepository",
    "ChatRepository",
    "ClientRepository",
    "ClosureRepository",
    "ConcurrencyRepository",
    "DispatchRepository",
    "FullPlanRepository",
    "FactoryPlanRepository",
    "OrderCoreRepository",
    "StockFlowRepository",
    "OrderStore",
]
