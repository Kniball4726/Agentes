"""Definición de secciones de menú, categorías y permisos por rol para el Sidebar."""

from datetime import datetime
from pathlib import Path
from typing import Any, Callable
import flet as ft

from ..theme import ROJO
from ..user_preferences import (
    guardar_preferencia_usuario,
    obtener_preferencias_usuario,
)
from ..dialogs.dlg_preferencias import mostrar_dialogo_preferencias
from ..dialogs.dlg_movimientos_rapidos import (
    mostrar_dialogo_ingreso_rapido,
    mostrar_dialogo_salida_rapida,
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

    if rol == "picker":
        return [
            SeccionMenu(
                titulo="DESPACHO",
                icono=ft.Icons.LOCAL_SHIPPING,
                items=[
                    ("Descontar Mercado Libre", ft.Icons.STOREFRONT, interfaz.mostrar_descuento_mercado_libre),
                    ("Descontar Mercado Full", ft.Icons.LOCAL_SHIPPING, interfaz.mostrar_descuento_mercado_full),
                ],
            ),
            SeccionMenu(
                titulo="MOVIMIENTOS DE STOCK",
                icono=ft.Icons.SWAP_VERT,
                items=[
                    ("Ingreso de Mercadería", ft.Icons.INPUT, interfaz.mostrar_dialogo_ingreso_rapido),
                    ("Ingreso de Fábrica", ft.Icons.INVENTORY_2, interfaz.mostrar_ingreso_fabrica),
                    ("Egreso de Mercadería", ft.Icons.OUTPUT, interfaz.mostrar_dialogo_salida_rapida),
                ],
            ),
            SeccionMenu(
                titulo="HERRAMIENTAS",
                icono=ft.Icons.BUILD,
                items=herramientas_comunes,
            ),
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
                    ("Ver Stock", ft.Icons.VISIBILITY, interfaz.mostrar_ver_stock),
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
                titulo="API REST Y SERVICIOS",
                icono=ft.Icons.API,
                items=[
                    ("Gestión de Claves API", ft.Icons.VPN_KEY, interfaz.mostrar_gestion_api_keys),
                    ("Documentación y Estado", ft.Icons.CODE, interfaz.mostrar_estado_api),
                    ("Sesiones de API Activas", ft.Icons.DEVICES, interfaz.mostrar_sesiones_api),
                ],
            ),
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



