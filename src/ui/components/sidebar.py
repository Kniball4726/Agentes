"""Componente del menú lateral (Sidebar) y barra horizontal con menús desplegables tipo acordeón organizados por roles y naturaleza funcional."""

from pathlib import Path
from typing import Any, Callable
import json
import flet as ft
from ..theme import ROJO
from ...paths import application_root
from ..dialogs.dlg_preferencias import mostrar_dialogo_preferencias
from ..dialogs.dlg_movimientos_rapidos import (
    mostrar_dialogo_ingreso_rapido,
    mostrar_dialogo_salida_rapida,
)


from ..user_preferences import (
    obtener_preferencias_usuario,
    guardar_preferencia_usuario,
)


def _crear_boton_cierre_jornada(interfaz: Any, ancho: int | None = 218) -> ft.Button:
    """Genera y registra el botón de Cierre de Jornada con soporte dinámico de contadores."""
    btn = interfaz.boton("Cierre de Jornada", ft.Icons.TASK_ALT, interfaz.mostrar_cierre_jornada)
    if ancho is not None:
        btn.width = ancho
    btn.icon = None
    btn.bgcolor = ft.Colors.TRANSPARENT
    btn.color = interfaz.texto
    btn.elevation = 0
    btn.height = 36
    btn.style = ft.ButtonStyle(
        shape=ft.RoundedRectangleBorder(radius=6),
        overlay_color=ft.Colors.with_opacity(0.08, interfaz.texto),
        alignment=ft.Alignment.CENTER_LEFT,
        padding=ft.Padding.only(left=16, right=8),
    )
    interfaz.btn_cierre_jornada = btn
    if not hasattr(interfaz, "botones_cierre_jornada") or interfaz.botones_cierre_jornada is None:
        interfaz.botones_cierre_jornada = []
    if btn not in interfaz.botones_cierre_jornada:
        interfaz.botones_cierre_jornada.append(btn)
    total_p = 0
    if hasattr(interfaz, "order_store") and interfaz.order_store:
        try:
            conteo_init = interfaz.order_store.contar_pedidos_pendientes_cierre_por_tipo()
            total_p = int(conteo_init.get("total", 0))
        except Exception:
            total_p = 0
    btn.disabled = (total_p == 0)
    btn.content = f"Cierre de Jornada ({total_p})" if total_p > 0 else "Cierre de Jornada"
    btn.tooltip = (
        "No hay pedidos pendientes de cierre"
        if total_p == 0
        else f"{total_p} pedido(s) pendiente(s) de cierre"
    )
    return btn


class SeccionMenu:
    """Definición canónica de una sección o módulo del sistema."""

    def __init__(
        self,
        titulo: str,
        icono: ft.IconData,
        items: list[tuple[str, ft.IconData, Callable[..., Any]]],
        es_control_cierre: bool = False,
    ):
        self.titulo = titulo
        self.icono = icono
        self.items = items
        self.es_control_cierre = es_control_cierre


def obtener_secciones_rol(interfaz: Any) -> list[SeccionMenu]:
    """Retorna la lista de secciones agrupadas por naturaleza funcional según el rol actual."""
    rol = interfaz.usuario_actual.role if interfaz.usuario_actual else "consulta"

    # Herramientas transversales disponibles para todos los roles
    herramientas_comunes = [
        ("Preferencias de Interfaz", ft.Icons.TUNE, lambda _: mostrar_dialogo_preferencias(interfaz)),
        ("Chat Interno", ft.Icons.CHAT_BUBBLE, interfaz.alternar_chat_flotante),
        ("Manual de Uso", ft.Icons.MENU_BOOK, interfaz.mostrar_manual_usuario),
        ("Búsqueda Rápida (F2)", ft.Icons.SEARCH, interfaz.mostrar_command_palette),
    ]

    if rol == "operador":
        return [
            SeccionMenu(
                titulo="ENTRADA DE MERCADERÍA",
                icono=ft.Icons.INVENTORY_2,
                items=[
                    ("Ingreso de Fábrica", ft.Icons.INVENTORY_2, interfaz.mostrar_ingreso_fabrica),
                ],
            ),
            SeccionMenu(
                titulo="PREPARACIÓN Y DESPACHO",
                icono=ft.Icons.LOCAL_SHIPPING,
                items=[
                    ("Cargar / Armar Pedido", ft.Icons.POST_ADD, interfaz.mostrar_crear_pedido),
                    ("Descontar Mercado Libre", ft.Icons.STOREFRONT, interfaz.mostrar_descuento_mercado_libre),
                    ("Descontar Mercado Full", ft.Icons.LOCAL_SHIPPING, interfaz.mostrar_descuento_mercado_full),
                    ("Imprimir Descuento", ft.Icons.PRINT, interfaz.mostrar_imprimir_descuentos),
                ],
            ),
            SeccionMenu(
                titulo="CLIENTES",
                icono=ft.Icons.PEOPLE_ALT,
                items=[
                    ("Gestión de Clientes", ft.Icons.PEOPLE_ALT, interfaz.mostrar_gestion_clientes),
                ],
            ),
            SeccionMenu(
                titulo="CONTROL Y CIERRE",
                icono=ft.Icons.TASK_ALT,
                items=[
                    ("Inventario en Vivo (Escáner)", ft.Icons.DOCUMENT_SCANNER, interfaz.mostrar_dialogo_inventario_vivo),
                    ("Cierre de Jornada", ft.Icons.TASK_ALT, interfaz.mostrar_cierre_jornada),
                ],
                es_control_cierre=True,
            ),
            SeccionMenu(
                titulo="INFORMES",
                icono=ft.Icons.ASSESSMENT,
                items=[
                    ("Historial de Pedidos", ft.Icons.RECEIPT_LONG, interfaz.mostrar_historial_pedidos),
                    ("Abrir informe", ft.Icons.OPEN_IN_NEW, interfaz.abrir_informe),
                    ("Compartir por correo", ft.Icons.EMAIL, interfaz.compartir_correo),
                    ("WhatsApp Web", ft.Icons.CHAT, interfaz.compartir_whatsapp),
                ],
            ),
            SeccionMenu(
                titulo="HERRAMIENTAS",
                icono=ft.Icons.BUILD,
                items=herramientas_comunes,
            ),
        ]

    if rol == "administrador":
        return [
            SeccionMenu(
                titulo="CATÁLOGO",
                icono=ft.Icons.CATEGORY,
                items=[
                    ("Gestionar productos", ft.Icons.ADD_BOX, interfaz.mostrar_gestion_productos),
                    ("Sincronizar con Excel", ft.Icons.SYNC, interfaz.sincronizar_catalogo_excel),
                ],
            ),
            SeccionMenu(
                titulo="CLIENTES",
                icono=ft.Icons.PEOPLE_ALT,
                items=[
                    ("Gestión de Clientes", ft.Icons.PEOPLE_ALT, interfaz.mostrar_gestion_clientes),
                ],
            ),
            SeccionMenu(
                titulo="INVENTARIO Y REPOSICIÓN",
                icono=ft.Icons.INVENTORY_2,
                items=[
                    ("Ajustar stock / Fábrica", ft.Icons.INVENTORY_2, interfaz.mostrar_ingreso_fabrica),
                    ("Comparativa stock físico", ft.Icons.COMPARE_ARROWS, interfaz.mostrar_comparativa_stock_fisico_admin),
                    ("Generar pedido fábrica (Excel)", ft.Icons.FACT_CHECK, interfaz.generar_pedido_fabrica),
                ],
            ),
            SeccionMenu(
                titulo="CANALES DE VENTA",
                icono=ft.Icons.STOREFRONT,
                items=[
                    ("Descontar Mercado Libre", ft.Icons.STOREFRONT, interfaz.mostrar_descuento_mercado_libre),
                    ("Sincronizar Mercado Libre (API)", ft.Icons.CLOUD_SYNC, interfaz.mostrar_sincronizacion_mercadolibre),
                    ("Descontar Mercado Full", ft.Icons.LOCAL_SHIPPING, interfaz.mostrar_descuento_mercado_full),
                ],
            ),
            SeccionMenu(
                titulo="SUPERVISIÓN",
                icono=ft.Icons.FACT_CHECK,
                items=[
                    ("Cierres de Operarios", ft.Icons.FACT_CHECK, interfaz.mostrar_historial_cierres_admin),
                    ("Historial de Pedidos", ft.Icons.RECEIPT_LONG, interfaz.mostrar_historial_pedidos),
                    ("Radar de anomalías", ft.Icons.AUTO_GRAPH, interfaz.mostrar_dialogo_anomalias),
                ],
            ),
            SeccionMenu(
                titulo="ANALÍTICA",
                icono=ft.Icons.INSIGHTS,
                items=[
                    ("Métricas y Rendimiento", ft.Icons.INSIGHTS, interfaz.mostrar_dashboard_metricas),
                    ("Estadísticas de salida", ft.Icons.BAR_CHART, interfaz.mostrar_estadisticas),
                    ("Heatmap y Picking", ft.Icons.GRID_VIEW_ROUNDED, interfaz.mostrar_dialogo_heatmap),
                ],
            ),
            SeccionMenu(
                titulo="INFORMES",
                icono=ft.Icons.ASSESSMENT,
                items=[
                    ("Abrir informe", ft.Icons.OPEN_IN_NEW, interfaz.abrir_informe),
                    ("Compartir por correo", ft.Icons.EMAIL, interfaz.compartir_correo),
                    ("WhatsApp Web", ft.Icons.CHAT, interfaz.compartir_whatsapp),
                ],
            ),
            SeccionMenu(
                titulo="ADMINISTRACIÓN Y RESGUARDO",
                icono=ft.Icons.ADMIN_PANEL_SETTINGS,
                items=[
                    ("Gestionar usuarios", ft.Icons.GROUP, interfaz.mostrar_gestion_usuarios),
                    ("Copia de Seguridad", ft.Icons.BACKUP, interfaz.mostrar_dialogo_backup),
                ],
            ),
            SeccionMenu(
                titulo="HERRAMIENTAS",
                icono=ft.Icons.BUILD,
                items=[
                    *herramientas_comunes,
                    ("Imprimir Descuento", ft.Icons.PRINT, interfaz.mostrar_imprimir_descuentos),
                ],
            ),
        ]

    if rol == "master":
        return [
            SeccionMenu(
                titulo="SEGURIDAD Y ACCESOS",
                icono=ft.Icons.SECURITY,
                items=[
                    ("Gestionar usuarios", ft.Icons.MANAGE_ACCOUNTS, interfaz.mostrar_gestion_usuarios),
                    ("Registro de Auditoría", ft.Icons.SECURITY, interfaz.mostrar_registro_auditoria),
                ],
            ),
            SeccionMenu(
                titulo="DATOS Y RESGUARDO",
                icono=ft.Icons.BACKUP,
                items=[
                    ("Copia de Seguridad", ft.Icons.BACKUP, interfaz.mostrar_dialogo_backup),
                    ("Restaurar documentos", ft.Icons.RESTORE, interfaz.confirmar_restaurar),
                    ("Archivado Histórico", ft.Icons.AUTO_DELETE, interfaz.mostrar_dialogo_archivo_historico),
                ],
            ),
            SeccionMenu(
                titulo="INTEGRACIONES",
                icono=ft.Icons.SETTINGS_APPLICATIONS,
                items=[
                    ("Configuración SMTP", ft.Icons.SETTINGS_APPLICATIONS, interfaz.mostrar_configuracion_smtp),
                    ("Alertas Telegram", ft.Icons.SEND, interfaz.mostrar_configuracion_telegram),
                    ("Mercado Libre API (Credenciales)", ft.Icons.CLOUD_SYNC, interfaz.mostrar_sincronizacion_mercadolibre),
                ],
            ),
            SeccionMenu(
                titulo="HERRAMIENTAS",
                icono=ft.Icons.BUILD,
                items=herramientas_comunes,
            ),
        ]

    # Rol Consulta
    return [
        SeccionMenu(
            titulo="INFORMES",
            icono=ft.Icons.ASSESSMENT,
            items=[
                ("Abrir informe", ft.Icons.OPEN_IN_NEW, interfaz.abrir_informe),
                ("Compartir por correo", ft.Icons.EMAIL, interfaz.compartir_correo),
                ("WhatsApp Web", ft.Icons.CHAT, interfaz.compartir_whatsapp),
            ],
        ),
        SeccionMenu(
            titulo="HERRAMIENTAS",
            icono=ft.Icons.BUILD,
            items=herramientas_comunes,
        ),
    ]


def _obtener_seccion_predeterminada(rol: str) -> str:
    """Devuelve la sección que debe abrirse por defecto según el rol del usuario."""
    mapa = {
        "operador": "PREPARACIÓN Y DESPACHO",
        "administrador": "CATÁLOGO",
        "master": "SEGURIDAD Y ACCESOS",
        "consulta": "INFORMES",
    }
    return mapa.get(rol, "INFORMES")


def verificar_pendientes_categoria(interfaz: Any, titulo_categoria: str) -> tuple[bool, str]:
    """Retorna si una categoría tiene tareas o ítems pendientes y su texto explicativo."""
    try:
        if titulo_categoria in ("CONTROL Y CIERRE", "SUPERVISIÓN"):
            if hasattr(interfaz, "order_store") and interfaz.order_store:
                conteo = interfaz.order_store.contar_pedidos_pendientes_cierre_por_tipo()
                total = int(conteo.get("total", 0))
                if total > 0:
                    return (True, f"{total} pedido(s) pendiente(s) de cierre")

        if titulo_categoria == "ENTRADA DE MERCADERÍA":
            if hasattr(interfaz, "menu") and interfaz.menu and hasattr(interfaz.menu, "_obtener_pendientes_fabrica"):
                fab = interfaz.menu._obtener_pendientes_fabrica()
                if len(fab) > 0:
                    return (True, f"{len(fab)} remito(s) de fábrica pendiente(s)")

        if titulo_categoria in ("PREPARACIÓN Y DESPACHO", "CANALES DE VENTA"):
            if hasattr(interfaz, "menu") and interfaz.menu:
                pendientes = interfaz.menu._obtener_pendientes()
                total_archivos = sum(len(p) for p in pendientes if isinstance(p, list))
                if total_archivos > 0:
                    return (True, f"{total_archivos} archivo(s) de pedidos pendiente(s)")

        if titulo_categoria == "INVENTARIO Y REPOSICIÓN":
            if getattr(interfaz, "alerta_quiebre_activa", False):
                return (True, "Productos en quiebre de stock o bajo el mínimo")
    except Exception:
        pass
    return (False, "")


def actualizar_puntos_pendientes_sidebar(interfaz: Any) -> None:
    """Refresca la visibilidad de los puntos rojos indicadores de pendientes en tiempo real."""
    puntos_v = getattr(interfaz, "puntos_pendientes_sidebar", None)
    if isinstance(puntos_v, dict):
        for cat, punto in list(puntos_v.items()):
            tiene, tooltip = verificar_pendientes_categoria(interfaz, cat)
            punto.visible = tiene
            punto.tooltip = tooltip if tiene else None

    puntos_h = getattr(interfaz, "puntos_pendientes_horizontal", None)
    if isinstance(puntos_h, dict):
        for cat, punto_h in list(puntos_h.items()):
            tiene, tooltip = verificar_pendientes_categoria(interfaz, cat)
            punto_h.visible = tiene
            punto_h.tooltip = tooltip if tiene else None


def construir_sidebar_controls(interfaz: Any) -> list[ft.Control]:
    """Genera la lista de controles para el panel lateral organizados en menús desplegables tipo acordeón."""
    assert interfaz.usuario_actual is not None
    logo_path = Path(__file__).resolve().parent.parent.parent / "img" / "ultratech.png"
    logo_bytes = logo_path.read_bytes() if logo_path.exists() else b""

    controls: list[ft.Control] = [
        ft.Row(
            [
                ft.Container(
                    width=42,
                    height=42,
                    border_radius=12,
                    bgcolor=ft.Colors.GREY_900 if interfaz.modo_oscuro else ft.Colors.RED_50,
                    border=ft.Border.all(
                        1,
                        ft.Colors.with_opacity(0.18, ft.Colors.WHITE) if interfaz.modo_oscuro else ft.Colors.RED_100,
                    ),
                    alignment=ft.Alignment.CENTER,
                    content=ft.Image(
                        src=logo_bytes,
                        width=42,
                        height=42,
                        fit=ft.BoxFit.CONTAIN,
                    ),
                ),
                ft.Column(
                    [
                        ft.Text("StockAgent", size=18, weight=ft.FontWeight.BOLD, color=interfaz.texto),
                        ft.Text("Panel de control", size=11, color=interfaz.secundario),
                    ],
                    spacing=2,
                ),
            ],
            spacing=10,
        ),
        ft.Text(
            f"{interfaz.usuario_actual.nombre_identificador} · {interfaz.usuario_actual.role}",
            size=11,
            color=interfaz.secundario,
        ),
        ft.Divider(height=16, color=interfaz.borde),
        ft.Container(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.SEARCH, size=15, color=ROJO),
                    ft.Text("Buscar módulo...", size=11, color=interfaz.secundario, expand=True),
                    ft.Container(
                        content=ft.Text("F2", size=9, weight=ft.FontWeight.BOLD, color=interfaz.secundario),
                        padding=ft.Padding.symmetric(horizontal=4, vertical=1),
                        border=ft.Border.all(1, ft.Colors.with_opacity(0.25, interfaz.borde)),
                        border_radius=4,
                    ),
                ],
                spacing=6,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding.symmetric(horizontal=10, vertical=7),
            border_radius=8,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.3, interfaz.borde)),
            bgcolor=ft.Colors.with_opacity(0.04, interfaz.texto),
            tooltip="Búsqueda Rápida Universal (Ctrl + K o F2)",
            on_click=lambda _: interfaz.mostrar_command_palette(),
            ink=True,
        ),
        ft.Container(height=4),
    ]

    secciones = obtener_secciones_rol(interfaz)
    username = interfaz.usuario_actual.username
    rol = interfaz.usuario_actual.role

    # Botonera de Acceso Rápido para Operador / Admin / Master: Entrada, Salida, Cargar Pedido y Mercado Libre
    if rol in ("operador", "administrador", "master"):
        btn_entrada = ft.Container(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.ADD_CIRCLE_OUTLINE, size=14, color=ft.Colors.GREEN_600),
                    ft.Text("Entrada", size=11, weight=ft.FontWeight.BOLD, color=interfaz.texto),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=4,
            ),
            expand=True,
            height=32,
            border_radius=7,
            bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.GREEN_600),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.35, ft.Colors.GREEN_600)),
            tooltip="⚡ Entrada Rápida express por escaneo (Devolución, Mov. Interno...)",
            on_click=lambda _: mostrar_dialogo_ingreso_rapido(interfaz),
            ink=True,
        )

        btn_salida = ft.Container(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.REMOVE_CIRCLE_OUTLINE, size=14, color=ft.Colors.AMBER_700),
                    ft.Text("Salida", size=11, weight=ft.FontWeight.BOLD, color=interfaz.texto),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=4,
            ),
            expand=True,
            height=32,
            border_radius=7,
            bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.AMBER_700),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.35, ft.Colors.AMBER_700)),
            tooltip="⚡ Salida Rápida express por escaneo (Rotura, Merma, Muestras...)",
            on_click=lambda _: mostrar_dialogo_salida_rapida(interfaz),
            ink=True,
        )

        btn_pedido = ft.Container(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.POST_ADD, size=14, color=ft.Colors.BLUE_500),
                    ft.Text("Cargar Pedido", size=10, weight=ft.FontWeight.BOLD, color=interfaz.texto),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=4,
            ),
            expand=True,
            height=32,
            border_radius=7,
            bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.BLUE_500),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.35, ft.Colors.BLUE_500)),
            tooltip="⚡ Cargar y escanear remito / armar nuevo pedido",
            on_click=lambda _: interfaz.mostrar_crear_pedido(),
            ink=True,
        )

        btn_meli = ft.Container(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.STOREFRONT, size=14, color=ft.Colors.AMBER_500),
                    ft.Text("Mercado Libre", size=10, weight=ft.FontWeight.BOLD, color=interfaz.texto),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=4,
            ),
            expand=True,
            height=32,
            border_radius=7,
            bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.AMBER_500),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.35, ft.Colors.AMBER_500)),
            tooltip="⚡ Descontar y escanear etiquetas de Mercado Libre",
            on_click=lambda _: interfaz.mostrar_descuento_mercado_libre(),
            ink=True,
        )

        controls.append(
            ft.Column(
                [
                    ft.Row([btn_entrada, btn_salida], spacing=6),
                    ft.Row([btn_pedido, btn_meli], spacing=6),
                ],
                spacing=6,
                tight=True,
            )
        )
        controls.append(ft.Container(height=4))

    prefs = obtener_preferencias_usuario(username)
    seccion_abierta_pref = prefs.get("seccion_abierta")
    seccion_por_defecto = _obtener_seccion_predeterminada(rol)

    # Si el usuario tiene una sección preferida guardada, abrir esa; si no, abrir la predeterminada del rol
    seccion_a_abrir = seccion_abierta_pref if seccion_abierta_pref is not None else seccion_por_defecto

    # Conteo dinámico de pedidos pendientes para el badge de CONTROL Y CIERRE
    conteo_cierre = 0
    if hasattr(interfaz, "order_store") and interfaz.order_store:
        try:
            conteo_dict = interfaz.order_store.contar_pedidos_pendientes_cierre_por_tipo()
            conteo_cierre = int(conteo_dict.get("total", 0))
        except Exception:
            conteo_cierre = 0

    lista_tiles: list[ft.ExpansionTile] = []

    def _crear_callback_acordeon(tile_obj: ft.ExpansionTile, nombre_sec: str) -> Callable[[Any], None]:
        def al_cambiar(e: Any) -> None:
            esta_abierto = str(e.data).lower() in ("true", "1")
            if esta_abierto:
                for t in lista_tiles:
                    if t is not tile_obj:
                        t.expanded = False
                guardar_preferencia_usuario(username, "seccion_abierta", nombre_sec)
            else:
                guardar_preferencia_usuario(username, "seccion_abierta", "")
            if hasattr(interfaz, "page") and interfaz.page:
                try:
                    interfaz.page.update()
                except Exception:
                    pass
        return al_cambiar

    for sec in secciones:
        esta_expandido = (sec.titulo == seccion_a_abrir)
        sec_buttons: list[ft.Control] = []

        for texto, icono, accion in sec.items:
            if sec.es_control_cierre and texto == "Cierre de Jornada":
                sec_buttons.append(_crear_boton_cierre_jornada(interfaz, ancho=218))
            else:
                btn = interfaz.boton(texto, icono, accion)
                btn.icon = None
                btn.bgcolor = ft.Colors.TRANSPARENT
                btn.color = interfaz.texto
                btn.elevation = 0
                btn.height = 36
                btn.style = ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=6),
                    overlay_color=ft.Colors.with_opacity(0.08, interfaz.texto),
                    alignment=ft.Alignment.CENTER_LEFT,
                    padding=ft.Padding.only(left=16, right=8),
                )
                sec_buttons.append(btn)

        # Encabezado del título con punto rojo indicador si hay pendientes
        tiene_pendientes, tooltip_pendientes = verificar_pendientes_categoria(interfaz, sec.titulo)
        punto_rojo = ft.Container(
            width=7,
            height=7,
            border_radius=4,
            bgcolor=ROJO,
            tooltip=tooltip_pendientes if tiene_pendientes else None,
            visible=tiene_pendientes,
        )
        if not isinstance(getattr(interfaz, "puntos_pendientes_sidebar", None), dict):
            interfaz.puntos_pendientes_sidebar = {}
        if isinstance(interfaz.puntos_pendientes_sidebar, dict):
            interfaz.puntos_pendientes_sidebar[sec.titulo] = punto_rojo

        if sec.es_control_cierre:
            interfaz.badge_seccion_cierre = punto_rojo

        titulo_tile = ft.Row(
            [
                ft.Text(sec.titulo, size=11, weight=ft.FontWeight.BOLD, color=interfaz.texto),
                punto_rojo,
            ],
            spacing=6,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        titulo_tile.value = sec.titulo

        tile = ft.ExpansionTile(
            title=titulo_tile,
            leading=ft.Icon(sec.icono, size=18, color=ROJO),
            controls=sec_buttons,
            controls_padding=ft.Padding.only(left=2, right=2, top=4, bottom=6),
            tile_padding=ft.Padding.symmetric(horizontal=4, vertical=0),
            maintain_state=True,
            expanded=esta_expandido,
            dense=True,
            shape=ft.RoundedRectangleBorder(radius=8, side=ft.BorderSide(0, ft.Colors.TRANSPARENT)),
            collapsed_shape=ft.RoundedRectangleBorder(radius=8, side=ft.BorderSide(0, ft.Colors.TRANSPARENT)),
        )
        tile.on_change = _crear_callback_acordeon(tile, sec.titulo)
        lista_tiles.append(tile)
        controls.append(tile)

    controls.extend(
        [
            ft.Container(height=8),
            ft.Row(
                [
                    ft.Icon(ft.Icons.CIRCLE, color=ft.Colors.GREEN_600, size=10),
                    ft.Text("Agente local activo", size=12, color=interfaz.secundario),
                ],
                spacing=8,
            ),
        ]
    )
    return controls


def construir_sidebar_horizontal_controls(interfaz: Any) -> list[ft.Control]:
    """Genera la lista de controles para el panel de navegación horizontal con menús desplegables (MenuBar)."""
    assert interfaz.usuario_actual is not None
    logo_path = Path(__file__).resolve().parent.parent.parent / "img" / "ultratech.png"
    logo_bytes = logo_path.read_bytes() if logo_path.exists() else b""

    secciones = obtener_secciones_rol(interfaz)
    rol = interfaz.usuario_actual.role

    # Conteo dinámico de pedidos pendientes
    conteo_cierre = 0
    if hasattr(interfaz, "order_store") and interfaz.order_store:
        try:
            conteo_dict = interfaz.order_store.contar_pedidos_pendientes_cierre_por_tipo()
            conteo_cierre = int(conteo_dict.get("total", 0))
        except Exception:
            conteo_cierre = 0

    menu_bar_controls: list[ft.Control] = []

    for sec in secciones:
        menu_items: list[ft.Control] = []
        for texto, icono, accion in sec.items:
            if sec.es_control_cierre and texto == "Cierre de Jornada":
                btn_item = ft.MenuItemButton(
                    content=ft.Text(f"Cierre de Jornada ({conteo_cierre})" if conteo_cierre > 0 else "Cierre de Jornada"),
                    on_click=accion,
                )
                menu_items.append(btn_item)
            else:
                menu_items.append(
                    ft.MenuItemButton(
                        content=ft.Text(texto),
                        on_click=accion,
                    )
                )

        # Encabezado con punto rojo indicador si hay pendientes
        tiene_pendientes_h, tooltip_h = verificar_pendientes_categoria(interfaz, sec.titulo)
        punto_rojo_h = ft.Container(
            width=7,
            height=7,
            border_radius=4,
            bgcolor=ROJO,
            tooltip=tooltip_h if tiene_pendientes_h else None,
            visible=tiene_pendientes_h,
        )
        if not isinstance(getattr(interfaz, "puntos_pendientes_horizontal", None), dict):
            interfaz.puntos_pendientes_horizontal = {}
        if isinstance(interfaz.puntos_pendientes_horizontal, dict):
            interfaz.puntos_pendientes_horizontal[sec.titulo] = punto_rojo_h

        if sec.es_control_cierre:
            interfaz.badge_h_seccion_cierre = punto_rojo_h

        header_content = ft.Row(
            [
                ft.Text(sec.titulo, size=12, weight=ft.FontWeight.W_600),
                punto_rojo_h,
            ],
            spacing=6,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        header_content.value = sec.titulo

        submenu = ft.SubmenuButton(
            content=header_content,
            leading=ft.Icon(sec.icono, size=16, color=ROJO),
            controls=menu_items,
        )
        menu_bar_controls.append(submenu)

    menu_bar = ft.MenuBar(
        style=ft.MenuStyle(
            bgcolor=ft.Colors.TRANSPARENT,
            elevation=0,
            padding=ft.Padding.symmetric(horizontal=4, vertical=2),
        ),
        controls=menu_bar_controls,
    )

    controls: list[ft.Control] = [
        ft.Row(
            [
                ft.Container(
                    width=28,
                    height=28,
                    border_radius=8,
                    bgcolor=ft.Colors.GREY_900 if interfaz.modo_oscuro else ft.Colors.RED_50,
                    border=ft.Border.all(
                        1,
                        ft.Colors.with_opacity(0.18, ft.Colors.WHITE) if interfaz.modo_oscuro else ft.Colors.RED_100,
                    ),
                    alignment=ft.Alignment.CENTER,
                    content=ft.Image(src=logo_bytes, width=28, height=28, fit=ft.BoxFit.CONTAIN),
                ),
                ft.Text("StockAgent", size=14, weight=ft.FontWeight.BOLD, color=interfaz.texto),
                ft.Container(
                    content=ft.Text(f"{rol}".upper(), size=9, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                    bgcolor=ROJO,
                    padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                    border_radius=4,
                ),
            ],
            spacing=6,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        ft.VerticalDivider(width=16, color=interfaz.borde),
        ft.IconButton(
            icon=ft.Icons.SEARCH,
            icon_size=18,
            icon_color=interfaz.secundario,
            tooltip="Búsqueda rápida (Ctrl + K / F2)",
            on_click=lambda _: interfaz.mostrar_command_palette(),
        ),
        ft.VerticalDivider(width=8, color=interfaz.borde),
    ]

    if rol in ("operador", "administrador", "master"):
        btn_ent_h = ft.Container(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.ADD_CIRCLE_OUTLINE, size=14, color=ft.Colors.GREEN_600),
                    ft.Text("Entrada", size=11, weight=ft.FontWeight.BOLD, color=interfaz.texto),
                ],
                spacing=4,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            height=30,
            padding=ft.Padding.symmetric(horizontal=8),
            border_radius=6,
            bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.GREEN_600),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.35, ft.Colors.GREEN_600)),
            tooltip="⚡ Entrada Rápida express (Devolución, Mov. Interno...)",
            on_click=lambda _: mostrar_dialogo_ingreso_rapido(interfaz),
            ink=True,
        )
        btn_sal_h = ft.Container(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.REMOVE_CIRCLE_OUTLINE, size=14, color=ft.Colors.AMBER_700),
                    ft.Text("Salida", size=11, weight=ft.FontWeight.BOLD, color=interfaz.texto),
                ],
                spacing=4,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            height=30,
            padding=ft.Padding.symmetric(horizontal=8),
            border_radius=6,
            bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.AMBER_700),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.35, ft.Colors.AMBER_700)),
            tooltip="⚡ Salida Rápida express (Rotura, Merma, Bajas...)",
            on_click=lambda _: mostrar_dialogo_salida_rapida(interfaz),
            ink=True,
        )
        btn_ped_h = ft.Container(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.POST_ADD, size=14, color=ft.Colors.BLUE_500),
                    ft.Text("Cargar Pedido", size=11, weight=ft.FontWeight.BOLD, color=interfaz.texto),
                ],
                spacing=4,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            height=30,
            padding=ft.Padding.symmetric(horizontal=8),
            border_radius=6,
            bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.BLUE_500),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.35, ft.Colors.BLUE_500)),
            tooltip="⚡ Cargar / Armar Pedido",
            on_click=lambda _: interfaz.mostrar_crear_pedido(),
            ink=True,
        )
        btn_meli_h = ft.Container(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.STOREFRONT, size=14, color=ft.Colors.AMBER_500),
                    ft.Text("Mercado Libre", size=11, weight=ft.FontWeight.BOLD, color=interfaz.texto),
                ],
                spacing=4,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            height=30,
            padding=ft.Padding.symmetric(horizontal=8),
            border_radius=6,
            bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.AMBER_500),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.35, ft.Colors.AMBER_500)),
            tooltip="⚡ Descontar Mercado Libre",
            on_click=lambda _: interfaz.mostrar_descuento_mercado_libre(),
            ink=True,
        )
        controls.extend([
            btn_ent_h,
            btn_sal_h,
            btn_ped_h,
            btn_meli_h,
            ft.VerticalDivider(width=8, color=interfaz.borde),
        ])

    controls.append(menu_bar)

    # Para operador, agregar también botón directo visible en la barra horizontal para Cierre rápido
    if rol == "operador":
        btn_cierre_directo = _crear_boton_cierre_jornada(interfaz, ancho=None)
        btn_cierre_directo.height = 34
        controls.extend([
            ft.VerticalDivider(width=12, color=interfaz.borde),
            btn_cierre_directo,
        ])

    return controls
