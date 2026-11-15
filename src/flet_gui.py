"""Interfaz gráfica principal en Flet ensamblada por composición e inyección de dependencias."""

from __future__ import annotations

import weakref
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import flet as ft

from .chat import obtener_mensaje_bienvenida
from .logger_config import configurar_logging
from .menu import MenuAgente
from .orders import OrderStore
from .paths import application_root, get_data_dir
from .products import ProductStore
from .server_app import (
    _RegistroConexionesMiddleware,
    _puerto_local_activo,
    iniciar_servidor_web,
    obtener_directorio_assets,
    obtener_ip_local,
    obtener_ip_tailscale,
)
from .auth import USER_ROLES, User, UserRole, UserStore, UserStoreError
from .inventory import StockManager
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
from .ui.controllers import (
    AuthSessionController,
    BatchTaskController,
    ChatAssistantController,
    DialogCoordinator,
    DocumentViewerService,
    FileTransferService,
    ResponsiveController,
    SessionSyncService,
    ThemeController,
)
from .ui.dashboard_presenter import actualizar_estado_dashboard
from .ui.dialogs import (
    actualizar_alerta_quiebre,
    mostrar_command_palette,
)
from .ui.protocols import AppDependencies
from .ui.theme import ROJO

logger = configurar_logging()

SESIONES_ACTIVAS: weakref.WeakSet["InterfazFlet"] = weakref.WeakSet()
PROCESAMIENTO_GLOBAL_ACTIVO: bool = False


class _Delegado:
    """Descriptor de fachada no-datos que delega en un controlador compuesto."""

    def __init__(
        self,
        ctrl_attr: str,
        factory: Callable[[Any], Any],
        target_name: str | None = None,
    ) -> None:
        self.ctrl_attr = ctrl_attr
        self.factory = factory
        self.target_name = target_name

    def __set_name__(self, owner: type, name: str) -> None:
        if self.target_name is None:
            self.target_name = name

    def __get__(self, instance: Any, owner: type | None = None) -> Any:
        if instance is None:
            return self
        ctrl = instance._obtener_ctrl(self.ctrl_attr, self.factory)
        return getattr(ctrl, self.target_name)  # type: ignore[arg-type]


class InterfazFlet:
    """Controlador principal de la interfaz Flet (Desktop y Web) basado en composición."""

    # --- Fachada delegada a ThemeController ---
    alternar_tema = _Delegado("theme_ctrl", lambda h: h._crear_theme_ctrl())

    # --- Fachada delegada a ResponsiveController ---
    ancho_adaptable = _Delegado("responsive_ctrl", lambda h: h._crear_responsive_ctrl())
    alto_adaptable = _Delegado("responsive_ctrl", lambda h: h._crear_responsive_ctrl())
    cerrar_drawer_si_movil = _Delegado("responsive_ctrl", lambda h: h._crear_responsive_ctrl())
    _asegurar_drawer_movil = _Delegado(
        "responsive_ctrl", lambda h: h._crear_responsive_ctrl(), "asegurar_drawer_movil"
    )
    _mostrar_menu_movil_fallback = _Delegado(
        "responsive_ctrl", lambda h: h._crear_responsive_ctrl(), "mostrar_menu_movil_fallback"
    )
    _abrir_drawer_click = _Delegado(
        "responsive_ctrl", lambda h: h._crear_responsive_ctrl(), "abrir_drawer_click"
    )
    _al_redimensionar = _Delegado(
        "responsive_ctrl", lambda h: h._crear_responsive_ctrl(), "al_redimensionar"
    )

    # --- Fachada delegada a FileTransferService ---
    _asegurar_file_picker = _Delegado(
        "file_transfer_svc", lambda h: h._crear_file_transfer_svc(), "asegurar_file_picker"
    )
    _descargar_archivo_navegador = _Delegado(
        "file_transfer_svc", lambda h: h._crear_file_transfer_svc(), "descargar_archivo_navegador"
    )
    subir_archivos_desde_pc = _Delegado("file_transfer_svc", lambda h: h._crear_file_transfer_svc())

    # --- Fachada delegada a DocumentViewerService ---
    abrir_url_en_navegador = _Delegado("doc_viewer_svc", lambda h: h._crear_doc_viewer_svc())
    ruta_informe = _Delegado("doc_viewer_svc", lambda h: h._crear_doc_viewer_svc())
    mostrar_manual_usuario = _Delegado("doc_viewer_svc", lambda h: h._crear_doc_viewer_svc())
    abrir_informe = _Delegado("doc_viewer_svc", lambda h: h._crear_doc_viewer_svc())
    mostrar_opciones_documento = _Delegado("doc_viewer_svc", lambda h: h._crear_doc_viewer_svc())
    abrir_carpeta_informe = _Delegado("doc_viewer_svc", lambda h: h._crear_doc_viewer_svc())
    compartir_correo = _Delegado("doc_viewer_svc", lambda h: h._crear_doc_viewer_svc())
    compartir_whatsapp = _Delegado("doc_viewer_svc", lambda h: h._crear_doc_viewer_svc())
    enviar_correo_cierre = _Delegado("doc_viewer_svc", lambda h: h._crear_doc_viewer_svc())

    # --- Fachada delegada a AuthSessionController ---
    mostrar_inicio_sesion = _Delegado("auth_ctrl", lambda h: h._crear_auth_ctrl())
    mostrar_cambio_clave_obligatorio = _Delegado("auth_ctrl", lambda h: h._crear_auth_ctrl())
    mostrar_cambiar_mi_clave = _Delegado("auth_ctrl", lambda h: h._crear_auth_ctrl())
    mostrar_mi_perfil = _Delegado("auth_ctrl", lambda h: h._crear_auth_ctrl())
    mostrar_configuracion_inicial = _Delegado("auth_ctrl", lambda h: h._crear_auth_ctrl())
    cerrar_sesion = _Delegado("auth_ctrl", lambda h: h._crear_auth_ctrl())
    exigir_roles = _Delegado("auth_ctrl", lambda h: h._crear_auth_ctrl())

    # --- Fachada delegada a BatchTaskController ---
    resumen_estado = _Delegado("batch_ctrl", lambda h: h._crear_batch_ctrl())
    resumen_informes = _Delegado("batch_ctrl", lambda h: h._crear_batch_ctrl())
    fuentes_seleccionadas = _Delegado("batch_ctrl", lambda h: h._crear_batch_ctrl())
    simular = _Delegado("batch_ctrl", lambda h: h._crear_batch_ctrl())
    procesar_real = _Delegado("batch_ctrl", lambda h: h._crear_batch_ctrl())
    confirmar_procesar_real = _Delegado("batch_ctrl", lambda h: h._crear_batch_ctrl())
    procesar = _Delegado("batch_ctrl", lambda h: h._crear_batch_ctrl())
    ejecutar_tarea = _Delegado("batch_ctrl", lambda h: h._crear_batch_ctrl())
    actualizar_progreso = _Delegado("batch_ctrl", lambda h: h._crear_batch_ctrl())
    _actualizar_estado_boton_cierre = _Delegado(
        "batch_ctrl", lambda h: h._crear_batch_ctrl(), "actualizar_estado_boton_cierre"
    )
    actualizar_estado_botones = _Delegado("batch_ctrl", lambda h: h._crear_batch_ctrl())

    # --- Fachada delegada a ChatAssistantController ---
    _enriquecer_mensaje_con_pedidos = _Delegado(
        "chat_ctrl", lambda h: h._crear_chat_ctrl(), "enriquecer_mensaje_con_pedidos"
    )
    alternar_chat_flotante = _Delegado("chat_ctrl", lambda h: h._crear_chat_ctrl())
    cerrar_chat_flotante = _Delegado("chat_ctrl", lambda h: h._crear_chat_ctrl())
    limpiar_chat = _Delegado("chat_ctrl", lambda h: h._crear_chat_ctrl())
    ejecutar_comando_rapido = _Delegado("chat_ctrl", lambda h: h._crear_chat_ctrl())
    cambiar_pestaña_chat = _Delegado(
        "chat_ctrl", lambda h: h._crear_chat_ctrl(), "cambiar_pestana_chat"
    )
    crear_ventana_chat_flotante = _Delegado("chat_ctrl", lambda h: h._crear_chat_ctrl())
    panel_chat = _Delegado("chat_ctrl", lambda h: h._crear_chat_ctrl())
    escribir_chat = _Delegado("chat_ctrl", lambda h: h._crear_chat_ctrl())
    enviar_chat = _Delegado("chat_ctrl", lambda h: h._crear_chat_ctrl())

    # --- Fachada delegada a SessionSyncService ---
    sincronizar_sesiones = _Delegado("session_sync_svc", lambda h: h._crear_session_sync_svc())
    actualizar_badge_chat = _Delegado("session_sync_svc", lambda h: h._crear_session_sync_svc())
    refrescar_usuarios_chat_equipo = _Delegado(
        "session_sync_svc", lambda h: h._crear_session_sync_svc()
    )
    cargar_mensajes_equipo = _Delegado("session_sync_svc", lambda h: h._crear_session_sync_svc())
    enviar_mensaje_equipo = _Delegado("session_sync_svc", lambda h: h._crear_session_sync_svc())

    # --- Fachada delegada a DialogCoordinator ---
    mostrar_dialogo_compartir_cierre = _Delegado("dialog_coord", lambda h: h._crear_dialog_coord())
    mostrar_dialogo_enviar_correo = _Delegado("dialog_coord", lambda h: h._crear_dialog_coord())
    mostrar_dialogo_api_master = _Delegado("dialog_coord", lambda h: h._crear_dialog_coord())
    mostrar_gestion_api_keys = _Delegado("dialog_coord", lambda h: h._crear_dialog_coord())
    mostrar_estado_api = _Delegado("dialog_coord", lambda h: h._crear_dialog_coord())
    mostrar_sesiones_api = _Delegado("dialog_coord", lambda h: h._crear_dialog_coord())
    mostrar_configuracion_smtp = _Delegado("dialog_coord", lambda h: h._crear_dialog_coord())
    confirmar_restaurar = _Delegado("dialog_coord", lambda h: h._crear_dialog_coord())
    restaurar = _Delegado("dialog_coord", lambda h: h._crear_dialog_coord())
    mostrar_gestion_usuarios = _Delegado("dialog_coord", lambda h: h._crear_dialog_coord())
    mostrar_dialogo_api_keys = _Delegado("dialog_coord", lambda h: h._crear_dialog_coord())
    mostrar_gestion_clientes = _Delegado("dialog_coord", lambda h: h._crear_dialog_coord())
    mostrar_crear_pedido = _Delegado("dialog_coord", lambda h: h._crear_dialog_coord())
    mostrar_historial_pedidos = _Delegado("dialog_coord", lambda h: h._crear_dialog_coord())
    mostrar_centro_reportes = _Delegado("dialog_coord", lambda h: h._crear_dialog_coord())
    mostrar_detalle_pedido_modal = _Delegado("dialog_coord", lambda h: h._crear_dialog_coord())
    mostrar_escaner_qr_despacho = _Delegado("dialog_coord", lambda h: h._crear_dialog_coord())
    mostrar_imprimir_descuentos = _Delegado("dialog_coord", lambda h: h._crear_dialog_coord())
    mostrar_cierre_jornada = _Delegado("dialog_coord", lambda h: h._crear_dialog_coord())
    mostrar_cierre_mercado = _Delegado("dialog_coord", lambda h: h._crear_dialog_coord())
    mostrar_historial_cierres_admin = _Delegado("dialog_coord", lambda h: h._crear_dialog_coord())
    mostrar_acceso_admin = _Delegado("dialog_coord", lambda h: h._crear_dialog_coord())
    mostrar_ver_stock = _Delegado("dialog_coord", lambda h: h._crear_dialog_coord())
    mostrar_gestion_productos = _Delegado("dialog_coord", lambda h: h._crear_dialog_coord())
    mostrar_historial_movimientos_stock = _Delegado(
        "dialog_coord", lambda h: h._crear_dialog_coord()
    )
    mostrar_formulario_producto = _Delegado("dialog_coord", lambda h: h._crear_dialog_coord())
    imprimir_rotulos_termicos_pedido = _Delegado("dialog_coord", lambda h: h._crear_dialog_coord())
    imprimir_rotulos_pedido = _Delegado("dialog_coord", lambda h: h._crear_dialog_coord())
    imprimir_rotulos_lote = _Delegado("dialog_coord", lambda h: h._crear_dialog_coord())
    confirmar_anulacion_pedido = _Delegado("dialog_coord", lambda h: h._crear_dialog_coord())
    mostrar_dialogo_editar_pedido = _Delegado("dialog_coord", lambda h: h._crear_dialog_coord())
    confirmar_desarmar_pedido = _Delegado("dialog_coord", lambda h: h._crear_dialog_coord())
    mostrar_dialogo_backup = _Delegado("dialog_coord", lambda h: h._crear_dialog_coord())
    mostrar_dialogo_archivo_historico = _Delegado("dialog_coord", lambda h: h._crear_dialog_coord())
    mostrar_configuracion_telegram = _Delegado("dialog_coord", lambda h: h._crear_dialog_coord())
    mostrar_sincronizacion_mercadolibre = _Delegado(
        "dialog_coord", lambda h: h._crear_dialog_coord()
    )
    mostrar_dialogo_anomalias = _Delegado("dialog_coord", lambda h: h._crear_dialog_coord())
    mostrar_dialogo_heatmap = _Delegado("dialog_coord", lambda h: h._crear_dialog_coord())
    sincronizar_catalogo_excel = _Delegado("dialog_coord", lambda h: h._crear_dialog_coord())
    mostrar_detalle_quiebre = _Delegado("dialog_coord", lambda h: h._crear_dialog_coord())
    mostrar_dashboard_metricas = _Delegado("dialog_coord", lambda h: h._crear_dialog_coord())
    mostrar_registro_auditoria = _Delegado("dialog_coord", lambda h: h._crear_dialog_coord())
    mostrar_estadisticas = _Delegado("dialog_coord", lambda h: h._crear_dialog_coord())
    generar_pedido_fabrica = _Delegado("dialog_coord", lambda h: h._crear_dialog_coord())
    mostrar_ingreso_fabrica = _Delegado("dialog_coord", lambda h: h._crear_dialog_coord())
    mostrar_planificar_ingreso_fabrica = _Delegado(
        "dialog_coord", lambda h: h._crear_dialog_coord()
    )
    mostrar_control_ingreso_fabrica = _Delegado("dialog_coord", lambda h: h._crear_dialog_coord())
    mostrar_descuento_mercado_full = _Delegado("dialog_coord", lambda h: h._crear_dialog_coord())
    mostrar_planificar_full = _Delegado("dialog_coord", lambda h: h._crear_dialog_coord())
    mostrar_picking_guiado_full = _Delegado("dialog_coord", lambda h: h._crear_dialog_coord())
    mostrar_descuento_mercado_libre = _Delegado("dialog_coord", lambda h: h._crear_dialog_coord())
    mostrar_notificaciones_admin = _Delegado("dialog_coord", lambda h: h._crear_dialog_coord())
    mostrar_stock_fisico_operario = _Delegado("dialog_coord", lambda h: h._crear_dialog_coord())
    mostrar_comparativa_stock_fisico_admin = _Delegado(
        "dialog_coord", lambda h: h._crear_dialog_coord()
    )
    mostrar_dialogo_ingreso_rapido = _Delegado("dialog_coord", lambda h: h._crear_dialog_coord())
    mostrar_dialogo_salida_rapida = _Delegado("dialog_coord", lambda h: h._crear_dialog_coord())
    mostrar_dialogo_inventario_vivo = _Delegado("dialog_coord", lambda h: h._crear_dialog_coord())
    mostrar_gestion_ambientes = _Delegado("dialog_coord", lambda h: h._crear_dialog_coord())

    def __init__(self, page: ft.Page, deps: AppDependencies | None = None) -> None:
        self.page = page
        SESIONES_ACTIVAS.add(self)
        deps_activas = deps or self._construir_dependencias_por_defecto()
        self._deps = deps_activas
        self.user_store = deps_activas.user_store
        self.order_store = deps_activas.order_store
        self.product_store = deps_activas.product_store
        self.menu = deps_activas.menu
        self._stock_manager_factory = deps_activas.stock_manager_factory or StockManager
        self._app_root_fn = deps_activas.app_root_fn or application_root

        self.usuario_actual: User | None = None
        self.ocupado = False
        self.informes: list[Path] = []
        self.informe_seleccionado: Path | None = None
        self.seleccion_fecha_restauracion: ft.Dropdown | None = None
        self.controles_tarea: list[ft.Button] = []
        self.btn_cierre_jornada: ft.Button | None = None
        self.botones_cierre_jornada: list[ft.Button] = []
        self.contadores: dict[str, ft.Text] = {}
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
        self.modo_chat_activo: str = "bot"
        self.ventana_chat_flotante: ft.Container | None = None
        self.boton_chat_flotante: ft.FloatingActionButton | None = None
        self.ultima_actividad: datetime = datetime.now()

        self._inicializar_controladores()
        self.theme_ctrl.aplicar_paleta(modo_oscuro=True, usar_paleta_preferencia=False)
        self._inicializar_controles_ui()

        self._asegurar_file_picker()
        self._configurar_ventana()
        if self.user_store.has_users:
            self.mostrar_inicio_sesion()
        else:
            self.mostrar_configuracion_inicial()

    # ------------------------------------------------------------------
    # Fábricas e Inyección de Dependencias
    # ------------------------------------------------------------------
    def _construir_dependencias_por_defecto(self) -> AppDependencies:
        data_dir = get_data_dir()
        (data_dir / "pedidos_archivos").mkdir(parents=True, exist_ok=True)
        return AppDependencies(
            user_store=UserStore(data_dir / "usuarios.sqlite3"),
            order_store=OrderStore(data_dir / "pedidos.sqlite3"),
            product_store=ProductStore(data_dir / "productos.sqlite3"),
            menu=MenuAgente(),
            stock_manager_factory=StockManager,
            app_root_fn=application_root,
        )

    def _crear_theme_ctrl(self) -> ThemeController:
        return ThemeController(self, on_rebuild=lambda: self.construir())

    def _crear_responsive_ctrl(self) -> ResponsiveController:
        return ResponsiveController(
            self,
            get_sidebar_controls=lambda: self._sidebar_controls(),
            on_rebuild=lambda: self.construir(),
            on_show_login=lambda: self.mostrar_inicio_sesion(),
            on_show_setup=lambda: self.mostrar_configuracion_inicial(),
        )

    def _crear_file_transfer_svc(self) -> FileTransferService:
        return FileTransferService(
            self,
            notify_fn=lambda msg: self.notificar(msg),
            on_files_saved=lambda: (self.actualizar_estado(), self.sincronizar_sesiones()),
        )

    def _crear_doc_viewer_svc(self) -> DocumentViewerService:
        root_fn = getattr(self, "_app_root_fn", None) or application_root
        return DocumentViewerService(
            self,
            check_roles_fn=lambda *r: self.exigir_roles(*r),
            notify_fn=lambda msg: self.notificar(msg),
            app_root_fn=root_fn,
        )

    def _crear_auth_ctrl(self) -> AuthSessionController:
        return AuthSessionController(
            self,
            inactivity_limit_fn=lambda: INACTIVIDAD_MAX_MINUTOS,
            notify_fn=lambda msg: self.notificar(msg),
            ensure_file_picker_fn=lambda forzar_recrear=False: self._asegurar_file_picker(
                forzar_recrear=forzar_recrear
            ),
        )

    def _crear_batch_ctrl(self) -> BatchTaskController:
        return BatchTaskController(
            self,
            get_global_lock_fn=lambda: bool(PROCESAMIENTO_GLOBAL_ACTIVO),
            set_global_lock_fn=_fijar_procesamiento_global,
            check_roles_fn=lambda *r: self.exigir_roles(*r),
            notify_fn=lambda msg: self.notificar(msg),
            refresh_dashboard_fn=lambda: self.actualizar_estado(),
            sync_sessions_fn=lambda: self.sincronizar_sesiones(),
        )

    def _crear_chat_ctrl(self) -> ChatAssistantController:
        return ChatAssistantController(self, check_roles_fn=lambda *r: self.exigir_roles(*r))

    def _crear_session_sync_svc(self) -> SessionSyncService:
        return SessionSyncService(
            self,
            sessions_provider=lambda: list(SESIONES_ACTIVAS),
            check_roles_fn=lambda *r: self.exigir_roles(*r),
            enrich_message_fn=lambda txt: self._enriquecer_mensaje_con_pedidos(txt),
        )

    def _crear_dialog_coord(self) -> DialogCoordinator:
        return DialogCoordinator(
            self,
            check_roles_fn=lambda *r: self.exigir_roles(*r),
            close_drawer_fn=lambda: self.cerrar_drawer_si_movil(),
            ensure_file_picker_fn=lambda: self._asegurar_file_picker(),
            notify_fn=lambda msg: self.notificar(msg),
        )

    def _inicializar_controladores(self) -> None:
        self.theme_ctrl = self._crear_theme_ctrl()
        self.responsive_ctrl = self._crear_responsive_ctrl()
        self.file_transfer_svc = self._crear_file_transfer_svc()
        self.doc_viewer_svc = self._crear_doc_viewer_svc()
        self.auth_ctrl = self._crear_auth_ctrl()
        self.batch_ctrl = self._crear_batch_ctrl()
        self.chat_ctrl = self._crear_chat_ctrl()
        self.session_sync_svc = self._crear_session_sync_svc()
        self.dialog_coord = self._crear_dialog_coord()

    def _obtener_ctrl(self, attr: str, factory: Callable[[Any], Any]) -> Any:
        ctrl = self.__dict__.get(attr)
        if ctrl is None:
            ctrl = factory(self)
            self.__dict__[attr] = ctrl
        return ctrl

    def _inicializar_controles_ui(self) -> None:
        self.mayoristas = ft.Checkbox(label="Mayoristas · PDF", value=True)
        self.canjes = ft.Checkbox(label="Canjes · Excel", value=True)
        self.mercado_libre = ft.Checkbox(label="Mercado Libre · DOCX", value=True)
        self.icono_estado_tarea = ft.Icon(
            ft.Icons.CHECK_CIRCLE_OUTLINE_ROUNDED,
            size=14,
            color=ft.Colors.GREEN_400,
        )
        self.estado_tarea = ft.Text(
            "Sistema listo", color=self.secundario, size=11, weight=ft.FontWeight.W_500
        )
        self.progreso_barra = ft.ProgressBar(width=160, value=None, color=ROJO, visible=False)
        self.lista_informes = ft.ListView(expand=True, spacing=4)
        self.actividad = ft.ListView(expand=True, spacing=6, auto_scroll=True)
        self.header_pedidos_fecha = ft.Text(
            "Fecha de hoy", size=13, weight=ft.FontWeight.BOLD, color=self.texto
        )
        self.header_pedidos_subtitulo = ft.Text(
            "0 pedidos preparados", size=11, color=self.secundario
        )
        self.header_pedidos_bultos = ft.Text(
            "0 bultos", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE
        )
        self.lista_pedidos_preparados = ft.ListView(expand=True, spacing=6)
        self.conversacion = ft.ListView(expand=True, spacing=8, auto_scroll=True)
        self.entrada_chat = ft.TextField(
            hint_text="Escribe una consulta o /ayuda",
            expand=True,
            min_lines=1,
            max_lines=3,
            on_submit=self.enviar_chat,
        )
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
        self.pendientes_texto = ft.Text("", color=self.secundario, size=12)

    @property
    def es_pantalla_movil(self) -> bool:
        ctrl = self._obtener_ctrl("responsive_ctrl", lambda h: h._crear_responsive_ctrl())
        return bool(ctrl.es_pantalla_movil)

    # ------------------------------------------------------------------
    # Ventana, Layout Principal y Controles Compartidos
    # ------------------------------------------------------------------
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
        """Cambia la ubicación del menú y reconstruye la vista."""
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
        """Acceso rápido inferior (Thumb Zone) para operarios con una sola mano."""
        manejar_cambio_navegacion_movil(self, e)

    def _sidebar_controls(self) -> list[ft.Control]:
        return construir_sidebar_controls(self)

    def construir(self) -> None:
        if self.usuario_actual is None:
            self.mostrar_inicio_sesion()
            return
        self.theme_ctrl.aplicar_preferencias_usuario(self.usuario_actual)

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
                self.barra_estado(),
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
            sm_factory = getattr(self, "_stock_manager_factory", None) or StockManager
            sm = sm_factory(self.menu.ruta_excel_base)
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

    def barra_estado(self) -> ft.Control:
        """Barra de estado inferior con diseño sutil e indicador de actividad del sistema."""
        return ft.Container(
            content=ft.Row(
                [
                    ft.Row(
                        [
                            self.icono_estado_tarea,
                            self.estado_tarea,
                        ],
                        spacing=7,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    self.progreso_barra,
                ],
                spacing=12,
                alignment=ft.MainAxisAlignment.START,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding(left=12, right=14, top=6, bottom=6),
            border_radius=8,
            bgcolor=ft.Colors.with_opacity(0.04, self.texto),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.08, self.texto)),
        )

    def fijar_estado_tarea(self, texto: str, estado: str = "listo") -> None:
        """Actualiza el texto y el ícono de la barra de estado inferior."""
        self.estado_tarea.value = texto
        if hasattr(self, "icono_estado_tarea") and self.icono_estado_tarea:
            texto_lower = (texto or "").lower()
            if estado == "listo" or "listo" in texto_lower or "finalizad" in texto_lower:
                self.icono_estado_tarea.name = ft.Icons.CHECK_CIRCLE_OUTLINE_ROUNDED
                self.icono_estado_tarea.color = ft.Colors.GREEN_400
            elif estado == "error" or "error" in texto_lower or "fall" in texto_lower:
                self.icono_estado_tarea.name = ft.Icons.ERROR_OUTLINE_ROUNDED
                self.icono_estado_tarea.color = ft.Colors.RED_400
            elif estado == "en_curso" or "curso" in texto_lower or "progreso" in texto_lower:
                self.icono_estado_tarea.name = ft.Icons.SYNC_ROUNDED
                self.icono_estado_tarea.color = ft.Colors.AMBER_400
            elif estado == "archivo":
                self.icono_estado_tarea.name = ft.Icons.DESCRIPTION_OUTLINED
                self.icono_estado_tarea.color = ft.Colors.LIGHT_BLUE_400
            else:
                self.icono_estado_tarea.name = ft.Icons.INFO_OUTLINE_ROUNDED
                self.icono_estado_tarea.color = self.secundario
        if hasattr(self, "page") and self.page:
            try:
                self.page.update()
            except Exception:
                pass

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

    def recargar_ambiente(self) -> None:
        """Recarga los almacenes de datos y el menú según el ambiente activo (Producción o QA)."""
        deps = self._construir_dependencias_por_defecto()
        self._deps = deps
        self.user_store = deps.user_store
        self.order_store = deps.order_store
        self.product_store = deps.product_store
        self.menu = deps.menu
        self.actualizar_estado()
        try:
            self.page.update()
        except Exception:
            pass

    def actualizar_alerta_quiebre(self, criticos: list | None = None) -> None:
        actualizar_alerta_quiebre(self, criticos)

    def seleccionar_informe(self, ruta: Path) -> None:
        self.informe_seleccionado = ruta
        tipo = "Pedido a fábrica" if ruta.name.startswith("Pedido_Fabrica") else "Informe"
        self.fijar_estado_tarea(f"{tipo} seleccionado: {ruta.name}", estado="archivo")

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


def _fijar_procesamiento_global(valor: bool) -> None:
    global PROCESAMIENTO_GLOBAL_ACTIVO
    PROCESAMIENTO_GLOBAL_ACTIVO = bool(valor)


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
