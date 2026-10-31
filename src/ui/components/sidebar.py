"""Componente del menú lateral (Sidebar) con navegación clasificada por roles y funcionalidad."""

from pathlib import Path
from typing import Any
import flet as ft
from ..theme import ROJO


def construir_sidebar_controls(interfaz: Any) -> list[ft.Control]:
    """Genera la lista de controles para el panel lateral organizados profesionalmente por rol y funcionalidad."""
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

    # =========================================================================
    # ROL MASTER: Seguridad, Auditoría Forense y Resguardo Técnico
    # =========================================================================
    if interfaz.usuario_actual.role == "master":
        controls.extend(
            [
                ft.Text("AUDITORÍA Y TRAZABILIDAD", size=11, weight=ft.FontWeight.BOLD, color=interfaz.secundario),
                interfaz.boton("Registro de Auditoría", ft.Icons.SECURITY, interfaz.mostrar_registro_auditoria),

                ft.Divider(height=18, color=interfaz.borde),
                ft.Text("RESGUARDO Y CONTINUIDAD", size=11, weight=ft.FontWeight.BOLD, color=interfaz.secundario),
                interfaz.boton("Copia de Seguridad", ft.Icons.BACKUP, interfaz.mostrar_dialogo_backup),
                interfaz.boton("Archivado Histórico", ft.Icons.AUTO_DELETE, interfaz.mostrar_dialogo_archivo_historico),

                ft.Divider(height=18, color=interfaz.borde),
                ft.Text("SISTEMA", size=11, weight=ft.FontWeight.BOLD, color=interfaz.secundario),
                interfaz.boton("Configuración SMTP", ft.Icons.SETTINGS_APPLICATIONS, interfaz.mostrar_configuracion_smtp),
                interfaz.boton("Alertas Telegram", ft.Icons.SEND, interfaz.mostrar_configuracion_telegram),
                interfaz.boton("Mercado Libre API (Credenciales)", ft.Icons.CLOUD_SYNC, interfaz.mostrar_sincronizacion_mercadolibre),

                # Gestión de Usuarios al final para Master
                ft.Divider(height=18, color=interfaz.borde),
                ft.Text("SEGURIDAD Y ACCESOS", size=11, weight=ft.FontWeight.BOLD, color=interfaz.secundario),
                interfaz.boton("Gestionar usuarios", ft.Icons.MANAGE_ACCOUNTS, interfaz.mostrar_gestion_usuarios),
            ]
        )

    # =========================================================================
    # ROL OPERADOR: Preparación de Pedidos, Escaneo y Cierre de Depósito
    # =========================================================================
    elif interfaz.usuario_actual.role == "operador":
        controls.extend(
            [
                ft.Text("PEDIDOS EN TIEMPO REAL", size=11, weight=ft.FontWeight.BOLD, color=interfaz.secundario),
                interfaz.boton("Cargar / Armar Pedido", ft.Icons.POST_ADD, interfaz.mostrar_crear_pedido),
                interfaz.boton("Gestión de Clientes", ft.Icons.PEOPLE_ALT, interfaz.mostrar_gestion_clientes),
                interfaz.boton("Descontar Mercado Libre", ft.Icons.STOREFRONT, interfaz.mostrar_descuento_mercado_libre),
                interfaz.boton("Sincronizar Mercado Libre (API)", ft.Icons.CLOUD_SYNC, interfaz.mostrar_sincronizacion_mercadolibre),
                interfaz.boton("Historial de Pedidos", ft.Icons.RECEIPT_LONG, interfaz.mostrar_historial_pedidos),
                interfaz.boton("Imprimir Descuento", ft.Icons.PRINT, interfaz.mostrar_imprimir_descuentos),

                ft.Divider(height=18, color=interfaz.borde),
                ft.Text("CONTROL DE DEPÓSITO", size=11, weight=ft.FontWeight.BOLD, color=interfaz.secundario),
                interfaz.boton("Inventario en Vivo (Escáner)", ft.Icons.DOCUMENT_SCANNER, interfaz.mostrar_dialogo_inventario_vivo),
                interfaz.boton("Cierre de Jornada", ft.Icons.TASK_ALT, interfaz.mostrar_cierre_jornada),

                ft.Divider(height=18, color=interfaz.borde),
                ft.Text("INFORMES", size=11, weight=ft.FontWeight.BOLD, color=interfaz.secundario),
                interfaz.boton("Abrir informe", ft.Icons.OPEN_IN_NEW, interfaz.abrir_informe),
                interfaz.boton("Compartir por correo", ft.Icons.EMAIL, interfaz.compartir_correo),
                interfaz.boton("WhatsApp Web", ft.Icons.CHAT, interfaz.compartir_whatsapp),
            ]
        )

    # =========================================================================
    # ROL ADMINISTRADOR: Gestión Integral dividida por funcionalidad operativa
    # =========================================================================
    elif interfaz.usuario_actual.role == "administrador":
        controls.extend(
            [
                # 1. Catálogo e Inventario
                ft.Text("STOCK Y CATÁLOGO", size=11, weight=ft.FontWeight.BOLD, color=interfaz.secundario),
                interfaz.boton("Gestionar productos", ft.Icons.ADD_BOX, interfaz.mostrar_gestion_productos),
                interfaz.boton("Ajustar stock / Fábrica", ft.Icons.INVENTORY_2, interfaz.mostrar_ingreso_fabrica),
                interfaz.boton("Comparativa stock físico", ft.Icons.COMPARE_ARROWS, interfaz.mostrar_comparativa_stock_fisico_admin),
                interfaz.boton("Sincronizar con Excel", ft.Icons.SYNC, interfaz.sincronizar_catalogo_excel),
                interfaz.boton("Generar pedido fábrica (Excel)", ft.Icons.FACT_CHECK, interfaz.generar_pedido_fabrica),

                # 2. Despachos y Canales de Venta
                ft.Divider(height=18, color=interfaz.borde),
                ft.Text("VENTAS Y DESPACHOS", size=11, weight=ft.FontWeight.BOLD, color=interfaz.secundario),
                interfaz.boton("Historial de Pedidos", ft.Icons.RECEIPT_LONG, interfaz.mostrar_historial_pedidos),
                interfaz.boton("Gestión de Clientes", ft.Icons.PEOPLE_ALT, interfaz.mostrar_gestion_clientes),
                interfaz.boton("Descontar Mercado Libre", ft.Icons.STOREFRONT, interfaz.mostrar_descuento_mercado_libre),
                interfaz.boton("Mercado Libre API (Sync)", ft.Icons.CLOUD_SYNC, interfaz.mostrar_sincronizacion_mercadolibre),
                interfaz.boton("Descontar Mercado Full", ft.Icons.LOCAL_SHIPPING, interfaz.mostrar_descuento_mercado_full),
                interfaz.boton("Restaurar documentos", ft.Icons.RESTORE, interfaz.confirmar_restaurar),

                # 3. Analítica, Métricas y Optimización de Picking
                ft.Divider(height=18, color=interfaz.borde),
                ft.Text("ANALÍTICA Y PICKING", size=11, weight=ft.FontWeight.BOLD, color=interfaz.secundario),
                interfaz.boton("Métricas y Rendimiento", ft.Icons.INSIGHTS, interfaz.mostrar_dashboard_metricas),
                interfaz.boton("Estadísticas de salida", ft.Icons.BAR_CHART, interfaz.mostrar_estadisticas),
                interfaz.boton("Radar de anomalías", ft.Icons.AUTO_GRAPH, interfaz.mostrar_dialogo_anomalias),
                interfaz.boton("Heatmap y Picking", ft.Icons.GRID_VIEW_ROUNDED, interfaz.mostrar_dialogo_heatmap),

                # 4. Informes y Comunicaciones
                ft.Divider(height=18, color=interfaz.borde),
                ft.Text("INFORMES", size=11, weight=ft.FontWeight.BOLD, color=interfaz.secundario),
                interfaz.boton("Abrir informe", ft.Icons.OPEN_IN_NEW, interfaz.abrir_informe),
                interfaz.boton("Compartir por correo", ft.Icons.EMAIL, interfaz.compartir_correo),
                interfaz.boton("WhatsApp Web", ft.Icons.CHAT, interfaz.compartir_whatsapp),

                # 5. Sistema y Resguardo
                ft.Divider(height=18, color=interfaz.borde),
                ft.Text("SISTEMA Y RESGUARDO", size=11, weight=ft.FontWeight.BOLD, color=interfaz.secundario),
                interfaz.boton("Copia de Seguridad", ft.Icons.BACKUP, interfaz.mostrar_dialogo_backup),

                # 6. Gestión de Usuarios (Al final de todo)
                ft.Divider(height=18, color=interfaz.borde),
                ft.Text("ADMINISTRACIÓN DE USUARIOS", size=11, weight=ft.FontWeight.BOLD, color=interfaz.secundario),
                interfaz.boton("Gestionar usuarios", ft.Icons.GROUP, interfaz.mostrar_gestion_usuarios),
            ]
        )

    # =========================================================================
    # ROL CONSULTA: Solo Informes y Compartir
    # =========================================================================
    else:
        controls.extend(
            [
                ft.Text("INFORMES", size=11, weight=ft.FontWeight.BOLD, color=interfaz.secundario),
                interfaz.boton("Abrir informe", ft.Icons.OPEN_IN_NEW, interfaz.abrir_informe),
                interfaz.boton("Compartir por correo", ft.Icons.EMAIL, interfaz.compartir_correo),
                interfaz.boton("WhatsApp Web", ft.Icons.CHAT, interfaz.compartir_whatsapp),
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
