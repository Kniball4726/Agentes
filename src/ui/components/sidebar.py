"""Componente del menú lateral (Sidebar) con navegación basada en roles."""
from pathlib import Path
from typing import Any
import flet as ft
from ..theme import ROJO


def construir_sidebar_controls(interfaz: Any) -> list[ft.Control]:
    """Genera la lista de controles para el panel lateral según el rol del usuario autenticado."""
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
                    bgcolor=ft.Colors.RED_50 if interfaz.modo_oscuro else ft.Colors.RED_50,
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
        ft.Divider(height=22, color=interfaz.borde),
    ]

    if interfaz.usuario_actual.role == "operador":
        controls.extend(
            [
                ft.Text("PEDIDOS EN TIEMPO REAL", size=11, weight=ft.FontWeight.BOLD, color=interfaz.secundario),
                interfaz.boton("Cargar / Armar Pedido", ft.Icons.POST_ADD, interfaz.mostrar_crear_pedido),
                interfaz.boton("Gestión de Clientes", ft.Icons.PEOPLE_ALT, interfaz.mostrar_gestion_clientes),
                interfaz.boton("Descontar Mercado Libre", ft.Icons.STOREFRONT, interfaz.mostrar_descuento_mercado_libre),
                interfaz.boton("Historial de Pedidos", ft.Icons.RECEIPT_LONG, interfaz.mostrar_historial_pedidos),
                interfaz.boton("Imprimir Descuento", ft.Icons.PRINT, interfaz.mostrar_imprimir_descuentos),
                interfaz.boton("Inventario en Vivo (Escáner)", ft.Icons.DOCUMENT_SCANNER, interfaz.mostrar_dialogo_inventario_vivo),
                interfaz.boton("Cierre de Jornada", ft.Icons.TASK_ALT, interfaz.mostrar_cierre_jornada),
            ]
        )

    controls.extend(
        [
            ft.Divider(height=18, color=interfaz.borde),
            ft.Text("INFORMES", size=11, weight=ft.FontWeight.BOLD, color=interfaz.secundario),
            interfaz.boton("Abrir informe", ft.Icons.OPEN_IN_NEW, interfaz.abrir_informe),
            interfaz.boton("Compartir por correo", ft.Icons.EMAIL, interfaz.compartir_correo),
            interfaz.boton("WhatsApp Web", ft.Icons.CHAT, interfaz.compartir_whatsapp),
        ]
    )

    if interfaz.usuario_actual.role in ("administrador", "master"):
        controls.extend(
            [
                ft.Divider(height=18, color=interfaz.borde),
                ft.Text("ADMINISTRACIÓN", size=11, weight=ft.FontWeight.BOLD, color=interfaz.secundario),
                interfaz.boton("Gestionar usuarios", ft.Icons.GROUP, interfaz.mostrar_gestion_usuarios),
                interfaz.boton("Gestión de Clientes", ft.Icons.PEOPLE_ALT, interfaz.mostrar_gestion_clientes),
                interfaz.boton("Historial de Pedidos", ft.Icons.RECEIPT_LONG, interfaz.mostrar_historial_pedidos),
                interfaz.boton("Restaurar documentos", ft.Icons.RESTORE, interfaz.confirmar_restaurar),
                interfaz.boton(
                    "Gestionar productos",
                    ft.Icons.ADD_BOX,
                    interfaz.mostrar_gestion_productos,
                ),
                interfaz.boton(
                    "Ajustar stock / Fábrica",
                    ft.Icons.INVENTORY_2,
                    interfaz.mostrar_ingreso_fabrica,
                ),
                interfaz.boton(
                    "Descontar Mercado Full",
                    ft.Icons.LOCAL_SHIPPING,
                    interfaz.mostrar_descuento_mercado_full,
                ),
                interfaz.boton(
                    "Descontar Mercado Libre",
                    ft.Icons.STOREFRONT,
                    interfaz.mostrar_descuento_mercado_libre,
                ),
                interfaz.boton(
                    "Comparativa stock físico",
                    ft.Icons.COMPARE_ARROWS,
                    interfaz.mostrar_comparativa_stock_fisico_admin,
                ),
                interfaz.boton(
                    "Generar pedido fábrica (Excel)",
                    ft.Icons.FACT_CHECK,
                    interfaz.generar_pedido_fabrica,
                ),
                interfaz.boton(
                    "Estadísticas de salida",
                    ft.Icons.BAR_CHART,
                    interfaz.mostrar_estadisticas,
                ),
                interfaz.boton(
                    "Métricas y Rendimiento",
                    ft.Icons.INSIGHTS,
                    interfaz.mostrar_dashboard_metricas,
                ),
                interfaz.boton(
                    "Registro de Auditoría",
                    ft.Icons.SECURITY,
                    interfaz.mostrar_registro_auditoria,
                ),
                interfaz.boton(
                    "Copia de Seguridad",
                    ft.Icons.BACKUP,
                    interfaz.mostrar_dialogo_backup,
                ),
            ]
        )

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
