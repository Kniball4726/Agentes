"""Prototipo de escritorio en Flet para el agente de control de stock."""

import weakref
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import flet as ft

from .internal_chat import obtener_mensaje_bienvenida
from .logger_config import configurar_logging
from .menu import MenuAgente
from .orders_store import OrderStore
from .paths import application_root
from .product_store import ProductStore
from .server import (
    _RegistroConexionesMiddleware,
    _puerto_local_activo,
    iniciar_servidor_web,
    obtener_directorio_assets,
    obtener_ip_local,
    obtener_ip_tailscale,
)
from .stock_manager import StockManager
from .user_store import USER_ROLES, User, UserRole, UserStore, UserStoreError
from .ui.app_config import (
    INACTIVIDAD_MAX_MINUTOS,
    PUERTO_WEB_DEFAULT,
    _obtener_inactividad_max_minutos,
    guardar_correo_cierre,
    obtener_correo_cierre_guardado,
)
from .ui.components import (
    actualizar_estado_conexion_ui,
    aplicar_posicion_sidebar_ui,
    construir_encabezado,
    construir_navigation_bar_movil,
    construir_panel_acceso_rapido,
    construir_panel_informes_actividad,
    construir_panel_metricas,
    construir_sidebar_controls,
    iniciar_heartbeat_red_daemon,
    manejar_cambio_navegacion_movil,
    reproducir_sonido_web,
)
from .ui.dashboard_presenter import actualizar_estado_dashboard
from .ui.dialogs import (
    actualizar_alerta_quiebre,
    mostrar_command_palette,
    mostrar_detalle_quiebre,
)
from .ui.mixins import (
    AuthSessionMixin,
    BatchProcessingMixin,
    ChatPanelMixin,
    DialogDispatcherMixin,
    DocumentViewerMixin,
    FileTransferMixin,
    ResponsiveLayoutMixin,
    SessionSyncMixin,
)
from .ui.theme import BORDE, FONDO, ROJO, SECUNDARIO, SUPERFICIE, TEXTO

logger = configurar_logging()

SESIONES_ACTIVAS: weakref.WeakSet["InterfazFlet"] = weakref.WeakSet()
PROCESAMIENTO_GLOBAL_ACTIVO: bool = False


class InterfazFlet(
    ResponsiveLayoutMixin,
    DocumentViewerMixin,
    SessionSyncMixin,
    DialogDispatcherMixin,
    FileTransferMixin,
    ChatPanelMixin,
    BatchProcessingMixin,
    AuthSessionMixin,
):
    """Controlador principal de la interfaz Flet (Desktop y Web)."""

    def __init__(self, page: ft.Page) -> None:
        self.page = page
        SESIONES_ACTIVAS.add(self)
        self.user_store = UserStore(application_root() / "data" / "usuarios.sqlite3")
        self.order_store = OrderStore(application_root() / "data" / "pedidos.sqlite3")
        self.product_store = ProductStore(application_root() / "data" / "productos.sqlite3")
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
        self.btn_cierre_jornada: ft.Button | None = None
        self.botones_cierre_jornada: list[ft.Button] = []
        self.mayoristas = ft.Checkbox(label="Mayoristas · PDF", value=True)
        self.canjes = ft.Checkbox(label="Canjes · Excel", value=True)
        self.mercado_libre = ft.Checkbox(label="Mercado Libre · DOCX", value=True)
        self.estado_tarea = ft.Text("Listo", color=self.secundario, size=12)
        self.progreso_barra = ft.ProgressBar(width=200, value=None, color=ROJO, visible=False)
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
        self.posicion_sidebar = "izquierda"
        self.semaforo_conexion: ft.Container | None = None
        self.semaforo_conexion_movil: ft.Container | None = None
        self._estado_red_actual: str = "online"
        self._heartbeat_activo: bool = True
        self._heartbeat_iniciado: bool = False
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
            self.page.window.icon = str(Path(__file__).resolve().parent / "img" / "ultratech.ico")
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

    def _sidebar_horizontal_controls(self) -> list[ft.Control]:
        from .ui.components.sidebar import construir_sidebar_horizontal_controls
        return construir_sidebar_horizontal_controls(self)

    def cambiar_posicion_sidebar(self, nueva_posicion: str) -> None:
        """Cambia la ubicación del menú (izquierda, derecha, arriba, abajo, oculto) y reconstruye la vista."""
        if nueva_posicion in ("izquierda", "derecha", "arriba", "abajo", "oculto"):
            self.posicion_sidebar = nueva_posicion
            self.construir()
            nombre_pos = {
                "izquierda": "a la izquierda",
                "derecha": "a la derecha",
                "arriba": "en barra superior (horizontal)",
                "abajo": "en barra inferior (horizontal)",
                "oculto": "oculto (pantalla completa · usa F2 para módulos)",
            }.get(nueva_posicion, nueva_posicion)
            try:
                snack = ft.SnackBar(
                    content=ft.Row(
                        [
                            ft.Icon(ft.Icons.DOCK, color=ft.Colors.WHITE, size=16),
                            ft.Text(
                                f"Menú ubicado {nombre_pos}. Atajo rápido: F2 o Ctrl+K.",
                                color=ft.Colors.WHITE,
                                size=12,
                            ),
                        ],
                        spacing=8,
                    ),
                    bgcolor=ROJO,
                    duration=2500,
                )
                self.page.show_dialog(snack)
                self.page.update()
            except Exception:
                pass

    def _aplicar_posicion_sidebar(self, dashboard: ft.Control, sidebar: ft.Control) -> None:
        aplicar_posicion_sidebar_ui(self, dashboard, sidebar)

    def _al_cambiar_navegacion_movil(self, e: Any) -> None:
        """Acceso rápido inferior (Thumb Zone) para operarios con una sola mano en depósito."""
        manejar_cambio_navegacion_movil(self, e)

    def _sidebar_controls(self) -> list[ft.Control]:
        return construir_sidebar_controls(self)

    def construir(self) -> None:
        if self.usuario_actual is None:
            self.mostrar_inicio_sesion()
            return
        if not getattr(self, "_prefs_cargadas_usuario", False) and self.usuario_actual:
            try:
                from .ui.components.sidebar import obtener_preferencias_usuario
                prefs = obtener_preferencias_usuario(self.usuario_actual.username)
                if "posicion_sidebar" in prefs and prefs["posicion_sidebar"] in (
                    "izquierda", "derecha", "arriba", "abajo", "oculto"
                ):
                    self.posicion_sidebar = prefs["posicion_sidebar"]
                if "modo_oscuro" in prefs:
                    deseado_oscuro = bool(prefs["modo_oscuro"])
                    if deseado_oscuro != self.modo_oscuro:
                        self.modo_oscuro = deseado_oscuro
                        self.fondo = FONDO if self.modo_oscuro else ft.Colors.WHITE
                        self.superficie = SUPERFICIE if self.modo_oscuro else ft.Colors.GREY_50
                        self.texto = TEXTO if self.modo_oscuro else ft.Colors.BLACK
                        self.secundario = SECUNDARIO if self.modo_oscuro else ft.Colors.GREY_700
                        self.borde = BORDE if self.modo_oscuro else ft.Colors.GREY_300
                        self.fondo_acento = ft.Colors.GREY_900 if self.modo_oscuro else ft.Colors.GREY_100
                self._prefs_cargadas_usuario = True
            except Exception:
                pass
        self.page.bgcolor = self.fondo
        self.page.theme_mode = ft.ThemeMode.DARK if self.modo_oscuro else ft.ThemeMode.LIGHT
        self.controles_tarea.clear()
        if hasattr(self, "botones_cierre_jornada") and self.botones_cierre_jornada is not None:
            self.botones_cierre_jornada.clear()
        self.btn_cierre_jornada = None
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
                        content=ft.Column(sidebar_items, spacing=8, tight=True),
                    )
                ],
            )
        elif hasattr(self.page, "drawer"):
            self.page.drawer = None

        self.page.navigation_bar = construir_navigation_bar_movil(self) if es_movil else None

        dashboard = ft.Column(
            [
                self.encabezado(),
                self.banner_alerta_quiebre,
                self.panel_metricas(),
                self.panel_acceso_rapido(),
                self.panel_informes_actividad(),
                ft.Row(
                    [self.estado_tarea, self.progreso_barra],
                    spacing=12,
                    alignment=ft.MainAxisAlignment.START,
                ),
            ],
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
                content=ft.Column(sidebar_items, spacing=8, scroll=ft.ScrollMode.AUTO),
            )
            self.page.add(
                ft.Row(
                    [
                        sidebar,
                        ft.Container(expand=True, padding=22, content=dashboard),
                    ],
                    expand=True,
                    spacing=0,
                    vertical_alignment=ft.CrossAxisAlignment.STRETCH,
                )
            )
            self._aplicar_posicion_sidebar(dashboard, sidebar)

        ventana_chat = self.crear_ventana_chat_flotante()
        if not hasattr(self.page, "overlay") or self.page.overlay is None:
            self.page.overlay = []
        else:
            self.page.overlay.clear()
        self._asegurar_file_picker(forzar_recrear=True)
        self.page.overlay.append(ventana_chat)

        self.boton_chat_flotante = ft.FloatingActionButton(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.SMART_TOY, color=ft.Colors.WHITE, size=18 if es_movil else 20),
                    ft.Text(
                        "Chat" if es_movil else "Asistente",
                        color=ft.Colors.WHITE,
                        weight=ft.FontWeight.BOLD,
                        size=12 if es_movil else 13,
                    ),
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
            self.escribir_chat("Agente", obtener_mensaje_bienvenida(rol_actual, nom_actual))
        self.actualizar_estado()
        self.refrescar_usuarios_chat_equipo()
        self._iniciar_heartbeat_red()
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

    def encabezado(self) -> ft.Control:
        return construir_encabezado(self)

    def panel_metricas(self) -> ft.Control:
        return construir_panel_metricas(self)

    def panel_acceso_rapido(self) -> ft.Control:
        return construir_panel_acceso_rapido(self)

    def panel_informes_actividad(self) -> ft.Control:
        return construir_panel_informes_actividad(self)

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
        """Actualiza y sincroniza en tiempo real todos los indicadores y listas del Dashboard."""
        actualizar_estado_dashboard(self, _evento)

    def actualizar_alerta_quiebre(self, criticos: list | None = None) -> None:
        actualizar_alerta_quiebre(self, criticos)

    def mostrar_detalle_quiebre(self, criticos: list) -> None:
        mostrar_detalle_quiebre(self, criticos)

    def seleccionar_informe(self, ruta: Path) -> None:
        self.informe_seleccionado = ruta
        tipo = "Pedido a fábrica" if ruta.name.startswith("Pedido_Fabrica") else "Informe"
        self.estado_tarea.value = f"{tipo} seleccionado: {ruta.name}"
        self.page.update()

    def notificar(self, mensaje: str) -> None:
        dialogo = ft.AlertDialog(
            title=ft.Text("Aviso"),
            content=ft.Text(mensaje),
            actions=[self.boton_dialogo("Aceptar", lambda _e: self.page.pop_dialog())],
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

    def actualizar_estado_conexion(
        self,
        estado: str = "online",
        mensaje: str = "",
        latencia_ms: float = 0.0,
    ) -> None:
        """Actualiza el semáforo de red y notifica en tiempo real microcortes y reconexiones."""
        actualizar_estado_conexion_ui(self, estado, mensaje, latencia_ms)

    def _iniciar_heartbeat_red(self) -> None:
        """Hilo en segundo plano para verificar enlace con la base de datos central periódicamente."""
        iniciar_heartbeat_red_daemon(self)

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
        reproducir_sonido_web(self, tipo)

    def _reproducir_sonido_legacy(self, tipo: str = "exito") -> None:
        reproducir_sonido_web(self, tipo)

    def mostrar_command_palette(self, _evento: ft.Event | None = None) -> None:
        mostrar_command_palette(self, _evento)


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
