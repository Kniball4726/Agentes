"""Motor de persistencia SQLite y fachada compuesta para pedidos, clientes y cierres."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator

from ..core.delegation import DelegadoAtributo
from ..core.sqlite_utils import sqlite_connection
from .audit_repo import AuditRepository
from .channel_report_repo import ChannelReportRepository
from .chat_repo import ChatRepository
from .client_repo import ClientRepository
from .closure_repo import ClosureRepository
from .concurrency_repo import ConcurrencyRepository
from .dispatch_repo import DispatchRepository
from .factory_plan_repo import FactoryPlanRepository
from .full_plan_repo import FullPlanRepository
from .models import Pedido
from .order_core_repo import OrderCoreRepository
from .schema import inicializar_esquema_pedidos
from .stock_flow_repo import StockFlowRepository


class OrderStore:
    """Gestor unificado de almacenamiento y operaciones de pedidos, clientes y despachos.

    Ensambla por composición los repositorios especializados de dominio y expone
    una fachada cohesiva mediante descriptores ``DelegadoAtributo``.
    """

    _initialized_dbs: set[tuple[str, int, int]] = set()

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)

        def _audit_cb(*args: object, **kwargs: object) -> Any:
            return self.registrar_auditoria(*args, **kwargs)  # type: ignore[arg-type]

        def _map_cb(row: Any) -> Pedido:
            return self._map_pedido(row)

        def _lookup_cb(nota_pedido: str) -> Pedido | None:
            return self.buscar_pedido_por_nota(nota_pedido)

        def _reg_client_cb(nombre: str) -> Any:
            return self.registrar_cliente(nombre)

        self.audit_repo = AuditRepository(self._connect)
        self.channel_report_repo = ChannelReportRepository(self._connect)
        self.concurrency_repo = ConcurrencyRepository(self._connect)
        self.factory_plan_repo = FactoryPlanRepository(self._connect)
        self.full_plan_repo = FullPlanRepository(self._connect)
        self.stock_flow_repo = StockFlowRepository(self._connect)
        self.client_repo = ClientRepository(self._connect, audit_fn=_audit_cb)
        self.dispatch_repo = DispatchRepository(
            self._connect,
            map_pedido_fn=_map_cb,
            audit_fn=_audit_cb,
        )
        self.closure_repo = ClosureRepository(
            self._connect,
            map_pedido_fn=_map_cb,
            audit_fn=_audit_cb,
        )
        self.chat_repo = ChatRepository(self._connect, lookup_order_fn=_lookup_cb)
        self.order_core_repo = OrderCoreRepository(
            self._connect,
            audit_fn=_audit_cb,
            register_client_fn=_reg_client_cb,
        )
        self._initialize()

    # --- Conexión e Inicialización de Esquema ---

    @contextmanager
    def _connect(self) -> Generator[sqlite3.Connection, None, None]:
        with sqlite_connection(
            self.database_path,
            synchronous_normal=True,
            temp_store_memory=True,
        ) as connection:
            yield connection

    def _db_signature(self) -> tuple[str, int, int] | None:
        try:
            if not self.database_path.exists():
                return None
            st = self.database_path.stat()
            if st.st_size <= 0:
                return None
            return (str(self.database_path.resolve()), st.st_ctime_ns, st.st_ino)
        except OSError:
            return None

    def _initialize(self) -> None:
        sig_before = self._db_signature()
        if sig_before is not None and sig_before in self._initialized_dbs:
            return
        with self._connect() as connection, connection:
            inicializar_esquema_pedidos(connection, self.database_path)
        sig_after = self._db_signature()
        if sig_after is not None:
            self._initialized_dbs.add(sig_after)

    # --- Auditoría y Métricas (AuditRepository) ---
    registrar_auditoria = DelegadoAtributo("audit_repo", AuditRepository)
    listar_auditoria = DelegadoAtributo("audit_repo", AuditRepository)
    obtener_metricas_dashboard = DelegadoAtributo("audit_repo", AuditRepository)
    _filtro_fechas = staticmethod(AuditRepository._filtro_fechas)

    # --- Reportes por Canal (ChannelReportRepository) ---
    obtener_descuentos_operario_por_canal = DelegadoAtributo(
        "channel_report_repo", ChannelReportRepository
    )
    obtener_ventana_ultimo_cierre = DelegadoAtributo(
        "channel_report_repo", ChannelReportRepository
    )

    # --- Chat Colaborativo (ChatRepository) ---
    obtener_pedido_resumen_chat = DelegadoAtributo("chat_repo", ChatRepository)
    enviar_mensaje_chat = DelegadoAtributo("chat_repo", ChatRepository)
    listar_mensajes_chat = DelegadoAtributo("chat_repo", ChatRepository)
    contar_mensajes_no_leidos = DelegadoAtributo("chat_repo", ChatRepository)
    marcar_mensajes_leidos = DelegadoAtributo("chat_repo", ChatRepository)

    # --- Gestión de Clientes (ClientRepository) ---
    listar_clientes = DelegadoAtributo("client_repo", ClientRepository)
    listar_nombres_clientes = DelegadoAtributo("client_repo", ClientRepository)
    buscar_clientes = DelegadoAtributo("client_repo", ClientRepository)
    crear_cliente = DelegadoAtributo("client_repo", ClientRepository)
    registrar_cliente = DelegadoAtributo("client_repo", ClientRepository)
    obtener_o_crear_cliente = DelegadoAtributo("client_repo", ClientRepository)
    actualizar_cliente = DelegadoAtributo("client_repo", ClientRepository)
    eliminar_cliente = DelegadoAtributo("client_repo", ClientRepository)

    # --- Cierres de Jornada y Mercado (ClosureRepository) ---
    listar_pedidos_pendientes_cierre = DelegadoAtributo("closure_repo", ClosureRepository)
    contar_pedidos_pendientes_cierre_por_tipo = DelegadoAtributo(
        "closure_repo", ClosureRepository
    )
    obtener_items_pendientes_cierre = DelegadoAtributo("closure_repo", ClosureRepository)
    registrar_cierre = DelegadoAtributo("closure_repo", ClosureRepository)
    listar_cierres = DelegadoAtributo("closure_repo", ClosureRepository)
    obtener_pedidos_por_cierre = DelegadoAtributo("closure_repo", ClosureRepository)
    actualizar_hoja_ruta_cierre = DelegadoAtributo("closure_repo", ClosureRepository)
    listar_pedidos_mercado_pendientes_cierre = DelegadoAtributo(
        "closure_repo", ClosureRepository
    )
    obtener_items_mercado_pendientes = DelegadoAtributo("closure_repo", ClosureRepository)
    registrar_cierre_mercado = DelegadoAtributo("closure_repo", ClosureRepository)
    listar_cierres_mercado = DelegadoAtributo("closure_repo", ClosureRepository)

    # --- Concurrencia e Idempotencia (ConcurrencyRepository) ---
    adquirir_bloqueo_pedido = DelegadoAtributo("concurrency_repo", ConcurrencyRepository)
    liberar_bloqueo_pedido = DelegadoAtributo("concurrency_repo", ConcurrencyRepository)
    consultar_bloqueo_pedido = DelegadoAtributo("concurrency_repo", ConcurrencyRepository)
    registrar_transaccion_idempotente = DelegadoAtributo(
        "concurrency_repo", ConcurrencyRepository
    )
    liberar_transaccion_idempotente = DelegadoAtributo(
        "concurrency_repo", ConcurrencyRepository
    )

    # --- Despacho y Escaneo QR (DispatchRepository) ---
    extraer_remito_de_codigo = staticmethod(DispatchRepository.extraer_remito_de_codigo)
    extraer_datos_qr_despacho = staticmethod(DispatchRepository.extraer_datos_qr_despacho)
    listar_pedidos_por_estado_despacho = DelegadoAtributo("dispatch_repo", DispatchRepository)
    obtener_bultos_escaneados = DelegadoAtributo("dispatch_repo", DispatchRepository)
    obtener_mapa_bultos_escaneados = DelegadoAtributo("dispatch_repo", DispatchRepository)
    registrar_escaneo_bulto_despacho = DelegadoAtributo("dispatch_repo", DispatchRepository)
    despachar_pedido_manual = DelegadoAtributo("dispatch_repo", DispatchRepository)
    buscar_pedido_por_nota = DelegadoAtributo("dispatch_repo", DispatchRepository)
    actualizar_estado_despacho = DelegadoAtributo("dispatch_repo", DispatchRepository)
    avanzar_estado_lote = DelegadoAtributo("dispatch_repo", DispatchRepository)
    avanzar_estado_por_codigo = DelegadoAtributo("dispatch_repo", DispatchRepository)

    # --- Planes de Ingreso de Fábrica (FactoryPlanRepository) ---
    crear_plan_ingreso_fabrica = DelegadoAtributo("factory_plan_repo", FactoryPlanRepository)
    obtener_plan_ingreso_fabrica = DelegadoAtributo("factory_plan_repo", FactoryPlanRepository)
    obtener_plan_activo_ingreso_fabrica = DelegadoAtributo(
        "factory_plan_repo", FactoryPlanRepository
    )
    listar_planes_ingreso_fabrica = DelegadoAtributo(
        "factory_plan_repo", FactoryPlanRepository
    )
    obtener_items_plan_ingreso_fabrica = DelegadoAtributo(
        "factory_plan_repo", FactoryPlanRepository
    )
    registrar_escaneo_item_ingreso_fabrica = DelegadoAtributo(
        "factory_plan_repo", FactoryPlanRepository
    )
    ajustar_cantidad_item_ingreso_fabrica = DelegadoAtributo(
        "factory_plan_repo", FactoryPlanRepository
    )
    registrar_cierre_parcial_ingreso_fabrica = DelegadoAtributo(
        "factory_plan_repo", FactoryPlanRepository
    )
    finalizar_plan_ingreso_fabrica = DelegadoAtributo(
        "factory_plan_repo", FactoryPlanRepository
    )
    listar_cierres_parciales_fabrica = DelegadoAtributo(
        "factory_plan_repo", FactoryPlanRepository
    )
    cancelar_plan_ingreso_fabrica = DelegadoAtributo(
        "factory_plan_repo", FactoryPlanRepository
    )

    # --- Planes de Mercado Envíos Full (FullPlanRepository) ---
    crear_plan_mercado_full = DelegadoAtributo("full_plan_repo", FullPlanRepository)
    obtener_plan_mercado_full = DelegadoAtributo("full_plan_repo", FullPlanRepository)
    obtener_plan_activo_mercado_full = DelegadoAtributo("full_plan_repo", FullPlanRepository)
    listar_planes_mercado_full = DelegadoAtributo("full_plan_repo", FullPlanRepository)
    obtener_items_plan_full = DelegadoAtributo("full_plan_repo", FullPlanRepository)
    registrar_escaneo_item_plan = DelegadoAtributo("full_plan_repo", FullPlanRepository)
    ajustar_cantidad_item_plan = DelegadoAtributo("full_plan_repo", FullPlanRepository)
    finalizar_plan_mercado_full = DelegadoAtributo("full_plan_repo", FullPlanRepository)
    cancelar_plan_mercado_full = DelegadoAtributo("full_plan_repo", FullPlanRepository)
    registrar_cierre_parcial_mercado_full = DelegadoAtributo(
        "full_plan_repo", FullPlanRepository
    )
    registrar_cierre_final_mercado_full = DelegadoAtributo(
        "full_plan_repo", FullPlanRepository
    )
    listar_cierres_parciales_full = DelegadoAtributo("full_plan_repo", FullPlanRepository)

    # --- Flujo Diario de Stock (StockFlowRepository) ---
    obtener_flujo_stock_diario = DelegadoAtributo("stock_flow_repo", StockFlowRepository)

    # --- Operaciones Core de Pedidos (OrderCoreRepository) ---
    _map_pedido = staticmethod(OrderCoreRepository.map_pedido)
    _obtener_fila_pedido = DelegadoAtributo(
        "order_core_repo", OrderCoreRepository, "obtener_fila_pedido"
    )
    existe_nota_pedido = DelegadoAtributo("order_core_repo", OrderCoreRepository)
    registrar_pedido = DelegadoAtributo("order_core_repo", OrderCoreRepository)
    buscar_pedido_por_hash = DelegadoAtributo("order_core_repo", OrderCoreRepository)
    listar_pedidos = DelegadoAtributo("order_core_repo", OrderCoreRepository)
    obtener_pedido_por_id = DelegadoAtributo("order_core_repo", OrderCoreRepository)
    obtener_resumen_pedidos_por_fecha = DelegadoAtributo(
        "order_core_repo", OrderCoreRepository
    )
    anular_pedido = DelegadoAtributo("order_core_repo", OrderCoreRepository)
    eliminar_pedido = DelegadoAtributo("order_core_repo", OrderCoreRepository)
    obtener_items_sin_coincidencia = DelegadoAtributo(
        "order_core_repo", OrderCoreRepository
    )
    guardar_items_sin_coincidencia = DelegadoAtributo(
        "order_core_repo", OrderCoreRepository
    )
    obtener_items_pedido = DelegadoAtributo("order_core_repo", OrderCoreRepository)
    actualizar_datos_pedido = DelegadoAtributo("order_core_repo", OrderCoreRepository)
