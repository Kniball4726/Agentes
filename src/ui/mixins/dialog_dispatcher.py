"""Mixin para despacho y lanzamiento de diálogos y vistas modales en Flet."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable

import flet as ft

from ..dialogs import (
    confirmar_restaurar,
    generar_pedido_fabrica,
    mostrar_centro_reportes,
    mostrar_comparativa_stock_fisico_admin,
    mostrar_dialogo_configuracion_smtp,
    mostrar_dashboard_metricas,
    mostrar_descuento_mercado_full,
    mostrar_planificar_full,
    mostrar_picking_guiado_full,
    mostrar_descuento_mercado_libre,
    mostrar_dialogo_api_keys,
    mostrar_dialogo_api_master,
    mostrar_gestion_ambientes,
    mostrar_dialogo_backup,
    mostrar_dialogo_cierre_jornada,
    mostrar_dialogo_cierre_mercado,
    mostrar_dialogo_cierres_operarios,
    mostrar_dialogo_compartir_cierre,
    mostrar_dialogo_confirmar_anulacion_pedido,
    mostrar_dialogo_confirmar_desarmar_pedido,
    mostrar_dialogo_crear_pedido,
    mostrar_dialogo_editar_pedido,
    mostrar_dialogo_enviar_correo,
    mostrar_dialogo_escaner_qr_despacho,
    mostrar_dialogo_formulario_producto,
    mostrar_dialogo_gestion_clientes,
    mostrar_dialogo_gestion_productos,
    mostrar_dialogo_historial_movimientos_stock,
    mostrar_dialogo_ingreso_rapido,
    mostrar_dialogo_inventario_vivo,
    mostrar_dialogo_salida_rapida,
    mostrar_dialogo_ver_stock,
    mostrar_estado_api,
    mostrar_estadisticas,
    mostrar_gestion_api_keys,
    mostrar_dialogo_gestion_usuarios,
    mostrar_historial_pedidos,
    mostrar_imprimir_descuentos,
    mostrar_ingreso_fabrica,
    mostrar_planificar_ingreso_fabrica,
    mostrar_control_ingreso_fabrica,
    mostrar_notificaciones_admin,
    mostrar_registro_auditoria,
    mostrar_sesiones_api,
    mostrar_stock_fisico_operario,
    restaurar_documentos,
)
from ..dialogs.dlg_archivo_historico import mostrar_dialogo_archivo_historico
from ..dialogs.dlg_telegram import mostrar_dialogo_configuracion_telegram
from ..components import (
    imprimir_rotulos_lote_ui,
    imprimir_rotulos_pedido_ui,
    imprimir_rotulos_termicos_pedido_ui,
)

logger = logging.getLogger(__name__)


class DialogDispatcherMixin:
    """Provee métodos delegados para desplegar todos los cuadros de diálogo de la plataforma."""

    order_store: Any
    menu: Any
    usuario_actual: Any

    def mostrar_dialogo_compartir_cierre(self, *args, **kwargs) -> None:
        mostrar_dialogo_compartir_cierre(self, *args, **kwargs)

    def mostrar_dialogo_enviar_correo(
        self,
        archivos_iniciales: list[Path] | None = None,
        asunto_inicial: str = "",
        cuerpo_inicial: str = "",
        destinatarios_iniciales: str = "",
        titulo_dialogo: str = "Enviar por Correo",
    ) -> None:
        mostrar_dialogo_enviar_correo(
            self,
            archivos_iniciales=archivos_iniciales,
            asunto_inicial=asunto_inicial,
            cuerpo_inicial=cuerpo_inicial,
            destinatarios_iniciales=destinatarios_iniciales,
            titulo_dialogo=titulo_dialogo,
        )

    def mostrar_dialogo_api_master(self, _evento: ft.Event | None = None, tab_inicial: int = 0) -> None:
        self.cerrar_drawer_si_movil()
        mostrar_dialogo_api_master(self, tab_inicial=tab_inicial)

    def mostrar_gestion_api_keys(self, _evento: ft.Event | None = None) -> None:
        self.mostrar_dialogo_api_master(_evento, tab_inicial=0)

    def mostrar_estado_api(self, _evento: ft.Event | None = None) -> None:
        self.mostrar_dialogo_api_master(_evento, tab_inicial=1)

    def mostrar_sesiones_api(self, _evento: ft.Event | None = None) -> None:
        self.mostrar_dialogo_api_master(_evento, tab_inicial=2)

    def mostrar_configuracion_smtp(self, _evento: ft.Event | None = None) -> None:
        mostrar_dialogo_configuracion_smtp(self)

    def confirmar_restaurar(self, _evento: ft.Event) -> None:
        confirmar_restaurar(self, _evento)

    async def restaurar(self, _evento: ft.Event | None = None) -> None:
        await restaurar_documentos(self, _evento)

    def mostrar_gestion_usuarios(self, _evento: ft.Event | None = None) -> None:
        mostrar_dialogo_gestion_usuarios(self)

    def mostrar_dialogo_api_keys(self, _evento: ft.Event | None = None) -> None:
        self.cerrar_drawer_si_movil()
        mostrar_dialogo_api_keys(self)

    def mostrar_gestion_clientes(self, _evento: ft.Event | None = None) -> None:
        self.cerrar_drawer_si_movil()
        mostrar_dialogo_gestion_clientes(self)

    def mostrar_crear_pedido(self, _evento: ft.Event | None = None) -> None:
        self.cerrar_drawer_si_movil()
        self._asegurar_file_picker()
        mostrar_dialogo_crear_pedido(self)

    def mostrar_historial_pedidos(self, _evento: ft.Event | None = None) -> None:
        self.cerrar_drawer_si_movil()
        mostrar_historial_pedidos(self, _evento)

    def mostrar_centro_reportes(self, _evento: ft.Event | None = None) -> None:
        self.cerrar_drawer_si_movil()
        mostrar_centro_reportes(self)

    def mostrar_detalle_pedido_modal(self, pedido: Any) -> None:
        from ..dialogs.dlg_historial_pedidos import mostrar_detalle_pedido_modal
        mostrar_detalle_pedido_modal(self, pedido)

    def mostrar_escaner_qr_despacho(
        self,
        al_actualizar: Callable[[], None] | None = None,
    ) -> None:
        mostrar_dialogo_escaner_qr_despacho(self, al_actualizar)

    def mostrar_imprimir_descuentos(self, _evento: ft.Event | None = None) -> None:
        mostrar_imprimir_descuentos(self, _evento)

    def mostrar_cierre_jornada(self, _evento: ft.Event | None = None) -> None:
        if not self.exigir_roles("operador"):
            return
        if hasattr(self, "order_store") and self.order_store:
            try:
                conteo = self.order_store.contar_pedidos_pendientes_cierre_por_tipo()
                if int(conteo.get("total", 0)) == 0:
                    self.notificar("No hay pedidos ni paquetes descontados pendientes para realizar el cierre de jornada.")
                    return
            except Exception:
                pass
        mostrar_dialogo_cierre_jornada(self)

    def mostrar_cierre_mercado(self, _evento: ft.Event | None = None) -> None:
        """Abre el panel de cierre de tanda de Mercado Libre y Mercado Full para pickers y supervisores."""
        if not self.exigir_roles("picker", "operador", "administrador", "master"):
            return
        mostrar_dialogo_cierre_mercado(self)

    def mostrar_historial_cierres_admin(self, _evento: ft.Event | None = None) -> None:
        if not self.exigir_roles("administrador", "master"):
            return
        mostrar_dialogo_cierres_operarios(self)

    def mostrar_acceso_admin(self, _evento: ft.Event) -> None:
        if not self.exigir_roles("administrador"):
            return
        self.mostrar_formulario_producto()

    def mostrar_ver_stock(self, _evento: ft.Event | None = None) -> None:
        mostrar_dialogo_ver_stock(self)

    def mostrar_gestion_productos(self, _evento: ft.Event | None = None) -> None:
        mostrar_dialogo_gestion_productos(self)

    def mostrar_historial_movimientos_stock(self, codigo_inicial: str = "") -> None:
        mostrar_dialogo_historial_movimientos_stock(self, codigo_inicial)

    def mostrar_formulario_producto(
        self, al_guardar: Callable[[], None] | None = None
    ) -> None:
        mostrar_dialogo_formulario_producto(self, al_guardar)

    def imprimir_rotulos_termicos_pedido(self, pedido: Any) -> None:
        imprimir_rotulos_termicos_pedido_ui(self, pedido)

    def imprimir_rotulos_pedido(self, pedido: Any, llenar_hoja: bool = False) -> None:
        imprimir_rotulos_pedido_ui(self, pedido, llenar_hoja)

    def imprimir_rotulos_lote(self, pedidos: list[Any], llenar_hoja: bool = False) -> None:
        imprimir_rotulos_lote_ui(self, pedidos, llenar_hoja)

    def confirmar_anulacion_pedido(self, pedido: Any, al_final: Callable[[], None] | None = None) -> None:
        mostrar_dialogo_confirmar_anulacion_pedido(self, pedido, al_final)

    def mostrar_dialogo_editar_pedido(self, pedido: Any, al_final: Callable[[], None] | None = None) -> None:
        mostrar_dialogo_editar_pedido(self, pedido, al_final)

    def confirmar_desarmar_pedido(self, pedido: Any, al_final: Callable[[], None] | None = None) -> None:
        mostrar_dialogo_confirmar_desarmar_pedido(self, pedido, al_final)

    def mostrar_dialogo_backup(self, _e: ft.Event | None = None) -> None:
        mostrar_dialogo_backup(self)

    def mostrar_dialogo_archivo_historico(self, _e: ft.Event | None = None) -> None:
        mostrar_dialogo_archivo_historico(self, _e)

    def mostrar_configuracion_telegram(self, _e: ft.Event | None = None) -> None:
        mostrar_dialogo_configuracion_telegram(self, _e)

    def mostrar_sincronizacion_mercadolibre(self, _e: ft.Event | None = None) -> None:
        from ..dialogs.dlg_mercadolibre import mostrar_dialogo_mercadolibre
        mostrar_dialogo_mercadolibre(self, _e)

    def mostrar_dialogo_anomalias(self, _e: ft.Event | None = None) -> None:
        from ..dialogs.dlg_anomalias import mostrar_dialogo_anomalias
        mostrar_dialogo_anomalias(self, _e)

    def mostrar_dialogo_heatmap(self, _e: ft.Event | None = None) -> None:
        from ..dialogs.dlg_heatmap import mostrar_dialogo_heatmap
        mostrar_dialogo_heatmap(self, _e)

    def sincronizar_catalogo_excel(self, _e: ft.Event | None = None) -> None:
        """Abre la consola modal para la sincronización con Productos.xlsx."""
        from ..dialogs.dlg_sincronizar_excel import mostrar_dialogo_sincronizar_excel
        mostrar_dialogo_sincronizar_excel(self)

    def mostrar_detalle_quiebre(self, criticos: list | None = None) -> None:
        """Abre el diálogo modal adaptativo de detalle de productos en quiebre."""
        from ..dialogs.dlg_quiebre import mostrar_detalle_quiebre
        mostrar_detalle_quiebre(self, criticos)

    def mostrar_dashboard_metricas(self, _e: ft.Event | None = None) -> None:
        mostrar_dashboard_metricas(self, _e)

    def mostrar_registro_auditoria(self, _e: ft.Event | None = None) -> None:
        mostrar_registro_auditoria(self, _e)

    def mostrar_estadisticas(self, _evento: ft.Event | None = None) -> None:
        mostrar_estadisticas(self, _evento)

    def generar_pedido_fabrica(self, _evento: ft.Event | None = None) -> None:
        generar_pedido_fabrica(self, _evento)

    def mostrar_ingreso_fabrica(self, _evento: ft.Event | None = None) -> None:
        self.cerrar_drawer_si_movil()
        self._asegurar_file_picker()
        mostrar_ingreso_fabrica(self, _evento)

    def mostrar_planificar_ingreso_fabrica(self, _evento: ft.Event | None = None) -> None:
        self.cerrar_drawer_si_movil()
        self._asegurar_file_picker()
        mostrar_planificar_ingreso_fabrica(self, _evento)

    def mostrar_control_ingreso_fabrica(self, _evento: ft.Event | None = None) -> None:
        self.cerrar_drawer_si_movil()
        mostrar_control_ingreso_fabrica(self, _evento)

    def mostrar_descuento_mercado_full(self, _evento: ft.Event | None = None) -> None:
        self.cerrar_drawer_si_movil()
        self._asegurar_file_picker()
        mostrar_descuento_mercado_full(self, _evento)

    def mostrar_planificar_full(self, _evento: ft.Event | None = None) -> None:
        self.cerrar_drawer_si_movil()
        self._asegurar_file_picker()
        mostrar_planificar_full(self, _evento)

    def mostrar_picking_guiado_full(self, _evento: ft.Event | None = None) -> None:
        self.cerrar_drawer_si_movil()
        mostrar_picking_guiado_full(self, _evento)

    def mostrar_descuento_mercado_libre(self, _evento: ft.Event | None = None) -> None:
        self.cerrar_drawer_si_movil()
        self._asegurar_file_picker()
        mostrar_descuento_mercado_libre(self, _evento)

    def mostrar_notificaciones_admin(self, _evento: ft.Event | None = None) -> None:
        mostrar_notificaciones_admin(self, _evento)

    def mostrar_stock_fisico_operario(self, _evento: ft.Event | None = None) -> None:
        self.cerrar_drawer_si_movil()
        self._asegurar_file_picker()
        mostrar_stock_fisico_operario(self, _evento)

    def mostrar_comparativa_stock_fisico_admin(self, _evento: ft.Event | None = None) -> None:
        mostrar_comparativa_stock_fisico_admin(self, _evento)

    def mostrar_dialogo_ingreso_rapido(self, _evento: ft.Event | None = None) -> None:
        self.cerrar_drawer_si_movil()
        mostrar_dialogo_ingreso_rapido(self, _evento)

    def mostrar_dialogo_salida_rapida(self, _evento: ft.Event | None = None) -> None:
        self.cerrar_drawer_si_movil()
        mostrar_dialogo_salida_rapida(self, _evento)

    def mostrar_dialogo_inventario_vivo(self, _evento: ft.Event | None = None) -> None:
        mostrar_dialogo_inventario_vivo(self, _evento)

    def mostrar_gestion_ambientes(self, _evento: ft.Event | None = None) -> None:
        self.cerrar_drawer_si_movil()
        mostrar_gestion_ambientes(self, _evento)
