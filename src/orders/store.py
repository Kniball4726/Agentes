"""Motor de persistencia SQLite y lógica de negocio para pedidos, clientes y cierres."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator

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
from .order_core_repo import OrderCoreRepository
from .stock_flow_repo import StockFlowRepository
from .models import (
    CierreJornada,
    CierreMercado,
    Cliente,
    MensajeChat,
    Pedido,
    RegistroAuditoria,
)
from .schema import inicializar_esquema_pedidos


class OrderStore:
    """Gestor unificado de almacenamiento y operaciones de pedidos, clientes y despachos."""

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

    # ------------------------------------------------------------------
    # Delegadores de repositorios compuestos
    # ------------------------------------------------------------------

    def registrar_auditoria(self, usuario: str, accion: str, detalle: str) -> None:
        self.audit_repo.registrar_auditoria(usuario, accion, detalle)

    def listar_auditoria(
        self,
        limit: int = 150,
        filtro_usuario: str = "",
        filtro_accion: str = "",
        filtro_texto: str = "",
        filtro: str = "",
    ) -> list[RegistroAuditoria]:
        return self.audit_repo.listar_auditoria(
            limit=limit,
            filtro_usuario=filtro_usuario,
            filtro_accion=filtro_accion,
            filtro_texto=filtro_texto,
            filtro=filtro,
        )

    @staticmethod
    def _filtro_fechas(
        columna: str,
        fecha_desde: str | None,
        fecha_hasta: str | None,
    ) -> tuple[str, list[str]]:
        return AuditRepository._filtro_fechas(columna, fecha_desde, fecha_hasta)

    def obtener_metricas_dashboard(
        self,
        fecha_desde: str | None = None,
        fecha_hasta: str | None = None,
    ) -> dict:
        return self.audit_repo.obtener_metricas_dashboard(
            fecha_desde=fecha_desde,
            fecha_hasta=fecha_hasta,
        )

    def obtener_descuentos_operario_por_canal(
        self,
        pedidos_ids: list[int] | None = None,
        solo_pendientes: bool = True,
        fecha_desde: str = "",
        fecha_hasta: str = "",
        cierre_id: int | None = None,
    ) -> list[dict[str, Any]]:
        return self.channel_report_repo.obtener_descuentos_operario_por_canal(
            pedidos_ids=pedidos_ids,
            solo_pendientes=solo_pendientes,
            fecha_desde=fecha_desde,
            fecha_hasta=fecha_hasta,
            cierre_id=cierre_id,
        )

    def obtener_ventana_ultimo_cierre(
        self,
        cierre_id: int | None = None,
    ) -> tuple[str, str, int | None]:
        return self.channel_report_repo.obtener_ventana_ultimo_cierre(cierre_id=cierre_id)

    def obtener_pedido_resumen_chat(self, nota_pedido: str) -> str:
        return self.chat_repo.obtener_pedido_resumen_chat(nota_pedido)

    def enviar_mensaje_chat(
        self,
        emisor: str,
        mensaje: str,
        destinatario: str = "Todos",
    ) -> MensajeChat:
        return self.chat_repo.enviar_mensaje_chat(
            emisor,
            mensaje,
            destinatario=destinatario,
        )

    def listar_mensajes_chat(self, usuario: str, limite: int = 60) -> list[MensajeChat]:
        return self.chat_repo.listar_mensajes_chat(usuario, limite=limite)

    def contar_mensajes_no_leidos(self, usuario: str) -> int:
        return self.chat_repo.contar_mensajes_no_leidos(usuario)

    def marcar_mensajes_leidos(self, usuario: str) -> None:
        self.chat_repo.marcar_mensajes_leidos(usuario)

    def listar_clientes(self) -> list[Cliente]:
        return self.client_repo.listar_clientes()

    def listar_nombres_clientes(self) -> list[str]:
        return self.client_repo.listar_nombres_clientes()

    def buscar_clientes(self, query: str = "") -> list[Cliente]:
        return self.client_repo.buscar_clientes(query=query)

    def crear_cliente(
        self,
        nombre: str,
        usuario: str = "Sistema",
        codigo: str = "",
        direccion: str = "",
    ) -> Cliente:
        return self.client_repo.crear_cliente(
            nombre,
            usuario=usuario,
            codigo=codigo,
            direccion=direccion,
        )

    def registrar_cliente(
        self,
        nombre: str,
        usuario: str = "Sistema",
        codigo: str = "",
        direccion: str = "",
    ) -> Cliente:
        return self.client_repo.registrar_cliente(
            nombre,
            usuario=usuario,
            codigo=codigo,
            direccion=direccion,
        )

    def obtener_o_crear_cliente(
        self,
        nombre: str,
        codigo: str = "",
        direccion: str = "",
        usuario: str = "Sistema",
    ) -> Cliente:
        return self.client_repo.obtener_o_crear_cliente(
            nombre,
            codigo=codigo,
            direccion=direccion,
            usuario=usuario,
        )

    def actualizar_cliente(
        self,
        cliente_id: int,
        nuevo_nombre: str,
        actualizar_pedidos: bool = True,
        usuario: str = "Sistema",
        codigo: str | None = None,
        direccion: str | None = None,
    ) -> Cliente:
        return self.client_repo.actualizar_cliente(
            cliente_id,
            nuevo_nombre,
            actualizar_pedidos=actualizar_pedidos,
            usuario=usuario,
            codigo=codigo,
            direccion=direccion,
        )

    def eliminar_cliente(self, cliente_id: int, usuario: str = "Sistema") -> None:
        self.client_repo.eliminar_cliente(cliente_id, usuario=usuario)

    def listar_pedidos_pendientes_cierre(self) -> list[Pedido]:
        return self.closure_repo.listar_pedidos_pendientes_cierre()

    def contar_pedidos_pendientes_cierre_por_tipo(self) -> dict[str, int]:
        return self.closure_repo.contar_pedidos_pendientes_cierre_por_tipo()

    def obtener_items_pendientes_cierre(self) -> list[tuple[str, str, int, list[str]]]:
        return self.closure_repo.obtener_items_pendientes_cierre()

    def registrar_cierre(
        self,
        usuario: str,
        pedidos_ids: list[int],
        articulos_totales: int,
        resumen_pedidos: str,
        archivo_pdf: str = "",
        archivo_excel: str = "",
        archivo_hoja_ruta: str = "",
    ) -> int:
        return self.closure_repo.registrar_cierre(
            usuario,
            pedidos_ids,
            articulos_totales,
            resumen_pedidos,
            archivo_pdf=archivo_pdf,
            archivo_excel=archivo_excel,
            archivo_hoja_ruta=archivo_hoja_ruta,
        )

    def listar_cierres(self, limit: int = 50) -> list[CierreJornada]:
        return self.closure_repo.listar_cierres(limit=limit)

    def obtener_pedidos_por_cierre(self, cierre_id: int) -> list[Pedido]:
        return self.closure_repo.obtener_pedidos_por_cierre(cierre_id)

    def actualizar_hoja_ruta_cierre(self, cierre_id: int, archivo_hoja_ruta: str) -> None:
        self.closure_repo.actualizar_hoja_ruta_cierre(cierre_id, archivo_hoja_ruta)

    def listar_pedidos_mercado_pendientes_cierre(
        self,
        tipo: str = "TODOS",
        armador: str | None = None,
    ) -> list[Pedido]:
        return self.closure_repo.listar_pedidos_mercado_pendientes_cierre(
            tipo=tipo,
            armador=armador,
        )

    def obtener_items_mercado_pendientes(
        self,
        pedidos_ids: list[int],
    ) -> list[tuple[str, str, int, list[str]]]:
        return self.closure_repo.obtener_items_mercado_pendientes(pedidos_ids)

    def registrar_cierre_mercado(
        self,
        usuario: str,
        tipo_mercado: str,
        pedidos_ids: list[int],
        articulos_totales: int,
        resumen_pedidos: str,
        archivo_pdf: str = "",
        archivo_excel: str = "",
    ) -> int:
        return self.closure_repo.registrar_cierre_mercado(
            usuario,
            tipo_mercado,
            pedidos_ids,
            articulos_totales,
            resumen_pedidos,
            archivo_pdf=archivo_pdf,
            archivo_excel=archivo_excel,
        )

    def listar_cierres_mercado(self, limit: int = 50) -> list[CierreMercado]:
        return self.closure_repo.listar_cierres_mercado(limit=limit)

    def adquirir_bloqueo_pedido(
        self,
        pedido_id: int,
        usuario: str,
        expiracion_minutos: int = 5,
    ) -> tuple[bool, str, str]:
        return self.concurrency_repo.adquirir_bloqueo_pedido(
            pedido_id,
            usuario,
            expiracion_minutos=expiracion_minutos,
        )

    def liberar_bloqueo_pedido(self, pedido_id: int, usuario: str | None = None) -> None:
        self.concurrency_repo.liberar_bloqueo_pedido(pedido_id, usuario=usuario)

    def consultar_bloqueo_pedido(
        self,
        pedido_id: int,
        expiracion_minutos: int = 5,
    ) -> tuple[str, str] | None:
        return self.concurrency_repo.consultar_bloqueo_pedido(
            pedido_id,
            expiracion_minutos=expiracion_minutos,
        )

    def registrar_transaccion_idempotente(
        self,
        tx_id: str,
        accion: str,
        detalle: str = "",
    ) -> bool:
        return self.concurrency_repo.registrar_transaccion_idempotente(
            tx_id,
            accion,
            detalle=detalle,
        )

    @staticmethod
    def extraer_remito_de_codigo(texto: str) -> str:
        return DispatchRepository.extraer_remito_de_codigo(texto)

    def buscar_pedido_por_nota(self, nota_pedido: str) -> Pedido | None:
        return self.dispatch_repo.buscar_pedido_por_nota(nota_pedido)

    def actualizar_estado_despacho(
        self,
        pedido_id: int,
        nuevo_estado: str,
        usuario: str = "Sistema",
        permitir_retroceso: bool = False,
    ) -> Pedido:
        return self.dispatch_repo.actualizar_estado_despacho(
            pedido_id,
            nuevo_estado,
            usuario=usuario,
            permitir_retroceso=permitir_retroceso,
        )

    def avanzar_estado_lote(
        self,
        pedido_ids: list[int],
        nuevo_estado: str,
        usuario: str = "Operador",
    ) -> int:
        return self.dispatch_repo.avanzar_estado_lote(
            pedido_ids,
            nuevo_estado,
            usuario=usuario,
        )

    def avanzar_estado_por_codigo(
        self,
        codigo: str = "",
        usuario: str = "Sistema",
        *,
        codigo_qr_o_remito: str = "",
        nuevo_estado: str | None = None,
    ) -> tuple[bool, str, Pedido | None]:
        return self.dispatch_repo.avanzar_estado_por_codigo(
            codigo=codigo,
            usuario=usuario,
            codigo_qr_o_remito=codigo_qr_o_remito,
            nuevo_estado=nuevo_estado,
        )

    def crear_plan_ingreso_fabrica(
        self,
        nombre_remito: str,
        archivo_remito: str,
        creado_por: str,
        items: list[tuple[str, str, int]],
    ) -> int:
        return self.factory_plan_repo.crear_plan_ingreso_fabrica(
            nombre_remito,
            archivo_remito,
            creado_por,
            items,
        )

    def obtener_plan_ingreso_fabrica(self, plan_id: int) -> dict[str, Any] | None:
        return self.factory_plan_repo.obtener_plan_ingreso_fabrica(plan_id)

    def obtener_plan_activo_ingreso_fabrica(self) -> dict[str, Any] | None:
        return self.factory_plan_repo.obtener_plan_activo_ingreso_fabrica()

    def listar_planes_ingreso_fabrica(
        self,
        estado: str | None = None,
    ) -> list[dict[str, Any]]:
        return self.factory_plan_repo.listar_planes_ingreso_fabrica(estado=estado)

    def obtener_items_plan_ingreso_fabrica(self, plan_id: int) -> list[dict[str, Any]]:
        return self.factory_plan_repo.obtener_items_plan_ingreso_fabrica(plan_id)

    def registrar_escaneo_item_ingreso_fabrica(
        self,
        plan_id: int,
        codigo_escaneado: str,
        cantidad: int = 1,
        picker: str = "",
    ) -> dict[str, Any]:
        return self.factory_plan_repo.registrar_escaneo_item_ingreso_fabrica(
            plan_id,
            codigo_escaneado,
            cantidad=cantidad,
            picker=picker,
        )

    def ajustar_cantidad_item_ingreso_fabrica(
        self,
        plan_id: int,
        codigo: str,
        nueva_cantidad: int,
        picker: str = "",
    ) -> dict[str, Any]:
        return self.factory_plan_repo.ajustar_cantidad_item_ingreso_fabrica(
            plan_id,
            codigo,
            nueva_cantidad,
            picker=picker,
        )

    def registrar_cierre_parcial_ingreso_fabrica(
        self,
        plan_id: int,
        picker: str = "",
    ) -> dict[str, Any]:
        return self.factory_plan_repo.registrar_cierre_parcial_ingreso_fabrica(
            plan_id,
            picker=picker,
        )

    def finalizar_plan_ingreso_fabrica(
        self,
        plan_id: int,
        picker: str = "",
    ) -> dict[str, Any]:
        return self.factory_plan_repo.finalizar_plan_ingreso_fabrica(
            plan_id,
            picker=picker,
        )

    def listar_cierres_parciales_fabrica(self, plan_id: int) -> list[dict[str, Any]]:
        return self.factory_plan_repo.listar_cierres_parciales_fabrica(plan_id)

    def cancelar_plan_ingreso_fabrica(self, plan_id: int) -> bool:
        return self.factory_plan_repo.cancelar_plan_ingreso_fabrica(plan_id)

    def crear_plan_mercado_full(
        self,
        nombre_envio: str,
        archivo_excel: str,
        creado_por: str,
        items: list[tuple[str, str, int]],
    ) -> int:
        return self.full_plan_repo.crear_plan_mercado_full(
            nombre_envio,
            archivo_excel,
            creado_por,
            items,
        )

    def obtener_plan_mercado_full(self, plan_id: int) -> dict[str, Any] | None:
        return self.full_plan_repo.obtener_plan_mercado_full(plan_id)

    def obtener_plan_activo_mercado_full(self) -> dict[str, Any] | None:
        return self.full_plan_repo.obtener_plan_activo_mercado_full()

    def listar_planes_mercado_full(
        self,
        estado: str | None = None,
    ) -> list[dict[str, Any]]:
        return self.full_plan_repo.listar_planes_mercado_full(estado=estado)

    def obtener_items_plan_full(self, plan_id: int) -> list[dict[str, Any]]:
        return self.full_plan_repo.obtener_items_plan_full(plan_id)

    def registrar_escaneo_item_plan(
        self,
        plan_id: int,
        codigo_escaneado: str,
        cantidad: int = 1,
        picker: str = "",
    ) -> dict[str, Any]:
        return self.full_plan_repo.registrar_escaneo_item_plan(
            plan_id,
            codigo_escaneado,
            cantidad=cantidad,
            picker=picker,
        )

    def ajustar_cantidad_item_plan(
        self,
        plan_id: int,
        codigo: str,
        nueva_cantidad: int,
        picker: str = "",
    ) -> dict[str, Any]:
        return self.full_plan_repo.ajustar_cantidad_item_plan(
            plan_id,
            codigo,
            nueva_cantidad,
            picker=picker,
        )

    def finalizar_plan_mercado_full(
        self,
        plan_id: int,
        picker: str = "",
    ) -> bool:
        return self.full_plan_repo.finalizar_plan_mercado_full(
            plan_id,
            picker=picker,
        )

    def cancelar_plan_mercado_full(self, plan_id: int) -> bool:
        return self.full_plan_repo.cancelar_plan_mercado_full(plan_id)

    def obtener_flujo_stock_diario(self, fecha: str = "") -> dict[str, Any]:
        return self.stock_flow_repo.obtener_flujo_stock_diario(fecha=fecha)

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
            inicializar_esquema_pedidos(connection)
        sig_after = self._db_signature()
        if sig_after is not None:
            self._initialized_dbs.add(sig_after)

    @staticmethod
    def _map_pedido(row: sqlite3.Row) -> Pedido:
        return OrderCoreRepository.map_pedido(row)

    def _obtener_fila_pedido(self, connection: sqlite3.Connection, pedido_id: int) -> sqlite3.Row | None:
        return self.order_core_repo.obtener_fila_pedido(connection, pedido_id)

    def existe_nota_pedido(self, nota_pedido: str) -> bool:
        """Indica si ya existe un pedido registrado con la nota especificada."""
        return self.order_core_repo.existe_nota_pedido(nota_pedido)

    def registrar_pedido(
        self,
        nota_pedido: str,
        numero_pedido: str,
        cliente: str,
        bultos: int,
        logistica: str,
        armador: str,
        tipo_archivo: str,
        nombre_archivo: str,
        agregado: bool = False,
        articulos_descontados: int = 0,
        resumen_items: str = "",
        fecha_retiro: str = "",
        archivo_descuento: str = "",
        items: list[tuple[str, str, int]] | None = None,
        archivo_hash: str = "",
        numero_guia: str = "",
        items_sin_coincidencia: list[tuple[str, str]] | None = None,
        canal: str = "",
    ) -> Pedido:
        """Valida e inserta un nuevo pedido junto a sus ítems y registro de auditoría."""
        return self.order_core_repo.registrar_pedido(
            nota_pedido=nota_pedido,
            numero_pedido=numero_pedido,
            cliente=cliente,
            bultos=bultos,
            logistica=logistica,
            armador=armador,
            tipo_archivo=tipo_archivo,
            nombre_archivo=nombre_archivo,
            agregado=agregado,
            articulos_descontados=articulos_descontados,
            resumen_items=resumen_items,
            fecha_retiro=fecha_retiro,
            archivo_descuento=archivo_descuento,
            items=items,
            archivo_hash=archivo_hash,
            numero_guia=numero_guia,
            items_sin_coincidencia=items_sin_coincidencia,
            canal=canal,
        )

    def buscar_pedido_por_hash(self, archivo_hash: str) -> Pedido | None:
        """Busca un pedido activo por el hash SHA-256 del archivo origen."""
        return self.order_core_repo.buscar_pedido_por_hash(archivo_hash)

    def listar_pedidos(self, limit: int = 50) -> list[Pedido]:
        """Lista los pedidos más recientes en orden descendente por ID."""
        return self.order_core_repo.listar_pedidos(limit=limit)

    def obtener_resumen_pedidos_por_fecha(self, limit: int = 30) -> list[dict[str, int | str]]:
        """Agrupa los pedidos armados (no anulados) por fecha en orden descendente."""
        return self.order_core_repo.obtener_resumen_pedidos_por_fecha(limit=limit)

    def anular_pedido(self, pedido_id: int, motivo: str = "", usuario: str = "Sistema") -> None:
        """Marca un pedido como anulado y registra el motivo en auditoría."""
        self.order_core_repo.anular_pedido(pedido_id, motivo=motivo, usuario=usuario)

    def obtener_items_sin_coincidencia(self, pedido_id: int) -> list[tuple[str, str]]:
        """Devuelve la lista JSON de ítems sin coincidencia guardada para un pedido."""
        return self.order_core_repo.obtener_items_sin_coincidencia(pedido_id)

    def guardar_items_sin_coincidencia(self, pedido_id: int, items: list[tuple[str, str]]) -> None:
        """Guarda el detalle JSON de ítems sin coincidencia para un pedido."""
        self.order_core_repo.guardar_items_sin_coincidencia(pedido_id, items)

    def obtener_items_pedido(self, pedido_id: int) -> list[tuple[str, str, int]]:
        """Retorna los ítems descontados asociados a un pedido."""
        return self.order_core_repo.obtener_items_pedido(pedido_id)

    def actualizar_datos_pedido(
        self,
        pedido_id: int,
        cliente: str | None = None,
        numero_pedido: str | None = None,
        bultos: int | None = None,
        logistica: str | None = None,
        fecha_retiro: str | None = None,
        usuario: str = "Sistema",
        numero_guia: str | None = None,
    ) -> Pedido:
        """Actualiza metadatos editables de un pedido con validación y trazabilidad."""
        return self.order_core_repo.actualizar_datos_pedido(
            pedido_id=pedido_id,
            cliente=cliente,
            numero_pedido=numero_pedido,
            bultos=bultos,
            logistica=logistica,
            fecha_retiro=fecha_retiro,
            usuario=usuario,
            numero_guia=numero_guia,
        )
