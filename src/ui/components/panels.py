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
                            expand=True,
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
    es_movil = bool(interfaz.es_pantalla_movil)
    titulo_derecha = "Eventos de auditoría recientes" if es_master else "Informes generados"
    icono_derecha = ft.Icons.SECURITY if es_master else ft.Icons.DESCRIPTION

    # En pantallas móviles el dashboard padre usa scroll=AUTO (altura vertical no acotada).
    # Por ello en móvil desactivamos expand=True vertical y asignamos alturas acotadas
    # a los ListView para evitar excepciones RenderFlex / RenderViewport en Flutter.
    interfaz.lista_informes.expand = not es_movil
    interfaz.lista_informes.height = 240 if es_movil else None
    interfaz.lista_pedidos_preparados.expand = not es_movil
    interfaz.lista_pedidos_preparados.height = 260 if es_movil else None

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
        expand=not es_movil,
        tight=es_movil,
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
                            expand=True,
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
        expand=not es_movil,
        tight=es_movil,
        spacing=8,
    )

    tarjeta_der = interfaz.tarjeta(contenido_derecha, expand=not es_movil)

    # El usuario Master no gestiona ni visualiza pedidos operativos (Segregación SoD)
    if es_master:
        return tarjeta_der

    tarjeta_izq = interfaz.tarjeta(contenido_izq, expand=not es_movil)

    if es_movil:
        return ft.Column(
            [
                tarjeta_izq,
                tarjeta_der,
            ],
            spacing=12,
            tight=True,
        )
    return ft.Row(
        [
            tarjeta_izq,
            tarjeta_der,
        ],
        spacing=12,
        expand=True,
    )



def construir_panel_acceso_rapido(interfaz: Any) -> ft.Control:
    """Genera el panel de accesos rápidos táctiles según el rol del usuario:
    - Master: Oculto / Eliminado.
    - Picker: Ingreso, Egreso y Descontar Mercado Libre.
    - Administrador: Solo Ingreso y Egreso.
    - Operador: Cargar Pedido, Descontar ML, Ingreso y Egreso.
    - Consulta / Otros: Oculto.
    """
    rol = str(getattr(getattr(interfaz, "usuario_actual", None), "role", "")).lower()
    if rol in ("consulta", ""):
        return ft.Container(height=0, visible=False)

    es_movil = bool(getattr(interfaz, "es_pantalla_movil", False))
    es_oscuro = bool(getattr(interfaz, "modo_oscuro", True))

    items_config = []
    if rol == "master":
        items_config = [
            (
                "Gestionar Usuarios",
                "Control de cuentas y credenciales IAM",
                ft.Icons.MANAGE_ACCOUNTS,
                ft.Colors.BLUE_600,
                interfaz.mostrar_gestion_usuarios,
            ),
            (
                "Registro de Auditoría",
                "Trazabilidad forense e historial de eventos",
                ft.Icons.SECURITY,
                ROJO,
                interfaz.mostrar_registro_auditoria,
            ),
        ]
    elif rol == "picker":
        items_config = [
            (
                "Descontar Mercado Libre",
                "Escaneo de paquetes y etiquetas ML",
                ft.Icons.STOREFRONT,
                ft.Colors.AMBER_600,
                interfaz.mostrar_descuento_mercado_libre,
            ),
            (
                "Ingreso de Stock",
                "Entrada rápida / Fábrica",
                ft.Icons.INPUT,
                ft.Colors.GREEN_700,
                interfaz.mostrar_dialogo_ingreso_rapido,
            ),
            (
                "Egreso de Stock",
                "Salida rápida de mercadería",
                ft.Icons.OUTPUT,
                ft.Colors.DEEP_ORANGE_600,
                interfaz.mostrar_dialogo_salida_rapida,
            ),
        ]
    elif rol == "administrador":
        items_config = [
            (
                "Gestionar Productos",
                "Catálogo maestro y existencias",
                ft.Icons.INVENTORY_2,
                ft.Colors.BLUE_600,
                interfaz.mostrar_gestion_productos,
            ),
            (
                "Ingreso de Stock",
                "Entrada rápida / Fábrica",
                ft.Icons.INPUT,
                ft.Colors.GREEN_700,
                interfaz.mostrar_dialogo_ingreso_rapido,
            ),
            (
                "Egreso de Stock",
                "Salida rápida de mercadería",
                ft.Icons.OUTPUT,
                ft.Colors.DEEP_ORANGE_600,
                interfaz.mostrar_dialogo_salida_rapida,
            ),
        ]
    elif rol == "operador":
        items_config = [
            (
                "Cargar / Armar Pedido",
                "Nuevo remito o canje",
                ft.Icons.POST_ADD,
                ft.Colors.BLUE_600,
                interfaz.mostrar_crear_pedido,
            ),
            (
                "Descontar Mercado Libre",
                "Escaneo de etiquetas ML",
                ft.Icons.STOREFRONT,
                ft.Colors.AMBER_600,
                interfaz.mostrar_descuento_mercado_libre,
            ),
            (
                "Ingreso de Stock",
                "Entrada rápida de fábrica",
                ft.Icons.INPUT,
                ft.Colors.GREEN_700,
                interfaz.mostrar_dialogo_ingreso_rapido,
            ),
            (
                "Egreso de Stock",
                "Salida rápida de mercadería",
                ft.Icons.OUTPUT,
                ft.Colors.DEEP_ORANGE_600,
                interfaz.mostrar_dialogo_salida_rapida,
            ),
        ]

    if not items_config:
        return ft.Container(height=0, visible=False)

    tarjetas = []
    for titulo, subtitulo, icono, color_icono, accion in items_config:
        bg_icon_container = (
            ft.Colors.with_opacity(0.18, color_icono)
            if es_oscuro
            else ft.Colors.with_opacity(0.12, color_icono)
        )
        card = ft.Container(
            expand=not es_movil,
            bgcolor=interfaz.superficie,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.15, interfaz.texto)),
            border_radius=12,
            padding=ft.Padding.symmetric(horizontal=14, vertical=12),
            ink=True,
            on_click=accion,
            content=ft.Row(
                [
                    ft.Container(
                        width=42,
                        height=42,
                        border_radius=10,
                        bgcolor=bg_icon_container,
                        alignment=ft.Alignment.CENTER,
                        content=ft.Icon(icono, color=color_icono, size=22),
                    ),
                    ft.Column(
                        [
                            ft.Text(titulo, size=13, weight=ft.FontWeight.BOLD, color=interfaz.texto),
                            ft.Text(subtitulo, size=11, color=interfaz.secundario),
                        ],
                        spacing=2,
                        expand=True,
                    ),
                    ft.Icon(ft.Icons.ARROW_FORWARD_IOS, size=12, color=interfaz.secundario),
                ],
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )
        tarjetas.append(card)

    if es_movil:
        for t in tarjetas:
            t.expand = False
            t.col = 12 if len(tarjetas) <= 2 else 6
        contenedor_tarjetas = ft.ResponsiveRow(tarjetas, spacing=8, run_spacing=8)
    else:
        contenedor_tarjetas = ft.Row(tarjetas, spacing=12)

    titulo_rapido = "Accesos Rápidos de Seguridad y Control" if rol == "master" else "Accesos Rápidos de Operación"
    icono_rapido = ft.Icons.SECURITY if rol == "master" else ft.Icons.FLASH_ON

    return ft.Container(
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Icon(icono_rapido, size=16, color=ROJO),
                        ft.Text(titulo_rapido, size=13, weight=ft.FontWeight.BOLD, color=interfaz.texto),
                    ],
                    spacing=6,
                ),
                contenedor_tarjetas,
            ],
            spacing=8,
            tight=True,
        ),
        padding=ft.Padding.only(bottom=4),
    )
