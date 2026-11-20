"""Coordinador independiente para el despacho uniforme de diálogos modales."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable

import flet as ft

from ..components import (
    imprimir_rotulos_lote_ui,
    imprimir_rotulos_pedido_ui,
    imprimir_rotulos_termicos_pedido_ui,
)
from ..dialogs.cierre.dlg_cierre_full_plan import (
    mostrar_cierre_final_mercado_full,
    mostrar_cierre_parcial_mercado_full,
)
from ..dialogs import (
    confirmar_restaurar,
    generar_pedido_fabrica,
    mostrar_centro_reportes,
    mostrar_comparativa_stock_fisico_admin,
    mostrar_control_ingreso_fabrica,
    mostrar_dashboard_metricas,
    mostrar_descuento_mercado_full,
    mostrar_descuento_mercado_libre,
    mostrar_dialogo_api_keys,
    mostrar_dialogo_api_master,
    mostrar_dialogo_backup,
    mostrar_dialogo_cierre_jornada,
    mostrar_dialogo_cierre_mercado,
    mostrar_dialogo_cierres_operarios,
    mostrar_dialogo_compartir_cierre,
    mostrar_dialogo_configuracion_smtp,
    mostrar_dialogo_confirmar_anulacion_pedido,
    mostrar_dialogo_confirmar_desarmar_pedido,
    mostrar_dialogo_crear_pedido,
    mostrar_dialogo_editar_pedido,
    mostrar_dialogo_ajuste_bultos_express,
    mostrar_dialogo_enviar_correo,
    mostrar_dialogo_escaner_qr_despacho,
    mostrar_modulo_despacho,
    mostrar_dialogo_formulario_producto,
    mostrar_dialogo_gestion_clientes,
    mostrar_dialogo_gestion_productos,
    mostrar_dialogo_gestion_usuarios,
    mostrar_dialogo_historial_movimientos_stock,
    mostrar_dialogo_ingreso_rapido,
    mostrar_dialogo_inventario_vivo,
    mostrar_dialogo_salida_rapida,
    mostrar_dialogo_ver_stock,
    mostrar_estadisticas,
    mostrar_gestion_ambientes,
    mostrar_historial_pedidos,
    mostrar_imprimir_descuentos,
    mostrar_ingreso_fabrica,
    mostrar_notificaciones_admin,
    mostrar_picking_guiado_full,
    mostrar_dialogo_ola_picking,
    mostrar_planificar_full,
    mostrar_planificar_ingreso_fabrica,
    mostrar_registro_auditoria,
    mostrar_stock_fisico_operario,
    restaurar_documentos,
)
from ..dialogs.dlg_archivo_historico import mostrar_dialogo_archivo_historico
from ..dialogs.dlg_telegram import mostrar_dialogo_configuracion_telegram

logger = logging.getLogger(__name__)


class DialogCoordinator:
    """Centraliza las precondiciones (roles, drawer móvil, FilePicker) y apertura de modales."""

    def __init__(
        self,
        host: Any,
        check_roles_fn: Callable[..., bool] | None = None,
        close_drawer_fn: Callable[[], None] | None = None,
        ensure_file_picker_fn: Callable[..., None] | None = None,
        notify_fn: Callable[[str], None] | None = None,
    ) -> None:
        self._host = host
        self._check_roles_fn = check_roles_fn
        self._close_drawer_fn = close_drawer_fn
        self._ensure_file_picker_fn = ensure_file_picker_fn
        self._notify_fn = notify_fn

    def _exigir_roles(self, *roles: Any) -> bool:
        fn = self._check_roles_fn or getattr(self._host, "exigir_roles", None)
        return bool(fn(*roles)) if callable(fn) else True

    def _cerrar_drawer(self) -> None:
        fn = self._close_drawer_fn or getattr(self._host, "cerrar_drawer_si_movil", None)
        if callable(fn):
            fn()

    def _asegurar_picker(self) -> None:
        fn = self._ensure_file_picker_fn or getattr(self._host, "_asegurar_file_picker", None)
        if callable(fn):
            fn()

    def _notificar(self, mensaje: str) -> None:
        fn = self._notify_fn or getattr(self._host, "notificar", None)
        if callable(fn):
            fn(mensaje)

    def _dispatch(
        self,
        dialog_fn: Callable[..., Any],
        *args: Any,
        close_drawer: bool = False,
        ensure_picker: bool = False,
        roles: tuple[Any, ...] | None = None,
        **kwargs: Any,
    ) -> Any:
        if roles and not self._exigir_roles(*roles):
            return None
        if close_drawer:
            self._cerrar_drawer()
        if ensure_picker:
            self._asegurar_picker()
        return dialog_fn(self._host, *args, **kwargs)

    def mostrar_dialogo_compartir_cierre(self, *args: Any, **kwargs: Any) -> None:
        self._dispatch(mostrar_dialogo_compartir_cierre, *args, **kwargs)

    def mostrar_dialogo_enviar_correo(
        self,
        archivos_iniciales: list[Path] | None = None,
        asunto_inicial: str = "",
        cuerpo_inicial: str = "",
        destinatarios_iniciales: str = "",
        titulo_dialogo: str = "Enviar por Correo",
    ) -> None:
        self._dispatch(
            mostrar_dialogo_enviar_correo,
            archivos_iniciales=archivos_iniciales,
            asunto_inicial=asunto_inicial,
            cuerpo_inicial=cuerpo_inicial,
            destinatarios_iniciales=destinatarios_iniciales,
            titulo_dialogo=titulo_dialogo,
        )

    def mostrar_dialogo_api_master(self, _evento: ft.Event | None = None, tab_inicial: int = 0) -> None:
        self._dispatch(mostrar_dialogo_api_master, close_drawer=True, tab_inicial=tab_inicial)

    def mostrar_gestion_api_keys(self, _evento: ft.Event | None = None) -> None:
        self.mostrar_dialogo_api_master(_evento, tab_inicial=0)

    def mostrar_estado_api(self, _evento: ft.Event | None = None) -> None:
        self.mostrar_dialogo_api_master(_evento, tab_inicial=1)

    def mostrar_sesiones_api(self, _evento: ft.Event | None = None) -> None:
        self.mostrar_dialogo_api_master(_evento, tab_inicial=2)

    def mostrar_configuracion_smtp(self, _evento: ft.Event | None = None) -> None:
        self._dispatch(mostrar_dialogo_configuracion_smtp)

    def confirmar_restaurar(self, _evento: ft.Event) -> None:
        self._dispatch(confirmar_restaurar, _evento)

    async def restaurar(self, _evento: ft.Event | None = None) -> None:
        await restaurar_documentos(self._host, _evento)

    def mostrar_gestion_usuarios(self, _evento: ft.Event | None = None) -> None:
        self._dispatch(mostrar_dialogo_gestion_usuarios)

    def mostrar_dialogo_api_keys(self, _evento: ft.Event | None = None) -> None:
        self._dispatch(mostrar_dialogo_api_keys, close_drawer=True)

    def mostrar_gestion_clientes(self, _evento: ft.Event | None = None) -> None:
        self._dispatch(mostrar_dialogo_gestion_clientes, close_drawer=True)

    def mostrar_crear_pedido(self, _evento: ft.Event | None = None) -> None:
        self._dispatch(mostrar_dialogo_crear_pedido, close_drawer=True, ensure_picker=True)

    def mostrar_historial_pedidos(self, _evento: ft.Event | None = None) -> None:
        self._dispatch(mostrar_historial_pedidos, _evento, close_drawer=True)

    def mostrar_centro_reportes(self, _evento: ft.Event | None = None) -> None:
        self._dispatch(mostrar_centro_reportes, close_drawer=True)

    def mostrar_detalle_pedido_modal(self, pedido: Any) -> None:
        from ..dialogs.dlg_historial_pedidos import mostrar_detalle_pedido_modal
        self._dispatch(mostrar_detalle_pedido_modal, pedido)

    def mostrar_escaner_qr_despacho(self, al_actualizar: Callable[[], None] | None = None) -> None:
        self._dispatch(mostrar_dialogo_escaner_qr_despacho, al_actualizar)

    def mostrar_modulo_despacho(self, _evento: ft.Event | None = None) -> None:
        self._dispatch(
            mostrar_modulo_despacho,
            _evento,
            close_drawer=True,
            roles=("despachador", "administrador"),
        )

    def mostrar_imprimir_descuentos(self, _evento: ft.Event | None = None) -> None:
        self._dispatch(mostrar_imprimir_descuentos, _evento)

    def mostrar_cierre_jornada(self, _evento: ft.Event | None = None) -> None:
        if not self._exigir_roles("operador"):
            return
        order_store = getattr(self._host, "order_store", None)
        if order_store:
            try:
                conteo = order_store.contar_pedidos_pendientes_cierre_por_tipo()
                if int(conteo.get("total", 0)) == 0:
                    self._notificar("No hay pedidos ni paquetes descontados pendientes para realizar el cierre de jornada.")
                    return
            except Exception:
                pass
        self._dispatch(mostrar_dialogo_cierre_jornada)

    def mostrar_cierre_mercado(self, _evento: ft.Event | None = None) -> None:
        self._dispatch(
            mostrar_dialogo_cierre_mercado,
            roles=("picker", "operador", "administrador", "master"),
        )

    def mostrar_cierre_mercado_envios(self, _evento: ft.Event | None = None) -> None:
        self._dispatch(
            mostrar_dialogo_cierre_mercado,
            tab_inicial=0,
            close_drawer=True,
            roles=("picker", "operador", "administrador", "master"),
        )

    def mostrar_cierre_parcial_mercado_full(self, _evento: ft.Event | None = None) -> None:
        self._dispatch(
            mostrar_cierre_parcial_mercado_full,
            close_drawer=True,
            roles=("picker", "operador", "administrador", "master"),
        )

    def mostrar_cierre_final_mercado_full(self, _evento: ft.Event | None = None) -> None:
        self._dispatch(
            mostrar_cierre_final_mercado_full,
            close_drawer=True,
            roles=("picker", "operador", "administrador", "master"),
        )

    def mostrar_historial_cierres_admin(self, _evento: ft.Event | None = None) -> None:
        self._dispatch(mostrar_dialogo_cierres_operarios, roles=("administrador", "master"))

    def mostrar_acceso_admin(self, _evento: ft.Event) -> None:
        if not self._exigir_roles("administrador"):
            return
        self.mostrar_formulario_producto()

    def mostrar_ver_stock(self, _evento: ft.Event | None = None) -> None:
        self._dispatch(mostrar_dialogo_ver_stock)

    def mostrar_gestion_productos(self, _evento: ft.Event | None = None) -> None:
        self._dispatch(mostrar_dialogo_gestion_productos)

    def mostrar_historial_movimientos_stock(self, codigo_inicial: str = "") -> None:
        self._dispatch(mostrar_dialogo_historial_movimientos_stock, codigo_inicial)

    def mostrar_formulario_producto(self, al_guardar: Callable[[], None] | None = None) -> None:
        self._dispatch(mostrar_dialogo_formulario_producto, al_guardar)

    def imprimir_rotulos_termicos_pedido(self, pedido: Any) -> None:
        self._dispatch(imprimir_rotulos_termicos_pedido_ui, pedido)

    def imprimir_rotulos_pedido(self, pedido: Any, llenar_hoja: bool = False) -> None:
        self._dispatch(imprimir_rotulos_pedido_ui, pedido, llenar_hoja)

    def imprimir_rotulos_lote(self, pedidos: list[Any], llenar_hoja: bool = False) -> None:
        self._dispatch(imprimir_rotulos_lote_ui, pedidos, llenar_hoja)

    def confirmar_anulacion_pedido(self, pedido: Any, al_final: Callable[[], None] | None = None) -> None:
        self._dispatch(mostrar_dialogo_confirmar_anulacion_pedido, pedido, al_final)

    def mostrar_dialogo_editar_pedido(self, pedido: Any, al_final: Callable[[], None] | None = None) -> None:
        self._dispatch(mostrar_dialogo_editar_pedido, pedido, al_final)

    def mostrar_dialogo_ajuste_bultos_express(self, pedido: Any, al_final: Callable[[], None] | None = None) -> None:
        self._dispatch(mostrar_dialogo_ajuste_bultos_express, pedido, al_final)

    def confirmar_desarmar_pedido(self, pedido: Any, al_final: Callable[[], None] | None = None) -> None:
        self._dispatch(mostrar_dialogo_confirmar_desarmar_pedido, pedido, al_final)

    def mostrar_dialogo_backup(self, _e: ft.Event | None = None) -> None:
        self._dispatch(mostrar_dialogo_backup)

    def mostrar_dialogo_archivo_historico(self, _e: ft.Event | None = None) -> None:
        self._dispatch(mostrar_dialogo_archivo_historico, _e)

    def mostrar_configuracion_telegram(self, _e: ft.Event | None = None) -> None:
        self._dispatch(mostrar_dialogo_configuracion_telegram, _e)

    def mostrar_sincronizacion_mercadolibre(self, _e: ft.Event | None = None) -> None:
        from ..dialogs.dlg_mercadolibre import mostrar_dialogo_mercadolibre
        self._dispatch(mostrar_dialogo_mercadolibre, _e)

    def mostrar_dialogo_anomalias(self, _e: ft.Event | None = None) -> None:
        from ..dialogs.dlg_anomalias import mostrar_dialogo_anomalias
        self._dispatch(mostrar_dialogo_anomalias, _e)

    def mostrar_dialogo_heatmap(self, _e: ft.Event | None = None) -> None:
        from ..dialogs.dlg_heatmap import mostrar_dialogo_heatmap
        self._dispatch(mostrar_dialogo_heatmap, _e)

    def sincronizar_catalogo_excel(self, _e: ft.Event | None = None) -> None:
        from ..dialogs.dlg_sincronizar_excel import mostrar_dialogo_sincronizar_excel
        self._dispatch(mostrar_dialogo_sincronizar_excel)

    def mostrar_detalle_quiebre(self, criticos: list | None = None) -> None:
        from ..dialogs.dlg_quiebre import mostrar_detalle_quiebre
        self._dispatch(mostrar_detalle_quiebre, criticos)

    def mostrar_dashboard_metricas(self, _e: ft.Event | None = None) -> None:
        self._dispatch(mostrar_dashboard_metricas, _e)

    def mostrar_registro_auditoria(self, _e: ft.Event | None = None) -> None:
        self._dispatch(mostrar_registro_auditoria, _e)

    def mostrar_estadisticas(self, _evento: ft.Event | None = None) -> None:
        self._dispatch(mostrar_estadisticas, _evento)

    def generar_pedido_fabrica(self, _evento: ft.Event | None = None) -> None:
        self._dispatch(generar_pedido_fabrica, _evento)

    def mostrar_ingreso_fabrica(self, _evento: ft.Event | None = None) -> None:
        self._dispatch(mostrar_ingreso_fabrica, _evento, close_drawer=True, ensure_picker=True)

    def mostrar_planificar_ingreso_fabrica(self, _evento: ft.Event | None = None) -> None:
        self._dispatch(mostrar_planificar_ingreso_fabrica, _evento, close_drawer=True, ensure_picker=True)

    def mostrar_control_ingreso_fabrica(self, _evento: ft.Event | None = None) -> None:
        self._dispatch(mostrar_control_ingreso_fabrica, _evento, close_drawer=True)

    def mostrar_descuento_mercado_full(self, _evento: ft.Event | None = None) -> None:
        self._dispatch(mostrar_descuento_mercado_full, _evento, close_drawer=True, ensure_picker=True)

    def mostrar_planificar_full(self, _evento: ft.Event | None = None) -> None:
        self._dispatch(mostrar_planificar_full, _evento, close_drawer=True, ensure_picker=True)

    def mostrar_picking_guiado_full(self, _evento: ft.Event | None = None) -> None:
        self._dispatch(mostrar_picking_guiado_full, _evento, close_drawer=True)

    def mostrar_dialogo_ola_picking(self, pedidos: list[Any] | None = None) -> None:
        self._dispatch(mostrar_dialogo_ola_picking, pedidos)

    def mostrar_descuento_mercado_libre(self, _evento: ft.Event | None = None) -> None:
        self._dispatch(mostrar_descuento_mercado_libre, _evento, close_drawer=True, ensure_picker=True)

    def mostrar_notificaciones_admin(self, _evento: ft.Event | None = None) -> None:
        self._dispatch(mostrar_notificaciones_admin, _evento)

    def mostrar_stock_fisico_operario(self, _evento: ft.Event | None = None) -> None:
        self._dispatch(mostrar_stock_fisico_operario, _evento, close_drawer=True, ensure_picker=True)

    def mostrar_comparativa_stock_fisico_admin(self, _evento: ft.Event | None = None) -> None:
        self._dispatch(mostrar_comparativa_stock_fisico_admin, _evento)

    def mostrar_dialogo_ingreso_rapido(self, _evento: ft.Event | None = None) -> None:
        self._dispatch(mostrar_dialogo_ingreso_rapido, _evento, close_drawer=True)

    def mostrar_dialogo_salida_rapida(self, _evento: ft.Event | None = None) -> None:
        self._dispatch(mostrar_dialogo_salida_rapida, _evento, close_drawer=True)

    def mostrar_dialogo_inventario_vivo(self, _evento: ft.Event | None = None) -> None:
        self._dispatch(mostrar_dialogo_inventario_vivo, _evento)

    def mostrar_gestion_ambientes(self, _evento: ft.Event | None = None) -> None:
        self._dispatch(mostrar_gestion_ambientes, _evento, close_drawer=True)
