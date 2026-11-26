"""Interfaz gráfica principal en Flet ensamblada por composición e inyección de dependencias."""

from __future__ import annotations

import weakref
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import flet as ft

from .logger_config import configurar_logging
from .menu import MenuAgente
from .orders import OrderStore
from .paths import application_root, get_data_dir
from .products import ProductStore
from .server_app import iniciar_servidor_web
from .auth import User, UserStore
from .inventory import StockManager
from .ui.app_config import INACTIVIDAD_MAX_MINUTOS, PUERTO_WEB_DEFAULT
from .ui.components import (
    actualizar_estado_conexion_ui,
    aplicar_posicion_sidebar_ui,
    construir_encabezado,
    construir_panel_acceso_rapido,
    construir_panel_informes_actividad,
    construir_panel_metricas,
    construir_sidebar_controls,
    detener_heartbeat_red,
    iniciar_heartbeat_red_daemon,
    manejar_cambio_navegacion_movil,
    reproducir_sonido_web,
)
from .ui.shell_builder import (
    actualizar_icono_notificaciones_ui,
    configurar_dialogos_adaptables_shell,
    configurar_ventana_shell,
    construir_barra_estado_ui,
    construir_dashboard_shell,
    construir_tarjeta_ui,
    copiar_al_portapapeles_ui,
    establecer_posicion_sidebar_ui,
    fijar_estado_tarea_ui,
    inicializar_controles_shell,
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
from .ui.controllers.batch_controller import (
    es_procesamiento_global_activo,
    set_procesamiento_global_activo,
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
    marcar_mensajes_chat_leidos = _Delegado(
        "session_sync_svc", lambda h: h._crear_session_sync_svc()
    )

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
    mostrar_modulo_despacho = _Delegado("dialog_coord", lambda h: h._crear_dialog_coord())
    mostrar_imprimir_descuentos = _Delegado("dialog_coord", lambda h: h._crear_dialog_coord())
    mostrar_cierre_jornada = _Delegado("dialog_coord", lambda h: h._crear_dialog_coord())
    mostrar_cierre_mercado = _Delegado("dialog_coord", lambda h: h._crear_dialog_coord())
    mostrar_cierre_mercado_envios = _Delegado("dialog_coord", lambda h: h._crear_dialog_coord())
    mostrar_cierre_parcial_mercado_full = _Delegado("dialog_coord", lambda h: h._crear_dialog_coord())
    mostrar_cierre_final_mercado_full = _Delegado("dialog_coord", lambda h: h._crear_dialog_coord())
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
    mostrar_dialogo_ajuste_bultos_express = _Delegado("dialog_coord", lambda h: h._crear_dialog_coord())
    confirmar_desarmar_pedido = _Delegado("dialog_coord", lambda h: h._crear_dialog_coord())
    confirmar_eliminacion_pedido = _Delegado("dialog_coord", lambda h: h._crear_dialog_coord())
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
    mostrar_dialogo_ola_picking = _Delegado("dialog_coord", lambda h: h._crear_dialog_coord())
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
        self._stock_manager_factory = (
            deps_activas.stock_manager_factory
            or (lambda *args, **kwargs: StockManager(*args, **kwargs))
        )
        self._app_root_fn = deps_activas.app_root_fn or (lambda: application_root())
        self._get_global_lock_fn = deps_activas.get_global_lock_fn or _obtener_procesamiento_global
        self._set_global_lock_fn = deps_activas.set_global_lock_fn or _fijar_procesamiento_global
        self._sessions_provider = deps_activas.sessions_provider or (lambda: list(SESIONES_ACTIVAS))
        self._session_discard_fn = deps_activas.session_discard_fn or (
            lambda sesion: SESIONES_ACTIVAS.discard(sesion)
        )
        self._inactivity_limit_fn = deps_activas.inactivity_limit_fn or (
            lambda: INACTIVIDAD_MAX_MINUTOS
        )

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
        self.sonido_chat_activo: bool = True
        self._mensajes_bot_no_leidos: int = 0
        self._ultimo_no_leidos_chat: int | None = None
        self.shared_prefs: ft.SharedPreferences | None = None
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
            stock_manager_factory=lambda *args, **kwargs: StockManager(*args, **kwargs),
            app_root_fn=lambda: application_root(),
            get_global_lock_fn=_obtener_procesamiento_global,
            set_global_lock_fn=_fijar_procesamiento_global,
            sessions_provider=lambda: list(SESIONES_ACTIVAS),
            session_discard_fn=lambda sesion: SESIONES_ACTIVAS.discard(sesion),
            inactivity_limit_fn=lambda: INACTIVIDAD_MAX_MINUTOS,
        )

    def resolver_stock_manager(self) -> Callable[..., Any]:
        """Devuelve la fábrica activa de StockManager inyectada en esta sesión."""
        factory = getattr(getattr(self, "_deps", None), "stock_manager_factory", None)
        return factory or self._stock_manager_factory

    def resolver_app_root(self) -> Path:
        """Devuelve la ruta raíz de la aplicación inyectada en esta sesión."""
        root_fn = getattr(getattr(self, "_deps", None), "app_root_fn", None) or self._app_root_fn
        return Path(root_fn())

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
            inactivity_limit_fn=self._inactivity_limit_fn,
            notify_fn=lambda msg: self.notificar(msg),
            ensure_file_picker_fn=lambda forzar_recrear=False: self._asegurar_file_picker(
                forzar_recrear=forzar_recrear
            ),
        )

    def _crear_batch_ctrl(self) -> BatchTaskController:
        return BatchTaskController(
            self,
            get_global_lock_fn=self._get_global_lock_fn,
            set_global_lock_fn=self._set_global_lock_fn,
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
            sessions_provider=self._sessions_provider,
            check_roles_fn=lambda *r: self.exigir_roles(*r),
            enrich_message_fn=lambda txt: self._enriquecer_mensaje_con_pedidos(txt),
            session_discard_fn=self._session_discard_fn,
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
        inicializar_controles_shell(self)

    @property
    def es_pantalla_movil(self) -> bool:
        ctrl = self._obtener_ctrl("responsive_ctrl", lambda h: h._crear_responsive_ctrl())
        return bool(ctrl.es_pantalla_movil)

    # ------------------------------------------------------------------
    # Ventana, Layout Principal y Controles Compartidos
    # ------------------------------------------------------------------
    def _configurar_dialogos_adaptables(self) -> None:
        """Interpreta dimensiones en diálogos para adaptarlos a pantallas pequeñas."""
        configurar_dialogos_adaptables_shell(self)

    def _configurar_ventana(self) -> None:
        icon_path = Path(__file__).resolve().parent / "img" / "ultratech.ico"
        configurar_ventana_shell(self, icon_path)

    def _al_desconectar(self, _evento: Any = None) -> None:
        """Libera recursos y detiene hilos de monitoreo cuando la sesión cliente se desconecta."""
        detener_heartbeat_red(self)
        self._session_discard_fn(self)

    def _sidebar_horizontal_controls(self) -> list[ft.Control]:
        from .ui.components.sidebar import construir_sidebar_horizontal_controls
        return construir_sidebar_horizontal_controls(self)

    def cambiar_posicion_sidebar(self, nueva_posicion: str) -> None:
        """Cambia la ubicación del menú y reconstruye la vista."""
        establecer_posicion_sidebar_ui(self, nueva_posicion)

    def _aplicar_posicion_sidebar(self, dashboard: ft.Control, sidebar: ft.Control) -> None:
        aplicar_posicion_sidebar_ui(self, dashboard, sidebar)

    def _al_cambiar_navegacion_movil(self, e: Any) -> None:
        """Acceso rápido inferior (Thumb Zone) para operarios con una sola mano."""
        manejar_cambio_navegacion_movil(self, e)

    def _sidebar_controls(self) -> list[ft.Control]:
        return construir_sidebar_controls(self)

    def construir(self) -> None:
        construir_dashboard_shell(self)

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
    def boton_dialogo(texto: str, accion: Callable, variante: str = "auto") -> ft.Button:
        """Botón de diálogo con jerarquía semántica (Cancelar/Cerrar neutros, destructivos diferenciados)."""
        from .ui.design import boton_dialogo_semantico

        return boton_dialogo_semantico(texto, accion, variante)  # type: ignore[arg-type]

    def _actualizar_icono_notificaciones(self) -> None:
        sm_cls = self.resolver_stock_manager()
        actualizar_icono_notificaciones_ui(self, sm_cls)

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
        return construir_barra_estado_ui(self)

    def fijar_estado_tarea(self, texto: str, estado: str = "listo") -> None:
        """Actualiza el texto y el ícono de la barra de estado inferior."""
        fijar_estado_tarea_ui(self, texto, estado)

    def tarjeta(self, contenido: ft.Control, expand: bool = False) -> ft.Container:
        return construir_tarjeta_ui(self, contenido, expand=expand)

    def actualizar_listas(self, _evento: ft.Event | None = None) -> None:
        """Alias de compatibilidad para actualizar el estado e informes."""
        self.actualizar_estado(_evento)

    def actualizar_estado(self, _evento: ft.Event | None = None) -> None:
        """Actualiza y sincroniza en tiempo real todos los indicadores y listas del Dashboard."""
        actualizar_estado_dashboard(self, _evento)

    def recargar_ambiente(self) -> None:
        """Recarga los almacenes de datos, la API REST y la interfaz según el ambiente activo."""
        from .api.deps import reset_api_stores

        reset_api_stores(revocar_sesiones_memoria=True)
        deps = self._construir_dependencias_por_defecto()
        self._deps = deps
        self.user_store = deps.user_store
        self.order_store = deps.order_store
        self.product_store = deps.product_store
        self.menu = deps.menu
        if self.usuario_actual is not None:
            self.construir()
        else:
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

    def notificar(self, mensaje: str, color: Any | None = None) -> None:
        if color is not None:
            try:
                snack = ft.SnackBar(
                    content=ft.Text(mensaje, color=ft.Colors.WHITE, size=13),
                    bgcolor=color,
                    duration=4000,
                )
                self.page.show_dialog(snack)
                self.page.update()
                return
            except Exception:
                pass
        dialogo = ft.AlertDialog(
            modal=True,
            title=ft.Text("Aviso"),
            icon=ft.Icon(ft.Icons.INFO_OUTLINE, color=ft.Colors.ON_SURFACE_VARIANT),
            content=ft.Text(mensaje),
            actions=[self.boton_dialogo("Aceptar", lambda _e: self.page.pop_dialog())],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.show_dialog(dialogo)

    def copiar_al_portapapeles(self, texto: str) -> None:
        """Copia texto al portapapeles del cliente de forma segura."""
        copiar_al_portapapeles_ui(self, texto)

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

    def mostrar_command_palette(self, _evento: ft.Event | None = None) -> None:
        mostrar_command_palette(self, _evento)


def _obtener_procesamiento_global() -> bool:
    return bool(PROCESAMIENTO_GLOBAL_ACTIVO or es_procesamiento_global_activo())


def _fijar_procesamiento_global(valor: bool) -> None:
    global PROCESAMIENTO_GLOBAL_ACTIVO
    PROCESAMIENTO_GLOBAL_ACTIVO = bool(valor)
    set_procesamiento_global_activo(valor)


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
