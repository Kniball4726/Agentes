"""Prototipo de escritorio en Flet para el agente de control de stock."""

import asyncio
import contextlib
import io
import json
import os
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

from .factory_parser import parsear_archivo_fabrica
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
from .backup_manager import crear_backup_sistema
from .canjes_parser import parsear_canje_excel
from .consolidator import ItemConsolidado
from .dispatch_manifest import generar_hoja_ruta_pdf
from .label_generator import generar_etiquetas_bultos_pdf
from .orders_store import CierreJornada, LOGISTICA_OPCIONES, OrderStore, RegistroAuditoria, calcular_hash_archivo
from .remito_parser import ResultadoRemito, normalizar_codigo, parsear_remito
from .paths import application_root
from .stock_manager import StockManager
from .user_store import USER_ROLES, User, UserRole, UserStore, UserStoreError


ROJO = ft.Colors.RED_700
FONDO = ft.Colors.GREY_100
SUPERFICIE = ft.Colors.WHITE
TEXTO = ft.Colors.BLUE_GREY_900
SECUNDARIO = ft.Colors.BLUE_GREY_600
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
        self.contadores: dict[str, ft.Text] = {}
        self.pendientes_texto = ft.Text("", color=self.secundario, size=12)
        self.banner_alerta_quiebre = ft.Container(visible=False)
        self.contenedor_notificaciones = ft.Container()
        self.file_picker = ft.FilePicker()
        self.chat_visible = False
        self.ventana_chat_flotante: ft.Container | None = None
        self.boton_chat_flotante: ft.FloatingActionButton | None = None
        if not hasattr(self.page, "overlay") or self.page.overlay is None:
            self.page.overlay = []
        if self.file_picker not in self.page.overlay:
            self.page.overlay.append(self.file_picker)
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

    def _configurar_ventana(self) -> None:
        self.page.title = "StockAgent"
        self.page.window.icon = str(
            Path(__file__).resolve().parent / "img" / "ultratech.ico"
        )
        self.page.padding = 0
        self.page.bgcolor = self.fondo
        self.page.theme_mode = ft.ThemeMode.DARK
        self.page.theme = ft.Theme(color_scheme_seed=ROJO)
        self.page.window.maximized = True
        self.page.window.min_width = 1050
        self.page.window.min_height = 720

    def mostrar_inicio_sesion(self, error: str = "") -> None:
        usuario = ft.TextField(label="Usuario", autofocus=True)
        clave = ft.TextField(label="Contraseña", password=True, can_reveal_password=True)
        mensaje = ft.Text(error, color=ft.Colors.RED_400)

        def iniciar(_evento: ft.Event) -> None:
            autenticado = self.user_store.authenticate(
                usuario.value or "", clave.value or ""
            )
            if autenticado is None:
                mensaje.value = "Usuario o contraseña incorrectos, o cuenta inactiva."
                self.page.update()
                return
            self.usuario_actual = autenticado
            self.construir()

        self.chat_visible = False
        self.page.floating_action_button = None
        if hasattr(self.page, "overlay") and self.page.overlay is not None:
            self.page.overlay.clear()
        self.page.controls.clear()
        self.page.add(
            ft.Container(
                expand=True,
                alignment=ft.Alignment.CENTER,
                bgcolor=self.fondo,
                content=ft.Container(
                    width=420,
                    padding=28,
                    bgcolor=self.superficie,
                    border=ft.Border.all(1, self.borde),
                    border_radius=16,
                    content=ft.Column(
                        [
                            ft.Text(
                                "Iniciar sesión",
                                size=24,
                                weight=ft.FontWeight.BOLD,
                                color=self.texto,
                            ),
                            ft.Text(
                                "Agente de control de stock",
                                color=self.secundario,
                            ),
                            usuario,
                            clave,
                            mensaje,
                            ft.Button(
                                "Ingresar",
                                icon=ft.Icons.LOGIN,
                                on_click=iniciar,
                                bgcolor=ROJO,
                                color=ft.Colors.WHITE,
                                width=360,
                            ),
                        ],
                        tight=True,
                        spacing=14,
                    ),
                ),
            )
        )
        self.page.update()

    def mostrar_configuracion_inicial(self, error: str = "") -> None:
        usuario = ft.TextField(label="Usuario administrador", autofocus=True)
        clave = ft.TextField(
            label="Contraseña (mínimo 10 caracteres)",
            password=True,
            can_reveal_password=True,
        )
        confirmar = ft.TextField(
            label="Confirmar contraseña",
            password=True,
            can_reveal_password=True,
        )
        mensaje = ft.Text(error, color=ft.Colors.RED_400)

        def crear_administrador(_evento: ft.Event) -> None:
            if clave.value != confirmar.value:
                mensaje.value = "Las contraseñas no coinciden."
                self.page.update()
                return
            try:
                self.usuario_actual = self.user_store.create_initial_admin(
                    usuario.value or "", clave.value or ""
                )
            except (ValueError, UserStoreError) as error:
                mensaje.value = str(error)
                self.page.update()
                return
            self.construir()

        self.chat_visible = False
        self.page.floating_action_button = None
        if hasattr(self.page, "overlay") and self.page.overlay is not None:
            self.page.overlay.clear()
        self.page.controls.clear()
        self.page.add(
            ft.Container(
                expand=True,
                alignment=ft.Alignment.CENTER,
                bgcolor=self.fondo,
                content=ft.Container(
                    width=460,
                    padding=28,
                    bgcolor=self.superficie,
                    border=ft.Border.all(1, self.borde),
                    border_radius=16,
                    content=ft.Column(
                        [
                            ft.Text(
                                "Configurar administrador",
                                size=24,
                                weight=ft.FontWeight.BOLD,
                                color=self.texto,
                            ),
                            ft.Text(
                                "Crea la primera cuenta para proteger el acceso al sistema.",
                                color=self.secundario,
                            ),
                            usuario,
                            clave,
                            confirmar,
                            mensaje,
                            ft.Button(
                                "Crear cuenta y continuar",
                                icon=ft.Icons.PERSON_ADD,
                                on_click=crear_administrador,
                                bgcolor=ROJO,
                                color=ft.Colors.WHITE,
                                width=400,
                            ),
                        ],
                        tight=True,
                        spacing=14,
                    ),
                ),
            )
        )
        self.page.update()

    def cerrar_sesion(self, _evento: ft.Event) -> None:
        self.usuario_actual = None
        self.controles_tarea.clear()
        self.conversacion.controls.clear()
        self.ventana_chat_flotante = None
        self.mostrar_inicio_sesion()

    def exigir_roles(self, *roles: UserRole) -> bool:
        if self.usuario_actual is None:
            self.mostrar_inicio_sesion()
            return False
        usuario = self.user_store.get_user(self.usuario_actual.id)
        if usuario is None or not usuario.active:
            self.usuario_actual = None
            self.mostrar_inicio_sesion("La cuenta ya no está activa. Inicia sesión nuevamente.")
            return False
        self.usuario_actual = usuario
        if usuario.role == "master":
            return True
        if "operador" in roles and usuario.role == "administrador":
            return True
        if usuario.role not in roles:
            self.notificar("Tu rol no tiene permiso para realizar esta acción.")
            return False
        return True

    def _sidebar_controls(self) -> list[ft.Control]:
        assert self.usuario_actual is not None
        controls: list[ft.Control] = [
            ft.Row(
                [
                    ft.Container(
                        width=42,
                        height=42,
                        border_radius=12,
                        bgcolor=ft.Colors.RED_50 if self.modo_oscuro else ft.Colors.RED_50,
                        alignment=ft.Alignment.CENTER,
                        content=ft.Image(
                            src=(
                                Path(__file__).resolve().parent
                                / "img"
                                / "ultratech.png"
                            ).read_bytes(),
                            width=42,
                            height=42,
                            fit=ft.BoxFit.CONTAIN,
                        ),
                    ),
                    ft.Column(
                        [
                            ft.Text("StockAgent", size=18, weight=ft.FontWeight.BOLD, color=self.texto),
                            ft.Text("Panel de control", size=11, color=self.secundario),
                        ],
                        spacing=2,
                    ),
                ],
                spacing=10,
            ),
            ft.Text(
                f"{self.usuario_actual.username} · {self.usuario_actual.role}",
                size=11,
                color=self.secundario,
            ),
            ft.Divider(height=22, color=self.borde),
        ]
        if self.usuario_actual.role == "operador":
            controls.extend(
                [
                    ft.Text("PEDIDOS EN TIEMPO REAL", size=11, weight=ft.FontWeight.BOLD, color=self.secundario),
                    self.boton("Cargar / Armar Pedido", ft.Icons.POST_ADD, self.mostrar_crear_pedido),
                    self.boton("Descontar Mercado Libre", ft.Icons.STOREFRONT, self.mostrar_descuento_mercado_libre),
                    self.boton("Historial de Pedidos", ft.Icons.RECEIPT_LONG, self.mostrar_historial_pedidos),
                    self.boton("Imprimir Descuento", ft.Icons.PRINT, self.mostrar_imprimir_descuentos),
                    self.boton("Cierre de Jornada", ft.Icons.TASK_ALT, self.mostrar_cierre_jornada),
                ]
            )
        controls.extend(
            [
                ft.Divider(height=18, color=self.borde),
                ft.Text("INFORMES", size=11, weight=ft.FontWeight.BOLD, color=self.secundario),
                self.boton("Abrir informe", ft.Icons.OPEN_IN_NEW, self.abrir_informe),
                self.boton("Compartir por correo", ft.Icons.EMAIL, self.compartir_correo),
                self.boton("WhatsApp Web", ft.Icons.CHAT, self.compartir_whatsapp),
            ]
        )
        if self.usuario_actual.role in ("administrador", "master"):
            controls.extend(
                [
                    ft.Divider(height=18, color=self.borde),
                    ft.Text("ADMINISTRACIÓN", size=11, weight=ft.FontWeight.BOLD, color=self.secundario),
                    self.boton("Gestionar usuarios", ft.Icons.GROUP, self.mostrar_gestion_usuarios),
                    self.boton("Historial de Pedidos", ft.Icons.RECEIPT_LONG, self.mostrar_historial_pedidos),
                    self.boton("Restaurar documentos", ft.Icons.RESTORE, self.confirmar_restaurar),
                    self.boton(
                        "Gestionar productos",
                        ft.Icons.ADD_BOX,
                        self.mostrar_gestion_productos,
                    ),
                    self.boton(
                        "Ajustar stock / Fábrica",
                        ft.Icons.INVENTORY_2,
                        self.mostrar_ingreso_fabrica,
                    ),
                    self.boton(
                        "Descontar Mercado Full",
                        ft.Icons.LOCAL_SHIPPING,
                        self.mostrar_descuento_mercado_full,
                    ),
                    self.boton(
                        "Descontar Mercado Libre",
                        ft.Icons.STOREFRONT,
                        self.mostrar_descuento_mercado_libre,
                    ),
                    self.boton(
                        "Comparativa stock físico",
                        ft.Icons.COMPARE_ARROWS,
                        self.mostrar_comparativa_stock_fisico_admin,
                    ),
                    self.boton(
                        "Generar pedido fábrica (Excel)",
                        ft.Icons.FACT_CHECK,
                        self.generar_pedido_fabrica,
                    ),
                    self.boton(
                        "Estadísticas de salida",
                        ft.Icons.BAR_CHART,
                        self.mostrar_estadisticas,
                    ),
                    self.boton(
                        "Métricas y Rendimiento",
                        ft.Icons.INSIGHTS,
                        self.mostrar_dashboard_metricas,
                    ),
                    self.boton(
                        "Registro de Auditoría",
                        ft.Icons.SECURITY,
                        self.mostrar_registro_auditoria,
                    ),
                    self.boton(
                        "Copia de Seguridad",
                        ft.Icons.BACKUP,
                        self.mostrar_dialogo_backup,
                    ),
                ]
            )
        controls.extend(
            [
                ft.Container(height=8),
                ft.Row(
                    [
                        ft.Icon(ft.Icons.CIRCLE, color=ft.Colors.GREEN_600, size=10),
                        ft.Text("Agente local activo", size=12, color=self.secundario),
                    ],
                    spacing=8,
                ),
            ]
        )
        return controls

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

        sidebar = ft.Container(
            width=258,
            bgcolor=self.superficie,
            padding=20,
            content=ft.Column(
                self._sidebar_controls(),
                spacing=8,
                scroll=ft.ScrollMode.AUTO,
            ),
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
        if hasattr(self.page, "overlay"):
            if self.page.overlay is None:
                self.page.overlay = []
            else:
                self.page.overlay.clear()
            self.page.overlay.append(self.file_picker)
            self.page.overlay.append(self.crear_ventana_chat_flotante())

        self.boton_chat_flotante = ft.FloatingActionButton(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.SMART_TOY, color=ft.Colors.WHITE, size=20),
                    ft.Text("Asistente", color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD, size=13),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=6,
            ),
            bgcolor=ROJO,
            tooltip="Abrir Asistente Virtual",
            on_click=self.alternar_chat_flotante,
            shape=ft.RoundedRectangleBorder(radius=16),
            width=130,
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
            self.contenedor_notificaciones.content = ft.Badge(
                content=ft.IconButton(
                    icon=ft.Icons.NOTIFICATIONS_ACTIVE,
                    icon_color=ft.Colors.AMBER_400,
                    tooltip=f"{no_leidas} notificación(es) de operarios sin leer",
                    on_click=self.mostrar_notificaciones_admin,
                ),
                text=str(no_leidas),
            )
        else:
            self.contenedor_notificaciones.content = ft.IconButton(
                icon=ft.Icons.NOTIFICATIONS_NONE,
                icon_color=self.secundario,
                tooltip="Notificaciones de operarios",
                on_click=self.mostrar_notificaciones_admin,
            )

    def sincronizar_sesiones(self) -> None:
        """Actualiza en tiempo real otras sesiones abiertas en el navegador (Opción 2)."""
        for sesion in list(SESIONES_ACTIVAS):
            if sesion is self or sesion.usuario_actual is None:
                continue
            try:
                sesion.actualizar_estado()
            except Exception:
                pass

    def encabezado(self) -> ft.Control:
        assert self.usuario_actual is not None
        boton_tema = ft.Button(
            content="Modo claro" if self.modo_oscuro else "Modo oscuro",
            icon=ft.Icons.WB_SUNNY if self.modo_oscuro else ft.Icons.DARK_MODE,
            on_click=self.alternar_tema,
            bgcolor=ROJO,
            color=ft.Colors.WHITE,
        )
        self._actualizar_icono_notificaciones()

        fila_acciones: list[ft.Control] = []
        if self.usuario_actual.role == "administrador":
            fila_acciones.append(self.contenedor_notificaciones)
        fila_acciones.extend(
            [
                boton_tema,
                ft.TextButton(
                    f"{self.usuario_actual.username} · Cerrar sesión",
                    icon=ft.Icons.LOGOUT,
                    on_click=self.cerrar_sesion,
                ),
                self.boton(
                    "Actualizar", ft.Icons.REFRESH, self.actualizar_estado, 150
                ),
            ]
        )

        ip_red = obtener_ip_local()
        puerto_red = os.environ.get("STOCKAGENT_PORT", str(PUERTO_WEB_DEFAULT))

        return ft.Row(
            [
                ft.Column(
                    [
                        ft.Text(
                            "Panel de control",
                            size=28,
                            weight=ft.FontWeight.BOLD,
                            color=self.texto,
                        ),
                        ft.Text(
                            f"Gestiona tus documentos, inventario y actividad · Red local: http://{ip_red}:{puerto_red}",
                            size=14,
                            color=self.secundario,
                        ),
                        self.pendientes_texto,
                    ],
                    spacing=4,
                ),
                ft.Row(
                    fila_acciones,
                    spacing=10,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

    def panel_metricas(self) -> ft.Control:
        metricas = [
            ("PDF pendientes", "pdf", ft.Icons.DESCRIPTION),
            ("Canjes pendientes", "canjes", ft.Icons.SHOPPING_BAG),
            ("Pedidos ML", "ml", ft.Icons.LOCAL_SHIPPING),
            ("Informes", "informes", ft.Icons.INSERT_CHART),
        ]
        if self.usuario_actual and self.usuario_actual.role == "administrador":
            metricas.append(("Quiebres de stock", "quiebres", ft.Icons.WARNING_AMBER))
        tarjetas = []
        for titulo, clave, icono in metricas:
            valor = ft.Text("0", size=25, weight=ft.FontWeight.BOLD, color=self.texto)
            self.contadores[clave] = valor
            tarjetas.append(
                ft.Container(
                    expand=True,
                    bgcolor=self.superficie,
                    border=ft.Border.all(1, self.borde),
                    border_radius=12,
                    padding=16,
                    content=ft.Row(
                        [
                            ft.Container(
                                width=40,
                                height=40,
                                border_radius=10,
                                bgcolor=ft.Colors.RED_50,
                                alignment=ft.Alignment.CENTER,
                                content=ft.Icon(icono, color=ROJO, size=20),
                            ),
                            ft.Column(
                                [
                                    ft.Text(titulo, size=11, color=self.secundario),
                                    valor,
                                ],
                                spacing=3,
                            ),
                        ],
                        spacing=12,
                    ),
                )
            )
        return ft.Row(tarjetas, spacing=12)

    def panel_informes_actividad(self) -> ft.Control:
        contenido_informes = ft.Column(
            [
                ft.Row(
                    [
                        ft.Text("Informes generados", size=16, weight=ft.FontWeight.BOLD, color=self.texto),
                        ft.Icon(ft.Icons.DESCRIPTION, color=ROJO, size=18),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                self.lista_informes,
            ],
            expand=True,
            spacing=10,
        )
        contenido_actividad = ft.Column(
            [
                ft.Row(
                    [
                        ft.Text("Actividad", size=16, weight=ft.FontWeight.BOLD, color=self.texto),
                        ft.Icon(ft.Icons.BOLT, color=ROJO, size=18),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                self.actividad,
            ],
            expand=True,
            spacing=10,
        )
        return ft.Row(
            [
                self.tarjeta(contenido_informes, expand=1),
                self.tarjeta(contenido_actividad, expand=1),
            ],
            expand=True,
            spacing=16,
            vertical_alignment=ft.CrossAxisAlignment.STRETCH,
        )

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

    def crear_ventana_chat_flotante(self) -> ft.Container:
        rol_actual = self.usuario_actual.role if self.usuario_actual else "operador"
        encabezado_chat = ft.Row(
            [
                ft.Row(
                    [
                        ft.Container(
                            width=34,
                            height=34,
                            border_radius=10,
                            bgcolor=ft.Colors.RED_900 if self.modo_oscuro else ft.Colors.RED_50,
                            alignment=ft.Alignment.CENTER,
                            content=ft.Icon(
                                ft.Icons.SMART_TOY,
                                color=ft.Colors.WHITE if self.modo_oscuro else ROJO,
                                size=18,
                            ),
                        ),
                        ft.Column(
                            [
                                ft.Text(
                                    "Asistente StockAgent",
                                    size=14,
                                    weight=ft.FontWeight.BOLD,
                                    color=self.texto,
                                ),
                                ft.Row(
                                    [
                                        ft.Icon(ft.Icons.CIRCLE, color=ft.Colors.GREEN_400, size=8),
                                        ft.Text(f"Rol: {rol_actual.capitalize()} · Listo", size=10, color=self.secundario),
                                    ],
                                    spacing=4,
                                ),
                            ],
                            spacing=1,
                        ),
                    ],
                    spacing=8,
                ),
                ft.Row(
                    [
                        ft.IconButton(
                            icon=ft.Icons.DELETE_SWEEP_OUTLINED,
                            icon_color=self.secundario,
                            icon_size=18,
                            tooltip="Limpiar conversación",
                            on_click=self.limpiar_chat,
                        ),
                        ft.IconButton(
                            icon=ft.Icons.KEYBOARD_ARROW_DOWN,
                            icon_color=self.secundario,
                            icon_size=20,
                            tooltip="Minimizar",
                            on_click=self.alternar_chat_flotante,
                        ),
                        ft.IconButton(
                            icon=ft.Icons.CLOSE,
                            icon_color=self.secundario,
                            icon_size=18,
                            tooltip="Cerrar",
                            on_click=self.cerrar_chat_flotante,
                        ),
                    ],
                    spacing=0,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

        chips_def = obtener_chips_configuracion(rol_actual)
        chips_fila = ft.Row(
            [
                ft.Chip(
                    label=ft.Text(etiqueta, size=11, color=self.texto),
                    bgcolor=self.fondo,
                    on_click=lambda _e, cmd=comando: self.ejecutar_comando_rapido(cmd),
                )
                for etiqueta, comando in chips_def
            ],
            scroll=ft.ScrollMode.AUTO,
            spacing=6,
        )

        input_fila = ft.Row(
            [
                self.entrada_chat,
                ft.IconButton(
                    icon=ft.Icons.SEND,
                    icon_color=ft.Colors.WHITE,
                    bgcolor=ROJO,
                    tooltip="Enviar mensaje",
                    on_click=self.enviar_chat,
                ),
            ],
            spacing=6,
            vertical_alignment=ft.CrossAxisAlignment.END,
        )

        pie_texto = ft.Text(
            obtener_pie_ayuda(rol_actual),
            size=10,
            color=self.secundario,
        )

        self.ventana_chat_flotante = ft.Container(
            width=390,
            height=530,
            right=24,
            bottom=90,
            bgcolor=self.superficie,
            border=ft.Border.all(1, self.borde),
            border_radius=16,
            shadow=ft.BoxShadow(
                blur_radius=22,
                spread_radius=2,
                color=ft.Colors.BLACK_54 if self.modo_oscuro else ft.Colors.BLACK_26,
                offset=ft.Offset(0, 8),
            ),
            padding=14,
            visible=self.chat_visible,
            content=ft.Column(
                [
                    encabezado_chat,
                    chips_fila,
                    ft.Divider(height=10, color=self.borde),
                    self.conversacion,
                    input_fila,
                    pie_texto,
                ],
                expand=True,
                spacing=8,
            ),
        )
        return self.ventana_chat_flotante

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
        self.contadores["pdf"].value = str(len(mayoristas))
        self.contadores["canjes"].value = str(len(canjes))
        self.contadores["ml"].value = str(len(mercado_libre))
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

        total_archivados = sum(map(len, archivados))
        self.pendientes_texto.value = (
            f"Archivados: {total_archivados} · Informes: {len(informes)}"
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
            pendientes = self.orders_store.listar_pedidos_pendientes_cierre()
            recientes = self.orders_store.listar_pedidos(limit=5)
            lineas = [
                "📦 Resumen de Pedidos del Sistema:\n",
                f"• Pendientes de cierre de jornada: {len(pendientes)} pedido(s) acumulados.",
            ]
            if pendientes:
                total_items = sum(len(p.items) for p in pendientes)
                lineas.append(f"• Total renglones a descontar en cierre: {total_items} ítem(s).")
            if recientes:
                lineas.append("\nÚltimos pedidos registrados:")
                for p in recientes[:4]:
                    cli = p.cliente_nombre or "Consumidor Final"
                    nota = f" [NP: {p.nota_pedido}]" if p.nota_pedido else ""
                    est = "🟡 Pendiente" if p.estado == "pendiente" else "🟢 Cerrado"
                    lineas.append(f"• {est} {p.fecha} {p.hora} - {cli}{nota} ({len(p.items)} items)")
            lineas.append("\nPuedes cargar nuevos pedidos desde el menú 'Cargar / Armar Pedido'.")
            respuesta = "\n".join(lineas)
        elif intencion == "cierre":
            pendientes = self.orders_store.listar_pedidos_pendientes_cierre()
            ultimos_cierres = self.orders_store.listar_cierres(limit=1)
            lineas = ["🖨️ Estado de Cierre de Jornada y Descuentos:\n"]
            lineas.append(f"• Pedidos acumulados para el próximo cierre: {len(pendientes)}")
            if pendientes:
                lineas.append("  (Al realizar el cierre, estos pedidos se consolidarán e imprimirán en el informe diario).")
            else:
                lineas.append("  (No hay pedidos pendientes de cierre en este momento).")
            if ultimos_cierres:
                uc = ultimos_cierres[0]
                lineas.append("\nÚltimo cierre realizado:")
                lineas.append(f"• Fecha: {uc.fecha} {uc.hora}")
                lineas.append(f"• Responsable: {uc.usuario}")
                lineas.append(f"• Pedidos consolidados: {uc.total_pedidos} ({uc.total_articulos} artículos)")
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
        else:
            respuesta = (
                f"No reconocí la consulta.\n"
                f"{obtener_pie_ayuda(rol)}"
            )
        self.escribir_chat("Agente", respuesta)
        self.page.update()
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
        except Exception:
            detalle = traceback.format_exc()
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
            if hasattr(self.page, "overlay"):
                if self.page.overlay is None:
                    self.page.overlay = []
                if self.file_picker not in self.page.overlay:
                    self.page.overlay.append(self.file_picker)
                    self.page.update()
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
            asyncio.create_task(self._descargar_archivo_navegador(ruta))
            return
        try:
            os.startfile(ruta)  # type: ignore[attr-defined]
        except OSError as error:
            self.notificar(f"No se pudo abrir el archivo:\n{error}")

    def abrir_carpeta_informe(self, ruta: Path) -> None:
        subprocess.Popen(["explorer.exe", f"/select,{ruta}"])

    def compartir_correo(self, _evento: ft.Event | None = None, ruta_especifica: Path | None = None) -> None:
        if not self.exigir_roles(*USER_ROLES):
            return
        ruta = ruta_especifica or self.ruta_informe()
        if ruta is None:
            return
        es_pedido = ruta.name.startswith("Pedido_Fabrica")
        asunto_txt = f"Pedido a fábrica: {ruta.name}" if es_pedido else f"Informe de descuentos: {ruta.name}"
        cuerpo_txt = (
            f"Adjunto la sugerencia de pedido a fábrica {ruta.name}."
            if es_pedido
            else f"Adjunto el informe de descuentos {ruta.name}."
        )
        asunto = urllib.parse.quote(asunto_txt)
        cuerpo = urllib.parse.quote(cuerpo_txt)
        try:
            self.abrir_carpeta_informe(ruta)
            os.startfile(f"mailto:?subject={asunto}&body={cuerpo}")  # type: ignore[attr-defined]
        except OSError as error:
            self.notificar(f"No se pudo abrir el correo o el archivo:\n{error}")

    def compartir_whatsapp(self, _evento: ft.Event | None = None, ruta_especifica: Path | None = None) -> None:
        if not self.exigir_roles(*USER_ROLES):
            return
        ruta = ruta_especifica or self.ruta_informe()
        if ruta is None:
            return
        try:
            self.abrir_carpeta_informe(ruta)
            if not webbrowser.open("https://web.whatsapp.com/"):
                raise RuntimeError("No se pudo abrir WhatsApp Web.")
        except (OSError, RuntimeError) as error:
            self.notificar(f"No se pudo abrir WhatsApp o el archivo:\n{error}")

    def enviar_correo_cierre(
        self,
        destinatarios: str,
        cierre_id: int,
        archivo_pdf: Path | None,
        archivo_excel: Path | None,
        resumen_pedidos: str,
        usuario: str,
        archivo_hoja_ruta: Path | None = None,
        alerta_stock: str = "",
    ) -> None:
        dest_limpio = destinatarios.strip()
        if not dest_limpio:
            return
        guardar_correo_cierre(dest_limpio)
        fecha_str = datetime.now().strftime("%d/%m/%Y %H:%M")
        asunto_txt = f"Cierre de Jornada #{cierre_id} - {fecha_str} ({resumen_pedidos})"
        lineas_cuerpo = [
            "Estimados,",
            "",
            f"Se ha completado el Cierre de Jornada #{cierre_id} en el sistema de depósito.",
            f"• Fecha y Hora: {fecha_str}",
            f"• Responsable: {usuario}",
            f"• Resumen consolidado: {resumen_pedidos}",
            "",
            "Archivos oficiales generados:",
        ]
        if archivo_pdf and archivo_pdf.exists():
            lineas_cuerpo.append(f"• PDF Cierre de Descuentos: {archivo_pdf.name}")
        if archivo_excel and archivo_excel.exists():
            lineas_cuerpo.append(f"• Excel Descuentos: {archivo_excel.name}")
        if archivo_hoja_ruta and archivo_hoja_ruta.exists():
            lineas_cuerpo.append(f"• Manifiesto / Hoja de Ruta de Despacho: {archivo_hoja_ruta.name}")
        if alerta_stock:
            lineas_cuerpo.append("\n⚠️ ALERTAS DE INVENTARIO POST-CIERRE:")
            lineas_cuerpo.append(alerta_stock)
        lineas_cuerpo.append("\nLos archivos se encuentran guardados en el servidor de depósito.")

        cuerpo_txt = "\n".join(lineas_cuerpo)
        asunto = urllib.parse.quote(asunto_txt)
        cuerpo = urllib.parse.quote(cuerpo_txt)
        dest = urllib.parse.quote(dest_limpio.replace(";", ","))

        if archivo_pdf and archivo_pdf.exists():
            self.abrir_carpeta_informe(archivo_pdf)
        elif archivo_hoja_ruta and archivo_hoja_ruta.exists():
            self.abrir_carpeta_informe(archivo_hoja_ruta)
        elif archivo_excel and archivo_excel.exists():
            self.abrir_carpeta_informe(archivo_excel)

        try:
            os.startfile(f"mailto:{dest}?subject={asunto}&body={cuerpo}")  # type: ignore[attr-defined]
        except Exception as error:
            self.notificar(f"No se pudo abrir el cliente de correo:\n{error}")

    def mostrar_dialogo_compartir_cierre(
        self,
        cierre_id: int,
        archivo_pdf: Path | None,
        archivo_excel: Path | None,
        resumen_pedidos: str,
        usuario: str,
        archivo_hoja_ruta: Path | None = None,
    ) -> None:
        correo_input = ft.TextField(
            label="Destinatarios de correo",
            value=obtener_correo_cierre_guardado(),
            hint_text="ej: gerencia@empresa.com, deposito@empresa.com",
            prefix_icon=ft.Icons.EMAIL,
            autofocus=True,
            expand=True,
        )
        msg_error = ft.Text("", size=11, color=ft.Colors.RED_400)

        def enviar(_e: ft.Event) -> None:
            dest = (correo_input.value or "").strip()
            if not dest:
                msg_error.value = "Ingresa al menos una dirección de correo."
                self.page.update()
                return
            guardar_correo_cierre(dest)
            self.page.pop_dialog()
            self.enviar_correo_cierre(
                destinatarios=dest,
                cierre_id=cierre_id,
                archivo_pdf=archivo_pdf,
                archivo_excel=archivo_excel,
                resumen_pedidos=resumen_pedidos,
                usuario=usuario,
                archivo_hoja_ruta=archivo_hoja_ruta,
            )

        dialogo = ft.AlertDialog(
            title=ft.Row(
                [
                    ft.Icon(ft.Icons.EMAIL, color=ft.Colors.BLUE_400, size=20),
                    ft.Text(f"Enviar Cierre #{cierre_id} por Correo", weight=ft.FontWeight.BOLD, size=15),
                ],
                spacing=8,
            ),
            content=ft.Container(
                width=480,
                content=ft.Column(
                    [
                        ft.Text(f"Resumen: {resumen_pedidos}", size=12, color=self.secundario),
                        ft.Text(f"Responsable: {usuario}", size=11, color=self.secundario),
                        ft.Divider(height=10),
                        correo_input,
                        msg_error,
                    ],
                    tight=True,
                    spacing=8,
                ),
            ),
            actions=[
                ft.Button("Enviar Correo", icon=ft.Icons.SEND, bgcolor=ROJO, color=ft.Colors.WHITE, on_click=enviar),
                self.boton_dialogo("Cancelar", lambda _e: self.page.pop_dialog()),
            ],
        )
        self.page.show_dialog(dialogo)

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
        if not self.exigir_roles("administrador"):
            return
        nuevo_usuario = ft.TextField(label="Nombre de usuario")
        nueva_clave = ft.TextField(
            label="Contraseña (mínimo 10 caracteres)",
            password=True,
            can_reveal_password=True,
        )
        es_master = bool(self.usuario_actual and self.usuario_actual.role == "master")
        roles_creables = ["administrador", "operador", "consulta"] if es_master else ["operador", "consulta"]
        nuevo_rol = ft.Dropdown(
            label="Rol",
            value="consulta",
            options=[
                ft.DropdownOption(key=role, text=role.capitalize())
                for role in roles_creables
            ],
            width=220,
        )
        mensaje = ft.Text(color=ft.Colors.RED_400, size=12)
        usuarios = ft.Column(spacing=6, scroll=ft.ScrollMode.AUTO, height=240)
        crear_boton = ft.Button(
            "Crear usuario",
            icon=ft.Icons.PERSON_ADD,
            bgcolor=ROJO,
            color=ft.Colors.WHITE,
        )
        dialogo = ft.AlertDialog(
            modal=True,
            title=ft.Text("Gestión de usuarios"),
            content=ft.Column(
                [
                    nuevo_usuario,
                    nueva_clave,
                    nuevo_rol,
                    mensaje,
                    crear_boton,
                    ft.Divider(),
                    usuarios,
                ],
                tight=True,
                width=520,
            ),
            actions=[
                self.boton_dialogo("Cerrar", lambda _e: self.page.pop_dialog())
            ],
        )

        def actualizar_lista() -> None:
            usuarios.controls.clear()
            actual = self.usuario_actual
            actual_es_master = bool(actual and actual.role == "master")
            roles_asignables = (
                ["administrador", "operador", "consulta"]
                if actual_es_master
                else ["operador", "consulta"]
            )
            for usuario in self.user_store.list_users(include_master=actual_es_master):
                if not actual_es_master and usuario.role == "master":
                    continue
                es_propio = actual is not None and usuario.id == actual.id
                es_target_master = usuario.role == "master"
                es_target_admin = usuario.role == "administrador"
                no_puede_editar = es_propio or es_target_master or (es_target_admin and not actual_es_master)

                selector_rol = ft.Dropdown(
                    value=usuario.role,
                    options=[
                        ft.DropdownOption(key=role, text=role.capitalize())
                        for role in (USER_ROLES if es_target_master else roles_asignables)
                    ],
                    width=160,
                    disabled=no_puede_editar,
                )
                boton_estado = ft.TextButton(
                    "Desactivar" if usuario.active else "Activar",
                    on_click=lambda _e, user_id=usuario.id, active=not usuario.active: cambiar_estado(
                        user_id, active
                    ),
                    disabled=no_puede_editar,
                )
                selector_rol.on_select = lambda _e, user_id=usuario.id, dropdown=selector_rol: cambiar_rol(
                    user_id, dropdown.value or ""
                )
                usuarios.controls.append(
                    ft.Row(
                        [
                            ft.Text(
                                f"{usuario.username}{' (inactivo)' if not usuario.active else ''}",
                                expand=True,
                            ),
                            selector_rol,
                            boton_estado,
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    )
                )

        def cambiar_rol(user_id: int, role: str) -> None:
            if not self.exigir_roles("administrador"):
                return
            try:
                self.user_store.update_role(
                    user_id,
                    role,
                    updater_role=self.usuario_actual.role if self.usuario_actual else None,
                )
                mensaje.value = ""
            except (ValueError, UserStoreError) as error:
                mensaje.value = str(error)
            actualizar_lista()
            self.page.update()

        def cambiar_estado(user_id: int, active: bool) -> None:
            if not self.exigir_roles("administrador"):
                return
            try:
                self.user_store.set_active(
                    user_id,
                    active,
                    updater_role=self.usuario_actual.role if self.usuario_actual else None,
                )
                mensaje.value = ""
            except UserStoreError as error:
                mensaje.value = str(error)
            actualizar_lista()
            self.page.update()

        def crear_usuario(_evento: ft.Event) -> None:
            if not self.exigir_roles("administrador"):
                return
            try:
                self.user_store.create_user(
                    nuevo_usuario.value or "",
                    nueva_clave.value or "",
                    nuevo_rol.value or "",
                    creator_role=self.usuario_actual.role if self.usuario_actual else None,
                )
            except (ValueError, UserStoreError) as error:
                mensaje.value = str(error)
            else:
                nuevo_usuario.value = ""
                nueva_clave.value = ""
                mensaje.value = "Usuario creado."
            actualizar_lista()
            self.page.update()

        crear_boton.on_click = crear_usuario
        actualizar_lista()
        self.page.show_dialog(dialogo)

    def mostrar_crear_pedido(self, _evento: ft.Event | None = None) -> None:
        if self.usuario_actual is None or self.usuario_actual.role != "operador":
            self.notificar("La carga de pedidos en tiempo real es una función exclusiva del rol operador.")
            return

        remito_factura_input = ft.TextField(
            label="Remito / Factura",
            autofocus=True,
            expand=True,
        )
        clientes_actuales = self.order_store.listar_nombres_clientes()
        selector_cliente = ft.Dropdown(
            label="Cliente",
            options=[ft.DropdownOption(key=c, text=c) for c in clientes_actuales],
            expand=True,
            value=clientes_actuales[0] if clientes_actuales else None,
        )

        def abrir_nuevo_cliente(_e: ft.Event) -> None:
            nombre_cliente_input = ft.TextField(
                label="Nombre o Razón Social del Cliente",
                autofocus=True,
            )
            error_cliente = ft.Text("", color=ft.Colors.RED_400, size=12)

            def guardar_cliente(_ev: ft.Event) -> None:
                nom = (nombre_cliente_input.value or "").strip()
                if not nom:
                    error_cliente.value = "Ingresa un nombre de cliente."
                    self.page.update()
                    return
                try:
                    self.order_store.crear_cliente(nom)
                    nuevos_clientes = self.order_store.listar_nombres_clientes()
                    selector_cliente.options = [
                        ft.DropdownOption(key=c, text=c) for c in nuevos_clientes
                    ]
                    selector_cliente.value = nom
                    self.page.pop_dialog()
                    self.page.update()
                except Exception as err:
                    error_cliente.value = str(err)
                    self.page.update()

            dlg_cliente = ft.AlertDialog(
                title=ft.Text("Nuevo Cliente"),
                content=ft.Column([nombre_cliente_input, error_cliente], tight=True, width=380),
                actions=[
                    ft.Button(
                        "Guardar Cliente",
                        bgcolor=ROJO,
                        color=ft.Colors.WHITE,
                        on_click=guardar_cliente,
                    ),
                    self.boton_dialogo("Cancelar", lambda _e: self.page.pop_dialog()),
                ],
            )
            self.page.show_dialog(dlg_cliente)

        boton_nuevo_cliente = ft.IconButton(
            icon=ft.Icons.PERSON_ADD,
            tooltip="Dar de alta un nuevo cliente",
            on_click=abrir_nuevo_cliente,
        )

        bultos_input = ft.TextField(
            label="Cantidad de bultos",
            value="1",
            keyboard_type=ft.KeyboardType.NUMBER,
            expand=True,
        )
        selector_logistica = ft.Dropdown(
            label="Tipo de Logística",
            value="Domicilio",
            options=[ft.DropdownOption(key=op, text=op) for op in LOGISTICA_OPCIONES],
            expand=True,
        )

        def fecha_seleccionada(_e: ft.Event) -> None:
            val = date_picker.value
            if val:
                if hasattr(val, "strftime"):
                    fecha_retiro_input.value = val.strftime("%d/%m/%Y")
                else:
                    fecha_retiro_input.value = str(val)[:10]
            self.page.update()

        date_picker = ft.DatePicker(
            on_change=fecha_seleccionada,
            help_text="Seleccionar fecha de retiro",
            confirm_text="Aceptar",
            cancel_text="Cancelar",
        )

        def abrir_calendario(_e: ft.Event) -> None:
            self.page.show_dialog(date_picker)

        def limpiar_fecha(_e: ft.Event) -> None:
            fecha_retiro_input.value = ""
            self.page.update()

        fecha_retiro_input = ft.TextField(
            label="Fecha de retiro (opcional)",
            hint_text="Sin fecha asignada",
            read_only=True,
            expand=True,
            on_click=abrir_calendario,
        )
        fila_fecha_retiro = ft.Row(
            [
                fecha_retiro_input,
                ft.IconButton(
                    icon=ft.Icons.CALENDAR_MONTH,
                    tooltip="Seleccionar fecha de retiro en calendario",
                    on_click=abrir_calendario,
                ),
                ft.IconButton(
                    icon=ft.Icons.BACKSPACE_OUTLINED,
                    tooltip="Quitar fecha de retiro",
                    on_click=limpiar_fecha,
                ),
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=4,
        )

        armador_nom = self.usuario_actual.username if self.usuario_actual else "Operario"
        armador_input = ft.TextField(
            label="Armador responsable",
            value=armador_nom,
            read_only=True,
            disabled=True,
            expand=True,
        )
        agregado_check = ft.Checkbox(
            label="Agregado",
            value=False,
        )

        ruta_comprobante: list[Path] = []
        texto_archivo = ft.Text(
            "Ningún comprobante seleccionado (.pdf o .xlsx/.xls)",
            size=12,
            color=self.secundario,
        )

        async def seleccionar_comprobante(_e: ft.Event) -> None:
            try:
                archivos = await self.subir_archivos_desde_pc(
                    carpeta_destino=application_root() / "data" / "pedidos_archivos",
                    extensiones=["pdf", "xlsx", "xls"],
                    titulo="Seleccionar Comprobante de Pedido",
                )
                if archivos:
                    arch_candidato = archivos[0]
                    hash_candidato = calcular_hash_archivo(arch_candidato)
                    if hash_candidato:
                        duplicado = self.order_store.buscar_pedido_por_hash(hash_candidato)
                        if duplicado:
                            ruta_comprobante.clear()
                            texto_archivo.value = f"⛔ DUPLICADO: {arch_candidato.name}"
                            texto_archivo.color = ft.Colors.RED_400
                            mensaje_error.value = (
                                f"⛔ ATENCIÓN: El contenido de este archivo ya fue procesado el {duplicado.created_at[:16]} "
                                f"(Comprobante: {duplicado.nota_pedido}, Cliente: {duplicado.cliente})."
                            )
                            self.page.update()
                            return

                    ruta_comprobante.clear()
                    ruta_comprobante.append(arch_candidato)
                    texto_archivo.value = f"Comprobante: {arch_candidato.name}"
                    texto_archivo.color = ft.Colors.GREEN_400
                    mensaje_error.value = ""
                    self.page.update()
            except Exception as err:
                mensaje_error.value = f"Error al seleccionar comprobante: {err}"
                self.page.update()

        boton_archivo = ft.Button(
            "Adjuntar Comprobante",
            icon=ft.Icons.ATTACH_FILE,
            bgcolor=ft.Colors.BLUE_GREY_800 if self.modo_oscuro else ft.Colors.BLUE_GREY_100,
            color=self.texto,
            on_click=seleccionar_comprobante,
        )

        contenedor_comprobante = ft.Container(
            bgcolor=ft.Colors.BLUE_GREY_900 if self.modo_oscuro else ft.Colors.GREY_100,
            border=ft.Border.all(1, self.borde),
            border_radius=10,
            padding=12,
            content=ft.Column(
                [
                    ft.Text(
                        "Comprobante adjunto (.pdf o .xlsx/.xls)",
                        size=12,
                        color=self.secundario,
                        weight=ft.FontWeight.W_500,
                    ),
                    ft.Row(
                        [boton_archivo, ft.Container(content=texto_archivo, expand=True)],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=12,
                    ),
                ],
                spacing=8,
            ),
        )

        mensaje_error = ft.Text("", color=ft.Colors.RED_400, size=12)

        async def confirmar_pedido(_e: ft.Event) -> None:
            remito = (remito_factura_input.value or "").strip()
            cli = selector_cliente.value or ""
            log = selector_logistica.value or ""
            f_retiro = (fecha_retiro_input.value or "").strip()
            es_agregado = bool(agregado_check.value)

            try:
                bultos_val = int(bultos_input.value or "1")
                if bultos_val < 1:
                    bultos_val = 1
            except ValueError:
                bultos_val = 1

            if not remito:
                mensaje_error.value = "Debes ingresar el Remito / Factura."
                self.page.update()
                return
            if self.order_store.existe_nota_pedido(remito):
                mensaje_error.value = f"El comprobante '{remito}' ya fue registrado previamente."
                self.page.update()
                return
            if not cli:
                mensaje_error.value = "Debes seleccionar o crear un Cliente."
                self.page.update()
                return
            if not ruta_comprobante:
                mensaje_error.value = "Debes adjuntar el comprobante (.pdf o .xlsx/.xls)."
                self.page.update()
                return

            archivo_path = ruta_comprobante[0]
            hash_comprobante = calcular_hash_archivo(archivo_path)
            if hash_comprobante:
                duplicado = self.order_store.buscar_pedido_por_hash(hash_comprobante)
                if duplicado:
                    mensaje_error.value = (
                        f"⛔ ALERTA DUPLICADO: Este archivo ya fue procesado el {duplicado.created_at[:16]} "
                        f"(Comprobante: {duplicado.nota_pedido}, Cliente: {duplicado.cliente})."
                    )
                    self.page.update()
                    return

            self.page.pop_dialog()
            ext = archivo_path.suffix.lower()
            tipo_archivo = "pdf" if ext == ".pdf" else "excel"

            def ejecutar_descuento_pedido() -> None:
                stock_mgr = StockManager(ruta_excel_base=self.menu.ruta_excel_base)
                agente = AgenteRemitosStock(stock_manager=stock_mgr)
                if tipo_archivo == "pdf":
                    reporte = agente.ejecutar(
                        rutas_pdf=[archivo_path],
                        carpeta_descuentos=self.menu.carpeta_descuentos,
                        simulacion=False,
                    )
                else:
                    reporte = agente.ejecutar(
                        rutas_canjes=[archivo_path],
                        carpeta_descuentos=self.menu.carpeta_descuentos,
                        simulacion=False,
                    )

                # Persistir la actualización de saldos en SQLite y registrar historial
                nombre_inf = Path(reporte.reporte_stock.archivo_guardado).name if reporte.reporte_stock.archivo_guardado else f"Pedido_{remito}"
                stock_mgr.actualizar_stock_base(
                    descuentos=reporte.reporte_stock.descuentos_aplicados,
                    sincronizar_excel=False,
                    nombre_archivo=nombre_inf,
                    usuario=armador_nom,
                )

                pdf_nom = Path(reporte.reporte_stock.archivo_pdf).name if reporte.reporte_stock.archivo_pdf else ""

                total_descontado = sum(
                    d.cantidad_descontada for d in reporte.reporte_stock.descuentos_aplicados
                )
                resumen_items = f"{len(reporte.reporte_stock.descuentos_aplicados)} productos ({total_descontado} un.)"
                items_descontados = [
                    (d.codigo, d.nombre_producto, d.cantidad_descontada)
                    for d in reporte.reporte_stock.descuentos_aplicados
                ]
                self.order_store.registrar_pedido(
                    nota_pedido=remito,
                    numero_pedido="",
                    cliente=cli,
                    bultos=bultos_val,
                    logistica=log,
                    armador=armador_nom,
                    tipo_archivo=tipo_archivo,
                    nombre_archivo=archivo_path.name,
                    agregado=es_agregado,
                    articulos_descontados=total_descontado,
                    resumen_items=resumen_items,
                    fecha_retiro=f_retiro,
                    archivo_descuento=pdf_nom,
                    items=items_descontados,
                    archivo_hash=hash_comprobante,
                )
                self.actualizar_listas()
                print(f"[PEDIDO REGISTRADO] Remito/Factura: {remito} | Cliente: {cli} | Descontados: {resumen_items} | Retiro: {f_retiro} | PDF: {pdf_nom}")

            await self.ejecutar_tarea(f"Remito #{remito} ({cli})", ejecutar_descuento_pedido)

        dialogo = ft.AlertDialog(
            modal=True,
            title=ft.Text("Cargar y Armar Pedido", weight=ft.FontWeight.BOLD),
            content=ft.Container(
                width=500,
                content=ft.Column(
                    [
                        remito_factura_input,
                        ft.Row(
                            [selector_cliente, boton_nuevo_cliente],
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=6,
                        ),
                        bultos_input,
                        selector_logistica,
                        fila_fecha_retiro,
                        armador_input,
                        agregado_check,
                        contenedor_comprobante,
                        mensaje_error,
                    ],
                    tight=True,
                    spacing=14,
                    scroll=ft.ScrollMode.AUTO,
                ),
            ),
            actions=[
                ft.Button(
                    "Confirmar y Descontar",
                    icon=ft.Icons.CHECK_CIRCLE,
                    bgcolor=ROJO,
                    color=ft.Colors.WHITE,
                    on_click=confirmar_pedido,
                ),
                self.boton_dialogo("Cancelar", lambda _e: self.page.pop_dialog()),
            ],
        )
        self.page.show_dialog(dialogo)

    def mostrar_historial_pedidos(self, _evento: ft.Event | None = None) -> None:
        if self.usuario_actual is None or self.usuario_actual.role not in ("operador", "administrador", "master"):
            self.notificar("No tienes permisos suficientes para acceder al historial de pedidos.")
            return

        pedidos = self.order_store.listar_pedidos(limit=400)
        items_lista = ft.ListView(expand=True, spacing=8)

        def formatear_fecha_corta(f_str: str) -> str:
            try:
                partes = f_str.split("-")
                if len(partes) == 3:
                    return f"{partes[2]}/{partes[1]}/{partes[0]}"
            except Exception:
                pass
            return f_str

        def coincide(p: Pedido, q: str) -> bool:
            if not q:
                return True
            q = q.lower().strip()
            if q in (p.cliente or "").lower():
                return True
            if q in (p.nota_pedido or "").lower():
                return True
            num_ped = str(getattr(p, "numero_pedido", "") or "").lower()
            if q in num_ped:
                return True
            if q in (p.armador or "").lower():
                return True
            if q in (p.logistica or "").lower():
                return True
            c_at = p.created_at or ""
            if q in c_at.lower():
                return True
            f_corta = formatear_fecha_corta(c_at[:10])
            if q in f_corta.lower():
                return True
            f_ret = str(getattr(p, "fecha_retiro", "") or "").lower()
            if q in f_ret:
                return True
            if q in (p.nombre_archivo or "").lower():
                return True
            return False

        texto_contador = ft.Text(f"Total: {len(pedidos)} pedidos" if pedidos else "", size=11, color=self.secundario)

        def recargar_y_actualizar() -> None:
            nonlocal pedidos
            pedidos = self.order_store.listar_pedidos(limit=400)
            actualizar_vista(campo_busqueda.value or "")

        def actualizar_vista(termino: str = "") -> None:
            filtrados = [p for p in pedidos if coincide(p, termino)]
            items_lista.controls.clear()

            if not filtrados:
                if not pedidos:
                    items_lista.controls.append(
                        ft.Container(
                            padding=30,
                            alignment=ft.Alignment.CENTER,
                            content=ft.Text("Aún no se han registrado pedidos en el sistema.", color=self.secundario, size=13),
                        )
                    )
                else:
                    items_lista.controls.append(
                        ft.Container(
                            padding=30,
                            alignment=ft.Alignment.CENTER,
                            content=ft.Column(
                                [
                                    ft.Icon(ft.Icons.SEARCH_OFF, size=34, color=self.secundario),
                                    ft.Text(f"No se encontraron pedidos para '{termino}'.", color=self.secundario, size=13),
                                ],
                                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                spacing=6,
                            ),
                        )
                    )
                texto_contador.value = f"0 de {len(pedidos)} pedidos"
                if self.page:
                    self.page.update()
                return

            texto_contador.value = (
                f"Mostrando {len(filtrados)} de {len(pedidos)} pedidos"
                if termino.strip()
                else f"Total: {len(pedidos)} pedidos"
            )

            pedidos_por_fecha: dict[str, list[Pedido]] = {}
            for p in filtrados:
                f_clave = p.created_at[:10] if p.created_at else "Sin fecha"
                pedidos_por_fecha.setdefault(f_clave, []).append(p)

            for f_clave, pedidos_grupo in pedidos_por_fecha.items():
                cant = len(pedidos_grupo)
                texto_cant = "1 pedido armado" if cant == 1 else f"{cant} pedidos armados"
                fecha_legible = formatear_fecha_corta(f_clave)

                encabezado_fecha = ft.Container(
                    bgcolor=ft.Colors.BLUE_GREY_900 if self.modo_oscuro else ft.Colors.BLUE_GREY_50,
                    border=ft.Border.all(1, ft.Colors.BLUE_GREY_700 if self.modo_oscuro else ft.Colors.BLUE_GREY_200),
                    border_radius=8,
                    padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                    margin=ft.Margin.only(top=8, bottom=2),
                    content=ft.Row(
                        [
                            ft.Row(
                                [
                                    ft.Icon(ft.Icons.CALENDAR_MONTH, size=16, color=ROJO),
                                    ft.Text(f"Fecha: {fecha_legible}", weight=ft.FontWeight.BOLD, size=13, color=self.texto),
                                ],
                                spacing=8,
                            ),
                            ft.Container(
                                content=ft.Text(texto_cant, size=11, weight=ft.FontWeight.W_500, color=ft.Colors.WHITE),
                                bgcolor=ROJO,
                                padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                                border_radius=12,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                )
                items_lista.controls.append(encabezado_fecha)

                for p in pedidos_grupo:
                    if getattr(p, "numero_pedido", ""):
                        num_ped_txt = f"Pedido #{p.numero_pedido} · Remito: {p.nota_pedido}"
                    else:
                        num_ped_txt = f"Remito / Factura: {p.nota_pedido}"
                    etiqueta_agregado = (
                        ft.Container(
                            content=ft.Text(
                                "AGREGADO",
                                size=10,
                                weight=ft.FontWeight.BOLD,
                                color=ft.Colors.AMBER_800 if not self.modo_oscuro else ft.Colors.AMBER_300,
                            ),
                            bgcolor=ft.Colors.AMBER_100 if not self.modo_oscuro else ft.Colors.AMBER_900,
                            padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                            border_radius=4,
                        )
                        if getattr(p, "agregado", False)
                        else ft.Container()
                    )
                    etiqueta_anulado = (
                        ft.Container(
                            content=ft.Text(
                                "ANULADO",
                                size=10,
                                weight=ft.FontWeight.BOLD,
                                color=ft.Colors.WHITE,
                            ),
                            bgcolor=ft.Colors.RED_600,
                            padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                            border_radius=4,
                        )
                        if getattr(p, "estado", "") == "anulado"
                        else ft.Container()
                    )
                    hora_txt = p.created_at[11:16] if len(p.created_at) >= 16 else p.created_at

                    boton_rotulo_hist = ft.IconButton(
                        icon=ft.Icons.QR_CODE_2,
                        tooltip="Imprimir Rótulos de Bultos con QR",
                        icon_color=ft.Colors.AMBER_700 if not self.modo_oscuro else ft.Colors.AMBER_400,
                        on_click=lambda _e, ped=p: self.imprimir_rotulos_pedido(ped),
                    )
                    boton_anular_hist = (
                        ft.IconButton(
                            icon=ft.Icons.CANCEL_OUTLINED,
                            tooltip="Anular este pedido",
                            icon_color=ft.Colors.RED_400,
                            on_click=lambda _e, ped=p: self.confirmar_anulacion_pedido(ped, al_final=recargar_y_actualizar),
                        )
                        if (self.usuario_actual and self.usuario_actual.role in ("administrador", "master") and p.estado != "anulado")
                        else ft.Container()
                    )

                    items_lista.controls.append(
                        ft.Container(
                            bgcolor=self.fondo_acento if self.modo_oscuro else ft.Colors.GREY_50,
                            border=ft.Border.all(1, self.borde),
                            border_radius=8,
                            padding=10,
                            content=ft.Row(
                                [
                                    ft.Column(
                                        [
                                            ft.Row(
                                                [
                                                    ft.Row(
                                                        [
                                                            ft.Text(num_ped_txt, weight=ft.FontWeight.BOLD, size=14, color=self.texto),
                                                            etiqueta_agregado,
                                                            etiqueta_anulado,
                                                        ],
                                                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                                        spacing=8,
                                                    ),
                                                    ft.Text(f"Hora: {hora_txt}", size=11, color=self.secundario),
                                                ],
                                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                            ),
                                            ft.Row(
                                                [
                                                    ft.Text(f"Cliente: {p.cliente}", size=12, weight=ft.FontWeight.W_500, color=self.texto),
                                                    ft.Text(f"Logística: {p.logistica}", size=12, color=self.secundario),
                                                    ft.Text(f"Bultos: {p.bultos}", size=12, color=self.secundario),
                                                    *(
                                                        [ft.Text(f"Retiro: {p.fecha_retiro}", size=12, weight=ft.FontWeight.W_500, color=ft.Colors.AMBER_400 if self.modo_oscuro else ft.Colors.AMBER_800)]
                                                        if getattr(p, "fecha_retiro", "")
                                                        else []
                                                    ),
                                                ],
                                                spacing=16,
                                            ),
                                            ft.Row(
                                                [
                                                    ft.Text(f"Armador: {p.armador}", size=11, color=self.secundario),
                                                    ft.Text(f"Archivo: {p.nombre_archivo}", size=11, color=self.secundario),
                                                    ft.Text(f"Descuento: {p.resumen_items}", size=11, weight=ft.FontWeight.W_500, color=ft.Colors.GREEN_400),
                                                ],
                                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                            ),
                                        ],
                                        spacing=4,
                                        expand=True,
                                    ),
                                    ft.Row([boton_rotulo_hist, boton_anular_hist], spacing=2),
                                ],
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                        )
                    )
            if self.page:
                self.page.update()

        campo_busqueda = ft.TextField(
            hint_text="Buscar por cliente, remito / nota, N° pedido, fecha (DD/MM/AAAA) o armador...",
            prefix_icon=ft.Icons.SEARCH,
            dense=True,
            content_padding=ft.Padding.symmetric(horizontal=12, vertical=8),
            bgcolor=self.fondo,
            border_color=self.borde,
            color=self.texto,
            expand=True,
            on_change=lambda e: actualizar_vista(campo_busqueda.value or ""),
        )

        def limpiar_busqueda(_e: ft.Event) -> None:
            campo_busqueda.value = ""
            actualizar_vista("")

        barra_busqueda = ft.Row(
            [
                campo_busqueda,
                ft.IconButton(
                    icon=ft.Icons.CLEAR,
                    icon_size=18,
                    icon_color=self.secundario,
                    tooltip="Borrar búsqueda",
                    on_click=limpiar_busqueda,
                ),
            ],
            spacing=6,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        actualizar_vista("")

        dialogo = ft.AlertDialog(
            title=ft.Row(
                [
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.RECEIPT_LONG, color=ROJO, size=22),
                            ft.Text("Historial de Pedidos", weight=ft.FontWeight.BOLD),
                        ],
                        spacing=8,
                    ),
                    texto_contador,
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            content=ft.Container(
                width=720,
                height=520,
                content=ft.Column(
                    [
                        barra_busqueda,
                        ft.Divider(height=10, color=self.borde),
                        items_lista,
                    ],
                    expand=True,
                    spacing=6,
                ),
            ),
            actions=[
                self.boton_dialogo("Cerrar", lambda _e: self.page.pop_dialog())
            ],
        )
        self.page.show_dialog(dialogo)

    def mostrar_imprimir_descuentos(self, _evento: ft.Event | None = None) -> None:
        if self.usuario_actual is None or self.usuario_actual.role != "operador":
            self.notificar("La impresión de descuentos es una función exclusiva del rol operador.")
            return

        pedidos = self.order_store.listar_pedidos(limit=200)

        todos_informes = self.menu._obtener_generados()
        informes_descuento_pdf = [
            r for r in sorted(todos_informes, key=lambda x: x.stat().st_mtime_ns, reverse=True)
            if r.name.startswith("Descuento") and r.suffix.lower() == ".pdf"
        ]

        ultimo_pdf: Path | None = informes_descuento_pdf[0] if informes_descuento_pdf else None

        items_contenido = ft.ListView(expand=True, spacing=10)

        if ultimo_pdf:
            items_contenido.controls.append(
                ft.Container(
                    bgcolor=ROJO,
                    border_radius=8,
                    padding=12,
                    content=ft.Row(
                        [
                            ft.Column(
                                [
                                    ft.Text("ÚLTIMO DESCUENTO GENERADO", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE_70),
                                    ft.Text(ultimo_pdf.name, size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                                ],
                                spacing=2,
                                expand=True,
                            ),
                            ft.Button(
                                "Imprimir / Abrir PDF",
                                icon=ft.Icons.PRINT,
                                bgcolor=ft.Colors.WHITE,
                                color=ROJO,
                                on_click=lambda _e, r=ultimo_pdf: self.abrir_informe(ruta_especifica=r),
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                )
            )

        items_contenido.controls.append(
            ft.Text("Lista de Pedidos Descontados", size=14, weight=ft.FontWeight.BOLD, color=self.texto)
        )

        if not pedidos:
            items_contenido.controls.append(
                ft.Text("Aún no hay pedidos descontados para mostrar o imprimir.", color=self.secundario, size=13)
            )
        else:
            for p in pedidos:
                if getattr(p, "numero_pedido", ""):
                    num_ped_txt = f"Pedido #{p.numero_pedido} · Remito: {p.nota_pedido}"
                else:
                    num_ped_txt = f"Remito / Factura: {p.nota_pedido}"

                pdf_archivo: Path | None = None
                if getattr(p, "archivo_descuento", ""):
                    candidato = self.menu.carpeta_descuentos / p.archivo_descuento
                    if candidato.exists():
                        pdf_archivo = candidato
                if not pdf_archivo and ultimo_pdf:
                    pdf_archivo = ultimo_pdf

                boton_rotulo = ft.IconButton(
                    icon=ft.Icons.QR_CODE_2,
                    tooltip="Imprimir Rótulos de Bultos con QR",
                    icon_color=ft.Colors.AMBER_700 if not self.modo_oscuro else ft.Colors.AMBER_400,
                    on_click=lambda _e, ped=p: self.imprimir_rotulos_pedido(ped),
                )
                boton_imprimir = (
                    ft.IconButton(
                        icon=ft.Icons.PRINT,
                        tooltip="Abrir / Imprimir informe PDF de este descuento",
                        icon_color=ROJO,
                        on_click=(lambda _e, r=pdf_archivo: self.abrir_informe(ruta_especifica=r)) if pdf_archivo else None,
                    )
                    if pdf_archivo
                    else ft.Container()
                )

                items_contenido.controls.append(
                    ft.Container(
                        bgcolor=self.fondo_acento if self.modo_oscuro else ft.Colors.GREY_50,
                        border=ft.Border.all(1, self.borde),
                        border_radius=8,
                        padding=10,
                        content=ft.Row(
                            [
                                ft.Column(
                                    [
                                        ft.Row(
                                            [
                                                ft.Text(num_ped_txt, weight=ft.FontWeight.BOLD, size=13, color=self.texto),
                                                ft.Text(f"Cliente: {p.cliente}", size=12, weight=ft.FontWeight.W_500, color=self.texto),
                                            ],
                                            spacing=12,
                                        ),
                                        ft.Row(
                                            [
                                                ft.Text(f"Logística: {p.logistica}", size=11, color=self.secundario),
                                                ft.Text(f"Bultos: {p.bultos}", size=11, color=self.secundario),
                                                ft.Text(f"Descuento: {p.resumen_items}", size=11, weight=ft.FontWeight.W_500, color=ft.Colors.GREEN_400),
                                                ft.Text(f"Fecha: {p.created_at[:16]}", size=11, color=self.secundario),
                                            ],
                                            spacing=12,
                                        ),
                                    ],
                                    spacing=4,
                                    expand=True,
                                ),
                                ft.Row([boton_rotulo, boton_imprimir], spacing=2),
                            ],
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                    )
                )

        dialogo = ft.AlertDialog(
            title=ft.Row(
                [
                    ft.Icon(ft.Icons.PRINT, color=ROJO),
                    ft.Text("Imprimir Descuentos de Pedidos", weight=ft.FontWeight.BOLD),
                ],
                spacing=8,
            ),
            content=ft.Container(
                width=680,
                height=480,
                content=items_contenido,
            ),
            actions=[
                self.boton_dialogo("Cerrar", lambda _e: self.page.pop_dialog())
            ],
        )
        self.page.show_dialog(dialogo)

    def mostrar_cierre_jornada(self, _evento: ft.Event | None = None) -> None:
        if self.usuario_actual is None or self.usuario_actual.role != "operador":
            self.notificar("El cierre de jornada es una función exclusiva del rol operador.")
            return

        pedidos_pendientes = self.order_store.listar_pedidos_pendientes_cierre()
        cierres_anteriores = self.order_store.listar_cierres(limit=25)

        items_pendientes = ft.ListView(expand=True, spacing=6)
        total_articulos_pendientes = sum(p.articulos_descontados for p in pedidos_pendientes)

        if not pedidos_pendientes:
            items_pendientes.controls.append(
                ft.Container(
                    bgcolor=ft.Colors.GREEN_900 if self.modo_oscuro else ft.Colors.GREEN_50,
                    border=ft.Border.all(1, ft.Colors.GREEN_700 if self.modo_oscuro else ft.Colors.GREEN_300),
                    border_radius=8,
                    padding=12,
                    content=ft.Row(
                        [
                            ft.Icon(ft.Icons.CHECK_CIRCLE, color=ft.Colors.GREEN_400),
                            ft.Text(
                                "No hay pedidos pendientes de cierre. Todos los pedidos armados ya fueron incluidos en cierres anteriores.",
                                size=12,
                                color=self.texto,
                                expand=True,
                            ),
                        ],
                        spacing=10,
                    ),
                )
            )
        else:
            for p in pedidos_pendientes:
                if getattr(p, "numero_pedido", ""):
                    num_ped_txt = f"Pedido #{p.numero_pedido} · Remito: {p.nota_pedido}"
                else:
                    num_ped_txt = f"Remito / Factura: {p.nota_pedido}"
                items_pendientes.controls.append(
                    ft.Container(
                        bgcolor=self.fondo_acento if self.modo_oscuro else ft.Colors.GREY_50,
                        border=ft.Border.all(1, self.borde),
                        border_radius=6,
                        padding=8,
                        content=ft.Row(
                            [
                                ft.Column(
                                    [
                                        ft.Row(
                                            [
                                                ft.Text(num_ped_txt, weight=ft.FontWeight.BOLD, size=12, color=self.texto),
                                                ft.Text(f"Cliente: {p.cliente}", size=11, color=self.texto),
                                            ],
                                            spacing=10,
                                        ),
                                        ft.Row(
                                            [
                                                ft.Text(f"Bultos: {p.bultos}", size=11, color=self.secundario),
                                                ft.Text(f"Logística: {p.logistica}", size=11, color=self.secundario),
                                                ft.Text(f"Descuento: {p.resumen_items}", size=11, color=ft.Colors.GREEN_400),
                                            ],
                                            spacing=10,
                                        ),
                                    ],
                                    spacing=2,
                                    expand=True,
                                ),
                                ft.Text(p.created_at[11:16], size=11, color=self.secundario),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                    )
                )

        lista_cierres = ft.ListView(expand=True, spacing=6)
        if not cierres_anteriores:
            lista_cierres.controls.append(
                ft.Text("Aún no se han ejecutado cierres de jornada.", size=12, color=self.secundario)
            )
        else:
            for c in cierres_anteriores:
                pdf_ruta = self.menu.carpeta_descuentos / c.archivo_pdf if c.archivo_pdf else None
                xls_ruta = self.menu.carpeta_descuentos / c.archivo_excel if c.archivo_excel else None
                hoja_ruta = self.menu.carpeta_descuentos / c.archivo_hoja_ruta if c.archivo_hoja_ruta else None

                def abrir_o_generar_hoja_ruta(cierre_obj=c, hr_path=hoja_ruta) -> None:
                    if hr_path and hr_path.exists():
                        self.abrir_informe(ruta_especifica=hr_path)
                    else:
                        peds = self.order_store.obtener_pedidos_por_cierre(cierre_obj.id)
                        if not peds:
                            self.notificar("No se encontraron registros de pedidos para generar la hoja de ruta de este cierre.")
                            return
                        nueva_hr = generar_hoja_ruta_pdf(
                            cierre_id=cierre_obj.id,
                            pedidos=peds,
                            usuario=cierre_obj.usuario,
                            carpeta_destino=self.menu.carpeta_descuentos,
                        )
                        self.order_store.actualizar_hoja_ruta_cierre(cierre_obj.id, nueva_hr.name)
                        self.abrir_informe(ruta_especifica=nueva_hr)

                boton_hoja_ruta_cierre = ft.IconButton(
                    icon=ft.Icons.LOCAL_SHIPPING,
                    tooltip="Ver / Imprimir Hoja de Ruta de Despacho",
                    icon_color=ft.Colors.TEAL_400 if self.modo_oscuro else ft.Colors.TEAL_700,
                    on_click=lambda _e, cierre_obj=c, hr_path=hoja_ruta: abrir_o_generar_hoja_ruta(cierre_obj, hr_path),
                )
                boton_imprimir_cierre = (
                    ft.IconButton(
                        icon=ft.Icons.PRINT,
                        tooltip="Imprimir / Abrir PDF de este cierre",
                        icon_color=ROJO,
                        on_click=(lambda _e, r=pdf_ruta: self.abrir_informe(ruta_especifica=r)) if (pdf_ruta and pdf_ruta.exists()) else None,
                    )
                    if (pdf_ruta and pdf_ruta.exists())
                    else ft.Container()
                )
                boton_correo_cierre = (
                    ft.IconButton(
                        icon=ft.Icons.EMAIL_OUTLINED,
                        tooltip="Enviar este cierre por correo",
                        icon_color=ft.Colors.BLUE_400,
                        on_click=(
                            lambda _e, cid=c.id, pdf=pdf_ruta, xls=xls_ruta, res=c.resumen_pedidos, usr=c.usuario, hr=hoja_ruta:
                            self.mostrar_dialogo_compartir_cierre(cid, pdf, xls, res, usr, hr)
                        ),
                    )
                    if ((pdf_ruta and pdf_ruta.exists()) or (xls_ruta and xls_ruta.exists()) or (hoja_ruta and hoja_ruta.exists()))
                    else ft.Container()
                )
                lista_cierres.controls.append(
                    ft.Container(
                        bgcolor=self.fondo_acento if self.modo_oscuro else ft.Colors.GREY_50,
                        border=ft.Border.all(1, self.borde),
                        border_radius=6,
                        padding=8,
                        content=ft.Row(
                            [
                                ft.Column(
                                    [
                                        ft.Row(
                                            [
                                                ft.Text(f"Cierre #{c.id}", weight=ft.FontWeight.BOLD, size=13, color=self.texto),
                                                ft.Text(f"{c.cantidad_pedidos} pedidos ({c.articulos_totales} un.)", size=11, weight=ft.FontWeight.W_500, color=ROJO),
                                                ft.Text(f"Armador: {c.usuario}", size=11, color=self.secundario),
                                            ],
                                            spacing=10,
                                        ),
                                        ft.Text(
                                            f"Fecha: {c.created_at[:16]} · Informe: {c.archivo_pdf or 'N/A'}"
                                            + (f" · Hoja de Ruta: {c.archivo_hoja_ruta}" if c.archivo_hoja_ruta else ""),
                                            size=10,
                                            color=self.secundario,
                                        ),
                                    ],
                                    spacing=2,
                                    expand=True,
                                 ),
                                ft.Row([boton_correo_cierre, boton_hoja_ruta_cierre, boton_imprimir_cierre], spacing=2),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                    )
                )

        correo_cierre_input = ft.TextField(
            label="Enviar copia de cierre por correo a (opcional)",
            value=obtener_correo_cierre_guardado(),
            hint_text="ej: gerencia@empresa.com, administracion@empresa.com",
            prefix_icon=ft.Icons.EMAIL,
            dense=True,
            content_padding=ft.Padding.symmetric(horizontal=10, vertical=8),
        )

        async def ejecutar_cierre(_e: ft.Event) -> None:
            if not pedidos_pendientes:
                self.notificar("No hay pedidos pendientes para cerrar.")
                return

            correo_destino = (correo_cierre_input.value or "").strip()
            if correo_destino:
                guardar_correo_cierre(correo_destino)

            self.page.pop_dialog()

            def tarea_cierre() -> None:
                items_pendientes_data = self.order_store.obtener_items_pendientes_cierre()
                items_consolidados: dict[str, ItemConsolidado] = {}

                for cod, desc, cant, remitos in items_pendientes_data:
                    items_consolidados[cod] = ItemConsolidado(
                        codigo=cod,
                        descripcion=desc,
                        cantidad_total=cant,
                        remitos_origen=remitos,
                    )

                if not items_consolidados:
                    for ped in pedidos_pendientes:
                        arch_path = application_root() / "data" / "pedidos_archivos" / ped.nombre_archivo
                        if arch_path.exists():
                            if ped.tipo_archivo == "pdf":
                                res = parsear_remito(arch_path)
                            else:
                                res = parsear_canje_excel(arch_path)
                            for it in res.items:
                                cod_n = normalizar_codigo(it.codigo)
                                if cod_n not in items_consolidados:
                                    items_consolidados[cod_n] = ItemConsolidado(
                                        codigo=cod_n,
                                        descripcion=it.descripcion,
                                        cantidad_total=it.cantidad,
                                        remitos_origen=[ped.nota_pedido],
                                    )
                                else:
                                    items_consolidados[cod_n].cantidad_total += it.cantidad
                                    if ped.nota_pedido not in items_consolidados[cod_n].remitos_origen:
                                        items_consolidados[cod_n].remitos_origen.append(ped.nota_pedido)

                pedidos_doc = [
                    ResultadoRemito(
                        archivo=p.nombre_archivo,
                        numero_remito=p.nota_pedido,
                        fecha=p.created_at[:10],
                        cliente=p.cliente,
                        articulos_declarados=p.articulos_descontados,
                        articulos_extraidos=p.articulos_descontados,
                        items=[],
                        discrepancia=False,
                        verificacion_ok=True,
                    )
                    for p in pedidos_pendientes
                ]

                stock_mgr = StockManager(ruta_excel_base=self.menu.ruta_excel_base)
                rep = stock_mgr.aplicar_descuentos(
                    items_consolidados=items_consolidados,
                    carpeta_destino=self.menu.carpeta_descuentos,
                    pedidos_procesados=pedidos_doc,
                    guardar_archivo=True,
                    prefijo_archivo="Cierre_Descuento",
                )

                pdf_path = Path(rep.archivo_pdf) if rep.archivo_pdf else None
                xls_path = Path(rep.archivo_guardado) if rep.archivo_guardado else None

                total_arts = sum(it.cantidad_total for it in items_consolidados.values())
                resumen_p = f"{len(pedidos_pendientes)} pedidos ({total_arts} un.)"

                cierre_id = self.order_store.registrar_cierre(
                    usuario=self.usuario_actual.username if self.usuario_actual else "Operario",
                    pedidos_ids=[p.id for p in pedidos_pendientes],
                    articulos_totales=total_arts,
                    resumen_pedidos=resumen_p,
                    archivo_pdf=pdf_path.name if pdf_path else "",
                    archivo_excel=xls_path.name if xls_path else "",
                )

                # Alertas de stock crítico o quiebre post-cierre
                art_quiebre = rep.articulos_quiebre
                art_criticos = rep.articulos_criticos
                alerta_texto_correo = ""
                alerta_resumen_notif = ""
                if art_quiebre or art_criticos:
                    lineas_alerta = []
                    if art_quiebre:
                        lineas_alerta.append(f"🔴 {len(art_quiebre)} producto(s) en QUIEBRE (stock <= 0)")
                    if art_criticos:
                        lineas_alerta.append(f"🟠 {len(art_criticos)} producto(s) en STOCK CRÍTICO (1 a 5 un.)")
                    alerta_resumen_notif = " · ".join(lineas_alerta)
                    alerta_texto_correo = alerta_resumen_notif
                    for r in art_quiebre:
                        alerta_texto_correo += f"\n  - [QUIEBRE] {r.codigo}: {r.nombre_producto} (Stock: {r.stock_nuevo})"
                    for r in art_criticos:
                        alerta_texto_correo += f"\n  - [CRÍTICO] {r.codigo}: {r.nombre_producto} (Stock: {r.stock_nuevo})"

                    self.order_store.registrar_auditoria(
                        usuario=self.usuario_actual.username if self.usuario_actual else "Operario",
                        accion="ALERTA_STOCK",
                        detalle=f"Cierre #{cierre_id}: {len(art_quiebre)} quiebres, {len(art_criticos)} críticos",
                    )

                # Generar Hoja de Ruta de Despacho por Transporte
                hoja_ruta_pdf: Path | None = None
                try:
                    hoja_ruta_pdf = generar_hoja_ruta_pdf(
                        cierre_id=cierre_id,
                        pedidos=pedidos_pendientes,
                        usuario=self.usuario_actual.username if self.usuario_actual else "Operario",
                        carpeta_destino=self.menu.carpeta_descuentos,
                    )
                    if hoja_ruta_pdf:
                        self.order_store.actualizar_hoja_ruta_cierre(cierre_id, hoja_ruta_pdf.name)
                except Exception as ex_hr:
                    print(f"Error generando hoja de ruta de despacho: {ex_hr}")

                # Copia de seguridad automática al cierre
                try:
                    bk_zip = crear_backup_sistema(
                        ruta_excel_base=self.menu.ruta_excel_base,
                        usuario=self.usuario_actual.username if self.usuario_actual else "Operario",
                    )
                    self.order_store.registrar_auditoria(
                        usuario=self.usuario_actual.username if self.usuario_actual else "Operario",
                        accion="BACKUP_AUTOMATICO",
                        detalle=f"Respaldo automático en cierre #{cierre_id}: {bk_zip.name}",
                    )
                except Exception as ex_bk:
                    print(f"Error en backup automático: {ex_bk}")

                self.actualizar_listas()
                if pdf_path and pdf_path.exists():
                    self.abrir_informe(ruta_especifica=pdf_path)
                if hoja_ruta_pdf and hoja_ruta_pdf.exists():
                    self.abrir_informe(ruta_especifica=hoja_ruta_pdf)

                if correo_destino:
                    self.enviar_correo_cierre(
                        destinatarios=correo_destino,
                        cierre_id=cierre_id,
                        archivo_pdf=pdf_path,
                        archivo_excel=xls_path,
                        resumen_pedidos=resumen_p,
                        usuario=self.usuario_actual.username if self.usuario_actual else "Operario",
                        archivo_hoja_ruta=hoja_ruta_pdf,
                        alerta_stock=alerta_texto_correo,
                    )

                mensaje_exito = (
                    f"Cierre de jornada #{cierre_id} realizado con éxito ({resumen_p}). "
                    "Se generó el informe, la Hoja de Ruta y el Respaldo de seguridad."
                )
                if alerta_resumen_notif:
                    mensaje_exito += f"\n⚠️ {alerta_resumen_notif}"
                self.notificar(mensaje_exito)

            await self.ejecutar_tarea("Cierre de Jornada", tarea_cierre)

        vista_pendientes = ft.Container(
            content=ft.Column(
                [
                    ft.Container(
                        bgcolor=ROJO if pedidos_pendientes else (ft.Colors.BLUE_GREY_900 if self.modo_oscuro else ft.Colors.BLUE_GREY_100),
                        border_radius=8,
                        padding=10,
                        content=ft.Row(
                            [
                                ft.Column(
                                    [
                                        ft.Text(
                                            f"{len(pedidos_pendientes)} Pedidos Acumulados" if pedidos_pendientes else "Sin pedidos acumulados",
                                            weight=ft.FontWeight.BOLD,
                                            size=13,
                                            color=ft.Colors.WHITE,
                                        ),
                                        ft.Text(
                                            f"Total de {total_articulos_pendientes} unidades descontadas listas para cerrar jornada."
                                            if pedidos_pendientes
                                            else "Todos los pedidos anteriores están cerrados.",
                                            size=11,
                                            color=ft.Colors.WHITE_70,
                                        ),
                                    ],
                                    spacing=2,
                                    expand=True,
                                ),
                                ft.Button(
                                    "Cerrar Jornada e Imprimir",
                                    icon=ft.Icons.LOCK,
                                    bgcolor=ft.Colors.WHITE,
                                    color=ROJO,
                                    disabled=not bool(pedidos_pendientes),
                                    on_click=ejecutar_cierre,
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                    ),
                    correo_cierre_input,
                    ft.Text("Pedidos incluidos en este cierre:", size=12, weight=ft.FontWeight.BOLD, color=self.texto),
                    ft.Container(content=items_pendientes, expand=True),
                ],
                spacing=10,
                expand=True,
            ),
            expand=True,
            visible=True,
        )

        vista_historial = ft.Container(
            content=ft.Column(
                [
                    ft.Text("Cierres de jornada anteriores (puedes reimprimir cualquier cierre):", size=12, color=self.secundario),
                    ft.Container(content=lista_cierres, expand=True),
                ],
                spacing=8,
                expand=True,
            ),
            expand=True,
            visible=False,
        )

        boton_tab_pendientes = ft.Button(
            f"Pendientes ({len(pedidos_pendientes)})",
            icon=ft.Icons.PENDING_ACTIONS,
            bgcolor=ROJO,
            color=ft.Colors.WHITE,
        )
        boton_tab_historial = ft.Button(
            f"Historial de Cierres ({len(cierres_anteriores)})",
            icon=ft.Icons.HISTORY,
            bgcolor=ft.Colors.BLUE_GREY_800 if self.modo_oscuro else ft.Colors.BLUE_GREY_100,
            color=self.texto,
        )

        def switch_tab(tab_idx: int) -> None:
            if tab_idx == 0:
                vista_pendientes.visible = True
                vista_historial.visible = False
                boton_tab_pendientes.bgcolor = ROJO
                boton_tab_pendientes.color = ft.Colors.WHITE
                boton_tab_historial.bgcolor = ft.Colors.BLUE_GREY_800 if self.modo_oscuro else ft.Colors.BLUE_GREY_100
                boton_tab_historial.color = self.texto
            else:
                vista_pendientes.visible = False
                vista_historial.visible = True
                boton_tab_pendientes.bgcolor = ft.Colors.BLUE_GREY_800 if self.modo_oscuro else ft.Colors.BLUE_GREY_100
                boton_tab_pendientes.color = self.texto
                boton_tab_historial.bgcolor = ROJO
                boton_tab_historial.color = ft.Colors.WHITE
            self.page.update()

        boton_tab_pendientes.on_click = lambda _e: switch_tab(0)
        boton_tab_historial.on_click = lambda _e: switch_tab(1)

        cuerpo_cierre = ft.Column(
            [
                ft.Row([boton_tab_pendientes, boton_tab_historial], spacing=10),
                vista_pendientes,
                vista_historial,
            ],
            spacing=12,
            expand=True,
        )

        dialogo = ft.AlertDialog(
            title=ft.Row(
                [
                    ft.Icon(ft.Icons.TASK_ALT, color=ROJO),
                    ft.Text("Cierre de Jornada de Pedidos", weight=ft.FontWeight.BOLD),
                ],
                spacing=8,
            ),
            content=ft.Container(
                width=720,
                height=520,
                content=cuerpo_cierre,
            ),
            actions=[
                self.boton_dialogo("Cerrar", lambda _e: self.page.pop_dialog())
            ],
        )
        self.page.show_dialog(dialogo)

    def mostrar_acceso_admin(self, _evento: ft.Event) -> None:
        if not self.exigir_roles("administrador"):
            return
        self.mostrar_formulario_producto()

    def mostrar_gestion_productos(self, _evento: ft.Event | None = None) -> None:
        if not self.exigir_roles("administrador"):
            return
        stock_manager = StockManager(self.menu.ruta_excel_base)
        busqueda = ft.TextField(
            label="Buscar por código o nombre",
            expand=True,
        )
        productos = ft.Column(spacing=6, scroll=ft.ScrollMode.AUTO)

        def actualizar_lista(_evento: ft.Event | None = None) -> None:
            productos.controls.clear()
            consulta = (busqueda.value or "").strip().casefold()
            for producto in stock_manager.listar_productos():
                codigo = str(producto["code"])
                nombre = str(producto["name"])
                activo = bool(producto["active"])
                if consulta and consulta not in f"{codigo} {nombre}".casefold():
                    continue

                stk = int(producto["stock"])
                try:
                    stk_min = int(producto["stock_minimo"])
                except Exception:
                    stk_min = 5
                try:
                    stk_max = int(producto["stock_maximo"])
                except Exception:
                    stk_max = 100

                if stk <= 0:
                    estado_texto, estado_color = "Agotado", ft.Colors.RED_400
                elif stk <= stk_min:
                    estado_texto, estado_color = f"Bajo (mín {stk_min})", ft.Colors.AMBER_400
                elif stk > stk_max:
                    estado_texto, estado_color = f"Sobrestock (máx {stk_max})", ft.Colors.PURPLE_300
                else:
                    estado_texto, estado_color = "Óptimo", ft.Colors.GREEN_400

                productos.controls.append(
                    ft.Container(
                        padding=8,
                        border=ft.Border.all(1, self.borde),
                        border_radius=8,
                        content=ft.Row(
                            [
                                ft.Text(codigo, width=90, color=self.texto, weight=ft.FontWeight.BOLD),
                                ft.Text(nombre, expand=True, color=self.texto),
                                ft.Text(
                                    f"{stk} un.",
                                    width=70,
                                    color=self.texto,
                                ),
                                ft.Text(
                                    estado_texto,
                                    width=130,
                                    size=12,
                                    color=estado_color,
                                    weight=ft.FontWeight.BOLD if stk <= stk_min else ft.FontWeight.NORMAL,
                                ),
                                ft.Text(
                                    "Activo" if activo else "Inactivo",
                                    width=70,
                                    size=12,
                                    color=(
                                        ft.Colors.GREEN_400
                                        if activo
                                        else self.secundario
                                    ),
                                ),
                                ft.TextButton(
                                    "Editar",
                                    on_click=lambda _e, item=producto: editar(item),
                                ),
                                ft.TextButton(
                                    "Desactivar" if activo else "Reactivar",
                                    on_click=lambda _e, code=codigo, status=activo: confirmar_estado(
                                        code, not status
                                    ),
                                ),
                            ],
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                    )
                )
            if not productos.controls:
                productos.controls.append(
                    ft.Text("No se encontraron productos.", color=self.secundario)
                )
            self.page.update()

        def editar(producto) -> None:
            if not self.exigir_roles("administrador"):
                return
            codigo_original = str(producto["code"])
            campo_codigo = ft.TextField(label="Código", value=codigo_original)
            campo_nombre = ft.TextField(
                label="Nombre", value=str(producto["name"])
            )
            campo_stock = ft.TextField(
                label="Stock",
                value=str(producto["stock"]),
                keyboard_type=ft.KeyboardType.NUMBER,
            )
            try:
                stock_min_val = int(producto["stock_minimo"])
            except Exception:
                stock_min_val = 5
            try:
                stock_max_val = int(producto["stock_maximo"])
            except Exception:
                stock_max_val = 100

            campo_min = ft.TextField(
                label="Stock mínimo (alerta quiebre)",
                value=str(stock_min_val),
                keyboard_type=ft.KeyboardType.NUMBER,
            )
            campo_max = ft.TextField(
                label="Stock máximo (alerta sobrestock)",
                value=str(stock_max_val),
                keyboard_type=ft.KeyboardType.NUMBER,
            )
            campos: list[ft.Control] = [
                campo_codigo,
                campo_nombre,
                campo_stock,
                campo_min,
                campo_max,
            ]

            async def guardar_edicion(_evento: ft.Event) -> None:
                if not self.exigir_roles("administrador"):
                    return
                codigo = (campo_codigo.value or "").strip()
                nombre = (campo_nombre.value or "").strip()
                stock_texto = (campo_stock.value or "").strip()
                if not codigo or not nombre or not stock_texto:
                    self.notificar("Completa el código, el nombre y el stock.")
                    return
                try:
                    stock = int(stock_texto)
                except ValueError:
                    self.notificar("El stock debe ser un número entero.")
                    return
                try:
                    s_min = int((campo_min.value or "5").strip())
                    s_max = int((campo_max.value or "100").strip())
                    if s_min < 0 or s_max < s_min:
                        self.notificar("El mínimo debe ser >= 0 y el máximo >= mínimo.")
                        return
                except ValueError:
                    self.notificar("Los stocks mínimo y máximo deben ser números enteros.")
                    return

                self.page.pop_dialog()
                actualizado = await self.ejecutar_tarea(
                    "Edición de producto",
                    lambda: stock_manager.actualizar_producto(
                        codigo_original, codigo, nombre, stock, s_min, s_max
                    ),
                )
                if actualizado:
                    actualizar_lista()

            dialogo_edicion = ft.AlertDialog(
                modal=True,
                title=ft.Text(f"Editar producto {codigo_original}"),
                content=ft.Column(campos, tight=True, width=380),
                actions=[
                    self.boton_dialogo(
                        "Cancelar", lambda _e: self.page.pop_dialog()
                    ),
                    self.boton_dialogo("Guardar", guardar_edicion),
                ],
            )
            self.page.show_dialog(dialogo_edicion)

        def confirmar_estado(codigo: str, activo: bool) -> None:
            if not self.exigir_roles("administrador"):
                return
            accion = "reactivar" if activo else "desactivar"

            async def aceptar_estado(_evento: ft.Event) -> None:
                await cambiar_estado(codigo, activo)

            dialogo_estado = ft.AlertDialog(
                modal=True,
                title=ft.Text(f"Confirmar {accion}"),
                content=ft.Text(
                    (
                        f"El producto {codigo} volverá a incluirse en futuros informes."
                        if activo
                        else f"El producto {codigo} se conservará en el catálogo, "
                        "pero no se incluirá en futuros informes."
                    )
                ),
                actions=[
                    self.boton_dialogo(
                        "Cancelar", lambda _e: self.page.pop_dialog()
                    ),
                    self.boton_dialogo(
                        accion.capitalize(),
                        aceptar_estado,
                    ),
                ],
            )
            self.page.show_dialog(dialogo_estado)

        async def cambiar_estado(codigo: str, activo: bool) -> None:
            if not self.exigir_roles("administrador"):
                return
            self.page.pop_dialog()
            actualizado = await self.ejecutar_tarea(
                "Actualización del estado del producto",
                lambda: stock_manager.cambiar_estado_producto(codigo, activo),
            )
            if actualizado:
                actualizar_lista()

        def agregar(_evento: ft.Event) -> None:
            if not self.exigir_roles("administrador"):
                return
            self.mostrar_formulario_producto(actualizar_lista)

        dialogo = ft.AlertDialog(
            modal=True,
            title=ft.Text("Gestión de productos"),
            content=ft.Column(
                [
                    ft.Text(
                        "Las bajas son lógicas: el producto se conserva, "
                        "pero no aparece en futuros informes."
                    ),
                    ft.Row(
                        [
                            busqueda,
                            ft.Button(
                                "Agregar producto",
                                icon=ft.Icons.ADD,
                                on_click=agregar,
                                bgcolor=ROJO,
                                color=ft.Colors.WHITE,
                            ),
                        ]
                    ),
                    ft.Row(
                        [
                            ft.Text(
                                "Código", width=100, weight=ft.FontWeight.BOLD
                            ),
                            ft.Text(
                                "Nombre", expand=True, weight=ft.FontWeight.BOLD
                            ),
                            ft.Text("Stock", width=70, weight=ft.FontWeight.BOLD),
                            ft.Text("Estado", width=80, weight=ft.FontWeight.BOLD),
                            ft.Container(width=145),
                        ]
                    ),
                    ft.Container(
                        height=420,
                        content=productos,
                    ),
                ],
                tight=True,
                width=900,
            ),
            actions=[
                self.boton_dialogo("Cerrar", lambda _e: self.page.pop_dialog())
            ],
        )
        busqueda.on_change = actualizar_lista
        actualizar_lista()
        self.page.show_dialog(dialogo)

    def mostrar_formulario_producto(
        self, al_guardar: Callable[[], None] | None = None
    ) -> None:
        if not self.exigir_roles("administrador"):
            return
        campos = {
            "codigo": ft.TextField(label="Código del nuevo producto"),
            "nombre": ft.TextField(label="Nombre del producto"),
            "referencia": ft.TextField(label="Código del producto anterior"),
            "stock": ft.TextField(label="Stock inicial (opcional)", keyboard_type=ft.KeyboardType.NUMBER),
        }

        async def guardar(_evento: ft.Event) -> None:
            if not self.exigir_roles("administrador"):
                return
            codigo = (campos["codigo"].value or "").strip()
            nombre = (campos["nombre"].value or "").strip()
            referencia = (campos["referencia"].value or "").strip()
            stock_texto = (campos["stock"].value or "").strip()
            if not codigo or not nombre or not referencia:
                self.notificar("Completa el código, el nombre y el código de referencia.")
                return
            try:
                stock = int(stock_texto) if stock_texto else None
            except ValueError:
                self.notificar("El stock inicial debe ser un número entero.")
                return

            self.page.pop_dialog()

            def insertar() -> None:
                stock_manager = StockManager(self.menu.ruta_excel_base)
                exito, mensaje, _ = stock_manager.agregar_producto_en_posicion(
                    codigo_nuevo=codigo,
                    nombre_nuevo=nombre,
                    codigo_arriba=referencia,
                    stock_inicial=stock,
                )
                if not exito:
                    raise ValueError(mensaje)
                print(f"[OK] {mensaje}")

            creado = await self.ejecutar_tarea("Alta de producto", insertar)
            if creado and al_guardar is not None:
                al_guardar()

        dialogo = ft.AlertDialog(
            modal=True,
            title=ft.Text("Datos del nuevo producto"),
            content=ft.Column(list(campos.values()), tight=True, width=380),
            actions=[
                self.boton_dialogo("Cancelar", lambda _e: self.page.pop_dialog()),
                self.boton_dialogo("Guardar", guardar),
            ],
        )
        self.page.show_dialog(dialogo)

    def imprimir_rotulos_pedido(self, pedido: Pedido) -> None:
        try:
            ruta_pdf = generar_etiquetas_bultos_pdf(pedido, self.menu.carpeta_descuentos)
            self.abrir_informe(ruta_especifica=ruta_pdf)
            self.notificar(f"Rótulos para {pedido.bultos} bulto(s) generados con éxito ({ruta_pdf.name}).")
        except Exception as error:
            self.notificar(f"Error generando rótulos de bulto:\n{error}")

    def confirmar_anulacion_pedido(self, pedido: Pedido, al_final: Callable[[], None] | None = None) -> None:
        motivo_input = ft.TextField(
            label="Motivo de la anulación (opcional)",
            hint_text="ej: Cancelado por el cliente, duplicado, error en carga",
            dense=True,
            autofocus=True,
        )

        def ejecutar_anulacion(_e: ft.Event) -> None:
            self.page.pop_dialog()
            try:
                self.order_store.anular_pedido(
                    pedido_id=pedido.id,
                    motivo=motivo_input.value or "",
                    usuario=self.usuario_actual.username if self.usuario_actual else "Sistema",
                )
                self.notificar(f"Pedido {pedido.nota_pedido} anulado correctamente.")
                if al_final:
                    al_final()
            except Exception as err:
                self.notificar(f"Error al anular pedido: {err}")

        dialogo = ft.AlertDialog(
            title=ft.Row([ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, color=ROJO), ft.Text("Confirmar Anulación de Pedido")]),
            content=ft.Container(
                width=420,
                content=ft.Column(
                    [
                        ft.Text(f"¿Estás seguro de anular el pedido '{pedido.nota_pedido}' del cliente '{pedido.cliente}'?"),
                        ft.Text("Esta acción quedará registrada en el log de auditoría del sistema.", size=11, color=self.secundario),
                        ft.Divider(height=10),
                        motivo_input,
                    ],
                    tight=True,
                    spacing=8,
                ),
            ),
            actions=[
                ft.Button("Anular Pedido", bgcolor=ROJO, color=ft.Colors.WHITE, on_click=ejecutar_anulacion),
                self.boton_dialogo("Cancelar", lambda _e: self.page.pop_dialog()),
            ],
        )
        self.page.show_dialog(dialogo)

    def mostrar_dialogo_backup(self, _e: ft.Event | None = None) -> None:
        if not self.exigir_roles("administrador"):
            return

        def ejecutar_backup(_ev: ft.Event) -> None:
            self.page.pop_dialog()
            try:
                ruta_zip = crear_backup_sistema(
                    ruta_excel_base=self.menu.ruta_excel_base,
                    usuario=self.usuario_actual.username if self.usuario_actual else "Sistema",
                )
                self.order_store.registrar_auditoria(
                    usuario=self.usuario_actual.username if self.usuario_actual else "Sistema",
                    accion="BACKUP_MANUAL",
                    detalle=f"Respaldo manual generado: {ruta_zip.name}",
                )
                self.notificar(f"Copia de seguridad generada con éxito:\n{ruta_zip.name}")
                self.abrir_carpeta_informe(ruta_zip)
            except Exception as err:
                self.notificar(f"Error al generar copia de seguridad:\n{err}")

        dialogo = ft.AlertDialog(
            title=ft.Row([ft.Icon(ft.Icons.BACKUP, color=ft.Colors.BLUE_600), ft.Text("Copia de Seguridad del Sistema")]),
            content=ft.Container(
                width=460,
                content=ft.Column(
                    [
                        ft.Text("Se generará un archivo comprimido .ZIP con:"),
                        ft.Text("• Base de datos SQLite (pedidos, clientes, cierres y auditoría)"),
                        ft.Text("• Archivo de usuarios y credenciales"),
                        ft.Text("• Configuraciones de notificaciones"),
                        ft.Text("• Archivo Excel maestro de stock"),
                        ft.Text("\nLos respaldos se almacenan automáticamente en data/backups/ (rotación de 30 copias).", size=11, color=self.secundario),
                    ],
                    tight=True,
                    spacing=4,
                ),
            ),
            actions=[
                ft.Button("Generar Respaldo Ahora", icon=ft.Icons.SAVE, bgcolor=ROJO, color=ft.Colors.WHITE, on_click=ejecutar_backup),
                self.boton_dialogo("Cancelar", lambda _ev: self.page.pop_dialog()),
            ],
        )
        self.page.show_dialog(dialogo)

    def mostrar_dashboard_metricas(self, _e: ft.Event | None = None) -> None:
        if not self.exigir_roles("administrador"):
            return

        m = self.order_store.obtener_metricas_dashboard()
        promedio_bultos = (m["total_bultos"] / m["total_pedidos"]) if m["total_pedidos"] > 0 else 0

        def tarjeta_kpi(titulo: str, valor: str, icono: str, color_ico: str) -> ft.Container:
            return ft.Container(
                bgcolor=self.fondo_acento if self.modo_oscuro else ft.Colors.WHITE,
                border=ft.Border.all(1, self.borde),
                border_radius=8,
                padding=12,
                expand=True,
                content=ft.Column(
                    [
                        ft.Row([ft.Icon(icono, color=color_ico, size=20), ft.Text(titulo, size=11, color=self.secundario, weight=ft.FontWeight.W_500)], spacing=6),
                        ft.Text(valor, size=20, weight=ft.FontWeight.BOLD, color=self.texto),
                    ],
                    spacing=4,
                ),
            )

        kpis = ft.Row(
            [
                tarjeta_kpi("Total Pedidos", str(m["total_pedidos"]), ft.Icons.INVENTORY, ft.Colors.BLUE_500),
                tarjeta_kpi("Total Bultos", str(m["total_bultos"]), ft.Icons.LOCAL_SHIPPING, ft.Colors.AMBER_600),
                tarjeta_kpi("Promedio Bultos/Ped.", f"{promedio_bultos:.1f}", ft.Icons.CALCULATE, ft.Colors.TEAL_500),
                tarjeta_kpi("Cierres de Jornada", str(m["total_cierres"]), ft.Icons.TASK_ALT, ft.Colors.GREEN_600),
            ],
            spacing=10,
        )

        filas_logistica = ft.Column(spacing=4)
        for log, cant, bultos in m["distribucion_logistica"]:
            porc = (cant / m["total_pedidos"] * 100) if m["total_pedidos"] > 0 else 0
            filas_logistica.controls.append(
                ft.Row(
                    [
                        ft.Text(log, size=12, weight=ft.FontWeight.W_500, expand=True, color=self.texto),
                        ft.Text(f"{cant} pedidos ({porc:.0f}%)", size=11, color=self.secundario),
                        ft.Text(f"{bultos} bultos", size=11, weight=ft.FontWeight.BOLD, color=ROJO),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                )
            )

        filas_armadores = ft.Column(spacing=4)
        for arm, cant, bultos in m["rendimiento_armadores"]:
            filas_armadores.controls.append(
                ft.Row(
                    [
                        ft.Text(arm, size=12, weight=ft.FontWeight.W_500, expand=True, color=self.texto),
                        ft.Text(f"{cant} pedidos", size=11, color=self.secundario),
                        ft.Text(f"{bultos} bultos", size=11, weight=ft.FontWeight.BOLD, color=ROJO),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                )
            )

        filas_top = ft.Column(spacing=4)
        for idx, (cod, desc, cant) in enumerate(m["top_articulos"], start=1):
            filas_top.controls.append(
                ft.Row(
                    [
                        ft.Text(f"{idx}. {cod}", size=11, weight=ft.FontWeight.BOLD, color=self.texto),
                        ft.Text(desc[:28] + ("..." if len(desc) > 28 else ""), size=11, color=self.secundario, expand=True),
                        ft.Text(f"{cant} un.", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_600),
                    ],
                    spacing=8,
                )
            )

        seccion_tablas = ft.Row(
            [
                ft.Container(
                    bgcolor=self.fondo_acento if self.modo_oscuro else ft.Colors.WHITE,
                    border=ft.Border.all(1, self.borde),
                    border_radius=8,
                    padding=12,
                    expand=True,
                    content=ft.Column(
                        [
                            ft.Text("Despacho por Logística", size=13, weight=ft.FontWeight.BOLD, color=self.texto),
                            ft.Divider(height=6),
                            filas_logistica if filas_logistica.controls else ft.Text("Sin datos", size=11, color=self.secundario),
                        ],
                        spacing=6,
                    ),
                ),
                ft.Container(
                    bgcolor=self.fondo_acento if self.modo_oscuro else ft.Colors.WHITE,
                    border=ft.Border.all(1, self.borde),
                    border_radius=8,
                    padding=12,
                    expand=True,
                    content=ft.Column(
                        [
                            ft.Text("Rendimiento de Armadores", size=13, weight=ft.FontWeight.BOLD, color=self.texto),
                            ft.Divider(height=6),
                            filas_armadores if filas_armadores.controls else ft.Text("Sin datos", size=11, color=self.secundario),
                        ],
                        spacing=6,
                    ),
                ),
                ft.Container(
                    bgcolor=self.fondo_acento if self.modo_oscuro else ft.Colors.WHITE,
                    border=ft.Border.all(1, self.borde),
                    border_radius=8,
                    padding=12,
                    expand=True,
                    content=ft.Column(
                        [
                            ft.Text("Top 10 Productos Más Rotados", size=13, weight=ft.FontWeight.BOLD, color=self.texto),
                            ft.Divider(height=6),
                            filas_top if filas_top.controls else ft.Text("Sin datos", size=11, color=self.secundario),
                        ],
                        spacing=6,
                    ),
                ),
            ],
            spacing=10,
            alignment=ft.MainAxisAlignment.START,
        )

        dialogo = ft.AlertDialog(
            title=ft.Row(
                [
                    ft.Icon(ft.Icons.INSIGHTS, color=ROJO),
                    ft.Text("Métricas y Rendimiento del Depósito", weight=ft.FontWeight.BOLD),
                ],
                spacing=8,
            ),
            content=ft.Container(
                width=850,
                content=ft.Column(
                    [
                        kpis,
                        ft.Container(height=8),
                        seccion_tablas,
                    ],
                    tight=True,
                    spacing=8,
                    scroll=ft.ScrollMode.AUTO,
                ),
            ),
            actions=[
                self.boton_dialogo("Cerrar", lambda _ev: self.page.pop_dialog()),
            ],
        )
        self.page.show_dialog(dialogo)

    def mostrar_registro_auditoria(self, _e: ft.Event | None = None) -> None:
        if not self.exigir_roles("administrador"):
            return

        lista_eventos = ft.ListView(expand=True, spacing=6, height=380)
        input_busqueda = ft.TextField(
            hint_text="Filtrar eventos por usuario, acción o detalle...",
            prefix_icon=ft.Icons.SEARCH,
            dense=True,
            expand=True,
        )

        def color_accion(accion: str) -> tuple[str, str]:
            if "CARGA" in accion or "CREAR" in accion:
                return (ft.Colors.BLUE_100 if not self.modo_oscuro else ft.Colors.BLUE_900, ft.Colors.BLUE_800 if not self.modo_oscuro else ft.Colors.BLUE_200)
            if "ANULAR" in accion or "ALERTA" in accion:
                return (ft.Colors.RED_100 if not self.modo_oscuro else ft.Colors.RED_900, ft.Colors.RED_800 if not self.modo_oscuro else ft.Colors.RED_200)
            if "CIERRE" in accion:
                return (ft.Colors.GREEN_100 if not self.modo_oscuro else ft.Colors.GREEN_900, ft.Colors.GREEN_800 if not self.modo_oscuro else ft.Colors.GREEN_200)
            if "BACKUP" in accion:
                return (ft.Colors.PURPLE_100 if not self.modo_oscuro else ft.Colors.PURPLE_900, ft.Colors.PURPLE_800 if not self.modo_oscuro else ft.Colors.PURPLE_200)
            return (ft.Colors.GREY_200 if not self.modo_oscuro else ft.Colors.GREY_800, self.texto)

        def refrescar_lista(_ev: ft.Event | None = None) -> None:
            lista_eventos.controls.clear()
            txt = (input_busqueda.value or "").strip()
            logs = self.order_store.listar_auditoria(limit=200, filtro_texto=txt)
            if not logs:
                lista_eventos.controls.append(ft.Text("No se encontraron registros de auditoría.", size=12, color=self.secundario))
            else:
                for reg in logs:
                    bg_col, txt_col = color_accion(reg.accion)
                    badge = ft.Container(
                        content=ft.Text(reg.accion, size=9, weight=ft.FontWeight.BOLD, color=txt_col),
                        bgcolor=bg_col,
                        padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                        border_radius=4,
                    )
                    lista_eventos.controls.append(
                        ft.Container(
                            bgcolor=self.fondo_acento if self.modo_oscuro else ft.Colors.GREY_50,
                            border=ft.Border.all(1, self.borde),
                            border_radius=6,
                            padding=8,
                            content=ft.Row(
                                [
                                    badge,
                                    ft.Text(f"[{reg.usuario}]", size=11, weight=ft.FontWeight.BOLD, color=self.texto),
                                    ft.Text(reg.detalle, size=11, color=self.texto, expand=True),
                                    ft.Text(reg.created_at[:16], size=10, color=self.secundario),
                                ],
                                spacing=8,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                        )
                    )
            self.page.update()

        input_busqueda.on_change = refrescar_lista
        refrescar_lista()

        dialogo = ft.AlertDialog(
            title=ft.Row(
                [
                    ft.Icon(ft.Icons.SECURITY, color=ROJO),
                    ft.Text("Registro de Auditoría y Trazabilidad", weight=ft.FontWeight.BOLD),
                ],
                spacing=8,
            ),
            content=ft.Container(
                width=740,
                content=ft.Column(
                    [
                        input_busqueda,
                        ft.Divider(height=6),
                        lista_eventos,
                    ],
                    tight=True,
                    spacing=8,
                ),
            ),
            actions=[
                self.boton_dialogo("Cerrar", lambda _ev: self.page.pop_dialog()),
            ],
        )
        self.page.show_dialog(dialogo)

    def mostrar_estadisticas(self, _evento: ft.Event | None = None) -> None:
        if not self.exigir_roles("administrador"):
            return

        hoy = datetime.now()
        hace_30_dias = hoy - timedelta(days=30)

        campo_desde = ft.TextField(
            label="Desde (DD/MM/AAAA)",
            value=hace_30_dias.strftime("%d/%m/%Y"),
            width=160,
            text_size=13,
        )
        campo_hasta = ft.TextField(
            label="Hasta (DD/MM/AAAA)",
            value=hoy.strftime("%d/%m/%Y"),
            width=160,
            text_size=13,
        )
        campo_top = ft.Dropdown(
            label="Top productos",
            value="15",
            options=[
                ft.DropdownOption("5"),
                ft.DropdownOption("10"),
                ft.DropdownOption("15"),
                ft.DropdownOption("20"),
                ft.DropdownOption("50"),
            ],
            width=110,
            text_size=13,
        )
        campo_tipo = ft.Dropdown(
            label="Tipo de movimiento",
            value="descuento",
            options=[
                ft.DropdownOption(key="descuento", text="Descuentos (salidas)"),
                ft.DropdownOption(key="ingreso_fabrica", text="Ingresos fábrica"),
                ft.DropdownOption(key="", text="Todos"),
            ],
            width=200,
            text_size=13,
        )

        contenedor_grafico = ft.Column(
            spacing=4,
            scroll=ft.ScrollMode.AUTO,
            height=350,
        )
        texto_resumen = ft.Text("", size=12, color=self.secundario)

        def parsear_fecha(texto: str) -> str | None:
            texto = texto.strip()
            for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
                try:
                    return datetime.strptime(texto, fmt).strftime("%Y-%m-%d")
                except ValueError:
                    continue
            return None

        def generar_grafico(_e: ft.Event | None = None) -> None:
            contenedor_grafico.controls.clear()

            desde_iso = parsear_fecha(campo_desde.value or "")
            hasta_iso = parsear_fecha(campo_hasta.value or "")
            if not desde_iso or not hasta_iso:
                contenedor_grafico.controls.append(
                    ft.Text(
                        "Formato de fecha inválido. Use DD/MM/AAAA.",
                        color=ft.Colors.RED_400,
                        size=13,
                    )
                )
                self.page.update()
                return

            top_n = int(campo_top.value or "15")
            tipo = campo_tipo.value or None
            if tipo == "":
                tipo = None

            try:
                sm = StockManager(self.menu.ruta_excel_base)
                resultados = sm.consultar_movimientos(
                    fecha_desde=desde_iso,
                    fecha_hasta=hasta_iso,
                    tipo=tipo,
                    top_n=top_n,
                )
            except Exception as err:
                contenedor_grafico.controls.append(
                    ft.Text(f"Error: {err}", color=ft.Colors.RED_400, size=13)
                )
                self.page.update()
                return

            if not resultados:
                contenedor_grafico.controls.append(
                    ft.Text(
                        "No se encontraron movimientos en el rango seleccionado.",
                        color=self.secundario,
                        size=13,
                    )
                )
                texto_resumen.value = ""
                self.page.update()
                return

            max_cant = max(row["total_quantity"] for row in resultados)
            total_unidades = sum(row["total_quantity"] for row in resultados)
            total_productos = len(resultados)

            colores_barra = [
                ft.Colors.RED_700,
                ft.Colors.RED_600,
                ft.Colors.RED_500,
                ft.Colors.RED_400,
                ft.Colors.RED_300,
                ft.Colors.ORANGE_400,
                ft.Colors.ORANGE_300,
                ft.Colors.AMBER_400,
                ft.Colors.AMBER_300,
                ft.Colors.YELLOW_400,
            ]

            for i, row in enumerate(resultados):
                cod = str(row["product_code"])
                nombre = str(row["product_name"])
                cant = int(row["total_quantity"])
                proporcion = cant / max_cant if max_cant > 0 else 0
                ancho_barra = max(8, int(proporcion * 300))
                color_idx = min(i, len(colores_barra) - 1)

                etiqueta = f"{nombre[:25]}" if len(nombre) > 25 else nombre
                fila = ft.Row(
                    [
                        ft.Text(cod, width=60, size=11, weight=ft.FontWeight.BOLD),
                        ft.Container(
                            width=ancho_barra,
                            height=20,
                            bgcolor=colores_barra[color_idx],
                            border_radius=ft.BorderRadius(3, 3, 3, 3),
                            alignment=ft.Alignment(-1, 0),
                            padding=ft.Padding(4, 0, 4, 0),
                            content=ft.Text(
                                str(cant),
                                size=10,
                                color=ft.Colors.WHITE,
                                weight=ft.FontWeight.BOLD,
                            ),
                        ),
                        ft.Text(
                            etiqueta,
                            size=11,
                            color=self.secundario,
                            expand=True,
                        ),
                    ],
                    spacing=6,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                )
                contenedor_grafico.controls.append(fila)

            tipo_texto = {
                "descuento": "descontadas",
                "ingreso_fabrica": "ingresadas (fábrica)",
            }.get(tipo or "", "movidas")
            texto_resumen.value = (
                f"📊 {total_productos} productos — {total_unidades} unidades {tipo_texto} "
                f"entre {campo_desde.value} y {campo_hasta.value}"
            )
            self.page.update()

        generar_grafico()

        dialogo = ft.AlertDialog(
            modal=True,
            title=ft.Text("Estadísticas de movimiento de stock"),
            content=ft.Column(
                [
                    ft.Row(
                        [campo_desde, campo_hasta, campo_top, campo_tipo],
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        wrap=True,
                    ),
                    ft.Button(
                        "Actualizar gráfico",
                        icon=ft.Icons.REFRESH,
                        on_click=generar_grafico,
                        bgcolor=ROJO,
                        color=ft.Colors.WHITE,
                    ),
                    ft.Divider(height=1),
                    texto_resumen,
                    contenedor_grafico,
                ],
                tight=True,
                width=700,
            ),
            actions=[
                self.boton_dialogo("Cerrar", lambda _e: self.page.pop_dialog()),
            ],
        )
        self.page.show_dialog(dialogo)

    def generar_pedido_fabrica(self, _evento: ft.Event | None = None) -> None:
        if not self.exigir_roles("administrador"):
            return

        try:
            sm = StockManager(self.menu.ruta_excel_base)
            analisis = sm.obtener_analisis_reposicion(solo_criticos=True)
            items_a_pedir = [p for p in analisis if int(p["cantidad_sugerida_pedir"]) > 0]
            ruta_excel = sm.generar_pedido_sugerido_fabrica(solo_criticos=True)
            self.actualizar_estado()
            self.seleccionar_informe(ruta_excel)
        except Exception as e:
            self.notificar(f"Error al generar pedido a fábrica: {e}")
            return

        total_unidades = sum(int(p["cantidad_sugerida_pedir"]) for p in items_a_pedir)
        cant_productos = len(items_a_pedir)

        contenido = ft.Column(
            [
                ft.Row(
                    [
                        ft.Icon(ft.Icons.CHECK_CIRCLE, color=ft.Colors.GREEN_400, size=32),
                        ft.Column(
                            [
                                ft.Text(
                                    "¡Pedido a fábrica generado con éxito!",
                                    weight=ft.FontWeight.BOLD,
                                    size=15,
                                    color=self.texto,
                                ),
                                ft.Text(
                                    f"{cant_productos} producto{'s' if cant_productos != 1 else ''} con sugerencia · {total_unidades} unidades calculadas para alcanzar el stock máximo.",
                                    size=12,
                                    color=self.secundario,
                                ),
                            ],
                            spacing=2,
                        ),
                    ],
                    spacing=12,
                ),
                ft.Divider(height=16),
                ft.Container(
                    bgcolor=self.superficie,
                    border=ft.Border.all(1, self.borde),
                    border_radius=8,
                    padding=12,
                    content=ft.Column(
                        [
                            ft.Text("Archivo Excel disponible en 'Informes generados':", size=11, color=self.secundario, weight=ft.FontWeight.BOLD),
                            ft.Text(str(ruta_excel.name), size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_300 if self.modo_oscuro else ft.Colors.BLUE_700),
                            ft.Text(f"Carpeta: {ruta_excel.parent}", size=11, color=self.secundario),
                        ],
                        spacing=4,
                    ),
                ),
            ],
            tight=True,
            width=500,
            spacing=10,
        )

        dialogo = ft.AlertDialog(
            modal=True,
            title=ft.Row(
                [
                    ft.Icon(ft.Icons.FACT_CHECK, color=ROJO, size=24),
                    ft.Text("Sugerencia de Pedido a Fábrica"),
                ],
                spacing=8,
            ),
            content=contenido,
            actions=[
                self.boton_dialogo("Cerrar", lambda _e: self.page.pop_dialog()),
                self.boton_dialogo(
                    "Abrir Excel",
                    lambda _e: (self.page.pop_dialog(), self.abrir_informe(ruta_especifica=ruta_excel)),
                ),
                self.boton_dialogo(
                    "Enviar correo",
                    lambda _e: (self.page.pop_dialog(), self.compartir_correo(ruta_especifica=ruta_excel)),
                ),
                self.boton_dialogo(
                    "WhatsApp",
                    lambda _e: (self.page.pop_dialog(), self.compartir_whatsapp(ruta_especifica=ruta_excel)),
                ),
            ],
        )
        self.page.show_dialog(dialogo)

    def mostrar_ingreso_fabrica(self, _evento: ft.Event | None = None) -> None:
        if not self.exigir_roles("administrador"):
            return

        stock_manager = StockManager(self.menu.ruta_excel_base)
        modo_sobrescribir = ft.Checkbox(
            label="Sobrescribir stock (establece el valor exacto indicado)",
            value=False,
        )

        # Tab 1: Carga manual
        campo_cod = ft.TextField(label="Código de producto", width=150)
        campo_cant = ft.TextField(
            label="Cantidad (negativo para descontar)",
            width=150,
            keyboard_type=ft.KeyboardType.NUMBER,
            hint_text="Ej: 10 o -5",
        )
        texto_info_prod = ft.Text("", size=12, color=self.secundario)
        lista_cargas = ft.Column(spacing=4, scroll=ft.ScrollMode.AUTO, height=180)
        items_cargados: dict[str, int] = {}

        def verificar_codigo(_e: ft.Event | None = None) -> None:
            c = (campo_cod.value or "").strip()
            if not c:
                texto_info_prod.value = ""
            elif c in stock_manager.catalogo:
                _, nom, st = stock_manager.catalogo[c]
                texto_info_prod.value = f"✔ {nom} (Stock actual: {st})"
                texto_info_prod.color = ft.Colors.GREEN_400
            else:
                texto_info_prod.value = "✖ Código no encontrado en catálogo"
                texto_info_prod.color = ft.Colors.RED_400
            self.page.update()

        campo_cod.on_change = verificar_codigo

        def refrescar_lista_manual() -> None:
            lista_cargas.controls.clear()
            for c, cant in items_cargados.items():
                nom = stock_manager.catalogo[c][1]
                lista_cargas.controls.append(
                    ft.Row(
                        [
                            ft.Text(c, width=70, weight=ft.FontWeight.BOLD),
                            ft.Text(nom, expand=True, size=12),
                            ft.Text(
                                f"={cant}" if modo_sobrescribir.value else (f"−{abs(cant)}" if cant < 0 else f"+{cant}"),
                                width=60,
                                color=ft.Colors.RED_400 if (cant < 0 and not modo_sobrescribir.value) else (ft.Colors.GREEN_400 if cant > 0 else self.texto),
                                weight=ft.FontWeight.BOLD,
                            ),
                            ft.IconButton(
                                icon=ft.Icons.DELETE_OUTLINE,
                                icon_size=18,
                                on_click=lambda _e, code=c: eliminar_item(code),
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    )
                )
            if not items_cargados:
                lista_cargas.controls.append(
                    ft.Text("No hay productos en la lista.", size=12, color=self.secundario)
                )
            self.page.update()

        def eliminar_item(code: str) -> None:
            items_cargados.pop(code, None)
            refrescar_lista_manual()

        def agregar_item(_e: ft.Event) -> None:
            c = (campo_cod.value or "").strip()
            cant_str = (campo_cant.value or "").strip()
            if not c or c not in stock_manager.catalogo:
                self.notificar("Ingrese un código de producto válido.")
                return
            try:
                cant = int(cant_str)
                if cant == 0:
                    self.notificar("La cantidad no puede ser 0.")
                    return
            except ValueError:
                self.notificar("La cantidad debe ser un número entero.")
                return
            items_cargados[c] = cant
            campo_cod.value = ""
            campo_cant.value = ""
            texto_info_prod.value = ""
            refrescar_lista_manual()

        async def guardar_manual(_e: ft.Event) -> None:
            if not self.exigir_roles("administrador"):
                return
            if not items_cargados:
                self.notificar("Agrega al menos un producto.")
                return
            self.page.pop_dialog()
            sobr = modo_sobrescribir.value

            def aplicar() -> None:
                sm = StockManager(self.menu.ruta_excel_base)
                res = sm.registrar_ingreso_fabrica(items_cargados, sobrescribir=sobr)
                print(f"[OK] Se actualizaron {len(res)} productos en catálogo y Excel:")
                for cod, (ant, nvo) in res.items():
                    print(f"     Código {cod}: {ant} -> {nvo}")

            await self.ejecutar_tarea("Ajuste manual de stock", aplicar)
            self.actualizar_estado()

        # Tab 2: Carga por archivo en Descuentos/Fabrica
        lista_archivos_fabrica = ft.Column(spacing=4, scroll=ft.ScrollMode.AUTO, height=180)
        archivos_pendientes = self.menu._obtener_pendientes_fabrica()

        def refrescar_archivos_fabrica() -> None:
            lista_archivos_fabrica.controls.clear()
            nonlocal archivos_pendientes
            archivos_pendientes = self.menu._obtener_pendientes_fabrica()
            if archivos_pendientes:
                for a in archivos_pendientes:
                    lista_archivos_fabrica.controls.append(
                        ft.Row(
                            [
                                ft.Icon(ft.Icons.DESCRIPTION, size=18, color=ROJO),
                                ft.Text(a.name, expand=True, size=13),
                            ]
                        )
                    )
            else:
                lista_archivos_fabrica.controls.append(
                    ft.Text(
                        f"No hay archivos en Descuentos/Fabrica.\n"
                        "Coloca archivos Excel (.xlsx, .xls) o PDF de remito de fábrica allí.",
                        size=12,
                        color=self.secundario,
                    )
                )
            self.page.update()

        async def procesar_archivos_fabrica(_e: ft.Event) -> None:
            if not self.exigir_roles("administrador"):
                return
            if not archivos_pendientes:
                self.notificar("No hay archivos para procesar en Descuentos/Fabrica.")
                return
            self.page.pop_dialog()
            sobr = modo_sobrescribir.value

            def ejecutar() -> None:
                sm = StockManager(self.menu.ruta_excel_base)
                total_archivos = 0
                for arch in archivos_pendientes:
                    totales, _ = parsear_archivo_fabrica(arch)
                    if not totales:
                        print(f"[AVISO] Sin items válidos en {arch.name}")
                        continue
                    res = sm.registrar_ingreso_fabrica(totales, sobrescribir=sobr)
                    print(f"[OK] {arch.name}: {len(res)} productos actualizados.")
                    for cod, (ant, nvo) in res.items():
                        print(f"     Código {cod}: {ant} -> {nvo}")

                    dest = self.menu.carpeta_descontados / "Fabrica"
                    dest.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(arch), str(dest / arch.name))
                    total_archivos += 1
                print(f"[FINALIZADO] {total_archivos} archivo(s) procesados y archivados.")

            await self.ejecutar_tarea("Ingreso de pedido de fábrica", ejecutar)
            self.actualizar_estado()

        # Contenedores para las vistas de Manual vs Archivo
        vista_manual = ft.Container(
            padding=10,
            content=ft.Column(
                [
                    ft.Row(
                        [
                            campo_cod,
                            campo_cant,
                            ft.Button(
                                "Agregar",
                                icon=ft.Icons.ADD,
                                on_click=agregar_item,
                                bgcolor=ROJO,
                                color=ft.Colors.WHITE,
                            ),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    texto_info_prod,
                    ft.Divider(height=10),
                    ft.Text("Productos listos para aplicar:", weight=ft.FontWeight.BOLD, size=12),
                    lista_cargas,
                ],
                tight=True,
            ),
            visible=True,
        )

        carpeta_fabrica = getattr(self.menu, "carpeta_fabrica", None) or (
            getattr(self.menu, "base_dir", Path(".")) / "Descuentos" / "Fabrica"
        )

        async def subir_fabrica_desde_pc(_e: ft.Event) -> None:
            await self.subir_archivos_desde_pc(
                carpeta_destino=carpeta_fabrica,
                extensiones=["xlsx", "xls", "pdf"],
                titulo="Seleccionar pedido de fábrica (.xlsx, .xls, .pdf)",
                al_terminar=lambda _guardados: refrescar_archivos_fabrica(),
            )

        vista_archivo = ft.Container(
            padding=10,
            content=ft.Column(
                [
                    ft.Text(
                        "Archivos pendientes en Descuentos/Fabrica (.xlsx, .xls, .pdf):",
                        size=12,
                        weight=ft.FontWeight.BOLD,
                    ),
                    lista_archivos_fabrica,
                    ft.Row(
                        [
                            ft.Button(
                                "Subir archivo desde mi PC",
                                icon=ft.Icons.UPLOAD_FILE,
                                bgcolor=ROJO,
                                color=ft.Colors.WHITE,
                                on_click=subir_fabrica_desde_pc,
                            ),
                            ft.TextButton(
                                "Abrir carpeta Fabrica",
                                icon=ft.Icons.FOLDER,
                                on_click=lambda _e: self.abrir_carpeta_informe(carpeta_fabrica),
                            ),
                            ft.TextButton(
                                "Actualizar",
                                icon=ft.Icons.REFRESH,
                                on_click=lambda _e: refrescar_archivos_fabrica(),
                            ),
                        ]
                    ),
                ],
                tight=True,
            ),
            visible=False,
        )

        modo_actual = ["manual"]

        def cambiar_pestana(modo: str) -> None:
            modo_actual[0] = modo
            vista_manual.visible = (modo == "manual")
            vista_archivo.visible = (modo == "archivo")
            btn_tab_manual.style = ft.ButtonStyle(
                color=ft.Colors.WHITE if modo == "manual" else self.secundario,
                bgcolor=ROJO if modo == "manual" else ft.Colors.TRANSPARENT,
            )
            btn_tab_archivo.style = ft.ButtonStyle(
                color=ft.Colors.WHITE if modo == "archivo" else self.secundario,
                bgcolor=ROJO if modo == "archivo" else ft.Colors.TRANSPARENT,
            )
            self.page.update()

        btn_tab_manual = ft.Button(
            "Carga manual",
            icon=ft.Icons.EDIT,
            on_click=lambda _e: cambiar_pestana("manual"),
            style=ft.ButtonStyle(color=ft.Colors.WHITE, bgcolor=ROJO),
        )
        btn_tab_archivo = ft.Button(
            "Por archivo (Fabrica)",
            icon=ft.Icons.FOLDER_OPEN,
            on_click=lambda _e: cambiar_pestana("archivo"),
            style=ft.ButtonStyle(color=self.secundario, bgcolor=ft.Colors.TRANSPARENT),
        )

        refrescar_lista_manual()
        refrescar_archivos_fabrica()

        async def aplicar_segun_modo(e: ft.Event) -> None:
            if modo_actual[0] == "manual":
                await guardar_manual(e)
            else:
                await procesar_archivos_fabrica(e)

        dialogo = ft.AlertDialog(
            modal=True,
            title=ft.Text("Ajustar stock / Cargar pedido de fábrica"),
            content=ft.Column(
                [
                    modo_sobrescribir,
                    ft.Row([btn_tab_manual, btn_tab_archivo], spacing=10),
                    ft.Divider(height=1),
                    vista_manual,
                    vista_archivo,
                ],
                tight=True,
                width=550,
            ),
            actions=[
                self.boton_dialogo("Cancelar", lambda _e: self.page.pop_dialog()),
                self.boton_dialogo("Aplicar a stock", aplicar_segun_modo),
            ],
        )
        self.page.show_dialog(dialogo)

    def mostrar_descuento_mercado_full(self, _evento: ft.Event | None = None) -> None:
        if not self.exigir_roles("administrador"):
            return

        carpeta_full = getattr(self.menu, "carpeta_mercado_full", None) or (
            getattr(self.menu, "base_dir", Path(".")) / "Descuentos" / "MercadoFull"
        )
        carpeta_full.mkdir(parents=True, exist_ok=True)
        archivos_pendientes: list[Path] = []
        if hasattr(self.menu, "_obtener_pendientes_mercado_full"):
            archivos_pendientes = self.menu._obtener_pendientes_mercado_full()
        else:
            for ext in ("*.xlsx", "*.xls"):
                archivos_pendientes.extend(carpeta_full.glob(ext))
            archivos_pendientes.sort()

        lista_previsualizacion = ft.ListView(
            expand=True,
            spacing=4,
            height=260,
        )

        resumen_texto = ft.Text(
            "Selecciona un archivo para previsualizar los productos a descontar."
            if archivos_pendientes
            else "No hay planillas de Mercado Full (.xlsx o .xls) en la carpeta Descuentos/MercadoFull.",
            size=12,
            color=self.secundario,
        )

        sm = StockManager(self.menu.ruta_excel_base)
        items_a_descontar: dict[str, int] = {}
        archivo_seleccionado: list[Path | None] = [archivos_pendientes[0] if archivos_pendientes else None]

        def cargar_previsualizacion_archivo(arch: Path) -> None:
            items_a_descontar.clear()
            lista_previsualizacion.controls.clear()
            try:
                totales, _ = parsear_archivo_mercado_full(arch)
            except Exception as e:
                resumen_texto.value = f"Error al leer {arch.name}: {e}"
                resumen_texto.color = ft.Colors.RED_400
                self.page.update()
                return

            if not totales:
                resumen_texto.value = f"El archivo {arch.name} no contiene productos o columnas reconocidas."
                resumen_texto.color = ft.Colors.AMBER_400
                self.page.update()
                return

            items_a_descontar.update(totales)
            total_unidades = sum(totales.values())
            resumen_texto.value = (
                f"Archivo: {arch.name} | {len(totales)} productos a descontar ({total_unidades} unidades en total)."
            )
            resumen_texto.color = self.texto

            for cod, cant in totales.items():
                nom = sm.catalogo.get(cod, ("", "Producto no encontrado en catálogo", 0))[1]
                stk_actual = sm.catalogo.get(cod, ("", "", 0))[2]
                stk_nuevo = stk_actual - cant

                color_alerta = None
                alerta_txt = ""
                if cod not in sm.catalogo:
                    color_alerta = ft.Colors.RED_400
                    alerta_txt = " [NO EXISTE]"
                elif stk_nuevo < 0:
                    color_alerta = ft.Colors.RED_400
                    alerta_txt = f" [NEGATIVO: {stk_nuevo}]"
                elif stk_nuevo <= 5:
                    color_alerta = ft.Colors.AMBER_400
                    alerta_txt = " [QUIEBRE]"

                lista_previsualizacion.controls.append(
                    ft.Container(
                        padding=ft.padding.symmetric(horizontal=8, vertical=4),
                        border_radius=6,
                        bgcolor=ft.Colors.WHITE_10 if self.modo_oscuro else ft.Colors.GREY_100,
                        content=ft.Row(
                            [
                                ft.Text(f"[{cod}]", weight=ft.FontWeight.BOLD, size=11, width=80),
                                ft.Text(nom, size=11, expand=True, no_wrap=True),
                                ft.Text(f"-{cant} un.", weight=ft.FontWeight.BOLD, color=ft.Colors.RED_400, size=11, width=65),
                                ft.Text(f"Stock: {stk_actual} -> {stk_nuevo}{alerta_txt}", size=11, color=color_alerta or self.secundario, width=150),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                    )
                )
            self.page.update()

        opciones_dropdown = [
            ft.dropdown.Option(arch.name) for arch in archivos_pendientes
        ]
        selector_archivo = ft.Dropdown(
            label="Planilla Mercado Full (.xlsx / .xls)",
            options=opciones_dropdown,
            value=archivos_pendientes[0].name if archivos_pendientes else None,
            expand=True,
            dense=True,
        )

        def cambiar_archivo_dropdown(_e: ft.Event) -> None:
            nombre = selector_archivo.value
            for arch in archivos_pendientes:
                if arch.name == nombre:
                    archivo_seleccionado[0] = arch
                    cargar_previsualizacion_archivo(arch)
                    break

        selector_archivo.on_change = cambiar_archivo_dropdown

        if archivo_seleccionado[0] is not None:
            cargar_previsualizacion_archivo(archivo_seleccionado[0])

        def al_subir_mercado_full(guardados: list[Path]) -> None:
            nonlocal archivos_pendientes
            if hasattr(self.menu, "_obtener_pendientes_mercado_full"):
                archivos_pendientes = self.menu._obtener_pendientes_mercado_full()
            else:
                archivos_pendientes = []
                for ext in ("*.xlsx", "*.xls"):
                    archivos_pendientes.extend(carpeta_full.glob(ext))
                archivos_pendientes.sort()
            for g in guardados:
                if g not in archivos_pendientes:
                    archivos_pendientes.append(g)
            selector_archivo.options = [
                ft.dropdown.Option(arch.name) for arch in archivos_pendientes
            ]
            ultimo = guardados[-1]
            archivo_seleccionado[0] = ultimo
            selector_archivo.value = ultimo.name
            cargar_previsualizacion_archivo(ultimo)

        async def subir_full_desde_pc(_e: ft.Event) -> None:
            await self.subir_archivos_desde_pc(
                carpeta_destino=carpeta_full,
                extensiones=["xlsx", "xls"],
                titulo="Seleccionar planilla de Mercado Full (.xlsx, .xls)",
                al_terminar=al_subir_mercado_full,
            )

        async def confirmar_descuento_full(_e: ft.Event) -> None:
            if not self.exigir_roles("administrador"):
                return
            if not archivo_seleccionado[0] or not items_a_descontar:
                self.notificar("No hay un archivo válido con productos para descontar.")
                return

            arch = archivo_seleccionado[0]
            self.page.pop_dialog()

            def ejecutar() -> None:
                stock_manager = StockManager(self.menu.ruta_excel_base)
                res = stock_manager.descontar_mercado_full(
                    items_a_descontar,
                    nombre_archivo=arch.name,
                    sincronizar_excel=True,
                )
                print(f"[OK] Mercado Full: {len(res)} productos descontados desde {arch.name}.")
                dest = self.menu.carpeta_descontados / "MercadoFull"
                dest.mkdir(parents=True, exist_ok=True)
                shutil.move(str(arch), str(dest / arch.name))
                print(f"[OK] Archivo movido a: {dest / arch.name}")

            await self.ejecutar_tarea(f"Descuento Mercado Full ({arch.name})", ejecutar)
            self.actualizar_estado()
            self.notificar(f"Se descontaron exitosamente los productos de {arch.name} para Mercado Full.")

        dialogo = ft.AlertDialog(
            modal=True,
            title=ft.Row(
                [
                    ft.Icon(ft.Icons.LOCAL_SHIPPING, color=ROJO),
                    ft.Text("Descontar Mercado Envíos Full (Excel)", size=16, weight=ft.FontWeight.BOLD),
                ],
                spacing=8,
            ),
            content=ft.Container(
                width=650,
                content=ft.Column(
                    [
                        ft.Text(
                            "Lee las planillas enviadas a Full desde Descuentos/MercadoFull y descuenta las unidades del depósito central.",
                            size=12,
                            color=self.secundario,
                        ),
                        ft.Divider(height=10),
                        ft.Row(
                            [
                                selector_archivo,
                                ft.Button(
                                    "Subir desde mi PC",
                                    icon=ft.Icons.UPLOAD_FILE,
                                    bgcolor=ROJO,
                                    color=ft.Colors.WHITE,
                                    on_click=subir_full_desde_pc,
                                ),
                                ft.TextButton(
                                    "Abrir carpeta",
                                    icon=ft.Icons.FOLDER_OPEN,
                                    on_click=lambda _e: self.abrir_carpeta_informe(carpeta_full),
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                        resumen_texto,
                        ft.Divider(height=10),
                        ft.Text("Previsualización de impacto en stock:", size=12, weight=ft.FontWeight.BOLD),
                        lista_previsualizacion,
                    ],
                    tight=True,
                    spacing=6,
                ),
            ),
            actions=[
                self.boton_dialogo("Cancelar", lambda _e: self.page.pop_dialog()),
                self.boton_dialogo("Confirmar Descuento", confirmar_descuento_full),
            ],
        )
        self.page.show_dialog(dialogo)

    def mostrar_descuento_mercado_libre(self, _evento: ft.Event | None = None) -> None:
        if not self.exigir_roles("operador", "administrador", "master"):
            return

        carpeta_ml = getattr(self.menu, "carpeta_mercado_libre", None) or (
            getattr(self.menu, "base_dir", Path(".")) / "Descuentos" / "MercadoLibre"
        )
        carpeta_ml.mkdir(parents=True, exist_ok=True)

        archivo_seleccionado: list[Path | None] = [None]
        resultado_parseo: list[ResultadoRemito | None] = [None]
        items_a_descontar: dict[str, int] = {}

        lista_previsualizacion = ft.ListView(
            expand=True,
            spacing=4,
            height=260,
        )
        resumen_texto = ft.Text(
            "Selecciona o sube un archivo .docx de Mercado Libre para previsualizar los productos a descontar.",
            size=12,
            color=self.secundario,
        )
        banner_no_encontrados = ft.Container(visible=False)

        def cargar_previsualizacion_docx(arch: Path) -> None:
            lista_previsualizacion.controls.clear()
            items_a_descontar.clear()
            banner_no_encontrados.visible = False
            sm = StockManager(self.menu.ruta_excel_base)
            productos_catalogo = [
                (codigo, nombre) for _, codigo, nombre, _ in sm.productos_base
            ]

            try:
                res = parsear_pedido_mercado_libre(arch, productos_catalogo)
                resultado_parseo[0] = res
            except Exception as e:
                resumen_texto.value = f"Error al leer el archivo {arch.name}: {e}"
                resumen_texto.color = ft.Colors.RED_400
                self.page.update()
                return

            if not res.items:
                resumen_texto.value = f"El archivo {arch.name} no contiene líneas de productos reconocidas."
                resumen_texto.color = ft.Colors.AMBER_400
                self.page.update()
                return

            total_unidades = sum(it.cantidad for it in res.items)
            for it in res.items:
                cod = normalizar_codigo(it.codigo)
                items_a_descontar[cod] = items_a_descontar.get(cod, 0) + it.cantidad

            resumen_texto.value = (
                f"Comprador: {res.cliente or 'No especificado'} | Paquete/Remito: {res.numero_remito or 'Sin número'} | "
                f"{len(items_a_descontar)} productos ({total_unidades} unidades a descontar)"
            )
            resumen_texto.color = self.texto

            if res.descripciones_sin_coincidencia:
                lineas_aviso = [
                    ft.Text(f"• {desc} ({motivo})", size=11, color=ft.Colors.AMBER_200 if self.modo_oscuro else ft.Colors.AMBER_900)
                    for desc, motivo in res.descripciones_sin_coincidencia
                ]
                banner_no_encontrados.visible = True
                banner_no_encontrados.content = ft.Container(
                    bgcolor=ft.Colors.AMBER_900 if self.modo_oscuro else ft.Colors.AMBER_100,
                    border=ft.Border.all(1, ft.Colors.AMBER_600),
                    border_radius=6,
                    padding=8,
                    content=ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Icon(ft.Icons.WARNING_AMBER, color=ft.Colors.AMBER_400, size=16),
                                    ft.Text(
                                        "Líneas que no coincidieron con el catálogo (no se descontarán):",
                                        weight=ft.FontWeight.BOLD,
                                        size=11,
                                        color=ft.Colors.AMBER_200 if self.modo_oscuro else ft.Colors.AMBER_900,
                                    ),
                                ],
                                spacing=6,
                            ),
                            *lineas_aviso,
                        ],
                        spacing=4,
                    ),
                )

            hash_candidato = calcular_hash_archivo(arch)
            duplicado = self.order_store.buscar_pedido_por_hash(hash_candidato) if hash_candidato else None
            if duplicado:
                banner_no_encontrados.visible = True
                banner_no_encontrados.content = ft.Container(
                    bgcolor=ft.Colors.RED_900 if self.modo_oscuro else ft.Colors.RED_100,
                    border=ft.Border.all(1, ft.Colors.RED_400),
                    border_radius=6,
                    padding=8,
                    content=ft.Row(
                        [
                            ft.Icon(ft.Icons.BLOCK, color=ft.Colors.RED_400, size=18),
                            ft.Text(
                                f"⛔ ATENCIÓN: Este archivo ya fue descontado el {duplicado.created_at[:16]} "
                                f"(Comprobante: {duplicado.nota_pedido}).",
                                weight=ft.FontWeight.BOLD,
                                size=11,
                                color=ft.Colors.RED_200 if self.modo_oscuro else ft.Colors.RED_900,
                                expand=True,
                            ),
                        ],
                        spacing=8,
                    ),
                )

            for cod, cant in items_a_descontar.items():
                nom = sm.catalogo.get(cod, ("", "Producto no encontrado", 0))[1]
                stk_actual = sm.catalogo.get(cod, ("", "", 0))[2]
                stk_nuevo = stk_actual - cant
                color_alerta = ft.Colors.RED_400 if stk_nuevo <= 0 else None
                alerta_txt = " (¡AGOTADO!)" if stk_nuevo <= 0 else ""

                lista_previsualizacion.controls.append(
                    ft.Container(
                        padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                        border_radius=6,
                        bgcolor=ft.Colors.WHITE_10 if self.modo_oscuro else ft.Colors.GREY_100,
                        content=ft.Row(
                            [
                                ft.Text(f"[{cod}]", weight=ft.FontWeight.BOLD, size=11, width=80),
                                ft.Text(nom, size=11, expand=True, no_wrap=True),
                                ft.Text(f"-{cant} un.", weight=ft.FontWeight.BOLD, color=ft.Colors.RED_400, size=11, width=65),
                                ft.Text(f"Stock: {stk_actual} -> {stk_nuevo}{alerta_txt}", size=11, color=color_alerta or self.secundario, width=150),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                    )
                )
            self.page.update()

        archivos_pendientes: list[Path] = sorted(list(carpeta_ml.glob("*.docx")))

        opciones_dropdown = [
            ft.dropdown.Option(arch.name) for arch in archivos_pendientes
        ]
        selector_archivo = ft.Dropdown(
            label="Seleccionar pedido de Mercado Libre (.docx)",
            options=opciones_dropdown,
            value=archivos_pendientes[0].name if archivos_pendientes else None,
            expand=True,
            dense=True,
        )

        def cambiar_archivo_dropdown(_e: ft.Event) -> None:
            nombre = selector_archivo.value
            for arch in archivos_pendientes:
                if arch.name == nombre:
                    archivo_seleccionado[0] = arch
                    cargar_previsualizacion_docx(arch)
                    break

        selector_archivo.on_change = cambiar_archivo_dropdown
        if archivos_pendientes:
            archivo_seleccionado[0] = archivos_pendientes[0]
            cargar_previsualizacion_docx(archivos_pendientes[0])

        def al_subir_docx(guardados: list[Path]) -> None:
            if not guardados:
                return
            nombres_existentes = {a.name for a in archivos_pendientes}
            for g in guardados:
                if g.name not in nombres_existentes:
                    archivos_pendientes.append(g)
                    nombres_existentes.add(g.name)
            selector_archivo.options = [
                ft.dropdown.Option(a.name) for a in archivos_pendientes
            ]
            arch = guardados[0]
            archivo_seleccionado[0] = arch
            selector_archivo.value = arch.name
            cargar_previsualizacion_docx(arch)
            self.page.update()

        async def subir_desde_pc(_e: ft.Event) -> None:
            try:
                guardados = await self.subir_archivos_desde_pc(
                    carpeta_destino=carpeta_ml,
                    extensiones=["docx"],
                    titulo="Seleccionar pedido de Mercado Libre (.docx)",
                    al_terminar=al_subir_docx,
                )
                if guardados:
                    al_subir_docx(guardados)
            except Exception as err:
                self.notificar(f"Error al subir archivo de Mercado Libre: {err}")

        async def confirmar_descuento_ml(_e: ft.Event) -> None:
            if not archivo_seleccionado[0] or not items_a_descontar:
                self.notificar("Debes seleccionar un archivo .docx válido con productos para descontar.")
                return

            arch = archivo_seleccionado[0]
            hash_doc = calcular_hash_archivo(arch)
            if hash_doc:
                dup = self.order_store.buscar_pedido_por_hash(hash_doc)
                if dup:
                    self.notificar(
                        f"⛔ Este archivo ya fue procesado el {dup.created_at[:16]} ({dup.nota_pedido}) y no puede volver a descontarse."
                    )
                    return

            res = resultado_parseo[0]
            armador_nom = self.usuario_actual.username if self.usuario_actual else "Operario"
            self.page.pop_dialog()

            def ejecutar_descuento_ml() -> None:
                sm = StockManager(self.menu.ruta_excel_base)
                agente = AgenteRemitosStock(stock_manager=sm)
                reporte = agente.ejecutar(
                    rutas_mercado_libre=[arch],
                    carpeta_descuentos=self.menu.carpeta_descuentos,
                    simulacion=False,
                )

                nombre_inf = Path(reporte.reporte_stock.archivo_guardado).name if reporte.reporte_stock.archivo_guardado else f"ML_{arch.stem}"
                sm.actualizar_stock_base(
                    descuentos=reporte.reporte_stock.descuentos_aplicados,
                    sincronizar_excel=True,
                    nombre_archivo=nombre_inf,
                    usuario=armador_nom,
                )

                pdf_nom = Path(reporte.reporte_stock.archivo_pdf).name if reporte.reporte_stock.archivo_pdf else ""
                total_desc = sum(d.cantidad_descontada for d in reporte.reporte_stock.descuentos_aplicados)
                resumen_items = f"{len(reporte.reporte_stock.descuentos_aplicados)} productos ({total_desc} un.)"

                nota_ml = (res.numero_remito or arch.stem).strip() if res else arch.stem
                if self.order_store.existe_nota_pedido(nota_ml):
                    nota_ml = f"{nota_ml}_{datetime.now().strftime('%H%M%S')}"

                cliente_ml = (res.cliente or "Mercado Libre").strip() if res else "Mercado Libre"

                items_descontados = [
                    (d.codigo, d.nombre_producto, d.cantidad_descontada)
                    for d in reporte.reporte_stock.descuentos_aplicados
                ]

                dest_pedidos = application_root() / "data" / "pedidos_archivos"
                dest_pedidos.mkdir(parents=True, exist_ok=True)
                try:
                    shutil.copy2(str(arch), str(dest_pedidos / arch.name))
                except Exception:
                    pass

                self.order_store.registrar_pedido(
                    nota_pedido=nota_ml,
                    numero_pedido=nota_ml,
                    cliente=cliente_ml,
                    bultos=1,
                    logistica="Transporte",
                    armador=armador_nom,
                    tipo_archivo="docx",
                    nombre_archivo=arch.name,
                    agregado=False,
                    articulos_descontados=total_desc,
                    resumen_items=resumen_items,
                    archivo_descuento=pdf_nom,
                    items=items_descontados,
                    archivo_hash=hash_doc,
                )

                dest_archivado = self.menu.carpeta_descontados / "MercadoLibre"
                dest_archivado.mkdir(parents=True, exist_ok=True)
                try:
                    shutil.move(str(arch), str(dest_archivado / arch.name))
                except Exception:
                    pass

                self.actualizar_listas()
                print(f"[OK] Mercado Libre descontado: {nota_ml} | Cliente: {cliente_ml} | Items: {resumen_items} | PDF: {pdf_nom}")

            await self.ejecutar_tarea(f"Descuento Mercado Libre ({arch.name})", ejecutar_descuento_ml)
            self.notificar(f"Se descontaron exitosamente los productos de Mercado Libre ({arch.name}).")

        dialogo = ft.AlertDialog(
            modal=True,
            title=ft.Row(
                [
                    ft.Icon(ft.Icons.STOREFRONT, color=ROJO),
                    ft.Text("Descontar Pedido Mercado Libre (DOCX)", size=16, weight=ft.FontWeight.BOLD),
                ],
                spacing=8,
            ),
            content=ft.Container(
                width=650,
                content=ft.Column(
                    [
                        ft.Text(
                            "Compara los nombres de productos del archivo .docx contra el catálogo y descuenta el stock en tiempo real en la base de datos.",
                            size=12,
                            color=self.secundario,
                        ),
                        ft.Divider(height=8),
                        ft.Row(
                            [
                                selector_archivo,
                                ft.Button(
                                    "Cargar de PC",
                                    icon=ft.Icons.UPLOAD_FILE,
                                    bgcolor=ft.Colors.BLUE_GREY_800 if self.modo_oscuro else ft.Colors.BLUE_GREY_100,
                                    color=self.texto,
                                    on_click=subir_desde_pc,
                                ),
                            ],
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=8,
                        ),
                        resumen_texto,
                        banner_no_encontrados,
                        ft.Text("Vista previa de productos a descontar:", size=12, weight=ft.FontWeight.BOLD, color=self.texto),
                        lista_previsualizacion,
                    ],
                    tight=True,
                    spacing=8,
                ),
            ),
            actions=[
                ft.Button(
                    "Confirmar y Descontar",
                    icon=ft.Icons.CHECK_CIRCLE,
                    bgcolor=ROJO,
                    color=ft.Colors.WHITE,
                    on_click=confirmar_descuento_ml,
                ),
                self.boton_dialogo("Cancelar", lambda _e: self.page.pop_dialog()),
            ],
        )
        self.page.show_dialog(dialogo)

    def mostrar_notificaciones_admin(self, _evento: ft.Event | None = None) -> None:
        if not self.exigir_roles("administrador"):
            return

        sm = StockManager(self.menu.ruta_excel_base)
        lista_notificaciones = ft.ListView(
            expand=True,
            spacing=8,
            height=340,
        )

        def recargar_lista() -> None:
            lista_notificaciones.controls.clear()
            items = sm.obtener_notificaciones_admin(solo_no_leidas=False)
            if not items:
                lista_notificaciones.controls.append(
                    ft.Container(
                        alignment=ft.Alignment.CENTER,
                        padding=20,
                        content=ft.Text(
                            "No hay notificaciones de operarios registradas.",
                            color=self.secundario,
                            size=13,
                        ),
                    )
                )
            else:
                for n in items:
                    nid = n["id"]
                    leida = bool(n["is_read"])
                    operador = n["operator_username"]
                    fecha = n["created_at"]
                    msg = n["message"]
                    tipo_notif = n["notification_type"] if "notification_type" in n.keys() else "descuento"

                    def crear_handler_marcar(notif_id: int):
                        def marcar(_e: ft.Event):
                            sm.marcar_notificaciones_leidas(notif_id)
                            recargar_lista()
                            self.page.update()
                        return marcar

                    badge_leida = None
                    if not leida:
                        badge_leida = ft.Container(
                            content=ft.Text("NUEVA", size=9, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                            bgcolor=ROJO,
                            padding=ft.padding.symmetric(horizontal=6, vertical=2),
                            border_radius=4,
                        )

                    etiqueta_tipo = "Inventario Físico" if tipo_notif == "stock_fisico" else "Descuento"
                    fila_cabecera = [
                        ft.Icon(
                            ft.Icons.ASSIGNMENT_TURNED_IN
                            if tipo_notif == "stock_fisico"
                            else (ft.Icons.NOTIFICATIONS_ACTIVE if not leida else ft.Icons.CHECK_CIRCLE),
                            color=ft.Colors.BLUE_500
                            if (tipo_notif == "stock_fisico" and not leida)
                            else (ROJO if not leida else ft.Colors.GREEN_600),
                            size=16,
                        ),
                        ft.Text(f"[{etiqueta_tipo}] Operario: {operador}", weight=ft.FontWeight.BOLD, size=12, color=self.texto),
                        ft.Text(f"· {fecha}", size=11, color=self.secundario),
                    ]
                    if badge_leida:
                        fila_cabecera.append(badge_leida)

                    card_content = [
                        ft.Row(fila_cabecera, vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=6),
                        ft.Text(msg, size=12, color=self.texto),
                    ]
                    acciones_fila = []
                    if tipo_notif == "stock_fisico":
                        acciones_fila.append(
                            ft.TextButton(
                                "Ver comparativa",
                                icon=ft.Icons.COMPARE_ARROWS,
                                on_click=lambda _e: (
                                    self.page.pop_dialog(),
                                    self.mostrar_comparativa_stock_fisico_admin(),
                                ),
                            )
                        )
                    if not leida:
                        acciones_fila.append(
                            ft.TextButton(
                                "Marcar como leída",
                                icon=ft.Icons.CHECK,
                                on_click=crear_handler_marcar(nid),
                            )
                        )
                    if acciones_fila:
                        card_content.append(
                            ft.Row(acciones_fila, alignment=ft.MainAxisAlignment.END)
                        )

                    lista_notificaciones.controls.append(
                        ft.Container(
                            padding=10,
                            border_radius=8,
                            bgcolor=ft.Colors.RED_50 if (not leida and not self.modo_oscuro) else (ft.Colors.WHITE_10 if not leida else ft.Colors.TRANSPARENT),
                            border=ft.border.all(1, ft.Colors.RED_200 if (not leida and not self.modo_oscuro) else self.borde),
                            content=ft.Column(card_content, spacing=4),
                        )
                    )
            self.page.update()

        recargar_lista()

        def marcar_todas_leidas(_e: ft.Event) -> None:
            sm.marcar_notificaciones_leidas(None)
            recargar_lista()
            self.page.update()

        dialogo = ft.AlertDialog(
            modal=True,
            title=ft.Row(
                [
                    ft.Icon(ft.Icons.NOTIFICATIONS, color=ROJO),
                    ft.Text("Notificaciones de Descuentos de Operarios", size=16, weight=ft.FontWeight.BOLD),
                ],
                spacing=8,
            ),
            content=ft.Container(
                width=550,
                content=ft.Column(
                    [
                        ft.Text(
                            "Registro de descuentos de stock ejecutados por usuarios con rol de operador.",
                            size=12,
                            color=self.secundario,
                        ),
                        ft.Divider(height=6),
                        lista_notificaciones,
                    ],
                    tight=True,
                    spacing=6,
                ),
            ),
            actions=[
                ft.TextButton("Marcar todas como leídas", icon=ft.Icons.DONE_ALL, on_click=marcar_todas_leidas),
                self.boton_dialogo("Cerrar", lambda _e: (self.page.pop_dialog(), self.actualizar_estado())),
            ],
        )
        self.page.show_dialog(dialogo)

    def mostrar_stock_fisico_operario(self, _evento: ft.Event | None = None) -> None:
        if not self.exigir_roles("operador"):
            return

        carpeta_sf = getattr(self.menu, "carpeta_stock_fisico", None) or (
            getattr(self.menu, "base_dir", Path(".")) / "Descuentos" / "StockFisico"
        )
        carpeta_sf.mkdir(parents=True, exist_ok=True)
        archivos_pendientes: list[Path] = []
        if hasattr(self.menu, "_obtener_pendientes_stock_fisico"):
            archivos_pendientes = self.menu._obtener_pendientes_stock_fisico()
        else:
            for ext in ("*.xlsx", "*.xls"):
                archivos_pendientes.extend(carpeta_sf.glob(ext))
            archivos_pendientes.sort()

        lista_comparativa = ft.ListView(
            expand=True,
            spacing=4,
            height=280,
        )

        resumen_texto = ft.Text(
            "Selecciona una planilla Excel para comparar el stock físico con el stock digital."
            if archivos_pendientes
            else "No hay planillas de stock físico (.xlsx o .xls) en Descuentos/StockFisico.",
            size=12,
            color=self.secundario,
        )

        sm = StockManager(self.menu.ruta_excel_base)
        items_relevados: dict[str, int] = {}
        archivo_seleccionado: list[Path | None] = [
            archivos_pendientes[0] if archivos_pendientes else None
        ]

        def cargar_comparativa_archivo(arch: Path) -> None:
            items_relevados.clear()
            lista_comparativa.controls.clear()
            try:
                totales, _ = parsear_excel_stock_fisico(arch)
            except Exception as e:
                resumen_texto.value = f"Error al leer {arch.name}: {e}"
                resumen_texto.color = ft.Colors.RED_400
                self.page.update()
                return

            if not totales:
                resumen_texto.value = (
                    f"El archivo {arch.name} no contiene productos o columnas válidas."
                )
                resumen_texto.color = ft.Colors.AMBER_400
                self.page.update()
                return

            items_relevados.update(totales)
            comparativa = sm.comparar_stock_fisico(totales)
            coinciden = sum(1 for i in comparativa if i["diferencia"] == 0 and i["en_catalogo"])
            faltantes = sum(1 for i in comparativa if i["diferencia"] < 0 and i["en_catalogo"])
            sobrantes = sum(1 for i in comparativa if i["diferencia"] > 0 and i["en_catalogo"])

            resumen_texto.value = (
                f"Archivo: {arch.name} | Relevados: {len(comparativa)} | "
                f"Coinciden: {coinciden} | Faltantes: {faltantes} | Sobrantes: {sobrantes}"
            )
            resumen_texto.color = self.texto

            for item in comparativa:
                cod = item["code"]
                nom = item["name"]
                stk_dig = item["stock_digital"]
                stk_fis = item["stock_fisico"]
                dif = item["diferencia"]
                estado = item["estado"]
                dif_str = f"+{dif}" if dif > 0 else str(dif)

                if estado == "COINCIDE":
                    color_est = ft.Colors.GREEN_500
                elif estado in ("FALTANTE", "NO_CATALOGADO"):
                    color_est = ft.Colors.RED_400
                else:
                    color_est = ft.Colors.AMBER_400

                lista_comparativa.controls.append(
                    ft.Container(
                        padding=ft.padding.symmetric(horizontal=8, vertical=4),
                        border_radius=6,
                        bgcolor=ft.Colors.WHITE_10 if self.modo_oscuro else ft.Colors.GREY_100,
                        content=ft.Row(
                            [
                                ft.Text(f"[{cod}]", weight=ft.FontWeight.BOLD, size=11, width=75),
                                ft.Text(nom, size=11, expand=True, no_wrap=True),
                                ft.Text(
                                    f"Dig: {stk_dig} | Fís: {stk_fis}",
                                    size=11,
                                    color=self.texto,
                                    width=120,
                                ),
                                ft.Text(
                                    f"Dif: {dif_str} [{estado}]",
                                    weight=ft.FontWeight.BOLD,
                                    size=11,
                                    color=color_est,
                                    width=145,
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                    )
                )
            self.page.update()

        opciones_dropdown = [
            ft.dropdown.Option(arch.name) for arch in archivos_pendientes
        ]
        selector_archivo = ft.Dropdown(
            label="Planilla de Stock Físico (.xlsx / .xls)",
            options=opciones_dropdown,
            value=archivos_pendientes[0].name if archivos_pendientes else None,
            expand=True,
            dense=True,
        )

        def cambiar_archivo_dropdown(_e: ft.Event) -> None:
            nombre = selector_archivo.value
            for arch in archivos_pendientes:
                if arch.name == nombre:
                    archivo_seleccionado[0] = arch
                    cargar_comparativa_archivo(arch)
                    break

        selector_archivo.on_change = cambiar_archivo_dropdown

        if archivo_seleccionado[0] is not None:
            cargar_comparativa_archivo(archivo_seleccionado[0])

        def al_subir_stock_fisico(guardados: list[Path]) -> None:
            nonlocal archivos_pendientes
            if hasattr(self.menu, "_obtener_pendientes_stock_fisico"):
                archivos_pendientes = self.menu._obtener_pendientes_stock_fisico()
            else:
                archivos_pendientes = []
                for ext in ("*.xlsx", "*.xls"):
                    archivos_pendientes.extend(carpeta_sf.glob(ext))
                archivos_pendientes.sort()
            for g in guardados:
                if g not in archivos_pendientes:
                    archivos_pendientes.append(g)
            selector_archivo.options = [
                ft.dropdown.Option(arch.name) for arch in archivos_pendientes
            ]
            ultimo = guardados[-1]
            archivo_seleccionado[0] = ultimo
            selector_archivo.value = ultimo.name
            cargar_comparativa_archivo(ultimo)

        async def subir_sf_desde_pc(_e: ft.Event) -> None:
            await self.subir_archivos_desde_pc(
                carpeta_destino=carpeta_sf,
                extensiones=["xlsx", "xls"],
                titulo="Seleccionar planilla de Stock Físico (.xlsx, .xls)",
                al_terminar=al_subir_stock_fisico,
            )

        async def confirmar_stock_fisico(_e: ft.Event) -> None:
            if not self.exigir_roles("operador"):
                return
            if not archivo_seleccionado[0] or not items_relevados:
                self.notificar("No hay un archivo válido con conteo físico para registrar.")
                return

            arch = archivo_seleccionado[0]
            operario_nom = self.usuario_actual.username if self.usuario_actual else "operador"
            self.page.pop_dialog()
            ruta_generada: list[Path | None] = [None]

            def ejecutar() -> None:
                stock_manager = StockManager(self.menu.ruta_excel_base)
                ruta_doc, comp = stock_manager.procesar_stock_fisico(
                    items_relevados,
                    usuario=operario_nom,
                    nombre_archivo=arch.name,
                )
                ruta_generada[0] = ruta_doc
                con_dif = sum(1 for i in comp if i["diferencia"] != 0)
                print(
                    f"[OK] Stock físico actualizado por '{operario_nom}': "
                    f"{len(comp)} productos ({con_dif} con diferencia)."
                )
                print(f"[OK] Documento unificado para administrador: {ruta_doc}")
                dest = self.menu.carpeta_descontados / "StockFisico"
                dest.mkdir(parents=True, exist_ok=True)
                shutil.move(str(arch), str(dest / arch.name))

            await self.ejecutar_tarea(f"Relevamiento de stock físico ({arch.name})", ejecutar)
            self.actualizar_estado()
            doc_msg = f" Se generó el documento unificado '{ruta_generada[0].name}' y se notificó al administrador." if ruta_generada[0] else ""
            self.notificar(f"Stock físico actualizado y comparado exitosamente.{doc_msg}")

        dialogo = ft.AlertDialog(
            modal=True,
            title=ft.Row(
                [
                    ft.Icon(ft.Icons.ASSIGNMENT_TURNED_IN, color=ROJO),
                    ft.Text("Hacer Stock Físico y Comparar con Digital", size=16, weight=ft.FontWeight.BOLD),
                ],
                spacing=8,
            ),
            content=ft.Container(
                width=680,
                content=ft.Column(
                    [
                        ft.Text(
                            "Lee la planilla Excel desde Descuentos/StockFisico, actualiza el stock físico, "
                            "compara con el stock digital mostrando diferencias y genera el documento unificado para el administrador.",
                            size=12,
                            color=self.secundario,
                        ),
                        ft.Divider(height=10),
                        ft.Row(
                            [
                                selector_archivo,
                                ft.Button(
                                    "Subir desde mi PC",
                                    icon=ft.Icons.UPLOAD_FILE,
                                    bgcolor=ROJO,
                                    color=ft.Colors.WHITE,
                                    on_click=subir_sf_desde_pc,
                                ),
                                ft.TextButton(
                                    "Abrir carpeta",
                                    icon=ft.Icons.FOLDER_OPEN,
                                    on_click=lambda _e: self.abrir_carpeta_informe(carpeta_sf),
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                        resumen_texto,
                        ft.Divider(height=10),
                        ft.Text("Comparativa Stock Digital vs. Stock Físico:", size=12, weight=ft.FontWeight.BOLD),
                        lista_comparativa,
                    ],
                    tight=True,
                    spacing=6,
                ),
            ),
            actions=[
                self.boton_dialogo("Cancelar", lambda _e: self.page.pop_dialog()),
                self.boton_dialogo("Confirmar y Notificar Admin", confirmar_stock_fisico),
            ],
        )
        self.page.show_dialog(dialogo)

    def mostrar_comparativa_stock_fisico_admin(self, _evento: ft.Event | None = None) -> None:
        if not self.exigir_roles("administrador"):
            return

        sm = StockManager(self.menu.ruta_excel_base)
        inventarios = sm.listar_inventarios_fisicos(limit=25)

        lista_detalles = ft.ListView(
            expand=True,
            spacing=4,
            height=300,
        )

        solo_diferencias = ft.Checkbox(label="Mostrar solo productos con diferencias", value=False)
        resumen_admin = ft.Text(
            "No se han registrado relevamientos de stock físico por parte de los operarios todavía."
            if not inventarios
            else "",
            size=12,
            color=self.secundario,
        )

        inv_actual: list = [inventarios[0] if inventarios else None]

        def recargar_detalle() -> None:
            lista_detalles.controls.clear()
            cab = inv_actual[0]
            if cab is None:
                self.page.update()
                return

            detalles = sm.obtener_detalle_inventario_fisico(int(cab["id"]))
            doc_unif = Path(cab["reporte_unificado"]).name if cab["reporte_unificado"] else "N/A"
            resumen_admin.value = (
                f"Operario: {cab['usuario']} · Fecha: {cab['fecha']} · "
                f"Relevados: {cab['total_relevados']} · Con diferencias: {cab['total_diferencias']} · "
                f"Documento: {doc_unif}"
            )
            resumen_admin.color = self.texto

            for d in detalles:
                dif = int(d["diferencia"])
                if solo_diferencias.value and dif == 0:
                    continue
                cod = str(d["product_code"])
                nom = str(d["product_name"])
                stk_dig = int(d["stock_digital"])
                stk_fis = int(d["stock_fisico"])
                estado = str(d["estado"])
                dif_str = f"+{dif}" if dif > 0 else str(dif)

                if estado == "COINCIDE":
                    color_est = ft.Colors.GREEN_500
                elif estado in ("FALTANTE", "NO_CATALOGADO"):
                    color_est = ft.Colors.RED_400
                else:
                    color_est = ft.Colors.AMBER_400

                lista_detalles.controls.append(
                    ft.Container(
                        padding=ft.padding.symmetric(horizontal=8, vertical=4),
                        border_radius=6,
                        bgcolor=ft.Colors.WHITE_10 if self.modo_oscuro else ft.Colors.GREY_100,
                        content=ft.Row(
                            [
                                ft.Text(f"[{cod}]", weight=ft.FontWeight.BOLD, size=11, width=75),
                                ft.Text(nom, size=11, expand=True, no_wrap=True),
                                ft.Text(f"Digital: {stk_dig}", size=11, width=85),
                                ft.Text(f"Físico: {stk_fis}", size=11, width=85),
                                ft.Text(
                                    f"Dif: {dif_str} [{estado}]",
                                    weight=ft.FontWeight.BOLD,
                                    size=11,
                                    color=color_est,
                                    width=145,
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                    )
                )
            self.page.update()

        opciones_inv = [
            ft.dropdown.Option(
                key=str(inv["id"]),
                text=f"#{inv['id']} · {inv['fecha']} · Operario: {inv['usuario']} ({inv['total_diferencias']} dif.)",
            )
            for inv in inventarios
        ]
        selector_inv = ft.Dropdown(
            label="Relevamientos de Stock Físico registrados",
            options=opciones_inv,
            value=str(inventarios[0]["id"]) if inventarios else None,
            expand=True,
            dense=True,
        )

        def cambiar_inv(_e: ft.Event) -> None:
            val = selector_inv.value
            for inv in inventarios:
                if str(inv["id"]) == val:
                    inv_actual[0] = inv
                    recargar_detalle()
                    break

        selector_inv.on_change = cambiar_inv
        solo_diferencias.on_change = lambda _e: recargar_detalle()

        if inv_actual[0] is not None:
            recargar_detalle()

        def abrir_documento_unificado(_e: ft.Event) -> None:
            cab = inv_actual[0]
            if cab is None or not cab["reporte_unificado"]:
                self.notificar("No hay un documento unificado asociado a este relevamiento.")
                return
            ruta = Path(cab["reporte_unificado"])
            if not ruta.exists():
                self.notificar(f"El archivo '{ruta.name}' no se encuentra en disco.")
                return
            self.abrir_informe(ruta_especifica=ruta)

        dialogo = ft.AlertDialog(
            modal=True,
            title=ft.Row(
                [
                    ft.Icon(ft.Icons.COMPARE_ARROWS, color=ROJO),
                    ft.Text("Comparativa y Diferencias: Stock Digital vs. Físico", size=16, weight=ft.FontWeight.BOLD),
                ],
                spacing=8,
            ),
            content=ft.Container(
                width=700,
                content=ft.Column(
                    [
                        ft.Row([selector_inv], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        resumen_admin,
                        solo_diferencias,
                        ft.Divider(height=6),
                        lista_detalles,
                    ],
                    tight=True,
                    spacing=6,
                ),
            ),
            actions=[
                ft.TextButton(
                    "Descargar / Abrir Documento Unificado (Excel)",
                    icon=ft.Icons.DOWNLOAD,
                    on_click=abrir_documento_unificado,
                ),
                self.boton_dialogo("Cerrar", lambda _e: self.page.pop_dialog()),
            ],
        )
        self.page.show_dialog(dialogo)

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
) -> None:
    import logging
    import sys
    import webbrowser

    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")

    os.environ["STOCKAGENT_PORT"] = str(port)
    if modo_web:
        # Si ya hay una instancia de StockAgent escuchando en este puerto,
        # abrir directamente el navegador hacia la instancia activa.
        if not hasattr(ft.run, "_mock_name") and _puerto_local_activo(port):
            url_activa = f"http://127.0.0.1:{port}"
            print(f"[INFO] Servidor activo detectado en {url_activa}. Abriendo navegador...")
            webbrowser.open(url_activa)
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

            _orig_open = getattr(_flet_app, "_orig_open_in_browser", _flet_app.open_in_browser)
            setattr(_flet_app, "_orig_open_in_browser", _orig_open)

            def _open_local_browser(url: str) -> None:
                _orig_open(url.replace("://0.0.0.0:", "://127.0.0.1:"))

            _flet_app.open_in_browser = _open_local_browser
        except Exception:
            pass

        try:
            import flet_web
            import flet_web.fastapi
            import flet_web.fastapi.serve_fastapi_web_app as _sfa
            from starlette.responses import FileResponse

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
        except Exception:
            pass

        ip_local = obtener_ip_local()
        print("=" * 66)
        print("  STOCK AGENT - SERVIDOR WEB MULTI-EQUIPO (OPCIÓN 2)")
        print("=" * 66)
        print(f"  -> En esta PC (Principal):   http://127.0.0.1:{port}")
        print(f"  -> Desde la 2da PC (Red):    http://{ip_local}:{port}")
        print("  Mantén esta aplicación ejecutándose para que ambas máquinas")
        print("  puedan operar sobre el inventario en tiempo real.")
        print("=" * 66)
        assets_dir = obtener_directorio_assets()
        os.environ["FLET_ASSETS_DIR"] = assets_dir
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
    else:
        assets_dir = obtener_directorio_assets()
        ft.run(
            main,
            view=ft.AppView.FLET_APP,
            name="StockAgent",
            assets_dir=assets_dir,
            no_cdn=False,
            web_renderer=ft.WebRenderer.AUTO,
        )
