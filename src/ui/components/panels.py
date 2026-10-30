"""Componentes visuales del panel principal: tarjetas de métricas e informes de actividad."""

from typing import Any

import flet as ft

from ..theme import ROJO


def construir_panel_metricas(interfaz: Any) -> ft.Control:
    """Genera las tarjetas de métricas en vivo para la jornada activa."""
    if interfaz.usuario_actual and interfaz.usuario_actual.role == "master":
        metricas = [
            ("Usuarios Registrados", "usuarios_total", ft.Icons.GROUP),
            ("Cuentas Activas", "usuarios_activos", ft.Icons.VERIFIED_USER),
            ("Eventos Auditoría", "auditoria_eventos", ft.Icons.SECURITY),
            ("Copias de Respaldo", "backups_total", ft.Icons.BACKUP),
            ("Espacio en Disco", "telemetria_disco", ft.Icons.STORAGE),
            ("Salud Servidor", "telemetria_salud", ft.Icons.HEALTH_AND_SAFETY),
        ]
    else:
        metricas = [
            ("PDF de la jornada", "pdf", ft.Icons.DESCRIPTION),
            ("Canjes de la jornada", "canjes", ft.Icons.SHOPPING_BAG),
            ("Pedidos ML", "ml", ft.Icons.LOCAL_SHIPPING),
            ("Total Jornada", "total", ft.Icons.RECEIPT_LONG),
            ("Informes", "informes", ft.Icons.INSERT_CHART),
        ]
        if interfaz.usuario_actual and interfaz.usuario_actual.role == "administrador":
            metricas.append(("Quiebres de stock", "quiebres", ft.Icons.WARNING_AMBER))

    tarjetas = []
    for titulo, clave, icono in metricas:
        valor = ft.Text("0", size=25, weight=ft.FontWeight.BOLD, color=interfaz.texto)
        interfaz.contadores[clave] = valor
        tarjetas.append(
            ft.Container(
                expand=True,
                bgcolor=interfaz.superficie,
                border=ft.Border.all(1, interfaz.borde),
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
                                ft.Text(titulo, size=11, color=interfaz.secundario),
                                valor,
                            ],
                            spacing=3,
                        ),
                    ],
                    spacing=12,
                ),
            )
        )
    if interfaz.es_pantalla_movil:
        for t in tarjetas:
            t.expand = False
            t.col = 6
            t.padding = 10
        return ft.ResponsiveRow(tarjetas, spacing=8, run_spacing=8)
    return ft.Row(tarjetas, spacing=12)


def construir_panel_informes_actividad(interfaz: Any) -> ft.Control:
    """Genera el panel principal: 
    - Lado izquierdo: Pedidos preparados en vivo del turno con contador de bultos acumulados y fecha.
    - Lado derecho: Informes generados (o eventos de auditoría para Master).
    """
    es_master = bool(interfaz.usuario_actual and interfaz.usuario_actual.role == "master")
    titulo_derecha = "Eventos de auditoría recientes" if es_master else "Informes generados"
    icono_derecha = ft.Icons.SECURITY if es_master else ft.Icons.DESCRIPTION

    # Panel LADO DERECHO: Informes generados
    contenido_derecha = ft.Column(
        [
            ft.Row(
                [
                    ft.Text(titulo_derecha, size=15, weight=ft.FontWeight.BOLD, color=interfaz.texto),
                    ft.Icon(icono_derecha, color=ROJO, size=18),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            interfaz.lista_informes,
        ],
        expand=True,
        spacing=8,
    )

    # Panel LADO IZQUIERDO: Pedidos preparados en tiempo real (descendiente)
    contenido_izq = ft.Column(
        [
            # Header con fecha y contador de bultos acumulados
            ft.Container(
                bgcolor=interfaz.fondo_acento if interfaz.modo_oscuro else ft.Colors.RED_50,
                border=ft.Border.all(1, ft.Colors.with_opacity(0.3, ROJO)),
                border_radius=8,
                padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                content=ft.Row(
                    [
                        ft.Column(
                            [
                                ft.Row(
                                    [
                                        ft.Icon(ft.Icons.CALENDAR_TODAY, size=14, color=ROJO),
                                        interfaz.header_pedidos_fecha,
                                    ],
                                    spacing=6,
                                ),
                                interfaz.header_pedidos_subtitulo,
                            ],
                            spacing=2,
                        ),
                        ft.Container(
                            content=interfaz.header_pedidos_bultos,
                            bgcolor=ROJO,
                            padding=ft.Padding.symmetric(horizontal=10, vertical=4),
                            border_radius=12,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ),
            interfaz.lista_pedidos_preparados,
        ],
        expand=True,
        spacing=8,
    )

    tarjeta_der = interfaz.tarjeta(contenido_derecha, expand=True)

    # El usuario Master no gestiona ni visualiza pedidos operativos (Segregación SoD)
    if es_master:
        return tarjeta_der

    tarjeta_izq = interfaz.tarjeta(contenido_izq, expand=True)

    if interfaz.es_pantalla_movil:
        return ft.Column(
            [
                tarjeta_izq,
                tarjeta_der,
            ],
            spacing=12,
        )
    return ft.Row(
        [
            tarjeta_izq,
            tarjeta_der,
        ],
        spacing=12,
        expand=True,
    )
