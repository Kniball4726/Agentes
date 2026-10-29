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
from typing import Callable

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
from .label_generator import generar_etiquetas_bultos_pdf
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


def obtener_directorio_assets() -> str:
    """Devuelve la ruta absoluta al directorio de assets estáticos (favicons, logos)."""
    if getattr(sys, "_MEIPASS", None):
        candidato = Path(sys._MEIPASS) / "assets"
        if candidato.is_dir():
            return str(candidato.resolve())
    candidato = application_root() / "assets"
    if candidato.is_dir():
        return str(candidato.resolve())
    candidato = Path(__file__).resolve().parent.parent / "assets"
    if candidato.is_dir():
        return str(candidato.resolve())
    return str((Path(__file__).resolve().parent / "img").resolve())


def obtener_ip_local() -> str:
    """Devuelve la dirección IP de la máquina en la red local (LAN)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(0.2)
            s.connect(("8.8.8.8", 80))
            return str(s.getsockname()[0])
    except Exception:
        try:
            return str(socket.gethostbyname(socket.gethostname()))
        except Exception:
            return "127.0.0.1"


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
        if hasattr(self.page, "services"):
            if self.file_picker not in self.page.services:
                self.page.services.append(self.file_picker)
        elif hasattr(self.page, "overlay"):
            if self.page.overlay is None:
                self.page.overlay = []
            if self.file_picker not in self.page.overlay:
                self.page.overlay.append(self.file_picker)

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
        """Determina si la pantalla actual corresponde a un viewport móvil (< 768px)."""
        w = getattr(self.page, "width", None)
        return bool(isinstance(w, (int, float)) and w > 0 and w < 768)

    def ancho_adaptable(self, deseado: int, margen: int = 24) -> int:
        """Calcula el ancho óptimo respetando el viewport móvil si está disponible."""
        w = getattr(self.page, "width", None)
        if isinstance(w, (int, float)) and w > 0:
            return min(deseado, max(280, int(w - margen)))
        return deseado

    def alto_adaptable(self, deseado: int, margen: int = 60) -> int:
        """Calcula el alto óptimo respetando el viewport móvil si está disponible."""
        h = getattr(self.page, "height", None)
        if isinstance(h, (int, float)) and h > 0:
            return min(deseado, max(300, int(h - margen)))
        return deseado

    def cerrar_drawer_si_movil(self) -> None:
        """Cierra el NavigationDrawer en pantallas móviles al abrir modales o navegar."""
        if self.es_pantalla_movil and hasattr(self.page, "close_drawer"):
            try:
                res = self.page.close_drawer()
                if asyncio.iscoroutine(res):
                    asyncio.create_task(res)
            except Exception:
                pass

    async def _abrir_drawer_click(self, _e: ft.Event | None = None) -> None:
        """Abre el panel de navegación drawer en dispositivos móviles."""
        if hasattr(self.page, "show_drawer"):
            res = self.page.show_drawer()
            if asyncio.iscoroutine(res):
                await res
        elif hasattr(self.page, "drawer") and self.page.drawer is not None:
            if hasattr(self.page.drawer, "open"):
                self.page.drawer.open = True
                self.page.update()

    def _al_redimensionar(self, _evento: ft.Event | None = None) -> None:
        """Manejador de redimensionamiento de pantalla para alternar layouts desktop/mobile."""
        es_movil = self.es_pantalla_movil
        modo_previo = getattr(self, "_modo_movil_previo", None)
        if modo_previo is None:
            self._modo_movil_previo = es_movil
            return
        if modo_previo != es_movil:
            self._modo_movil_previo = es_movil
            if self.usuario_actual is not None:
                self.construir()
            elif self.usuario_actual is None:
                self.mostrar_inicio_sesion()
        else:
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

        usuario = self.user_store.get_user(self.usuario_actual.id)
        if usuario is None or not usuario.active:
            self.usuario_actual = None
            self.mostrar_inicio_sesion("La cuenta ya no está activa. Inicia sesión nuevamente.")
            return False
        self.usuario_actual = usuario
        if usuario.role == "master":
            return True
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

        if es_movil and hasattr(self.page, "drawer"):
            self.page.drawer = ft.NavigationDrawer(
                bgcolor=self.superficie,
                controls=[
                    ft.Container(
                        padding=16,
                        content=ft.Column(
                            sidebar_items,
                            spacing=8,
                            scroll=ft.ScrollMode.AUTO,
                        ),
                    )
                ],
            )

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

        self._asegurar_file_picker()
        ventana_chat = self.crear_ventana_chat_flotante()
        if not hasattr(self.page, "overlay") or self.page.overlay is None:
            self.page.overlay = []
        else:
            self.page.overlay.clear()
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
        informes = sorted(
            self.menu._obtener_generados(),
            key=lambda ruta: (ruta.stat().st_mtime_ns, ruta.name.casefold()),
            reverse=True,
        )
        self.informes = informes
        conteo_jornada = {"pdf": 0, "excel": 0, "docx": 0, "total": 0}
        if hasattr(self, "order_store") and self.order_store:
            try:
                conteo_jornada = self.order_store.contar_pedidos_pendientes_cierre_por_tipo()
            except Exception:
                pass
        self.contadores["pdf"].value = str(conteo_jornada.get("pdf", 0))
        self.contadores["canjes"].value = str(conteo_jornada.get("excel", 0))
        self.contadores["ml"].value = str(conteo_jornada.get("docx", 0))
        if "total" in self.contadores:
            self.contadores["total"].value = str(conteo_jornada.get("total", 0))
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

        total_descontados = conteo_jornada.get("total", 0)
        total_archivados = sum(map(len, archivados))
        self.pendientes_texto.value = (
            f"Jornada en curso: {total_descontados} pedido(s) descontado(s) · Archivados: {total_archivados} · Informes: {len(informes)}"
        )
        self.lista_informes.controls.clear()
        if not informes:
            self.lista_informes.controls.append(
                ft.Text("Todavía no hay informes.", size=12, color=self.secundario)
            )
        else:
            for ruta in informes:
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
                    mtime = datetime.fromtimestamp(ruta.stat().st_mtime)
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
        if self.usuario_actual is None or self.usuario_actual.role != "administrador":
            self.banner_alerta_quiebre.visible = False
            return

        if criticos is None:
            try:
                sm = StockManager(self.menu.ruta_excel_base)
                criticos = sm.obtener_analisis_reposicion(solo_criticos=True)
            except Exception:
                criticos = []

        if not criticos:
            self.banner_alerta_quiebre.visible = False
            return

        agotados = sum(1 for p in criticos if int(p["stock"]) <= 0)
        quiebres = len(criticos) - agotados

        self.banner_alerta_quiebre.visible = True
        self.banner_alerta_quiebre.bgcolor = (
            ft.Colors.RED_900 if self.modo_oscuro else ft.Colors.RED_50
        )
        self.banner_alerta_quiebre.border = ft.Border.all(
            1.5, ft.Colors.RED_400 if self.modo_oscuro else ft.Colors.RED_700
        )
        self.banner_alerta_quiebre.border_radius = 12
        self.banner_alerta_quiebre.padding = ft.Padding(16, 12, 16, 12)
        self.banner_alerta_quiebre.content = ft.Row(
            [
                ft.Row(
                    [
                        ft.Icon(
                            ft.Icons.WARNING_AMBER_ROUNDED,
                            color=ft.Colors.RED_400 if self.modo_oscuro else ft.Colors.RED_700,
                            size=28,
                        ),
                        ft.Column(
                            [
                                ft.Text(
                                    f"ALERTA DE QUIEBRE DE STOCK ({len(criticos)} producto{'s' if len(criticos) != 1 else ''} en riesgo)",
                                    weight=ft.FontWeight.BOLD,
                                    size=13,
                                    color=ft.Colors.RED_300 if self.modo_oscuro else ft.Colors.RED_800,
                                ),
                                ft.Text(
                                    f"{agotados} sin stock o negativo · {quiebres} en stock mínimo de seguridad",
                                    size=11,
                                    color=self.texto,
                                ),
                            ],
                            spacing=2,
                        ),
                    ],
                    spacing=12,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    expand=True,
                ),
                ft.Row(
                    [
                        ft.Button(
                            "Ver detalle",
                            icon=ft.Icons.VISIBILITY,
                            on_click=lambda _e, items=criticos: self.mostrar_detalle_quiebre(items),
                            bgcolor=ft.Colors.TRANSPARENT,
                            color=ft.Colors.RED_300 if self.modo_oscuro else ft.Colors.RED_800,
                        ),
                        ft.Button(
                            "Generar pedido fábrica",
                            icon=ft.Icons.FILE_DOWNLOAD,
                            on_click=self.generar_pedido_fabrica,
                            bgcolor=ft.Colors.TRANSPARENT,
                            color=ft.Colors.RED_300 if self.modo_oscuro else ft.Colors.RED_800,
                        ),
                        ft.Button(
                            "Cargar pedido fábrica",
                            icon=ft.Icons.INVENTORY_2,
                            on_click=self.mostrar_ingreso_fabrica,
                            bgcolor=ROJO,
                            color=ft.Colors.WHITE,
                        ),
                    ],
                    spacing=6,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

    def mostrar_detalle_quiebre(self, criticos: list) -> None:
        if not self.exigir_roles("administrador"):
            return

        lista = ft.Column(spacing=6, scroll=ft.ScrollMode.AUTO, height=360)
        for p in criticos:
            cod = str(p["code"])
            nom = str(p["name"])
            stk = int(p["stock"])
            s_min = int(p["stock_minimo"])
            pedir = int(p["cantidad_sugerida_pedir"])

            if stk <= 0:
                tag_txt = "AGOTADO"
                tag_color = ft.Colors.RED_400
            else:
                tag_txt = f"QUIEBRE (Mín: {s_min})"
                tag_color = ft.Colors.AMBER_400

            lista.controls.append(
                ft.Container(
                    padding=8,
                    border=ft.Border.all(1, self.borde),
                    border_radius=8,
                    content=ft.Row(
                        [
                            ft.Text(cod, width=70, weight=ft.FontWeight.BOLD, size=12),
                            ft.Text(nom, expand=True, size=12),
                            ft.Text(
                                f"{stk} un.",
                                width=65,
                                color=tag_color,
                                weight=ft.FontWeight.BOLD,
                                size=12,
                            ),
                            ft.Text(
                                tag_txt,
                                width=120,
                                color=tag_color,
                                size=11,
                                weight=ft.FontWeight.BOLD,
                            ),
                            ft.Text(
                                f"Pedir: +{pedir} un.",
                                width=100,
                                color=ft.Colors.BLUE_300 if self.modo_oscuro else ft.Colors.BLUE_700,
                                size=11,
                            ),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                )
            )

        if not criticos:
            lista.controls.append(
                ft.Text("No hay productos en quiebre de stock.", color=self.secundario)
            )

        dialogo = ft.AlertDialog(
            modal=True,
            title=ft.Row(
                [
                    ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, color=ft.Colors.RED_400, size=24),
                    ft.Text(f"Productos en quiebre de stock ({len(criticos)})"),
                ],
                spacing=8,
            ),
            content=ft.Column(
                [
                    ft.Text(
                        "Productos cuyo stock actual es menor o igual al mínimo de seguridad establecido:",
                        size=12,
                        color=self.secundario,
                    ),
                    ft.Divider(height=1),
                    lista,
                ],
                tight=True,
                width=680,
            ),
            actions=[
                self.boton_dialogo("Cerrar", lambda _e: self.page.pop_dialog()),
                self.boton_dialogo(
                    "Generar pedido Excel",
                    lambda _e: (self.page.pop_dialog(), self.generar_pedido_fabrica()),
                ),
                self.boton_dialogo(
                    "Cargar pedido fábrica",
                    lambda _e: (self.page.pop_dialog(), self.mostrar_ingreso_fabrica()),
                ),
            ],
        )
        self.page.show_dialog(dialogo)

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
        intencion = detectar_intencion(mensaje)
        rol = self.usuario_actual.role if self.usuario_actual else "operador"
        nom = self.usuario_actual.username if self.usuario_actual else ""

        # Control de permisos según el rol activo
        if rol == "operador" and intencion in ("simular", "reposicion", "diagnostico"):
            self.escribir_chat(
                "Agente",
                "⚠️ Esta función está reservada para roles de gestión (Administrador / Master).\n"
                "Como Operador puedes consultar /stock, /pedidos, /cierre o /mercadolibre.",
            )
            self.page.update()
            return

        if rol == "consulta" and intencion in ("simular", "cierre", "mercadolibre", "pedidos"):
            self.escribir_chat(
                "Agente",
                "⚠️ El rol Consulta es de solo lectura. Puedes consultar /stock, /criticos o /informes.",
            )
            self.page.update()
            return

        if intencion == "estado":
            respuesta = self.resumen_estado()
        elif intencion == "informes":
            respuesta = self.resumen_informes()
        elif intencion == "saludo":
            respuesta = obtener_mensaje_bienvenida(rol, nom)
        elif intencion == "ayuda":
            respuesta = obtener_comandos_ayuda(rol)
        elif intencion == "pedidos":
            pendientes = self.order_store.listar_pedidos_pendientes_cierre()
            recientes = self.order_store.listar_pedidos(limit=5)
            lineas = [
                "📦 Resumen de Pedidos del Sistema:\n",
                f"• Pendientes de cierre de jornada: {len(pendientes)} pedido(s) acumulados.",
            ]
            if pendientes:
                total_items = sum(p.articulos_descontados for p in pendientes)
                lineas.append(f"• Total unidades en pedidos pendientes: {total_items} ítem(s).")
            if recientes:
                lineas.append("\nÚltimos pedidos registrados:")
                for p in recientes[:4]:
                    cli = p.cliente or "Consumidor Final"
                    nota = f" [NP: {p.nota_pedido}]" if p.nota_pedido else ""
                    est = "🟡 Pendiente" if p.cierre_id is None else "🟢 Cerrado"
                    lineas.append(f"• {est} {p.created_at[:16]} - {cli}{nota} ({p.articulos_descontados} un., {p.estado_despacho})")
            lineas.append("\nPuedes cargar nuevos pedidos desde el menú 'Cargar / Armar Pedido'.")
            respuesta = "\n".join(lineas)
        elif intencion == "cierre":
            pendientes = self.order_store.listar_pedidos_pendientes_cierre()
            ultimos_cierres = self.order_store.listar_cierres(limit=1)
            lineas = ["🖨️ Estado de Cierre de Jornada y Descuentos:\n"]
            lineas.append(f"• Pedidos acumulados para el próximo cierre: {len(pendientes)}")
            if pendientes:
                lineas.append("  (Al realizar el cierre, estos pedidos se consolidarán e imprimirán en el informe diario).")
            else:
                lineas.append("  (No hay pedidos pendientes de cierre en este momento).")
            if ultimos_cierres:
                uc = ultimos_cierres[0]
                lineas.append("\nÚltimo cierre realizado:")
                lineas.append(f"• Fecha: {uc.created_at[:16]}")
                lineas.append(f"• Responsable: {uc.usuario}")
                lineas.append(f"• Pedidos consolidados: {uc.cantidad_pedidos} ({uc.articulos_totales} artículos)")
            lineas.append("\nPara generar un cierre formal, presiona 'Cierre de Jornada' en el menú lateral.")
            respuesta = "\n".join(lineas)
        elif intencion == "mercadolibre":
            respuesta = (
                "🟡 Descuento Mercado Libre (DOCX):\n"
                "• Permite descontar stock cargando las etiquetas o remitos en formato .docx.\n"
                "• Los productos se emparejan automáticamente por descripción contra el catálogo oficial.\n"
                "• Se actualiza el stock en la base SQLite y en el Excel, registrando además el pedido y generando un informe PDF.\n\n"
                "👉 Para utilizarlo, presiona el botón 'Descontar Mercado Libre' en el menú lateral."
            )
        elif intencion == "metricas":
            m = self.order_store.obtener_metricas_dashboard()
            prom = (m["total_bultos"] / m["total_pedidos"]) if m["total_pedidos"] > 0 else 0
            respuesta = (
                f"📊 **Métricas del Depósito:**\n"
                f"• Total Pedidos: {m['total_pedidos']}\n"
                f"• Total Bultos: {m['total_bultos']} (promedio: {prom:.1f} bultos/pedido)\n"
                f"• Pedidos cerrados: {m['pedidos_cerrados']} | Pendientes: {m['pedidos_pendientes']}\n"
                f"• Cierres de jornada: {m['total_cierres']}\n\n"
                f"💡 Presiona 'Métricas y Rendimiento' en el menú de Administración para ver el panel interactivo completo."
            )
        elif intencion == "auditoria":
            logs = self.order_store.listar_auditoria(limit=5)
            lineas = ["🛡️ **Últimos 5 Eventos de Auditoría:**\n"]
            for l in logs:
                lineas.append(f"• [{l.created_at[11:16]}] {l.usuario} ({l.accion}): {l.detalle}")
            lineas.append("\n💡 Accede a 'Registro de Auditoría' en el menú lateral para buscar y filtrar todos los eventos.")
            respuesta = "\n".join(lineas)
        elif intencion == "backup":
            carpeta_bks = application_root() / "data" / "backups"
            bks = sorted(carpeta_bks.glob("Backup_Deposito_*.zip"), key=lambda p: p.stat().st_mtime, reverse=True) if carpeta_bks.exists() else []
            if bks:
                ultimo = bks[0]
                t_str = datetime.fromtimestamp(ultimo.stat().st_mtime).strftime("%d/%m/%Y %H:%M")
                respuesta = (
                    f"💾 **Copia de Seguridad:**\n"
                    f"• Último respaldo: {ultimo.name}\n"
                    f"• Fecha: {t_str}\n"
                    f"• Respaldos en disco: {len(bks)} archivos en data/backups/\n\n"
                    f"💡 Puedes generar un respaldo manual en cualquier momento desde 'Copia de Seguridad' en el menú lateral."
                )
            else:
                respuesta = "💾 Aún no se han generado copias de seguridad. Se generará una automáticamente en el próximo Cierre de Jornada o puedes presionar 'Copia de Seguridad' en el menú lateral."
        elif intencion == "criticos":
            stock_mgr = StockManager(self.menu.ruta_excel_base)
            productos = stock_mgr.listar_productos()
            respuesta = formatear_respuesta_criticos(productos)
        elif intencion == "reposicion" or mensaje.strip().casefold().startswith("/reposicion"):
            stock_mgr = StockManager(self.menu.ruta_excel_base)
            analisis = stock_mgr.obtener_analisis_reposicion(solo_criticos=True)
            if not analisis:
                respuesta = "¡Excelente! No hay productos en quiebre de stock ni bajo su umbral mínimo."
            else:
                lineas = [f"📋 Análisis de reposición ({len(analisis)} productos a pedir a fábrica):\n"]
                for r in analisis[:12]:
                    cod = str(r["code"])
                    nom = str(r["name"])[:30]
                    stk = int(r["stock"])
                    s_min = int(r["stock_minimo"])
                    s_max = int(r["stock_maximo"])
                    pedir = int(r["cantidad_sugerida_pedir"])
                    est = str(r["estado_inventario"])
                    lineas.append(f"• [{est}] [{cod}] {nom} -> Stock: {stk} (Mín: {s_min}, Máx: {s_max}) | Sugerido pedir: +{pedir} un.")
                if len(analisis) > 12:
                    lineas.append(f"\n... y {len(analisis) - 12} productos más.")
                respuesta = "\n".join(lineas)
        elif intencion == "diagnostico":
            mayoristas, canjes, ml = self.menu._obtener_pendientes()
            fab = self.menu._obtener_pendientes_fabrica()
            full = getattr(self.menu, "_obtener_pendientes_mercado_full", lambda: [])()
            respuesta = formatear_diagnostico_archivos(mayoristas, canjes, ml, fab, full)
        elif intencion == "ultimo_informe":
            respuesta = formatear_ultimo_informe(self.informes)
        elif intencion == "buscar_stock":
            termino = extraer_termino_busqueda(mensaje)
            stock_mgr = StockManager(self.menu.ruta_excel_base)
            productos = stock_mgr.listar_productos()
            respuesta = formatear_respuesta_stock(termino, productos)
        elif intencion == "limpiar":
            self.limpiar_chat()
            return
        elif intencion == "simular":
            if self.ocupado:
                respuesta = "Ya hay una operación en curso. Inténtalo de nuevo al finalizar."
            elif not any(self.fuentes_seleccionadas()):
                respuesta = "Selecciona al menos una fuente antes de iniciar la simulación."
            elif self.usuario_actual is None or self.usuario_actual.role not in ("operador", "administrador", "master"):
                respuesta = "No tienes permisos suficientes para iniciar simulaciones."
            else:
                respuesta = "Simulación de solo lectura iniciada."
                await self.simular(None)
        elif intencion == "chat_equipo":
            cuerpo_msg = ""
            destinatario = "Todos"
            texto_limpio = mensaje.strip()

            if texto_limpio.lower().startswith(("/msg", "/mensaje", "/avisar", "msg ", "mensaje ")):
                partes = texto_limpio.split(maxsplit=2)
                if len(partes) > 1:
                    if partes[1].startswith("@") and len(partes) > 2:
                        destinatario = partes[1].lstrip("@")
                        cuerpo_msg = partes[2]
                    elif not partes[1].startswith("@"):
                        cuerpo_msg = texto_limpio.split(maxsplit=1)[1]
            elif texto_limpio.startswith("@"):
                partes = texto_limpio.split(maxsplit=1)
                destinatario = partes[0].lstrip("@")
                if len(partes) > 1:
                    cuerpo_msg = partes[1]

            if cuerpo_msg:
                emisor_nom = self.usuario_actual.username if self.usuario_actual else "Operador"
                cuerpo_enriq = self._enriquecer_mensaje_con_pedidos(cuerpo_msg)
                self.order_store.enviar_mensaje_chat(
                    emisor=emisor_nom,
                    mensaje=cuerpo_enriq,
                    destinatario=destinatario,
                )
                self.sincronizar_sesiones(notificar_chat=(emisor_nom, destinatario, cuerpo_msg))
                self.cargar_mensajes_equipo()
                tag_dest_txt = f"@{destinatario}" if destinatario != "Todos" else "📢 Todos los usuarios"
                respuesta = (
                    f"💬 **Mensaje enviado al equipo:**\n"
                    f"• Para: {tag_dest_txt}\n"
                    f"• Mensaje: \"{cuerpo_msg}\"\n\n"
                    f"💡 Puedes cambiar a la pestaña 'Chat Equipo' para ver la conversación completa."
                )
            else:
                self.cambiar_pestaña_chat("equipo")
                respuesta = (
                    "👥 Cambiado al canal de **Chat de Equipo**.\n"
                    "Aquí puedes escribir directamente a tus compañeros o al canal general."
                )
        else:
            respuesta = (
                f"No reconocí la consulta.\n"
                f"{obtener_pie_ayuda(rol)}"
            )
        self.escribir_chat("Agente", respuesta)
        self.page.update()

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
            seleccionados = await self.file_picker.pick_files(
                dialog_title=titulo,
                file_type=ft.FilePickerFileType.CUSTOM,
                allowed_extensions=ext_limpias,
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
        try:
            for item in seleccionados:
                nombre_limpio = Path(item.name).name
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

        if guardados:
            if al_terminar is not None:
                al_terminar(guardados)
            self.actualizar_estado()
            self.sincronizar_sesiones()
        return guardados

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
        resultado_cierre: dict,
        destinatarios: list[str],
        asunto: str,
        adjuntar_pdf: bool = True,
        adjuntar_excel: bool = True,
        mensaje_adicional: str = "",
    ) -> tuple[bool, str]:
        return enviar_correo_cierre(
            self,
            resultado_cierre,
            destinatarios,
            asunto,
            adjuntar_pdf=adjuntar_pdf,
            adjuntar_excel=adjuntar_excel,
            mensaje_adicional=mensaje_adicional,
        )

    def mostrar_dialogo_compartir_cierre(
        self,
        resultado_cierre: dict,
        _e: ft.Event | None = None,
    ) -> None:
        mostrar_dialogo_compartir_cierre(self, resultado_cierre, _e)

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
        if not self.exigir_roles("administrador"):
            return
        fechas = self.menu.fechas_descuento_disponibles()
        if not fechas:
            self.notificar(
                "No hay documentos archivados asociados a informes de descuento."
            )
            return
        seleccion_fecha = ft.Dropdown(
            label="Fecha de descuento",
            value=fechas[0],
            options=[
                ft.DropdownOption(
                    key=fecha,
                    text=datetime.strptime(fecha, "%Y-%m-%d").strftime("%d/%m/%Y"),
                )
                for fecha in fechas
            ],
            width=250,
        )
        self.seleccion_fecha_restauracion = seleccion_fecha
        dialogo = ft.AlertDialog(
            modal=True,
            title=ft.Text("Restaurar documentos"),
            content=ft.Column(
                [
                    ft.Text(
                        "Selecciona la fecha de descuento de los documentos "
                        "que quieres restaurar. Si ya existe un archivo con el "
                        "mismo nombre en pendientes, será reemplazado."
                    ),
                    seleccion_fecha,
                ],
                tight=True,
                spacing=12,
            ),
            actions=[
                self.boton_dialogo("Cancelar", lambda _e: self.page.pop_dialog()),
                self.boton_dialogo("Restaurar", self.restaurar),
            ],
        )
        self.page.show_dialog(dialogo)

    async def restaurar(self, _evento: ft.Event) -> None:
        if not self.exigir_roles("administrador"):
            return
        if self.seleccion_fecha_restauracion is None:
            self.notificar("No se cargó la selección de fecha.")
            return
        fecha = self.seleccion_fecha_restauracion.value
        if not fecha:
            self.notificar("Selecciona una fecha de descuento.")
            return
        self.page.pop_dialog()
        await self.ejecutar_tarea(
            "Restauración de documentos",
            lambda: self.menu.restaurar_para_pruebas(fecha),
        )

    def mostrar_gestion_usuarios(self, _evento: ft.Event | None = None) -> None:
        mostrar_dialogo_gestion_usuarios(self)

    def mostrar_gestion_clientes(self, _evento: ft.Event | None = None) -> None:
        mostrar_dialogo_gestion_clientes(self)

    def mostrar_crear_pedido(self, _evento: ft.Event | None = None) -> None:
        mostrar_dialogo_crear_pedido(self)

    def mostrar_historial_pedidos(self, _evento: ft.Event | None = None) -> None:
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

    def imprimir_rotulos_pedido(self, pedido: Pedido) -> None:
        try:
            ruta_pdf = generar_etiquetas_bultos_pdf(pedido, self.menu.carpeta_descuentos)
            self.abrir_informe(ruta_especifica=ruta_pdf)
            self.notificar(f"Rótulos para {pedido.bultos} bulto(s) generados con éxito ({ruta_pdf.name}).")
        except Exception as error:
            self.notificar(f"Error generando rótulos de bulto:\n{error}")

    def confirmar_anulacion_pedido(self, pedido: Pedido, al_final: Callable[[], None] | None = None) -> None:
        mostrar_dialogo_confirmar_anulacion_pedido(self, pedido, al_final)

    def mostrar_dialogo_editar_pedido(self, pedido: Pedido, al_final: Callable[[], None] | None = None) -> None:
        mostrar_dialogo_editar_pedido(self, pedido, al_final)

    def confirmar_desarmar_pedido(self, pedido: Pedido, al_final: Callable[[], None] | None = None) -> None:
        mostrar_dialogo_confirmar_desarmar_pedido(self, pedido, al_final)

    def mostrar_dialogo_backup(self, _e: ft.Event | None = None) -> None:
        mostrar_dialogo_backup(self)

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
        mostrar_descuento_mercado_full(self, _evento)

    def mostrar_descuento_mercado_libre(self, _evento: ft.Event | None = None) -> None:
        mostrar_descuento_mercado_libre(self, _evento)

    def mostrar_notificaciones_admin(self, _evento: ft.Event | None = None) -> None:
        mostrar_notificaciones_admin(self, _evento)

    def mostrar_stock_fisico_operario(self, _evento: ft.Event | None = None) -> None:
        mostrar_stock_fisico_operario(self, _evento)

    def mostrar_comparativa_stock_fisico_admin(self, _evento: ft.Event | None = None) -> None:
        mostrar_comparativa_stock_fisico_admin(self, _evento)

async def main(page: ft.Page) -> None:
    setattr(page, "_interfaz_flet", InterfazFlet(page))


def _puerto_local_activo(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.4):
            return True
    except OSError:
        return False


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
    import logging
    import sys
    import webbrowser

    if ocultar_consola and sys.platform == "win32":
        try:
            import ctypes
            hwnd = ctypes.windll.kernel32.GetConsoleWindow()
            if hwnd:
                ctypes.windll.user32.ShowWindow(hwnd, 0)
        except Exception:
            pass

    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")

    configurar_logging()
    try:
        iniciar_planificador()
    except Exception:
        pass

    esquema = "https" if https else "http"
    os.environ["STOCKAGENT_PORT"] = str(port)
    os.environ["STOCKAGENT_SCHEME"] = esquema

    cert_path_final: Path | None = None
    key_path_final: Path | None = None
    if modo_web and https:
        try:
            cert_path_final, key_path_final = asegurar_certificado_ssl(
                Path(ssl_certfile) if ssl_certfile else None,
                Path(ssl_keyfile) if ssl_keyfile else None,
            )
            logger.info("Certificado SSL preparado para HTTPS: %s", cert_path_final)
        except Exception as exc_ssl:
            logger.warning("No se pudo preparar certificado SSL, continuando en HTTP: %s", exc_ssl)
            https = False
            esquema = "http"
            os.environ["STOCKAGENT_SCHEME"] = "http"

    if modo_web:
        # Si ya hay una instancia de StockAgent escuchando en este puerto,
        # abrir directamente el navegador hacia la instancia activa (si abrir_navegador es True).
        if not hasattr(ft.run, "_mock_name") and _puerto_local_activo(port):
            url_activa = f"{esquema}://127.0.0.1:{port}"
            if abrir_navegador:
                print(f"[INFO] Servidor activo detectado en {url_activa}. Abriendo navegador...")
                webbrowser.open(url_activa)
            else:
                print(f"[INFO] Servidor activo detectado en {url_activa}.")
            return

        # Limpiar FLET_SERVER_IP=127.0.0.1 inyectado por el runtime hook de PyInstaller
        os.environ.pop("FLET_SERVER_IP", None)
        # Asegurar nivel de log compatible con uvicorn (evita 'fatal')
        flet_logger = logging.getLogger("flet")
        if flet_logger.getEffectiveLevel() in (logging.CRITICAL, logging.NOTSET):
            flet_logger.setLevel(logging.WARNING)

        # En Windows, 0.0.0.0 escucha en todas las placas de red pero los clientes
        # locales (navegador / Flet View / CLI) deben abrir 127.0.0.1 en lugar de 0.0.0.0
        try:
            import flet.app as _flet_app
            import flet.utils as _flet_utils

            _orig_open = getattr(_flet_app, "_orig_open_in_browser", getattr(_flet_app, "open_in_browser", None))
            if _orig_open:
                setattr(_flet_app, "_orig_open_in_browser", _orig_open)

            _browser_opened = False

            def _open_local_browser(url: str) -> None:
                nonlocal _browser_opened
                if not abrir_navegador:
                    return
                if _browser_opened:
                    return
                _browser_opened = True
                url_local = url.replace("://0.0.0.0:", "://127.0.0.1:")
                if https and url_local.startswith("http://"):
                    url_local = "https://" + url_local[len("http://"):]
                if _orig_open:
                    _orig_open(url_local)
                else:
                    webbrowser.open(url_local)

            _flet_app.open_in_browser = _open_local_browser
            _flet_utils.open_in_browser = _open_local_browser
        except Exception:
            pass

        try:
            import flet_web
            import flet_web.fastapi
            import flet_web.fastapi.serve_fastapi_web_app as _sfa
            import uvicorn
            from starlette.responses import FileResponse

            if https and cert_path_final and key_path_final:
                _orig_uv_init = getattr(uvicorn.Config, "_orig_init", uvicorn.Config.__init__)
                setattr(uvicorn.Config, "_orig_init", _orig_uv_init)

                def _https_uv_init(self_cfg, *u_args, **u_kwargs):
                    u_kwargs.setdefault("ssl_certfile", str(cert_path_final))
                    u_kwargs.setdefault("ssl_keyfile", str(key_path_final))
                    _orig_uv_init(self_cfg, *u_args, **u_kwargs)

                uvicorn.Config.__init__ = _https_uv_init

            _orig_serve = getattr(
                _sfa, "_orig_serve_fastapi_web_app", _sfa.serve_fastapi_web_app
            )
            setattr(_sfa, "_orig_serve_fastapi_web_app", _orig_serve)

            async def _serve_local_url(*args, **kwargs):
                if kwargs.get("url_host") in ("0.0.0.0", "*", "", None):
                    kwargs["url_host"] = "127.0.0.1"
                elif len(args) >= 4 and args[3] in ("0.0.0.0", "*", "", None):
                    args = (*args[:3], "127.0.0.1", *args[4:])

                assets_path = Path(obtener_directorio_assets())
                ico_path = assets_path / "favicon.ico"
                png_path = assets_path / "favicon.png"

                if not hasattr(flet_web.fastapi.FastAPI, "_orig_init"):
                    orig_init = flet_web.fastapi.FastAPI.__init__
                    setattr(flet_web.fastapi.FastAPI, "_orig_init", orig_init)

                    def custom_fastapi_init(self, *a, **kw):
                        orig_init(self, *a, **kw)
                        if ico_path.exists():
                            @self.get("/favicon.ico")
                            async def _serve_favicon_ico():
                                return FileResponse(
                                    str(ico_path),
                                    media_type="image/x-icon",
                                    headers={"Cache-Control": "no-cache, must-revalidate"},
                                )
                        if png_path.exists():
                            @self.get("/favicon.png")
                            async def _serve_favicon_png():
                                return FileResponse(
                                    str(png_path),
                                    media_type="image/png",
                                    headers={"Cache-Control": "no-cache, must-revalidate"},
                                )

                    flet_web.fastapi.FastAPI.__init__ = custom_fastapi_init

                handle = await _orig_serve(*args, **kwargs)
                for _ in range(100):
                    if getattr(handle.server, "started", False) or handle.serve_task.done():
                        break
                    await asyncio.sleep(0.05)
                return handle

            _sfa.serve_fastapi_web_app = _serve_local_url

            import flet_web.fastapi.flet_app as _ffa

            if hasattr(_ffa, "FletApp"):
                if not hasattr(_ffa.FletApp, "_orig_send_loop"):
                    _orig_send_loop = getattr(_ffa.FletApp, "_FletApp__send_loop", None)
                    if _orig_send_loop:
                        setattr(_ffa.FletApp, "_orig_send_loop", _orig_send_loop)

                        async def _clean_send_loop(self):
                            try:
                                await _orig_send_loop(self)
                            except Exception as e:
                                c_name = e.__class__.__name__
                                if any(k in c_name for k in ("Disconnect", "InvalidState", "ConnectionClosed", "ClientDisconnected")):
                                    pass
                                else:
                                    raise

                        setattr(_ffa.FletApp, "_FletApp__send_loop", _clean_send_loop)

                if not hasattr(_ffa.FletApp, "_orig_handle"):
                    _orig_handle = _ffa.FletApp.handle
                    setattr(_ffa.FletApp, "_orig_handle", _orig_handle)

                    async def _clean_handle(self, websocket):
                        try:
                            await _orig_handle(self, websocket)
                        except Exception as e:
                            c_name = e.__class__.__name__
                            if any(k in c_name for k in ("Disconnect", "InvalidState", "ConnectionClosed", "ClientDisconnected")):
                                pass
                            else:
                                raise

                    _ffa.FletApp.handle = _clean_handle
        except Exception:
            pass

        ip_local = obtener_ip_local()
        print("=" * 66)
        print(f"  STOCK AGENT - SERVIDOR WEB MULTI-EQUIPO ({esquema.upper()})")
        print("=" * 66)
        print(f"  -> En esta PC (Principal):   {esquema}://127.0.0.1:{port}")
        print(f"  -> Desde la 2da PC (Red):    {esquema}://{ip_local}:{port}")
        if https and cert_path_final:
            print(f"  -> Certificado SSL activo:   {cert_path_final}")
        print("  Mantén esta aplicación ejecutándose para que ambas máquinas")
        print("  puedan operar sobre el inventario en tiempo real.")
        print("=" * 66)
        assets_dir = obtener_directorio_assets()
        os.environ["FLET_ASSETS_DIR"] = assets_dir

        tray_service = None
        if con_tray:
            try:
                from .tray_icon import iniciar_icono_bandeja

                tray_service = iniciar_icono_bandeja(
                    port=port,
                    host=host,
                    https=https,
                )
            except Exception as exc_tray:
                logger.warning("No se pudo iniciar icono en bandeja del sistema: %s", exc_tray)

        try:
            ft.run(
                main,
                view=ft.AppView.WEB_BROWSER,
                host=host,
                port=port,
                name="",
                assets_dir=assets_dir,
                no_cdn=False,
                web_renderer=ft.WebRenderer.AUTO,
            )
        finally:
            if tray_service:
                tray_service.detener()
    else:
        assets_dir = obtener_directorio_assets()
        ft.run(
            main,
            view=ft.AppView.FLET_APP,
            name="Control de Inventario Depósito Pasteur",
            assets_dir=assets_dir,
            no_cdn=False,
            web_renderer=ft.WebRenderer.AUTO,
        )
