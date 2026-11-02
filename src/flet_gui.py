"""Prototipo de escritorio en Flet para el agente de control de stock."""

import asyncio
import contextlib
import io
import json
import logging
import os
import re
import shutil
import socket
import subprocess
import sys
import traceback
import urllib.parse
import weakref
import webbrowser
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable

import flet as ft
import openpyxl

from .alertas_programadas import enviar_resumen_ahora, iniciar_planificador
from .factory_parser import parsear_archivo_fabrica
from .logger_config import configurar_logging
from .mercado_full_parser import parsear_archivo_mercado_full
from .mercado_libre_parser import parsear_pedido_mercado_libre
from .physical_stock_parser import parsear_excel_stock_fisico
from .internal_chat import (
    detectar_intencion,
    extraer_termino_busqueda,
    formatear_diagnostico_archivos,
    formatear_respuesta_criticos,
    formatear_respuesta_stock,
    formatear_ultimo_informe,
    obtener_chips_configuracion,
    obtener_comandos_ayuda,
    obtener_mensaje_bienvenida,
    obtener_pie_ayuda,
)
from .menu import MenuAgente
from .agent import AgenteRemitosStock
from .backup_manager import (
    crear_backup_sistema,
    guardar_config_backup,
    listar_backups_disponibles,
    obtener_config_backup,
    restaurar_backup_sistema,
)
from .canjes_parser import parsear_canje_excel
from .consolidator import ItemConsolidado
from .dispatch_manifest import generar_hoja_ruta_pdf
from .email_sender import (
    despachar_correo,
    guardar_config_email,
    obtener_config_email,
    probar_conexion_smtp,
)
from .label_generator import generar_etiquetas_bultos_pdf, generar_etiquetas_lote_pedidos_pdf, generar_etiquetas_termicas_pdf
from .orders_store import (
    CierreJornada,
    ESTADOS_DESPACHO,
    LOGISTICA_OPCIONES,
    MensajeChat,
    OrderStore,
    Pedido,
    RegistroAuditoria,
    calcular_hash_archivo,
)
from .remito_parser import ItemRemito, ResultadoRemito, normalizar_codigo, parsear_remito
from .paths import application_root
from .product_store import ProductStore
from .ssl_manager import asegurar_certificado_ssl
from .stock_manager import StockManager
from .user_store import USER_ROLES, User, UserRole, UserStore, UserStoreError
from .ui.theme import (
    ROJO,
    FONDO,
    SUPERFICIE,
    TEXTO,
    SECUNDARIO,
    BORDE,
)
from .ui.components import (
    construir_sidebar_controls,
    crear_ventana_chat_flotante,
    procesar_mensaje_chat_agente,
    construir_encabezado,
    construir_panel_metricas,
    construir_panel_informes_actividad,
)
from .ui.dialogs import (
    compartir_correo,
    compartir_whatsapp,
    enviar_correo_cierre,
    generar_pedido_fabrica,
    mostrar_cambiar_mi_clave,
    mostrar_cambio_clave_obligatorio,
    mostrar_comparativa_stock_fisico_admin,
    mostrar_configuracion_inicial,
    mostrar_dashboard_metricas,
    mostrar_descuento_mercado_full,
    mostrar_descuento_mercado_libre,
    mostrar_dialogo_backup,
    mostrar_dialogo_cierre_jornada,
    mostrar_dialogo_cierres_operarios,
    mostrar_dialogo_compartir_cierre,
    mostrar_dialogo_configuracion_smtp,
    mostrar_dialogo_confirmar_anulacion_pedido,
    mostrar_dialogo_confirmar_desarmar_pedido,
    mostrar_dialogo_crear_pedido,
    mostrar_dialogo_editar_pedido,
    mostrar_dialogo_enviar_correo,
    mostrar_dialogo_escaner_qr_despacho,
    mostrar_dialogo_formulario_producto,
    mostrar_dialogo_gestion_clientes,
    mostrar_dialogo_gestion_productos,
    mostrar_dialogo_gestion_usuarios,
    mostrar_dialogo_historial_movimientos_stock,
    mostrar_estadisticas,
    mostrar_historial_pedidos,
    mostrar_imprimir_descuentos,
    mostrar_ingreso_fabrica,
    mostrar_inicio_sesion,
    mostrar_mi_perfil,
    mostrar_notificaciones_admin,
    mostrar_registro_auditoria,
    mostrar_stock_fisico_operario,
    mostrar_dialogo_inventario_vivo,
    mostrar_command_palette,
    actualizar_alerta_quiebre,
    mostrar_detalle_quiebre,
    confirmar_restaurar,
    restaurar_documentos,
)
from .ui.dialogs.dlg_archivo_historico import mostrar_dialogo_archivo_historico
from .ui.dialogs.dlg_telegram import mostrar_dialogo_configuracion_telegram
from .server import (
    iniciar_servidor_web,
    _RegistroConexionesMiddleware,
    _puerto_local_activo,
    obtener_directorio_assets,
    obtener_ip_local,
    obtener_ip_tailscale,
)

logger = configurar_logging()

def _obtener_inactividad_max_minutos() -> int:
    val = os.environ.get("STOCKAGENT_INACTIVIDAD_MINUTOS", "720")
    try:
        return int(val)
    except ValueError:
        return 720

# Tiempo de inactividad antes de cerrar sesion (por defecto 720 min = 12 horas; 0 desactiva el cierre)
INACTIVIDAD_MAX_MINUTOS = _obtener_inactividad_max_minutos()


# Constantes de tema importadas desde .ui.theme (ROJO, FONDO, SUPERFICIE, TEXTO, SECUNDARIO)
PUERTO_WEB_DEFAULT = 8550
SESIONES_ACTIVAS: weakref.WeakSet["InterfazFlet"] = weakref.WeakSet()
PROCESAMIENTO_GLOBAL_ACTIVO: bool = False





def obtener_correo_cierre_guardado() -> str:
    """Recupera los destinatarios guardados para el cierre de jornada."""
    cfg = application_root() / "data" / "config_notificaciones.json"
    if cfg.exists():
        try:
            with open(cfg, "r", encoding="utf-8") as f:
                data = json.load(f)
                return str(data.get("correo_cierre", "") or "")
        except Exception:
            pass
    return ""


def guardar_correo_cierre(correo: str) -> None:
    """Guarda las direcciones de correo destinatarias del cierre."""
    cfg = application_root() / "data" / "config_notificaciones.json"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    try:
        data = {}
        if cfg.exists():
            with open(cfg, "r", encoding="utf-8") as f:
                data = json.load(f)
        data["correo_cierre"] = correo.strip()
        with open(cfg, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


class InterfazFlet:
    def __init__(self, page: ft.Page) -> None:
        self.page = page
        SESIONES_ACTIVAS.add(self)
        self.user_store = UserStore(
            application_root() / "data" / "usuarios.sqlite3"
        )
        self.order_store = OrderStore(
            application_root() / "data" / "pedidos.sqlite3"
        )
        self.product_store = ProductStore(
            application_root() / "data" / "productos.sqlite3"
        )
        (application_root() / "data" / "pedidos_archivos").mkdir(parents=True, exist_ok=True)
        self.usuario_actual: User | None = None
        self.modo_oscuro = True
        self.fondo = ft.Colors.BLACK
        self.superficie = ft.Colors.BLUE_GREY_900
        self.texto = ft.Colors.WHITE
        self.secundario = ft.Colors.BLUE_GREY_300
        self.borde = ft.Colors.BLUE_GREY_700
        self.fondo_acento = ft.Colors.RED_700
        self.menu = MenuAgente()
        self.ocupado = False
        self.informes: list[Path] = []
        self.informe_seleccionado: Path | None = None
        self.seleccion_fecha_restauracion: ft.Dropdown | None = None
        self.controles_tarea: list[ft.Button] = []
        self.mayoristas = ft.Checkbox(label="Mayoristas · PDF", value=True)
        self.canjes = ft.Checkbox(label="Canjes · Excel", value=True)
        self.mercado_libre = ft.Checkbox(label="Mercado Libre · DOCX", value=True)
        self.estado_tarea = ft.Text("Listo", color=self.secundario, size=12)
        self.lista_informes = ft.ListView(expand=True, spacing=4)
        self.actividad = ft.ListView(expand=True, spacing=6, auto_scroll=True)
        self.header_pedidos_fecha = ft.Text("Fecha de hoy", size=13, weight=ft.FontWeight.BOLD, color=self.texto)
        self.header_pedidos_subtitulo = ft.Text("0 pedidos preparados", size=11, color=self.secundario)
        self.header_pedidos_bultos = ft.Text("0 bultos", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE)
        self.lista_pedidos_preparados = ft.ListView(expand=True, spacing=6)
        self.conversacion = ft.ListView(expand=True, spacing=8, auto_scroll=True)
        self.entrada_chat = ft.TextField(
            hint_text="Escribe una consulta o /ayuda",
            expand=True,
            min_lines=1,
            max_lines=3,
            on_submit=self.enviar_chat,
        )
        self.modo_chat_activo: str = "bot"
        self.conversacion_equipo = ft.ListView(expand=True, spacing=8, auto_scroll=True)
        self.entrada_chat_equipo = ft.TextField(
            hint_text="Escribe un mensaje para el equipo...",
            expand=True,
            dense=True,
            on_submit=self.enviar_mensaje_equipo,
        )
        self.selector_destinatario_equipo = ft.Dropdown(
            label="Destinatario",
            options=[ft.dropdown.Option("Todos", "📢 Todos (Canal General)")],
            value="Todos",
            dense=True,
            expand=True,
        )
        self.texto_badge_chat = ft.Text("", size=10, color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD)
        self.badge_chat_container = ft.Container(
            content=self.texto_badge_chat,
            bgcolor=ft.Colors.RED_600,
            border_radius=10,
            padding=ft.Padding.symmetric(horizontal=5, vertical=1),
            visible=False,
        )
        self.texto_badge_tab = ft.Text("", size=10, color=ft.Colors.RED_400, weight=ft.FontWeight.BOLD)
        self.contadores: dict[str, ft.Text] = {}
        self.pendientes_texto = ft.Text("", color=self.secundario, size=12)
        self.banner_alerta_quiebre = ft.Container(visible=False)
        self.contenedor_notificaciones = ft.Container()
        self.file_picker = ft.FilePicker()
        self.chat_visible = False
        self.ventana_chat_flotante: ft.Container | None = None
        self.boton_chat_flotante: ft.FloatingActionButton | None = None
        self.ultima_actividad: datetime = datetime.now()
        self._asegurar_file_picker()
        self._configurar_ventana()
        if self.user_store.has_users:
            self.mostrar_inicio_sesion()
        else:
            self.mostrar_configuracion_inicial()

    def _asegurar_file_picker(self) -> None:
        """Asegura que FilePicker esté registrado como servicio (Flet 1.0) sin corromper el overlay visual."""
        if hasattr(self.page, "services") and self.page.services is not None:
            if self.file_picker not in self.page.services:
                self.page.services.append(self.file_picker)
        elif hasattr(self.page, "overlay"):
            if self.page.overlay is None:
                self.page.overlay = []
            if self.file_picker not in self.page.overlay:
                self.page.overlay.append(self.file_picker)
        reg = getattr(self.page, "_services", None)
        if type(reg).__name__ == "ServiceRegistry" and hasattr(reg, "_services"):
            if self.file_picker not in reg._services:
                try:
                    reg.register_service(self.file_picker)
                except Exception:
                    pass

    def alternar_tema(self, _evento: ft.Event | None = None) -> None:
        self.modo_oscuro = not self.modo_oscuro
        if self.modo_oscuro:
            self.fondo = ft.Colors.BLACK
            self.superficie = ft.Colors.BLUE_GREY_900
            self.texto = ft.Colors.WHITE
            self.secundario = ft.Colors.BLUE_GREY_300
            self.borde = ft.Colors.BLUE_GREY_700
            self.fondo_acento = ft.Colors.RED_700
        else:
            self.fondo = ft.Colors.GREY_100
            self.superficie = ft.Colors.WHITE
            self.texto = ft.Colors.BLUE_GREY_900
            self.secundario = ft.Colors.BLUE_GREY_600
            self.borde = ft.Colors.GREY_300
            self.fondo_acento = ft.Colors.RED_50
        self.construir()

    @property
    def es_pantalla_movil(self) -> bool:
        """Determina si la pantalla actual corresponde a un dispositivo o viewport móvil."""
        ua = str(getattr(self.page, "client_user_agent", "") or "").lower()
        if any(tok in ua for tok in ("android", "iphone", "ipad", "ipod", "mobile", "; wv")):
            return True
        plat = str(getattr(self.page, "platform", "") or "").lower()
        if any(tok in plat for tok in ("android", "ios")):
            return True
        w = getattr(self.page, "width", None)
        if isinstance(w, (int, float)) and w > 0:
            return bool(w < 768)
        return False

    def ancho_adaptable(self, deseado: int, margen: int = 24) -> int:
        """Calcula el ancho óptimo respetando el viewport móvil si está disponible."""
        w = getattr(self.page, "width", None)
        if self.es_pantalla_movil:
            if isinstance(w, (int, float)) and 0 < w < 768:
                return min(deseado, max(260, int(w - margen)))
            return min(deseado, max(260, 360 - margen))
        if isinstance(w, (int, float)) and w > 0:
            return min(deseado, max(280, int(w - margen)))
        return deseado

    def alto_adaptable(self, deseado: int, margen: int = 60) -> int:
        """Calcula el alto óptimo respetando el viewport móvil si está disponible."""
        h = getattr(self.page, "height", None)
        if self.es_pantalla_movil:
            if isinstance(h, (int, float)) and 0 < h < 1024:
                return min(deseado, max(300, int(h - margen)))
            return min(deseado, 560)
        if isinstance(h, (int, float)) and h > 0:
            return min(deseado, max(300, int(h - margen)))
        return deseado

    def cerrar_drawer_si_movil(self) -> None:
        """Cierra el NavigationDrawer en pantallas móviles al abrir modales o navegar."""
        if self.es_pantalla_movil and hasattr(self.page, "close_drawer"):
            try:
                res = self.page.close_drawer()
                if asyncio.iscoroutine(res):
                    async def _cerrar_seguro(coro: Any) -> None:
                        try:
                            await coro
                        except Exception:
                            pass

                    asyncio.create_task(_cerrar_seguro(res))
            except Exception:
                pass

    def _asegurar_drawer_movil(self) -> None:
        """Garantiza que el NavigationDrawer esté inicializado cuando se solicita en móvil."""
        if hasattr(self.page, "drawer") and getattr(self.page, "drawer", None) is None and self.usuario_actual is not None:
            self.page.drawer = ft.NavigationDrawer(
                bgcolor=self.superficie,
                controls=[
                    ft.Container(
                        padding=16,
                        content=ft.Column(
                            self._sidebar_controls(),
                            spacing=8,
                            tight=True,
                        ),
                    )
                ],
            )
            try:
                self.page.update()
            except Exception:
                pass

    def _mostrar_menu_movil_fallback(self) -> None:
        """Muestra el menú lateral en un diálogo modal si el NavigationDrawer falla por timeout."""
        if self.usuario_actual is None:
            return
        dlg_menu = ft.AlertDialog(
            modal=False,
            bgcolor=self.superficie,
            content=ft.Container(
                width=self.ancho_adaptable(300),
                content=ft.Column(
                    self._sidebar_controls(),
                    spacing=8,
                    tight=True,
                    scroll=ft.ScrollMode.AUTO,
                ),
            ),
            actions=[
                ft.TextButton("Cerrar menú", on_click=lambda _e: self.page.pop_dialog()),
            ],
        )
        try:
            self.page.show_dialog(dlg_menu)
        except Exception:
            pass

    async def _abrir_drawer_click(self, _e: ft.Event | None = None) -> None:
        """Abre el panel de navegación drawer en dispositivos móviles."""
        self._asegurar_drawer_movil()
        if hasattr(self.page, "show_drawer"):
            try:
                res = self.page.show_drawer()
                if asyncio.iscoroutine(res):
                    await res
                return
            except Exception as exc:
                logger.warning("Fallo al abrir NavigationDrawer con show_drawer (%s), usando menú alternativo.", exc)
        if hasattr(self.page, "drawer") and self.page.drawer is not None:
            if hasattr(self.page.drawer, "open"):
                try:
                    self.page.drawer.open = True
                    self.page.update()
                    return
                except Exception:
                    pass
        self._mostrar_menu_movil_fallback()

    def _al_redimensionar(self, _evento: ft.Event | None = None) -> None:
        """Manejador de redimensionamiento de pantalla para alternar layouts desktop/mobile."""
        es_movil = self.es_pantalla_movil
        modo_previo = getattr(self, "_modo_movil_previo", None)
        w_actual = getattr(self.page, "width", None)
        ancho_previo = getattr(self, "_ancho_previo", None)
        cambio_ancho_auth = (
            self.usuario_actual is None
            and isinstance(w_actual, (int, float))
            and w_actual > 0
            and (ancho_previo is None or abs(float(w_actual) - float(ancho_previo)) >= 16)
        )
        if modo_previo is None or modo_previo != es_movil or cambio_ancho_auth:
            self._modo_movil_previo = es_movil
            if isinstance(w_actual, (int, float)) and w_actual > 0:
                self._ancho_previo = float(w_actual)
            if self.usuario_actual is not None:
                self.construir()
            else:
                if not self.user_store.has_users:
                    self.mostrar_configuracion_inicial()
                else:
                    self.mostrar_inicio_sesion()
        else:
            if isinstance(w_actual, (int, float)) and w_actual > 0:
                self._ancho_previo = float(w_actual)
            if self.ventana_chat_flotante is not None and getattr(self.ventana_chat_flotante, "visible", False):
                if es_movil:
                    self.ventana_chat_flotante.width = None
                    self.ventana_chat_flotante.left = 8
                    self.ventana_chat_flotante.right = 8
                else:
                    self.ventana_chat_flotante.width = 420
                    self.ventana_chat_flotante.left = None
                    self.ventana_chat_flotante.right = 24
                self.page.update()

    def _configurar_dialogos_adaptables(self) -> None:
        """Interpreta dimensiones en diálogos para adaptarlos a pantallas pequeñas."""
        if hasattr(self.page, "show_dialog") and not getattr(self.page, "_dialogos_adaptables_configurados", False):
            orig_show = self.page.show_dialog
            def show_dialog_adaptable(dialogo):
                self.cerrar_drawer_si_movil()
                if hasattr(dialogo, "content") and dialogo.content is not None:
                    for c in [dialogo.content, getattr(dialogo.content, "content", None)]:
                        if c is not None:
                            w_orig = getattr(c, "width", None)
                            if isinstance(w_orig, (int, float)):
                                c.width = self.ancho_adaptable(int(w_orig))
                            h_orig = getattr(c, "height", None)
                            if isinstance(h_orig, (int, float)):
                                c.height = self.alto_adaptable(int(h_orig))
                return orig_show(dialogo)
            self.page.show_dialog = show_dialog_adaptable
            self.page._dialogos_adaptables_configurados = True

    def _configurar_ventana(self) -> None:
        self.page.title = "Control de Inventario Depósito Pasteur"
        if hasattr(self.page, "window"):
            self.page.window.icon = str(
                Path(__file__).resolve().parent / "img" / "ultratech.ico"
            )
            self.page.window.maximized = True
            self.page.window.min_width = 360
            self.page.window.min_height = 480
        self.page.padding = 0
        self.page.bgcolor = self.fondo
        self.page.theme_mode = ft.ThemeMode.DARK
        self.page.theme = ft.Theme(color_scheme_seed=ROJO)
        if hasattr(self.page, "on_resize"):
            self.page.on_resize = self._al_redimensionar
        self.page.on_keyboard_event = self._manejar_teclas_globales
        self._configurar_dialogos_adaptables()

    def mostrar_inicio_sesion(self, error: str = "") -> None:
        mostrar_inicio_sesion(self, error=error)

    def mostrar_cambio_clave_obligatorio(self) -> None:
        mostrar_cambio_clave_obligatorio(self)

    def mostrar_cambiar_mi_clave(self, _evento: ft.Event | None = None) -> None:
        mostrar_cambiar_mi_clave(self, _evento)

    def mostrar_mi_perfil(self, _evento: ft.Event | None = None) -> None:
        mostrar_mi_perfil(self, _evento)

    def mostrar_configuracion_inicial(self, error: str = "") -> None:
        mostrar_configuracion_inicial(self, error=error)

    def cerrar_sesion(self, _evento: ft.Event | None = None) -> None:
        if self.usuario_actual is not None:
            try:
                self.order_store.registrar_auditoria(
                    usuario=self.usuario_actual.username,
                    accion="LOGOUT",
                    detalle="Cierre de sesión manual",
                )
            except Exception:
                pass
            logger.info("Sesión cerrada manualmente por %s", self.usuario_actual.username)
        self.usuario_actual = None
        self.controles_tarea.clear()
        self.conversacion.controls.clear()
        self.ventana_chat_flotante = None
        self.mostrar_inicio_sesion()

    def exigir_roles(self, *roles: UserRole) -> bool:
        if self.usuario_actual is None:
            self.mostrar_inicio_sesion()
            return False
        ahora = datetime.now()
        if INACTIVIDAD_MAX_MINUTOS > 0 and (ahora - self.ultima_actividad).total_seconds() > INACTIVIDAD_MAX_MINUTOS * 60:
            nom_exp = self.usuario_actual.username
            self.usuario_actual = None
            tiempo_inactividad = (
                f"{INACTIVIDAD_MAX_MINUTOS // 60} h"
                if INACTIVIDAD_MAX_MINUTOS % 60 == 0
                else f"{INACTIVIDAD_MAX_MINUTOS} min"
            )
            try:
                self.order_store.registrar_auditoria(
                    usuario=nom_exp,
                    accion="LOGOUT_INACTIVIDAD",
                    detalle=f"Sesión cerrada automáticamente tras {tiempo_inactividad} de inactividad",
                )
            except Exception:
                pass
            logger.info("Sesión de '%s' expirada por inactividad (%s)", nom_exp, tiempo_inactividad)
            self.mostrar_inicio_sesion(
                f"Tu sesión se cerró por inactividad ({tiempo_inactividad}). vuelve a ingresar."
            )
            return False
        self.ultima_actividad = ahora

        usuario = None
        if self.user_store:
            try:
                usuario_db = self.user_store.get_user(self.usuario_actual.id)
                if usuario_db and usuario_db.username.lower() == self.usuario_actual.username.lower():
                    usuario = usuario_db
            except Exception:
                pass
        if usuario is None:
            usuario = self.usuario_actual
        if usuario is None or not usuario.active:
            self.usuario_actual = None
            self.mostrar_inicio_sesion("La cuenta ya no está activa. Inicia sesión nuevamente.")
            return False
        self.usuario_actual = usuario
        if usuario.role not in roles:
            self.notificar("Tu rol no tiene permiso para realizar esta acción.")
            return False
        return True

    def _sidebar_controls(self) -> list[ft.Control]:
        return construir_sidebar_controls(self)

    def construir(self) -> None:
        if self.usuario_actual is None:
            self.mostrar_inicio_sesion()
            return
        self.page.bgcolor = self.fondo
        self.page.theme_mode = ft.ThemeMode.DARK if self.modo_oscuro else ft.ThemeMode.LIGHT
        self.controles_tarea.clear()
        self.chat_visible = False
        self.page.floating_action_button = None
        if hasattr(self.page, "overlay") and self.page.overlay is not None:
            self.page.overlay.clear()
        self.page.controls.clear()

        sidebar_items = self._sidebar_controls()
        es_movil = self.es_pantalla_movil
        self._modo_movil_previo = es_movil

        if es_movil and hasattr(self.page, "drawer"):
            self.page.drawer = ft.NavigationDrawer(
                bgcolor=self.superficie,
                controls=[
                    ft.Container(
                        padding=16,
                        content=ft.Column(
                            sidebar_items,
                            spacing=8,
                            tight=True,
                        ),
                    )
                ],
            )
        elif hasattr(self.page, "drawer"):
            self.page.drawer = None

        dashboard_controls: list[ft.Control] = [
            self.encabezado(),
            self.banner_alerta_quiebre,
            self.panel_metricas(),
            self.panel_informes_actividad(),
            self.estado_tarea,
        ]
        dashboard = ft.Column(
            dashboard_controls,
            expand=True,
            spacing=16,
            scroll=ft.ScrollMode.AUTO if es_movil else None,
        )

        if es_movil:
            self.page.add(
                ft.Container(
                    expand=True,
                    padding=ft.Padding(left=10, right=10, top=10, bottom=10),
                    content=dashboard,
                )
            )
        else:
            sidebar = ft.Container(
                width=258,
                bgcolor=self.superficie,
                padding=20,
                content=ft.Column(
                    sidebar_items,
                    spacing=8,
                    scroll=ft.ScrollMode.AUTO,
                ),
            )
            self.page.add(
                ft.Row(
                    [
                        sidebar,
                        ft.Container(
                            expand=True,
                            padding=22,
                            content=dashboard,
                        ),
                    ],
                    expand=True,
                    spacing=0,
                    vertical_alignment=ft.CrossAxisAlignment.STRETCH,
                )
            )

        ventana_chat = self.crear_ventana_chat_flotante()
        if not hasattr(self.page, "overlay") or self.page.overlay is None:
            self.page.overlay = []
        else:
            self.page.overlay.clear()
        self._asegurar_file_picker()
        self.page.overlay.append(ventana_chat)

        self.boton_chat_flotante = ft.FloatingActionButton(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.SMART_TOY, color=ft.Colors.WHITE, size=18 if es_movil else 20),
                    ft.Text("Chat" if es_movil else "Asistente", color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD, size=12 if es_movil else 13),
                    self.badge_chat_container,
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=4 if es_movil else 5,
            ),
            bgcolor=ROJO,
            tooltip="Asistente Virtual y Chat de Equipo",
            on_click=self.alternar_chat_flotante,
            shape=ft.RoundedRectangleBorder(radius=16),
            width=110 if es_movil else 140,
        )
        self.page.floating_action_button = self.boton_chat_flotante
        if not self.conversacion.controls:
            rol_actual = self.usuario_actual.role if self.usuario_actual else "operador"
            nom_actual = self.usuario_actual.username if self.usuario_actual else ""
            self.escribir_chat(
                "Agente",
                obtener_mensaje_bienvenida(rol_actual, nom_actual),
            )
        self.actualizar_estado()
        self.refrescar_usuarios_chat_equipo()
        self.cargar_mensajes_equipo()
        self.actualizar_badge_chat()

    def boton(
        self,
        texto: str,
        icono: ft.IconData,
        accion: Callable,
        ancho: int = 218,
    ) -> ft.Button:
        control = ft.Button(
            content=texto,
            icon=icono,
            bgcolor=ROJO,
            color=ft.Colors.WHITE,
            on_click=accion,
            width=ancho,
        )
        self.controles_tarea.append(control)
        return control

    @staticmethod
    def boton_dialogo(texto: str, accion: Callable) -> ft.Button:
        return ft.Button(
            content=texto,
            bgcolor=ROJO,
            color=ft.Colors.WHITE,
            on_click=accion,
        )

    def _actualizar_icono_notificaciones(self) -> None:
        if self.usuario_actual is None or self.usuario_actual.role != "administrador":
            self.contenedor_notificaciones.content = None
            return
        try:
            sm = StockManager(self.menu.ruta_excel_base)
            raw_no_leidas = sm.contar_notificaciones_no_leidas()
            no_leidas = raw_no_leidas if isinstance(raw_no_leidas, int) else 0
        except Exception:
            no_leidas = 0

        if no_leidas > 0:
            self.contenedor_notificaciones.content = ft.IconButton(
                icon=ft.Icons.NOTIFICATIONS_ACTIVE,
                icon_color=ft.Colors.AMBER_400,
                tooltip=f"{no_leidas} notificación(es) de operarios sin leer",
                on_click=self.mostrar_notificaciones_admin,
                badge=ft.Badge(label=str(no_leidas)),
            )
        else:
            self.contenedor_notificaciones.content = ft.IconButton(
                icon=ft.Icons.NOTIFICATIONS_NONE,
                icon_color=self.secundario,
                tooltip="Notificaciones de operarios",
                on_click=self.mostrar_notificaciones_admin,
            )

    def _enriquecer_mensaje_con_pedidos(self, texto: str) -> str:
        """Si el mensaje menciona #remito o #nota, adjunta automáticamente el resumen del pedido."""
        referencias = re.findall(r"#([A-Za-z0-9_-]{2,40})", texto)
        if not referencias:
            return texto
        resumenes: list[str] = []
        vistos: set[str] = set()
        for ref in referencias:
            ref_norm = ref.upper()
            if ref_norm in vistos:
                continue
            vistos.add(ref_norm)
            res = self.order_store.obtener_pedido_resumen_chat(ref)
            if res:
                resumenes.append(res)
        if resumenes:
            return texto + "\n" + "\n".join(resumenes)
        return texto

    def sincronizar_sesiones(
        self,
        notificar_chat: tuple[str, str, str] | None = None,
    ) -> None:
        """Actualiza en tiempo real otras sesiones abiertas en el navegador y el chat de equipo."""
        for sesion in list(SESIONES_ACTIVAS):
            if sesion is self or sesion.usuario_actual is None:
                continue
            try:
                sesion.actualizar_estado()
                sesion.actualizar_badge_chat()
                if sesion.modo_chat_activo == "equipo":
                    sesion.cargar_mensajes_equipo()
                if notificar_chat is not None:
                    emisor, dest, msg_corto = notificar_chat
                    usr_dest = sesion.usuario_actual.username
                    if dest == "Todos" or dest.lower() == usr_dest.lower():
                        aviso = f"💬 Nuevo mensaje de @{emisor}: {msg_corto[:65]}"
                        snack = ft.SnackBar(
                            content=ft.Text(aviso, color=ft.Colors.WHITE, size=12),
                            bgcolor=ROJO,
                            duration=4000,
                        )
                        sesion.page.show_dialog(snack)
                        sesion.page.update()
            except Exception:
                pass

    def actualizar_badge_chat(self) -> None:
        if not self.usuario_actual:
            return
        try:
            no_leidos = self.order_store.contar_mensajes_no_leidos(self.usuario_actual.username)
            if hasattr(self, "badge_chat_container") and hasattr(self, "texto_badge_chat"):
                if no_leidos > 0:
                    self.texto_badge_chat.value = str(no_leidos)
                    self.badge_chat_container.visible = True
                else:
                    self.badge_chat_container.visible = False
            if hasattr(self, "texto_badge_tab"):
                self.texto_badge_tab.value = f" ({no_leidos})" if no_leidos > 0 else ""
            self.page.update()
        except Exception:
            pass

    def refrescar_usuarios_chat_equipo(self) -> None:
        opciones = [ft.dropdown.Option("Todos", "📢 Todos (Canal General)")]
        try:
            usuarios = self.user_store.list_users(include_master=True)
            for u in usuarios:
                if self.usuario_actual and u.username != self.usuario_actual.username and u.active:
                    etiqueta = (
                        f"👤 {u.nombre} (@{u.username}) ({u.role.capitalize()})"
                        if u.nombre and u.nombre.strip()
                        else f"👤 @{u.username} ({u.role.capitalize()})"
                    )
                    opciones.append(ft.dropdown.Option(u.username, etiqueta))
        except Exception:
            pass
        self.selector_destinatario_equipo.options = opciones
        if not self.selector_destinatario_equipo.value:
            self.selector_destinatario_equipo.value = "Todos"

    def cargar_mensajes_equipo(self) -> None:
        if not self.usuario_actual:
            return
        mensajes = self.order_store.listar_mensajes_chat(usuario=self.usuario_actual.username, limite=60)
        self.conversacion_equipo.controls.clear()

        if not mensajes:
            self.conversacion_equipo.controls.append(
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Icon(ft.Icons.FORUM_OUTLINED, size=36, color=self.secundario),
                            ft.Text(
                                "No hay mensajes en el canal de equipo.\nEscribe para comunicarte con tus compañeros.",
                                size=12,
                                color=self.secundario,
                                text_align=ft.TextAlign.CENTER,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=6,
                    ),
                    padding=25,
                    alignment=ft.Alignment.CENTER,
                )
            )
        else:
            for m in mensajes:
                es_mio = m.emisor == self.usuario_actual.username
                bg_burbuja = (
                    ft.Colors.RED_900 if self.modo_oscuro else ft.Colors.RED_50
                ) if es_mio else (
                    ft.Colors.BLUE_GREY_800 if self.modo_oscuro else ft.Colors.GREY_100
                )
                borde_burbuja = ft.Border.all(
                    1,
                    ft.Colors.RED_300 if es_mio else self.borde,
                )

                if m.destinatario == "Todos":
                    tag_dest = "📢 Para: Todos"
                    color_tag = ft.Colors.BLUE_400 if self.modo_oscuro else ft.Colors.BLUE_700
                else:
                    tag_dest = f"🔒 {'Para ti' if not es_mio else f'Para @{m.destinatario}'}"
                    color_tag = ft.Colors.AMBER_400 if self.modo_oscuro else ft.Colors.AMBER_800

                titulo_emisor = "Tú" if es_mio else f"@{m.emisor}"
                color_emisor = ROJO if es_mio else (ft.Colors.BLUE_300 if self.modo_oscuro else ft.Colors.BLUE_GREY_900)

                burbuja = ft.Container(
                    content=ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Text(titulo_emisor, size=11, weight=ft.FontWeight.BOLD, color=color_emisor),
                                    ft.Text(tag_dest, size=9, weight=ft.FontWeight.W_500, color=color_tag),
                                    ft.Text(m.created_at[11:16], size=9, color=self.secundario),
                                ],
                                spacing=8,
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            ),
                            ft.Text(m.mensaje, size=12, color=self.texto, selectable=True),
                        ],
                        spacing=3,
                        tight=True,
                    ),
                    bgcolor=bg_burbuja,
                    border=borde_burbuja,
                    border_radius=10,
                    padding=ft.Padding.symmetric(horizontal=10, vertical=7),
                    margin=ft.Margin.only(
                        left=35 if es_mio else 0,
                        right=0 if es_mio else 35,
                    ),
                )
                self.conversacion_equipo.controls.append(burbuja)

        try:
            self.page.update()
        except Exception:
            pass

    def enviar_mensaje_equipo(self, _evento: ft.Event | None = None) -> None:
        if not self.exigir_roles(*USER_ROLES):
            return
        texto = (self.entrada_chat_equipo.value or "").strip()
        if not texto:
            return
        self.entrada_chat_equipo.value = ""
        emisor = self.usuario_actual.username if self.usuario_actual else "Operador"
        destinatario = self.selector_destinatario_equipo.value or "Todos"
        texto_enriquecido = self._enriquecer_mensaje_con_pedidos(texto)

        self.order_store.enviar_mensaje_chat(
            emisor=emisor,
            mensaje=texto_enriquecido,
            destinatario=destinatario,
        )
        self.cargar_mensajes_equipo()
        self.sincronizar_sesiones(notificar_chat=(emisor, destinatario, texto))

    def encabezado(self) -> ft.Control:
        return construir_encabezado(self)

    def panel_metricas(self) -> ft.Control:
        return construir_panel_metricas(self)

    def panel_informes_actividad(self) -> ft.Control:
        return construir_panel_informes_actividad(self)

    def alternar_chat_flotante(self, _evento: ft.Event | None = None) -> None:
        self.chat_visible = not self.chat_visible
        if self.ventana_chat_flotante is not None:
            self.ventana_chat_flotante.visible = self.chat_visible
            self.page.update()

    def cerrar_chat_flotante(self, _evento: ft.Event | None = None) -> None:
        self.chat_visible = False
        if self.ventana_chat_flotante is not None:
            self.ventana_chat_flotante.visible = False
            self.page.update()

    def limpiar_chat(self, _evento: ft.Event | None = None) -> None:
        self.conversacion.controls.clear()
        rol_actual = self.usuario_actual.role if self.usuario_actual else "operador"
        nom_actual = self.usuario_actual.username if self.usuario_actual else ""
        self.escribir_chat(
            "Agente",
            f"Conversación reiniciada.\n\n{obtener_mensaje_bienvenida(rol_actual, nom_actual)}",
        )
        self.page.update()

    def ejecutar_comando_rapido(self, comando: str) -> None:
        if comando == "/stock":
            self.entrada_chat.value = "/stock "
            self.entrada_chat.focus()
            self.page.update()
            return
        self.entrada_chat.value = comando
        asyncio.create_task(self.enviar_chat(None))

    def cambiar_pestaña_chat(self, modo: str) -> None:
        self.modo_chat_activo = modo
        if self.ventana_chat_flotante is not None:
            self.ventana_chat_flotante.visible = True
            self.chat_visible = True
        if hasattr(self, "_cambiar_tab_fn") and self._cambiar_tab_fn is not None:
            self._cambiar_tab_fn(modo)
        else:
            self.page.update()

    def crear_ventana_chat_flotante(self) -> ft.Container:
        return crear_ventana_chat_flotante(self)

    def panel_chat(self) -> ft.Control:
        if self.ventana_chat_flotante is None:
            self.crear_ventana_chat_flotante()
        return self.ventana_chat_flotante

    def tarjeta(self, contenido: ft.Control, expand: bool = False) -> ft.Container:
        return ft.Container(
            expand=expand,
            bgcolor=self.superficie,
            border=ft.Border.all(1, self.borde),
            border_radius=14,
            padding=16,
            content=contenido,
        )

    def actualizar_listas(self, _evento: ft.Event | None = None) -> None:
        """Alias de compatibilidad para actualizar el estado e informes."""
        self.actualizar_estado(_evento)

    def actualizar_estado(self, _evento: ft.Event | None = None) -> None:
        if not self.exigir_roles(*USER_ROLES):
            return
        mayoristas, canjes, mercado_libre = self.menu._obtener_pendientes()
        archivados = self.menu._obtener_archivados()
        mtimes_informes: dict[Path, float] = {}
        def _clave_informe(ruta: Path) -> tuple[int, str]:
            try:
                st = ruta.stat()
                mtimes_informes[ruta] = st.st_mtime
                return (st.st_mtime_ns, ruta.name.casefold())
            except OSError:
                return (0, ruta.name.casefold())

        informes = sorted(
            self.menu._obtener_generados(),
            key=_clave_informe,
            reverse=True,
        )
        self.informes = informes
        conteo_jornada = {"pdf": 0, "excel": 0, "docx": 0, "total": 0}
        if hasattr(self, "order_store") and self.order_store:
            try:
                conteo_jornada = self.order_store.contar_pedidos_pendientes_cierre_por_tipo()
            except Exception:
                pass
        if "pdf" in self.contadores:
            self.contadores["pdf"].value = str(conteo_jornada.get("pdf", 0))
        if "canjes" in self.contadores:
            self.contadores["canjes"].value = str(conteo_jornada.get("excel", 0))
        if "ml" in self.contadores:
            self.contadores["ml"].value = str(conteo_jornada.get("docx", 0))
        if "total" in self.contadores:
            self.contadores["total"].value = str(conteo_jornada.get("total", 0))
        if "informes" in self.contadores:
            self.contadores["informes"].value = str(len(informes))

        if self.usuario_actual and self.usuario_actual.role == "administrador":
            try:
                sm = StockManager(self.menu.ruta_excel_base)
                criticos = sm.obtener_analisis_reposicion(solo_criticos=True)
            except Exception:
                criticos = []
            if "quiebres" in self.contadores:
                self.contadores["quiebres"].value = str(len(criticos))
                self.contadores["quiebres"].color = (
                    ft.Colors.RED_400 if len(criticos) > 0 else self.texto
                )
            self.actualizar_alerta_quiebre(criticos)
            self._actualizar_icono_notificaciones()
        else:
            self.banner_alerta_quiebre.visible = False

        if self.usuario_actual and self.usuario_actual.role == "master":
            try:
                todos_usr = self.user_store.list_users()
                activos_usr = sum(1 for u in todos_usr if u.active)
            except Exception:
                todos_usr = []
                activos_usr = 0

            if "usuarios_total" in self.contadores:
                self.contadores["usuarios_total"].value = str(len(todos_usr))
            if "usuarios_activos" in self.contadores:
                self.contadores["usuarios_activos"].value = str(activos_usr)

            eventos_auditoria = []
            if hasattr(self, "order_store") and self.order_store:
                try:
                    eventos_auditoria = self.order_store.listar_auditoria(limit=100)
                except Exception:
                    pass
            if "auditoria_eventos" in self.contadores:
                self.contadores["auditoria_eventos"].value = str(len(eventos_auditoria))

            try:
                from .backup_manager import listar_backups
                bks = listar_backups()
            except Exception:
                bks = []
            if "backups_total" in self.contadores:
                self.contadores["backups_total"].value = str(len(bks))
            if "servidor_seguro" in self.contadores:
                self.contadores["servidor_seguro"].value = "HTTPS" if getattr(self, "https", True) else "HTTP"

            try:
                from .system_telemetry import obtener_telemetria_sistema
                telem = obtener_telemetria_sistema()
            except Exception:
                telem = None

            if telem:
                if "telemetria_disco" in self.contadores:
                    self.contadores["telemetria_disco"].value = f"{telem.disco_libre_gb} GB"
                    self.contadores["telemetria_disco"].color = (
                        ft.Colors.RED_400 if telem.disco_alerta else self.texto
                    )
                if "telemetria_salud" in self.contadores:
                    self.contadores["telemetria_salud"].value = telem.estado_salud
                    if telem.estado_salud == "Óptimo":
                        self.contadores["telemetria_salud"].color = ft.Colors.GREEN_400
                    elif telem.estado_salud == "Atención":
                        self.contadores["telemetria_salud"].color = ft.Colors.AMBER_400
                    else:
                        self.contadores["telemetria_salud"].color = ft.Colors.RED_400

            self.banner_alerta_quiebre.visible = False
            self.pendientes_texto.value = (
                f"Consola de Auditoría y Control de Accesos · Usuarios: {len(todos_usr)} · Cuentas activas: {activos_usr} · Backups: {len(bks)}"
            )
            self.lista_informes.controls.clear()
            if not eventos_auditoria:
                self.lista_informes.controls.append(
                    ft.Text("Todavía no hay eventos de auditoría registrados.", size=12, color=self.secundario)
                )
            else:
                for ev in eventos_auditoria[:15]:
                    accion_ev = getattr(ev, "accion", "")
                    usuario_ev = getattr(ev, "usuario", "")
                    fecha_ev = getattr(ev, "fecha", "")
                    detalle_ev = getattr(ev, "detalle", "")

                    if "LOGIN" in accion_ev or "AUTH" in accion_ev:
                        icono_ev = ft.Icons.LOGIN
                        color_ev = ft.Colors.GREEN_400
                    elif "LOCK" in accion_ev or "BLOQUEO" in accion_ev or "ANULAR" in accion_ev:
                        icono_ev = ft.Icons.LOCK
                        color_ev = ft.Colors.RED_400
                    elif "RESET" in accion_ev or "USER" in accion_ev:
                        icono_ev = ft.Icons.MANAGE_ACCOUNTS
                        color_ev = ft.Colors.BLUE_400
                    elif "BACKUP" in accion_ev:
                        icono_ev = ft.Icons.BACKUP
                        color_ev = ft.Colors.PURPLE_400
                    else:
                        icono_ev = ft.Icons.SECURITY
                        color_ev = ROJO

                    self.lista_informes.controls.append(
                        ft.ListTile(
                            leading=ft.Icon(icono_ev, color=color_ev, size=19),
                            title=ft.Text(f"[{accion_ev}] @{usuario_ev}", size=12, color=self.texto, weight=ft.FontWeight.W_500),
                            subtitle=ft.Text(f"{detalle_ev} · {fecha_ev}", size=10, color=self.secundario),
                        )
                    )
        else:
            total_descontados = conteo_jornada.get("total", 0)
            total_archivados = sum(map(len, archivados))
            self.pendientes_texto.value = (
                f"Jornada en curso: {total_descontados} pedido(s) descontado(s) · Archivados: {total_archivados} · Informes: {len(informes)}"
            )

            # Actualizar tarjeta izquierda: Pedidos preparados en tiempo real (descendiente)
            pedidos_pendientes_turno = self.order_store.listar_pedidos_pendientes_cierre()
            # Orden descendiente (el más reciente primero)
            pedidos_pendientes_turno.sort(key=lambda p: p.id, reverse=True)
            total_bultos_turno = sum(p.bultos for p in pedidos_pendientes_turno)
            fecha_hoy_str = datetime.now().strftime("%A %d/%m/%Y").capitalize()

            self.header_pedidos_fecha.value = fecha_hoy_str
            self.header_pedidos_subtitulo.value = (
                f"{len(pedidos_pendientes_turno)} pedido(s) preparados en el turno actual"
                if pedidos_pendientes_turno
                else "Turno activo · Sin pedidos pendientes"
            )
            self.header_pedidos_bultos.value = f"📦 {total_bultos_turno} bultos preparados"

            self.lista_pedidos_preparados.controls.clear()
            if not pedidos_pendientes_turno:
                self.lista_pedidos_preparados.controls.append(
                    ft.Container(
                        padding=20,
                        alignment=ft.Alignment.CENTER,
                        content=ft.Column(
                            [
                                ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE, size=32, color=ft.Colors.GREEN_400),
                                ft.Text("No hay pedidos pendientes de cierre.", size=12, color=self.secundario),
                                ft.Text("Los pedidos que cargues aparecerán aquí en tiempo real.", size=11, color=self.secundario),
                            ],
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=4,
                        ),
                    )
                )
            else:
                for ped in pedidos_pendientes_turno:
                    hora_c = ped.created_at[11:16] if ped.created_at and len(ped.created_at) >= 16 else ""
                    num_p = f"Pedido #{ped.numero_pedido} · " if getattr(ped, "numero_pedido", "") else ""
                    titulo_card = f"{num_p}Remito: {ped.nota_pedido}"

                    def abrir_modificar_o_ver(p_obj=ped):
                        if self.usuario_actual and self.usuario_actual.role == "operador":
                            self.mostrar_dialogo_editar_pedido(p_obj, al_final=self.actualizar_listas)
                        elif self.usuario_actual and self.usuario_actual.role == "administrador":
                            self.mostrar_detalle_pedido_modal(p_obj)

                    card_pedido = ft.Container(
                        bgcolor=self.superficie,
                        border=ft.Border.all(1, self.borde),
                        border_radius=8,
                        padding=ft.Padding.symmetric(horizontal=10, vertical=8),
                        ink=True,
                        tooltip="Clic para abrir y modificar este pedido" if (self.usuario_actual and self.usuario_actual.role == "operador") else "Clic para ver detalle del pedido",
                        on_click=lambda _e, p_obj=ped: abrir_modificar_o_ver(p_obj),
                        content=ft.Row(
                            [
                                ft.Row(
                                    [
                                        ft.Container(
                                            content=ft.Icon(ft.Icons.INVENTORY_2, size=18, color=ROJO),
                                            bgcolor=ft.Colors.RED_50,
                                            padding=6,
                                            border_radius=6,
                                        ),
                                        ft.Column(
                                            [
                                                ft.Row(
                                                    [
                                                        ft.Text(titulo_card, weight=ft.FontWeight.BOLD, size=12, color=self.texto),
                                                        ft.Container(
                                                            content=ft.Text(f"{ped.bultos} bulto(s)", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                                                            bgcolor=ft.Colors.BLUE_GREY_700,
                                                            padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                                                            border_radius=10,
                                                        ),
                                                    ],
                                                    spacing=6,
                                                ),
                                                ft.Text(f"Cliente: {ped.cliente} · {ped.logistica}", size=11, color=self.secundario),
                                                ft.Text(f"Artículos: {ped.resumen_items or f'{ped.articulos_descontados} un.'}", size=10, color=ft.Colors.GREEN_400),
                                            ],
                                            spacing=2,
                                            expand=True,
                                        ),
                                    ],
                                    spacing=8,
                                    expand=True,
                                ),
                                ft.Column(
                                    [
                                        ft.Text(hora_c, size=10, color=self.secundario, weight=ft.FontWeight.W_500),
                                        *(
                                            [
                                                ft.IconButton(
                                                    icon=ft.Icons.EDIT_OUTLINED,
                                                    icon_size=16,
                                                    tooltip="Modificar pedido",
                                                    icon_color=ft.Colors.BLUE_400,
                                                    on_click=lambda _e, p_obj=ped: self.mostrar_dialogo_editar_pedido(p_obj, al_final=self.actualizar_listas),
                                                )
                                            ]
                                            if (self.usuario_actual and self.usuario_actual.role == "operador")
                                            else []
                                        ),
                                    ],
                                    horizontal_alignment=ft.CrossAxisAlignment.END,
                                    spacing=2,
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                    )
                    self.lista_pedidos_preparados.controls.append(card_pedido)
            self.lista_informes.controls.clear()
            if not informes:
                self.lista_informes.controls.append(
                    ft.Text("Todavía no hay informes.", size=12, color=self.secundario)
                )
            else:
                for ruta in informes[:30]:
                    es_fabrica = ruta.name.startswith("Pedido_Fabrica")
                    es_comparativa = ruta.name.startswith("Comparativa_Stock_Fisico")
                    if es_comparativa:
                        icono = ft.Icons.COMPARE_ARROWS
                        color_icono = ft.Colors.BLUE_400
                        tipo_txt = "Comparativa stock físico"
                    elif es_fabrica:
                        icono = ft.Icons.INVENTORY_2
                        color_icono = ft.Colors.AMBER_400
                        tipo_txt = "Pedido a fábrica"
                    else:
                        icono = ft.Icons.DESCRIPTION
                        color_icono = ROJO
                        tipo_txt = "Informe de descuentos"
                    try:
                        ts = mtimes_informes.get(ruta)
                        if ts is None:
                            ts = ruta.stat().st_mtime
                        mtime = datetime.fromtimestamp(ts)
                        fecha_fmt = mtime.strftime("%d/%m/%Y %H:%M")
                    except Exception:
                        fecha_fmt = ""

                    subtitulo_txt = f"{tipo_txt} · {fecha_fmt}" if fecha_fmt else tipo_txt

                    subtitulo = ft.Text(
                        subtitulo_txt,
                        size=10,
                        color=ft.Colors.BLUE_300
                        if (es_comparativa and self.modo_oscuro)
                        else (
                            ft.Colors.BLUE_700
                            if es_comparativa
                            else (
                                ft.Colors.AMBER_300
                                if (es_fabrica and self.modo_oscuro)
                                else (ft.Colors.AMBER_700 if es_fabrica else self.secundario)
                            )
                        ),
                    )
                    self.lista_informes.controls.append(
                        ft.ListTile(
                            leading=ft.Icon(icono, color=color_icono, size=19),
                            title=ft.Text(ruta.name, size=12, color=self.texto, weight=ft.FontWeight.W_500),
                            subtitle=subtitulo,
                            on_click=lambda _e, archivo=ruta: self.seleccionar_informe(archivo),
                        )
                    )
        self.actualizar_badge_chat()
        if self.page.controls:
            self.page.update()

    def actualizar_alerta_quiebre(self, criticos: list | None = None) -> None:
        actualizar_alerta_quiebre(self, criticos)

    def mostrar_detalle_quiebre(self, criticos: list) -> None:
        mostrar_detalle_quiebre(self, criticos)

    def seleccionar_informe(self, ruta: Path) -> None:
        self.informe_seleccionado = ruta
        tipo = "Pedido a fábrica" if ruta.name.startswith("Pedido_Fabrica") else "Informe"
        self.estado_tarea.value = f"{tipo} seleccionado: {ruta.name}"
        self.page.update()

    def escribir_chat(self, emisor: str, mensaje: str) -> None:
        color = ROJO if emisor == "Tú" else ft.Colors.RED_300
        if emisor == "Tú":
            bgcolor = ft.Colors.RED_900 if self.modo_oscuro else ft.Colors.RED_50
        else:
            bgcolor = ft.Colors.BLUE_GREY_800 if self.modo_oscuro else ft.Colors.GREY_100
        self.conversacion.controls.append(
            ft.Container(
                bgcolor=bgcolor,
                border_radius=10,
                padding=10,
                content=ft.Column(
                    [
                        ft.Text(emisor, size=10, weight=ft.FontWeight.BOLD, color=color),
                        ft.Text(mensaje, size=12, color=self.texto),
                    ],
                    spacing=3,
                ),
            )
        )

    async def enviar_chat(self, _evento: ft.Event | None = None) -> None:
        if not self.exigir_roles(*USER_ROLES):
            return
        mensaje = (self.entrada_chat.value or "").strip()
        if not mensaje:
            return
        self.entrada_chat.value = ""
        self.escribir_chat("Tú", mensaje)
        await procesar_mensaje_chat_agente(self, mensaje)

    def resumen_estado(self) -> str:
        mayoristas, canjes, mercado_libre = self.menu._obtener_pendientes()
        fab = self.menu._obtener_pendientes_fabrica()
        full = getattr(self.menu, "_obtener_pendientes_mercado_full", lambda: [])()
        archivados = self.menu._obtener_archivados()
        return (
            f"Pendientes: {len(mayoristas)} PDF mayoristas, {len(canjes)} Excel "
            f"de canjes, {len(mercado_libre)} DOCX de Mercado Libre, {len(fab)} fábrica "
            f"y {len(full)} Mercado Full. "
            f"Archivados: {sum(map(len, archivados))}. "
            f"Informes disponibles: {len(self.menu._obtener_generados())}."
        )

    def resumen_informes(self) -> str:
        informes = self.menu._obtener_generados()
        if not informes:
            return "Todavía no hay informes generados."
        nombres = [ruta.name for ruta in informes[-10:]]
        return "Informes recientes:\n" + "\n".join(nombres)

    def fuentes_seleccionadas(self) -> tuple[bool, bool, bool]:
        return (
            bool(self.mayoristas.value),
            bool(self.canjes.value),
            bool(self.mercado_libre.value),
        )

    async def simular(self, _evento: ft.Event | None) -> None:
        if not self.exigir_roles("operador"):
            return
        await self.procesar(simulacion=True)

    def procesar_real(self, _evento: ft.Event) -> None:
        if not self.exigir_roles("operador"):
            return
        dialogo = ft.AlertDialog(
            modal=True,
            title=ft.Text("Confirmar procesamiento real"),
            content=ft.Text(
                "Esta operación generará el informe y moverá los documentos "
                "procesados a 'descontados'. No modificará Productos.xlsx. ¿Quieres continuar?"
            ),
            actions=[
                self.boton_dialogo("Cancelar", lambda _e: self.page.pop_dialog()),
                self.boton_dialogo("Confirmar", self.confirmar_procesar_real),
            ],
        )
        self.page.show_dialog(dialogo)

    async def confirmar_procesar_real(self, _evento: ft.Event) -> None:
        if not self.exigir_roles("operador"):
            return
        self.page.pop_dialog()
        await self.procesar(simulacion=False)

    async def procesar(self, simulacion: bool) -> None:
        if not self.exigir_roles("operador"):
            return
        if PROCESAMIENTO_GLOBAL_ACTIVO or self.ocupado:
            self.notificar(
                "Hay una operación de procesamiento de stock en curso desde otra sesión o pestaña. "
                "Por seguridad en los archivos, espera a que finalice."
            )
            return
        fuentes = self.fuentes_seleccionadas()
        if not any(fuentes):
            self.notificar("Selecciona al menos una fuente.")
            return

        usuario_actual_nom = self.usuario_actual.username if self.usuario_actual else "operador"
        await self.ejecutar_tarea(
            "Simulación" if simulacion else "Procesamiento real",
            lambda: self.menu.procesar(
                incluir_mayoristas=fuentes[0],
                incluir_canjes=fuentes[1],
                incluir_mercado_libre=fuentes[2],
                simulacion=simulacion,
                usuario=usuario_actual_nom,
            ),
        )

    async def ejecutar_tarea(
        self, nombre: str, accion: Callable[[], object]
    ) -> bool:
        global PROCESAMIENTO_GLOBAL_ACTIVO
        if PROCESAMIENTO_GLOBAL_ACTIVO or self.ocupado:
            self.notificar(
                "Hay una operación de procesamiento de stock en curso desde otra sesión o pestaña. "
                "Por seguridad en los archivos, espera a que finalice."
            )
            return False

        self.ocupado = True
        PROCESAMIENTO_GLOBAL_ACTIVO = True
        self.estado_tarea.value = f"En curso: {nombre}"
        self.actualizar_estado_botones()
        self.sincronizar_sesiones()
        self.page.update()

        salida = io.StringIO()
        exito = False

        def ejecutar() -> None:
            with contextlib.redirect_stdout(salida), contextlib.redirect_stderr(salida):
                accion()

        try:
            await asyncio.to_thread(ejecutar)
        except Exception as exc:
            detalle = traceback.format_exc()
            logger.error("Error ejecutando tarea '%s': %s\n%s", nombre, exc, detalle)
            self.actividad.controls.append(
                ft.Text(
                    f"[ERROR]\n{detalle}",
                    color=ft.Colors.RED_400 if self.modo_oscuro else ft.Colors.RED_700,
                    size=14,
                )
            )
            self.estado_tarea.value = f"{nombre} terminó con un error."
            self.notificar("La operación falló. Revisa el panel Actividad.")
        else:
            texto = salida.getvalue().strip()
            if texto:
                self.actividad.controls.append(
                    ft.Text(texto, color=self.texto, size=14)
                )
            self.estado_tarea.value = f"{nombre} finalizada."
            exito = True
        finally:
            self.ocupado = False
            PROCESAMIENTO_GLOBAL_ACTIVO = False
            self.actualizar_estado_botones()
            self.actualizar_estado()
            self.sincronizar_sesiones()
        return exito

    def actualizar_estado_botones(self) -> None:
        deshabilitado = self.ocupado or PROCESAMIENTO_GLOBAL_ACTIVO
        for control in self.controles_tarea:
            control.disabled = deshabilitado
        self.page.update()

    def notificar(self, mensaje: str) -> None:
        dialogo = ft.AlertDialog(
            title=ft.Text("Aviso"),
            content=ft.Text(mensaje),
            actions=[
                self.boton_dialogo("Aceptar", lambda _e: self.page.pop_dialog())
            ],
        )
        self.page.show_dialog(dialogo)

    def copiar_al_portapapeles(self, texto: str) -> None:
        """Copia texto al portapapeles del cliente de forma segura."""
        try:
            if self.page:
                cb = ft.Clipboard()
                self.page.overlay.append(cb)
                self.page.update()
                cb.set(str(texto))
        except Exception:
            pass

    def ruta_informe(self) -> Path | None:
        if not self.exigir_roles(*USER_ROLES):
            return None
        if self.informe_seleccionado and self.informe_seleccionado.exists():
            return self.informe_seleccionado
        if self.informes:
            self.informe_seleccionado = self.informes[0]
            return self.informe_seleccionado
        self.notificar("Todavía no hay informes generados.")
        return None

    async def _descargar_archivo_navegador(self, ruta: Path) -> None:
        try:
            self._asegurar_file_picker()
            contenido_bytes = ruta.read_bytes()
            await self.file_picker.save_file(
                dialog_title=f"Guardar {ruta.name}",
                file_name=ruta.name,
                src_bytes=contenido_bytes,
            )
        except Exception as error:
            self.notificar(f"No se pudo descargar el archivo en el navegador:\n{error}")

    async def subir_archivos_desde_pc(
        self,
        carpeta_destino: Path,
        extensiones: list[str],
        titulo: str = "Seleccionar archivo(s) desde esta PC",
        al_terminar: Callable[[list[Path]], None] | None = None,
    ) -> list[Path]:
        try:
            self._asegurar_file_picker()
            ext_limpias: list[str] = []
            for ext in extensiones:
                e = ext.lstrip(".").lower()
                if e not in ext_limpias:
                    ext_limpias.append(e)
            es_movil = self.es_pantalla_movil
            tipo_selector = (
                ft.FilePickerFileType.ANY
                if (es_movil or not ext_limpias)
                else ft.FilePickerFileType.CUSTOM
            )
            ext_selector = None if (es_movil or not ext_limpias) else ext_limpias
            seleccionados = await self.file_picker.pick_files(
                dialog_title=titulo,
                file_type=tipo_selector,
                allowed_extensions=ext_selector,
                allow_multiple=True,
                with_data=True,
                cancel_upload_on_window_blur=False,
            )
        except Exception as error:
            self.notificar(f"Error al abrir el selector de archivos:\n{error}")
            return []

        if not seleccionados:
            return []

        carpeta_destino.mkdir(parents=True, exist_ok=True)
        guardados: list[Path] = []
        rechazados: list[str] = []
        try:
            for item in seleccionados:
                nombre_limpio = Path(item.name).name
                if ext_limpias:
                    ext_item = Path(nombre_limpio).suffix.lstrip(".").lower()
                    if ext_item not in ext_limpias:
                        rechazados.append(nombre_limpio)
                        continue
                destino = carpeta_destino / nombre_limpio
                if item.bytes and len(item.bytes) > 0:
                    destino.write_bytes(item.bytes)
                    guardados.append(destino)
                elif item.path:
                    origen = Path(item.path)
                    if origen.exists():
                        if origen.resolve() != destino.resolve():
                            shutil.copy2(origen, destino)
                        guardados.append(destino)
                elif item.bytes is not None:
                    destino.write_bytes(item.bytes)
                    guardados.append(destino)
        except Exception as error:
            self.notificar(f"Error al guardar el archivo subido:\n{error}")
            return []

        if rechazados and not guardados:
            formatos_str = ", ".join(f".{x}" for x in ext_limpias)
            self.notificar(
                f"El archivo seleccionado ({', '.join(rechazados)}) no tiene un formato permitido ({formatos_str})."
            )
            return []

        if guardados:
            if al_terminar is not None:
                al_terminar(guardados)
            self.actualizar_estado()
            self.sincronizar_sesiones()
        return guardados

    def mostrar_manual_usuario(self, _evento: ft.Event | None = None) -> None:
        """Abre directamente la documentación oficial en PDF correspondiente al rol del usuario activo."""
        if self.usuario_actual is None:
            return

        role = (self.usuario_actual.role or "operador").strip().lower()
        mapa_archivos = {
            "operador": "Manual_Operador.pdf",
            "administrador": "Manual_Administrador.pdf",
            "master": "Manual_Master.pdf",
            "consulta": "Manual_Consulta.pdf",
        }
        nombre_archivo = mapa_archivos.get(role, "Manual_Operador.pdf")
        doc_dir = Path(application_root()) / "Documentacion"
        doc_dir.mkdir(parents=True, exist_ok=True)
        ruta_pdf = doc_dir / nombre_archivo

        # Si el archivo aún no existe en disco, autogenerarlo al vuelo
        if not ruta_pdf.exists():
            try:
                from Documentacion.generar_manual_pdf import generar_todos_los_manuales
                generar_todos_los_manuales(doc_dir)
            except Exception as exc_gen:
                logger.warning("No se pudo autogenerar la documentación: %s", exc_gen)

        if not ruta_pdf.exists():
            self.notificar(f"No se encontró el manual oficial: {nombre_archivo}")
            return

        # En modo Web: abrir inline en nueva pestaña usando launch_url con cache-busting
        if getattr(self.page, "web", False):
            ts = int(ruta_pdf.stat().st_mtime)
            url_doc = f"/documentacion/{nombre_archivo}?v={ts}"
            try:
                self.page.launch_url(url_doc)
            except Exception:
                self.abrir_informe(ruta_especifica=ruta_pdf)
            return

        # En modo escritorio nativo: abrir con el visor PDF predeterminado del sistema
        try:
            os.startfile(ruta_pdf)  # type: ignore[attr-defined]
        except OSError as error:
            self.notificar(f"No se pudo abrir el manual:\n{error}")

    def abrir_informe(self, _evento: ft.Event | None = None, ruta_especifica: Path | None = None) -> None:
        ruta = ruta_especifica or self.ruta_informe()
        if ruta is None:
            return
        if getattr(self.page, "web", False):
            if hasattr(self.page, "run_task"):
                self.page.run_task(self._descargar_archivo_navegador, ruta)
            else:
                try:
                    asyncio.create_task(self._descargar_archivo_navegador(ruta))
                except RuntimeError:
                    pass
            return
        try:
            os.startfile(ruta)  # type: ignore[attr-defined]
        except OSError as error:
            self.notificar(f"No se pudo abrir el archivo:\n{error}")

    def abrir_carpeta_informe(self, ruta: Path) -> None:
        subprocess.Popen(["explorer.exe", f"/select,{ruta}"])

    def compartir_correo(
        self,
        _evento: ft.Event | None = None,
        ruta_especifica: Path | None = None,
    ) -> None:
        compartir_correo(self, _evento, ruta_especifica)

    def compartir_whatsapp(
        self,
        _evento: ft.Event | None = None,
        ruta_especifica: Path | None = None,
    ) -> None:
        compartir_whatsapp(self, _evento, ruta_especifica)

    def enviar_correo_cierre(
        self,
        *args,
        **kwargs,
    ) -> None:
        return enviar_correo_cierre(self, *args, **kwargs)

    def mostrar_dialogo_compartir_cierre(
        self,
        *args,
        **kwargs,
    ) -> None:
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

    def mostrar_configuracion_smtp(self, _evento: ft.Event | None = None) -> None:
        mostrar_dialogo_configuracion_smtp(self)

    def confirmar_restaurar(self, _evento: ft.Event) -> None:
        confirmar_restaurar(self, _evento)

    async def restaurar(self, _evento: ft.Event | None = None) -> None:
        await restaurar_documentos(self, _evento)

    def mostrar_gestion_usuarios(self, _evento: ft.Event | None = None) -> None:
        mostrar_dialogo_gestion_usuarios(self)

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

    def mostrar_escaner_qr_despacho(
        self,
        al_actualizar: Callable[[], None] | None = None,
    ) -> None:
        mostrar_dialogo_escaner_qr_despacho(self, al_actualizar)

    def mostrar_imprimir_descuentos(self, _evento: ft.Event | None = None) -> None:
        mostrar_imprimir_descuentos(self, _evento)

    def mostrar_cierre_jornada(self, _evento: ft.Event | None = None) -> None:
        mostrar_dialogo_cierre_jornada(self)

    def mostrar_historial_cierres_admin(self, _evento: ft.Event | None = None) -> None:
        if not self.exigir_roles("administrador", "master"):
            return
        mostrar_dialogo_cierres_operarios(self)

    def mostrar_acceso_admin(self, _evento: ft.Event) -> None:
        if not self.exigir_roles("administrador"):
            return
        self.mostrar_formulario_producto()

    def mostrar_gestion_productos(self, _evento: ft.Event | None = None) -> None:
        mostrar_dialogo_gestion_productos(self)

    def mostrar_historial_movimientos_stock(self, codigo_inicial: str = "") -> None:
        mostrar_dialogo_historial_movimientos_stock(self, codigo_inicial)

    def mostrar_formulario_producto(
        self, al_guardar: Callable[[], None] | None = None
    ) -> None:
        mostrar_dialogo_formulario_producto(self, al_guardar)

    def _manejar_teclas_globales(self, e: Any) -> None:
        try:
            k = (getattr(e, "key", "") or "").lower()
            ctrl = getattr(e, "ctrl", False) or getattr(e, "meta", False)
            if (k == "k" and ctrl) or k == "f2":
                self.mostrar_command_palette()
        except Exception:
            pass

    def reproducir_sonido(self, tipo: str = "exito") -> None:
        """Emite un feedback sonoro breve (Web Audio API) en el navegador / cliente."""
        try:
            if not self.page:
                return
            if tipo == "exito":
                js = """
                (() => {
                    try {
                        const ctx = new (window.AudioContext || window.webkitAudioContext)();
                        const osc = ctx.createOscillator();
                        const gain = ctx.createGain();
                        osc.connect(gain);
                        gain.connect(ctx.destination);
                        osc.type = 'sine';
                        osc.frequency.setValueAtTime(880, ctx.currentTime);
                        gain.gain.setValueAtTime(0.12, ctx.currentTime);
                        gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.14);
                        osc.start();
                        osc.stop(ctx.currentTime + 0.14);
                    } catch(e) {}
                })()
                """
            else:
                js = """
                (() => {
                    try {
                        const ctx = new (window.AudioContext || window.webkitAudioContext)();
                        const playTone = (freq, delay, dur) => {
                            const osc = ctx.createOscillator();
                            const gain = ctx.createGain();
                            osc.connect(gain);
                            gain.connect(ctx.destination);
                            osc.type = 'triangle';
                            osc.frequency.setValueAtTime(freq, ctx.currentTime + delay);
                            gain.gain.setValueAtTime(0.18, ctx.currentTime + delay);
                            gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + delay + dur);
                            osc.start(ctx.currentTime + delay);
                            osc.stop(ctx.currentTime + delay + dur);
                        };
                        playTone(280, 0, 0.15);
                        playTone(200, 0.17, 0.18);
                    } catch(e) {}
                })()
                """
            if hasattr(self.page, "run_js"):
                self.page.run_js(js)
        except Exception:
            pass

    def mostrar_command_palette(self, _evento: ft.Event | None = None) -> None:
        mostrar_command_palette(self, _evento)

    def imprimir_rotulos_termicos_pedido(self, pedido: Pedido) -> None:
        try:
            ruta_pdf = generar_etiquetas_termicas_pdf(pedido, self.menu.carpeta_descuentos / "Rotulos")
            self.abrir_informe(ruta_especifica=ruta_pdf)
            self.notificar(f"Rótulo térmico para {pedido.bultos} bulto(s) generado con éxito ({ruta_pdf.name}).")
        except Exception as error:
            self.notificar(f"Error generando rótulo térmico: {error}")

    def imprimir_rotulos_pedido(self, pedido: Pedido, llenar_hoja: bool = False) -> None:
        try:
            ruta_pdf = generar_etiquetas_bultos_pdf(pedido, self.menu.carpeta_descuentos, llenar_hoja=llenar_hoja)
            self.abrir_informe(ruta_especifica=ruta_pdf)
            self.notificar(f"Rótulos para {pedido.bultos} bulto(s) generados con éxito ({ruta_pdf.name}).")
        except Exception as error:
            self.notificar(f"Error generando rótulos de bulto:\n{error}")

    def imprimir_rotulos_lote(self, pedidos: list[Pedido], llenar_hoja: bool = False) -> None:
        try:
            pedidos_validos = [p for p in pedidos if getattr(p, "estado", "") != "anulado" and getattr(p, "bultos", 0) > 0]
            if not pedidos_validos:
                self.notificar("No hay pedidos válidos con bultos para generar rótulos.")
                return
            ruta_pdf = generar_etiquetas_lote_pedidos_pdf(pedidos_validos, self.menu.carpeta_descuentos, llenar_hoja=llenar_hoja)
            self.abrir_informe(ruta_especifica=ruta_pdf)
            total_bultos = sum(p.bultos for p in pedidos_validos)
            self.notificar(f"Rótulos para {len(pedidos_validos)} pedido(s) ({total_bultos} bultos) generados en A4 ({ruta_pdf.name}).")
        except Exception as error:
            self.notificar(f"Error generando lote de rótulos:\n{error}")

    def confirmar_anulacion_pedido(self, pedido: Pedido, al_final: Callable[[], None] | None = None) -> None:
        mostrar_dialogo_confirmar_anulacion_pedido(self, pedido, al_final)

    def mostrar_dialogo_editar_pedido(self, pedido: Pedido, al_final: Callable[[], None] | None = None) -> None:
        mostrar_dialogo_editar_pedido(self, pedido, al_final)

    def confirmar_desarmar_pedido(self, pedido: Pedido, al_final: Callable[[], None] | None = None) -> None:
        mostrar_dialogo_confirmar_desarmar_pedido(self, pedido, al_final)

    def mostrar_dialogo_backup(self, _e: ft.Event | None = None) -> None:
        mostrar_dialogo_backup(self)

    def mostrar_dialogo_archivo_historico(self, _e: ft.Event | None = None) -> None:
        mostrar_dialogo_archivo_historico(self, _e)

    def mostrar_configuracion_telegram(self, _e: ft.Event | None = None) -> None:
        mostrar_dialogo_configuracion_telegram(self, _e)

    def mostrar_sincronizacion_mercadolibre(self, _e: ft.Event | None = None) -> None:
        from .ui.dialogs.dlg_mercadolibre import mostrar_dialogo_mercadolibre
        mostrar_dialogo_mercadolibre(self, _e)

    def mostrar_dialogo_anomalias(self, _e: ft.Event | None = None) -> None:
        from .ui.dialogs.dlg_anomalias import mostrar_dialogo_anomalias
        mostrar_dialogo_anomalias(self, _e)

    def mostrar_dialogo_heatmap(self, _e: ft.Event | None = None) -> None:
        from .ui.dialogs.dlg_heatmap import mostrar_dialogo_heatmap
        mostrar_dialogo_heatmap(self, _e)

    def sincronizar_catalogo_excel(self, _e: ft.Event | None = None) -> None:
        """Vuelca de forma atómica y completa el catálogo SQLite hacia Productos.xlsx."""
        if not self.exigir_roles("administrador", "master"):
            return
        try:
            from .stock_manager import StockManager
            sm = StockManager(self.menu.ruta_excel_base)
            total = sm.sincronizar_catalogo_completo_excel()
            self.notificar(f"✅ Se sincronizaron {total} productos en 'Productos.xlsx' con éxito.")
        except Exception as exc:
            self.notificar(f"❌ Error al sincronizar con Excel: {exc}")

    def mostrar_dashboard_metricas(self, _e: ft.Event | None = None) -> None:
        mostrar_dashboard_metricas(self, _e)

    def mostrar_registro_auditoria(self, _e: ft.Event | None = None) -> None:
        mostrar_registro_auditoria(self, _e)

    def mostrar_estadisticas(self, _evento: ft.Event | None = None) -> None:
        mostrar_estadisticas(self, _evento)

    def generar_pedido_fabrica(self, _evento: ft.Event | None = None) -> None:
        generar_pedido_fabrica(self, _evento)

    def mostrar_ingreso_fabrica(self, _evento: ft.Event | None = None) -> None:
        mostrar_ingreso_fabrica(self, _evento)

    def mostrar_descuento_mercado_full(self, _evento: ft.Event | None = None) -> None:
        self.cerrar_drawer_si_movil()
        self._asegurar_file_picker()
        mostrar_descuento_mercado_full(self, _evento)

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

    def mostrar_dialogo_inventario_vivo(self, _evento: ft.Event | None = None) -> None:
        mostrar_dialogo_inventario_vivo(self, _evento)

async def main(page: ft.Page) -> None:
    setattr(page, "_interfaz_flet", InterfazFlet(page))


def iniciar(
    modo_web: bool = True,
    host: str = "0.0.0.0",
    port: int = PUERTO_WEB_DEFAULT,
    https: bool = True,
    ssl_certfile: str | None = None,
    ssl_keyfile: str | None = None,
    ocultar_consola: bool = False,
    abrir_navegador: bool = True,
    con_tray: bool = True,
    **kwargs,
) -> None:
    """Inicia el servidor web ASGI / FastAPI o la aplicación en modo ventana."""
    return iniciar_servidor_web(
        entrypoint_main=main,
        modo_web=modo_web,
        host=host,
        port=port,
        https=https,
        ssl_certfile=ssl_certfile,
        ssl_keyfile=ssl_keyfile,
        ocultar_consola=ocultar_consola,
        abrir_navegador=abrir_navegador,
        con_tray=con_tray,
        **kwargs,
    )
