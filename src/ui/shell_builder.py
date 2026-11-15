"""Constructor modular del shell Flet (ventana, controles compartidos, layout y barra de estado)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import flet as ft

from ..chat import obtener_mensaje_bienvenida
from .components import (
    aplicar_posicion_sidebar_ui,
    construir_navigation_bar_movil,
    construir_sidebar_controls,
)
from .theme import ROJO


def inicializar_controles_shell(interfaz: Any) -> None:
    """Inicializa los controles de estado y mensajería compartidos por el dashboard."""
    interfaz.mayoristas = ft.Checkbox(label="Mayoristas · PDF", value=True)
    interfaz.canjes = ft.Checkbox(label="Canjes · Excel", value=True)
    interfaz.mercado_libre = ft.Checkbox(label="Mercado Libre · DOCX", value=True)
    interfaz.icono_estado_tarea = ft.Icon(
        ft.Icons.CHECK_CIRCLE_OUTLINE_ROUNDED,
        size=14,
        color=ft.Colors.GREEN_400,
    )
    interfaz.estado_tarea = ft.Text(
        "Sistema listo", color=interfaz.secundario, size=11, weight=ft.FontWeight.W_500
    )
    interfaz.progreso_barra = ft.ProgressBar(width=160, value=None, color=ROJO, visible=False)
    interfaz.lista_informes = ft.ListView(expand=True, spacing=4)
    interfaz.actividad = ft.ListView(expand=True, spacing=6, auto_scroll=True)
    interfaz.header_pedidos_fecha = ft.Text(
        "Fecha de hoy", size=13, weight=ft.FontWeight.BOLD, color=interfaz.texto
    )
    interfaz.header_pedidos_subtitulo = ft.Text(
        "0 pedidos preparados", size=11, color=interfaz.secundario
    )
    interfaz.header_pedidos_bultos = ft.Text(
        "0 bultos", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE
    )
    interfaz.lista_pedidos_preparados = ft.ListView(expand=True, spacing=6)
    interfaz.conversacion = ft.ListView(expand=True, spacing=8, auto_scroll=True)
    interfaz.entrada_chat = ft.TextField(
        hint_text="Escribe una consulta o /ayuda",
        expand=True,
        min_lines=1,
        max_lines=3,
        on_submit=interfaz.enviar_chat,
    )
    interfaz.conversacion_equipo = ft.ListView(expand=True, spacing=8, auto_scroll=True)
    interfaz.entrada_chat_equipo = ft.TextField(
        hint_text="Escribe un mensaje para el equipo...",
        expand=True,
        dense=True,
        on_submit=interfaz.enviar_mensaje_equipo,
    )
    interfaz.selector_destinatario_equipo = ft.Dropdown(
        label="Destinatario",
        options=[ft.dropdown.Option("Todos", "📢 Todos (Canal General)")],
        value="Todos",
        dense=True,
        expand=True,
    )
    interfaz.texto_badge_chat = ft.Text("", size=10, color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD)
    interfaz.badge_chat_container = ft.Container(
        content=interfaz.texto_badge_chat,
        bgcolor=ft.Colors.RED_600,
        border_radius=10,
        padding=ft.Padding.symmetric(horizontal=5, vertical=1),
        visible=False,
    )
    interfaz.texto_badge_tab = ft.Text("", size=10, color=ft.Colors.RED_400, weight=ft.FontWeight.BOLD)
    interfaz.pendientes_texto = ft.Text("", color=interfaz.secundario, size=12)


def configurar_dialogos_adaptables_shell(interfaz: Any) -> None:
    """Interpreta dimensiones en diálogos para adaptarlos a pantallas pequeñas."""
    page = interfaz.page
    if hasattr(page, "show_dialog") and not getattr(page, "_dialogos_adaptables_configurados", False):
        orig_show = page.show_dialog

        def show_dialog_adaptable(dialogo):
            interfaz.cerrar_drawer_si_movil()
            if hasattr(dialogo, "content") and dialogo.content is not None:
                for ctrl in [dialogo.content, getattr(dialogo.content, "content", None)]:
                    if ctrl is not None:
                        w_orig = getattr(ctrl, "width", None)
                        if isinstance(w_orig, (int, float)):
                            ctrl.width = interfaz.ancho_adaptable(int(w_orig))
                        h_orig = getattr(ctrl, "height", None)
                        if isinstance(h_orig, (int, float)):
                            ctrl.height = interfaz.alto_adaptable(int(h_orig))
            return orig_show(dialogo)

        page.show_dialog = show_dialog_adaptable
        page._dialogos_adaptables_configurados = True


def configurar_ventana_shell(interfaz: Any, icon_path: Path) -> None:
    """Configura ventana, tema base y eventos globales del shell."""
    page = interfaz.page
    page.title = "Control de Inventario Depósito Pasteur"
    if hasattr(page, "window"):
        page.window.icon = str(icon_path)
        page.window.maximized = True
        page.window.min_width = 360
        page.window.min_height = 480
    page.padding = 0
    page.bgcolor = interfaz.fondo
    page.theme_mode = ft.ThemeMode.DARK
    page.theme = ft.Theme(color_scheme_seed=ROJO)
    if hasattr(page, "on_resize"):
        page.on_resize = interfaz._al_redimensionar
    page.on_keyboard_event = interfaz._manejar_teclas_globales
    configurar_dialogos_adaptables_shell(interfaz)


def establecer_posicion_sidebar_ui(interfaz: Any, nueva_posicion: str) -> None:
    """Cambia la ubicación del menú y reconstruye la vista con feedback visual."""
    if nueva_posicion not in ("izquierda", "derecha", "arriba", "abajo", "oculto"):
        return
    interfaz.posicion_sidebar = nueva_posicion
    interfaz.construir()
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
        interfaz.page.show_dialog(snack)
        interfaz.page.update()
    except Exception:
        pass


def construir_dashboard_shell(interfaz: Any) -> None:
    """Reconstruye por completo el dashboard principal según rol, viewport y tema."""
    if interfaz.usuario_actual is None:
        interfaz.mostrar_inicio_sesion()
        return
    interfaz.theme_ctrl.aplicar_preferencias_usuario(interfaz.usuario_actual)

    page = interfaz.page
    page.bgcolor = interfaz.fondo
    page.theme_mode = ft.ThemeMode.DARK if interfaz.modo_oscuro else ft.ThemeMode.LIGHT
    interfaz.controles_tarea.clear()
    if hasattr(interfaz, "botones_cierre_jornada") and interfaz.botones_cierre_jornada is not None:
        interfaz.botones_cierre_jornada.clear()
    interfaz.btn_cierre_jornada = None
    interfaz.chat_visible = False

    page.floating_action_button = None
    if hasattr(page, "overlay") and page.overlay is not None:
        page.overlay.clear()
    page.controls.clear()

    sidebar_items = interfaz._sidebar_controls()
    es_movil = interfaz.es_pantalla_movil
    interfaz._modo_movil_previo = es_movil

    if es_movil and hasattr(page, "drawer"):
        page.drawer = ft.NavigationDrawer(
            bgcolor=interfaz.superficie,
            controls=[
                ft.Container(
                    padding=16,
                    content=ft.Column(sidebar_items, spacing=8, tight=True),
                )
            ],
        )
    elif hasattr(page, "drawer"):
        page.drawer = None

    page.navigation_bar = construir_navigation_bar_movil(interfaz) if es_movil else None

    dashboard = ft.Column(
        [
            interfaz.encabezado(),
            interfaz.banner_alerta_quiebre,
            interfaz.panel_metricas(),
            interfaz.panel_acceso_rapido(),
            interfaz.panel_informes_actividad(),
            interfaz.barra_estado(),
        ],
        expand=True,
        spacing=16,
        scroll=ft.ScrollMode.AUTO if es_movil else None,
    )

    if es_movil:
        page.add(
            ft.Container(
                expand=True,
                padding=ft.Padding(left=10, right=10, top=10, bottom=10),
                content=dashboard,
            )
        )
    else:
        sidebar = ft.Container(
            width=258,
            bgcolor=interfaz.superficie,
            padding=20,
            content=ft.Column(sidebar_items, spacing=8, scroll=ft.ScrollMode.AUTO),
        )
        page.add(
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
        aplicar_posicion_sidebar_ui(interfaz, dashboard, sidebar)

    ventana_chat = interfaz.crear_ventana_chat_flotante()
    if not hasattr(page, "overlay") or page.overlay is None:
        page.overlay = []
    else:
        page.overlay.clear()
    interfaz._asegurar_file_picker(forzar_recrear=True)
    page.overlay.append(ventana_chat)

    interfaz.boton_chat_flotante = ft.FloatingActionButton(
        content=ft.Row(
            [
                ft.Icon(ft.Icons.SMART_TOY, color=ft.Colors.WHITE, size=18 if es_movil else 20),
                ft.Text(
                    "Chat" if es_movil else "Asistente",
                    color=ft.Colors.WHITE,
                    weight=ft.FontWeight.BOLD,
                    size=12 if es_movil else 13,
                ),
                interfaz.badge_chat_container,
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=4 if es_movil else 5,
        ),
        bgcolor=ROJO,
        tooltip="Asistente Virtual y Chat de Equipo",
        on_click=interfaz.alternar_chat_flotante,
        shape=ft.RoundedRectangleBorder(radius=16),
        width=110 if es_movil else 140,
    )
    page.floating_action_button = interfaz.boton_chat_flotante
    if not interfaz.conversacion.controls:
        rol_actual = interfaz.usuario_actual.role if interfaz.usuario_actual else "operador"
        nom_actual = interfaz.usuario_actual.username if interfaz.usuario_actual else ""
        interfaz.escribir_chat("Agente", obtener_mensaje_bienvenida(rol_actual, nom_actual))
    interfaz.actualizar_estado()
    interfaz.refrescar_usuarios_chat_equipo()
    interfaz._iniciar_heartbeat_red()
    interfaz.cargar_mensajes_equipo()
    interfaz.actualizar_badge_chat()


def actualizar_icono_notificaciones_ui(interfaz: Any, stock_manager_cls: Any) -> None:
    """Actualiza la campana de notificaciones para administradores."""
    if interfaz.usuario_actual is None or interfaz.usuario_actual.role != "administrador":
        interfaz.contenedor_notificaciones.content = None
        return
    try:
        sm = stock_manager_cls(interfaz.menu.ruta_excel_base)
        raw_no_leidas = sm.contar_notificaciones_no_leidas()
        no_leidas = raw_no_leidas if isinstance(raw_no_leidas, int) else 0
    except Exception:
        no_leidas = 0

    if no_leidas > 0:
        interfaz.contenedor_notificaciones.content = ft.IconButton(
            icon=ft.Icons.NOTIFICATIONS_ACTIVE,
            icon_color=ft.Colors.AMBER_400,
            tooltip=f"{no_leidas} notificación(es) de operarios sin leer",
            on_click=interfaz.mostrar_notificaciones_admin,
            badge=ft.Badge(label=str(no_leidas)),
        )
    else:
        interfaz.contenedor_notificaciones.content = ft.IconButton(
            icon=ft.Icons.NOTIFICATIONS_NONE,
            icon_color=interfaz.secundario,
            tooltip="Notificaciones de operarios",
            on_click=interfaz.mostrar_notificaciones_admin,
        )


def construir_barra_estado_ui(interfaz: Any) -> ft.Control:
    """Barra de estado inferior con diseño sutil e indicador de actividad del sistema."""
    return ft.Container(
        content=ft.Row(
            [
                ft.Row(
                    [
                        interfaz.icono_estado_tarea,
                        interfaz.estado_tarea,
                    ],
                    spacing=7,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                interfaz.progreso_barra,
            ],
            spacing=12,
            alignment=ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=ft.Padding(left=12, right=14, top=6, bottom=6),
        border_radius=8,
        bgcolor=ft.Colors.with_opacity(0.04, interfaz.texto),
        border=ft.Border.all(1, ft.Colors.with_opacity(0.08, interfaz.texto)),
    )


def fijar_estado_tarea_ui(interfaz: Any, texto: str, estado: str = "listo") -> None:
    """Actualiza el texto y el ícono de la barra de estado inferior."""
    interfaz.estado_tarea.value = texto
    if hasattr(interfaz, "icono_estado_tarea") and interfaz.icono_estado_tarea:
        texto_lower = (texto or "").lower()
        if estado == "listo" or "listo" in texto_lower or "finalizad" in texto_lower:
            interfaz.icono_estado_tarea.name = ft.Icons.CHECK_CIRCLE_OUTLINE_ROUNDED
            interfaz.icono_estado_tarea.color = ft.Colors.GREEN_400
        elif estado == "error" or "error" in texto_lower or "fall" in texto_lower:
            interfaz.icono_estado_tarea.name = ft.Icons.ERROR_OUTLINE_ROUNDED
            interfaz.icono_estado_tarea.color = ft.Colors.RED_400
        elif estado == "en_curso" or "curso" in texto_lower or "progreso" in texto_lower:
            interfaz.icono_estado_tarea.name = ft.Icons.SYNC_ROUNDED
            interfaz.icono_estado_tarea.color = ft.Colors.AMBER_400
        elif estado == "archivo":
            interfaz.icono_estado_tarea.name = ft.Icons.DESCRIPTION_OUTLINED
            interfaz.icono_estado_tarea.color = ft.Colors.LIGHT_BLUE_400
        else:
            interfaz.icono_estado_tarea.name = ft.Icons.INFO_OUTLINE_ROUNDED
            interfaz.icono_estado_tarea.color = interfaz.secundario
    if hasattr(interfaz, "page") and interfaz.page:
        try:
            interfaz.page.update()
        except Exception:
            pass


def construir_tarjeta_ui(interfaz: Any, contenido: ft.Control, expand: bool = False) -> ft.Container:
    """Construye una tarjeta estándar con los colores y bordes del tema activo."""
    return ft.Container(
        expand=expand,
        bgcolor=interfaz.superficie,
        border=ft.Border.all(1, interfaz.borde),
        border_radius=14,
        padding=16,
        content=contenido,
    )


def copiar_al_portapapeles_ui(interfaz: Any, texto: str) -> None:
    """Copia texto al portapapeles del cliente de forma segura."""
    try:
        if interfaz.page:
            cb = ft.Clipboard()
            interfaz.page.overlay.append(cb)
            interfaz.page.update()
            cb.set(str(texto))
    except Exception:
        pass


__all__ = [
    "inicializar_controles_shell",
    "configurar_dialogos_adaptables_shell",
    "configurar_ventana_shell",
    "establecer_posicion_sidebar_ui",
    "construir_dashboard_shell",
    "actualizar_icono_notificaciones_ui",
    "construir_barra_estado_ui",
    "fijar_estado_tarea_ui",
    "construir_tarjeta_ui",
    "copiar_al_portapapeles_ui",
    "construir_sidebar_controls",
]
