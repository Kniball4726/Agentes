"""Diálogo modal para la Búsqueda Rápida Global y Paleta de Comandos (Ctrl+K / F2)."""

from typing import Any
import flet as ft
from ..theme import ROJO


def mostrar_command_palette(interfaz: Any, _evento: ft.Event | None = None) -> None:
    """Abre la paleta de comandos universal para búsqueda instantánea en todo el sistema."""
    if not interfaz.usuario_actual or not interfaz.page:
        return

    rol = interfaz.usuario_actual.role

    # Acciones y accesos rápidos según el rol del usuario (100% de los módulos disponibles)
    accesos_rapidos = []
    if rol == "operador":
        accesos_rapidos.extend([
            ("Ver Stock", "Consulta de existencias y niveles en tiempo real", ft.Icons.VISIBILITY, ft.Colors.CYAN_400, interfaz.mostrar_ver_stock),
            ("Cargar / Armar Pedido", "Formulario rápido de remitos y canjes", ft.Icons.POST_ADD, ft.Colors.BLUE_400, interfaz.mostrar_crear_pedido),
            ("Ingreso de Fábrica", "Escáner rápido de recepción de mercadería", ft.Icons.INVENTORY_2, ft.Colors.ORANGE_400, interfaz.mostrar_ingreso_fabrica),
            ("Inventario en Vivo (Escáner)", "Conteo con cámara de celular o lector USB", ft.Icons.DOCUMENT_SCANNER, ft.Colors.GREEN_400, interfaz.mostrar_dialogo_inventario_vivo),
            ("Cierre de Jornada", "Consolidar turnos y generar hoja de ruta PDF", ft.Icons.TASK_ALT, ROJO, interfaz.mostrar_cierre_jornada),
            ("Historial de Pedidos", "Buscar, reimprimir y ver pedidos del turno", ft.Icons.RECEIPT_LONG, ft.Colors.AMBER_400, interfaz.mostrar_historial_pedidos),
            ("Imprimir Descuento", "Consultar y reimprimir comprobantes de descuento", ft.Icons.PRINT, ft.Colors.CYAN_400, interfaz.mostrar_imprimir_descuentos),
            ("Gestión de Clientes", "Directorio y consulta de clientes", ft.Icons.PEOPLE_ALT, ft.Colors.TEAL_400, interfaz.mostrar_gestion_clientes),
            ("Descontar Mercado Libre", "Escaneo rápido de paquetes y etiquetas ML", ft.Icons.STOREFRONT, ft.Colors.AMBER_600, interfaz.mostrar_descuento_mercado_libre),
            ("Descontar Mercado Full", "Procesamiento de envíos Mercado Libre Full", ft.Icons.LOCAL_SHIPPING, ft.Colors.ORANGE_400, interfaz.mostrar_descuento_mercado_full),
            ("Abrir Informe", "Descargar o visualizar el último informe generado", ft.Icons.OPEN_IN_NEW, ft.Colors.INDIGO_400, interfaz.abrir_informe),
            ("Compartir por Correo", "Enviar informes de stock por correo electrónico", ft.Icons.EMAIL, ft.Colors.BLUE_300, interfaz.compartir_correo),
            ("WhatsApp Web", "Compartir remitos o estado de pedidos por WhatsApp", ft.Icons.CHAT, ft.Colors.GREEN_600, interfaz.compartir_whatsapp),
            ("Manual de Uso", "Documentación oficial del operario en PDF", ft.Icons.MENU_BOOK, ft.Colors.CYAN_400, interfaz.mostrar_manual_usuario),
        ])
    elif rol == "administrador":
        accesos_rapidos.extend([
            ("Ver Stock", "Consulta de existencias y niveles en tiempo real", ft.Icons.VISIBILITY, ft.Colors.CYAN_400, interfaz.mostrar_ver_stock),
            ("Gestionar Productos", "Catálogo maestro y existencias en Productos.xlsx", ft.Icons.ADD_BOX, ft.Colors.BLUE_400, interfaz.mostrar_gestion_productos),
            ("Métricas y Rendimiento", "Dashboard ejecutivo, rotación y volumen", ft.Icons.INSIGHTS, ft.Colors.PURPLE_400, interfaz.mostrar_dashboard_metricas),
            ("Historial de Pedidos", "Supervisión, reimpresión y rótulos en lote", ft.Icons.RECEIPT_LONG, ft.Colors.AMBER_400, interfaz.mostrar_historial_pedidos),
            ("Cierres de Operarios", "Historial descendente de cierres creados por operarios", ft.Icons.FACT_CHECK, ft.Colors.ORANGE_400, interfaz.mostrar_historial_cierres_admin),
            ("Ajustar Stock / Fábrica", "Ingresos de mercadería y remitos de fábrica", ft.Icons.INVENTORY_2, ft.Colors.GREEN_400, interfaz.mostrar_ingreso_fabrica),
            ("Copia de Seguridad", "Respaldos .ZIP y espejo en red / nube", ft.Icons.BACKUP, ROJO, interfaz.mostrar_dialogo_backup),
            ("Comparativa Stock Físico", "Contraste de conteos físicos contra inventario", ft.Icons.COMPARE_ARROWS, ft.Colors.TEAL_400, interfaz.mostrar_comparativa_stock_fisico_admin),
            ("Sincronizar con Excel", "Volcar catálogo SQLite a Productos.xlsx", ft.Icons.SYNC, ft.Colors.LIGHT_BLUE_400, interfaz.sincronizar_catalogo_excel),
            ("Generar Pedido Fábrica (Excel)", "Cálculo de sugerido y planilla de reposición", ft.Icons.FACT_CHECK, ft.Colors.AMBER_400, interfaz.generar_pedido_fabrica),
            ("Gestión de Clientes", "Directorio y consulta de clientes mayoristas", ft.Icons.PEOPLE_ALT, ft.Colors.TEAL_400, interfaz.mostrar_gestion_clientes),
            ("Descontar Mercado Libre", "Escaneo rápido de paquetes y etiquetas ML", ft.Icons.STOREFRONT, ft.Colors.AMBER_600, interfaz.mostrar_descuento_mercado_libre),
            ("Sincronizar Mercado Libre (API)", "Conexión y credenciales de Mercado Libre", ft.Icons.CLOUD_SYNC, ft.Colors.AMBER_600, interfaz.mostrar_sincronizacion_mercadolibre),
            ("Descontar Mercado Full", "Procesamiento de envíos Mercado Libre Full", ft.Icons.LOCAL_SHIPPING, ft.Colors.ORANGE_400, interfaz.mostrar_descuento_mercado_full),
            ("Estadísticas de Salida", "Gráficos de ventas y flujo histórico de bultos", ft.Icons.BAR_CHART, ft.Colors.BLUE_GREY_400, interfaz.mostrar_estadisticas),
            ("Radar de Anomalías", "Detección estadística de saltos bruscos y desvíos", ft.Icons.AUTO_GRAPH, ft.Colors.RED_400, interfaz.mostrar_dialogo_anomalias),
            ("Heatmap y Picking", "Distribución en planta y optimización de recorrido", ft.Icons.GRID_VIEW_ROUNDED, ft.Colors.PINK_400, interfaz.mostrar_dialogo_heatmap),
            ("Abrir Informe", "Descargar o visualizar informes y balances", ft.Icons.OPEN_IN_NEW, ft.Colors.INDIGO_400, interfaz.abrir_informe),
            ("Compartir por Correo", "Enviar informes y balances por correo", ft.Icons.EMAIL, ft.Colors.BLUE_300, interfaz.compartir_correo),
            ("WhatsApp Web", "Compartir balances o remitos vía WhatsApp", ft.Icons.CHAT, ft.Colors.GREEN_600, interfaz.compartir_whatsapp),
            ("Gestionar Usuarios", "Control de cuentas y credenciales IAM", ft.Icons.GROUP, ft.Colors.BLUE_400, interfaz.mostrar_gestion_usuarios),
            ("Manual de Uso", "Documentación oficial del administrador en PDF", ft.Icons.MENU_BOOK, ft.Colors.CYAN_400, interfaz.mostrar_manual_usuario),
        ])
    elif rol == "master":
        accesos_rapidos.extend([
            ("Gestión de Claves API", "Administrar tokens y claves de integración externa", ft.Icons.VPN_KEY, ft.Colors.CYAN_400, interfaz.mostrar_gestion_api_keys),
            ("Documentación y Estado API", "Swagger UI, ReDoc y estado del servidor REST", ft.Icons.API, ft.Colors.BLUE_400, interfaz.mostrar_estado_api),
            ("Sesiones de API Activas", "Ver y revocar sesiones REST conectadas", ft.Icons.DEVICES, ft.Colors.TEAL_400, interfaz.mostrar_sesiones_api),
        ])
        accesos_rapidos.extend([
            ("Registro de Auditoría", "Trazabilidad forense e historial de eventos", ft.Icons.SECURITY, ROJO, interfaz.mostrar_registro_auditoria),
            ("Copia de Seguridad", "Gestión de respaldos y espejo en red", ft.Icons.BACKUP, ft.Colors.PURPLE_400, interfaz.mostrar_dialogo_backup),
            ("Gestionar Usuarios", "Control de cuentas y credenciales IAM", ft.Icons.MANAGE_ACCOUNTS, ft.Colors.BLUE_400, interfaz.mostrar_gestion_usuarios),
            ("Configuración SMTP", "Servidor de correo para reportes", ft.Icons.SETTINGS_APPLICATIONS, ft.Colors.TEAL_400, interfaz.mostrar_configuracion_smtp),
            ("Alertas Telegram", "Configuración de bot de avisos proactivos", ft.Icons.SEND, ft.Colors.CYAN_400, interfaz.mostrar_configuracion_telegram),
            ("Restaurar Documentos", "Recuperación de base de datos desde copias de seguridad", ft.Icons.RESTORE, ft.Colors.DEEP_ORANGE_400, interfaz.confirmar_restaurar),
            ("Archivado Histórico", "Archivar pedidos antiguos y compactar base de datos", ft.Icons.AUTO_DELETE, ft.Colors.BROWN_400, interfaz.mostrar_dialogo_archivo_historico),
            ("Mercado Libre API (Credenciales)", "Configuración OAuth y sincronización API", ft.Icons.CLOUD_SYNC, ft.Colors.AMBER_600, interfaz.mostrar_sincronizacion_mercadolibre),
            ("Manual de Uso", "Documentación oficial del usuario master en PDF", ft.Icons.MENU_BOOK, ft.Colors.CYAN_400, interfaz.mostrar_manual_usuario),
        ])
    elif rol == "picker":
        accesos_rapidos.extend([
            ("Descontar Mercado Libre", "Escaneo rápido de paquetes y etiquetas ML", ft.Icons.STOREFRONT, ft.Colors.AMBER_600, interfaz.mostrar_descuento_mercado_libre),
            ("Descontar Mercado Full", "Procesamiento de envíos Mercado Libre Full", ft.Icons.LOCAL_SHIPPING, ft.Colors.ORANGE_400, interfaz.mostrar_descuento_mercado_full),
            ("Ingreso de Mercadería", "Entrada rápida de stock", ft.Icons.INPUT, ft.Colors.GREEN_400, interfaz.mostrar_dialogo_ingreso_rapido),
            ("Ingreso de Fábrica", "Escáner rápido de recepción de mercadería", ft.Icons.INVENTORY_2, ft.Colors.ORANGE_400, interfaz.mostrar_ingreso_fabrica),
            ("Egreso de Mercadería", "Salida rápida de stock", ft.Icons.OUTPUT, ft.Colors.RED_400, interfaz.mostrar_dialogo_salida_rapida),
            ("Manual de Uso", "Documentación oficial en PDF", ft.Icons.MENU_BOOK, ft.Colors.CYAN_400, interfaz.mostrar_manual_usuario),
        ])
    else:
        accesos_rapidos.extend([
            ("Abrir Informe", "Descargar o visualizar informes y balances", ft.Icons.OPEN_IN_NEW, ft.Colors.INDIGO_400, interfaz.abrir_informe),
            ("Compartir por Correo", "Enviar informes por correo", ft.Icons.EMAIL, ft.Colors.BLUE_300, interfaz.compartir_correo),
            ("WhatsApp Web", "Compartir informes vía WhatsApp", ft.Icons.CHAT, ft.Colors.GREEN_600, interfaz.compartir_whatsapp),
            ("Manual de Uso", "Documentación oficial de consulta en PDF", ft.Icons.MENU_BOOK, ft.Colors.CYAN_400, interfaz.mostrar_manual_usuario),
        ])

    accesos_rapidos.extend([
        ("Mover Barra: A la Izquierda", "Ubicar el panel de menú en el lateral izquierdo", ft.Icons.DOCK, ft.Colors.LIGHT_BLUE_300, lambda: getattr(interfaz, "cambiar_posicion_sidebar", lambda _p: None)("izquierda")),
        ("Mover Barra: A la Derecha", "Ubicar el panel de menú en el lateral derecho", ft.Icons.DOCK, ft.Colors.LIGHT_BLUE_300, lambda: getattr(interfaz, "cambiar_posicion_sidebar", lambda _p: None)("derecha")),
        ("Mover Barra: Arriba (Horizontal)", "Ubicar el menú superior de forma horizontal", ft.Icons.HORIZONTAL_SPLIT, ft.Colors.TEAL_300, lambda: getattr(interfaz, "cambiar_posicion_sidebar", lambda _p: None)("arriba")),
        ("Mover Barra: Abajo (Horizontal)", "Ubicar el menú inferior de forma horizontal", ft.Icons.HORIZONTAL_SPLIT, ft.Colors.TEAL_300, lambda: getattr(interfaz, "cambiar_posicion_sidebar", lambda _p: None)("abajo")),
        ("Ocultar Barra (Pantalla Completa)", "Modo enfoque sin barra lateral (usa F2 o el header)", ft.Icons.FULLSCREEN, ft.Colors.AMBER_300, lambda: getattr(interfaz, "cambiar_posicion_sidebar", lambda _p: None)("oculto")),
        ("Alternar Modo Claro / Oscuro", "Cambiar entre apariencia diurna y nocturna", ft.Icons.DARK_MODE, ft.Colors.PURPLE_300, interfaz.alternar_tema),
        ("Abrir Asistente / Chat de Equipo", "Panel interactivo de consultas y chat interno", ft.Icons.SMART_TOY, ft.Colors.GREEN_300, interfaz.alternar_chat_flotante),
        ("Actualizar Todo (Refrescar)", "Recargar pedidos, contadores y métricas", ft.Icons.REFRESH, ft.Colors.ORANGE_300, interfaz.actualizar_estado),
        ])

    resultados_lista = ft.ListView(expand=True, spacing=6, height=360)
    indicador_estado = ft.Text("Escribe para buscar productos, clientes, pedidos o comandos...", size=11, color=interfaz.secundario)

    def ejecutar_accion(callback: Any) -> None:
        try:
            interfaz.page.pop_dialog()
        except Exception:
            pass
        if callable(callback):
            callback()

    def renderizar_resultados(query: str = "") -> None:
        q = (query or "").strip().lower()
        resultados_lista.controls.clear()

        # Si el campo está vacío, mostramos los accesos directos principales
        if not q:
            indicador_estado.value = "Accesos rápidos sugeridos (escribe para buscar en profundidad):"
            for titulo, desc, icono, col, cb in accesos_rapidos:
                resultados_lista.controls.append(
                    ft.Container(
                        bgcolor=interfaz.superficie,
                        border=ft.Border.all(1, interfaz.borde),
                        border_radius=8,
                        padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                        ink=True,
                        on_click=lambda _e, fn=cb: ejecutar_accion(fn),
                        content=ft.Row(
                            [
                                ft.Icon(icono, color=col, size=20),
                                ft.Column(
                                    [
                                        ft.Text(titulo, weight=ft.FontWeight.BOLD, size=12, color=interfaz.texto),
                                        ft.Text(desc, size=10, color=interfaz.secundario),
                                    ],
                                    spacing=2,
                                    expand=True,
                                ),
                                ft.Container(
                                    content=ft.Text("Módulo", size=9, weight=ft.FontWeight.BOLD, color=col),
                                    bgcolor=ft.Colors.with_opacity(0.12, col),
                                    padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                                    border_radius=4,
                                ),
                            ],
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                    )
                )
            if interfaz.page:
                interfaz.page.update()
            return

        total_encontrados = 0

        # 1. Comandos / Módulos coincidentes
        comandos_match = [
            (t, d, ic, col, cb) for t, d, ic, col, cb in accesos_rapidos
            if q in t.lower() or q in d.lower()
        ]
        if comandos_match:
            resultados_lista.controls.append(
                ft.Text("ACCIONES Y MÓDULOS", size=10, weight=ft.FontWeight.BOLD, color=interfaz.secundario)
            )
            for titulo, desc, icono, col, cb in comandos_match:
                total_encontrados += 1
                resultados_lista.controls.append(
                    ft.Container(
                        bgcolor=interfaz.superficie,
                        border=ft.Border.all(1, interfaz.borde),
                        border_radius=8,
                        padding=ft.Padding.symmetric(horizontal=10, vertical=7),
                        ink=True,
                        on_click=lambda _e, fn=cb: ejecutar_accion(fn),
                        content=ft.Row(
                            [
                                ft.Icon(icono, color=col, size=18),
                                ft.Column(
                                    [
                                        ft.Text(titulo, weight=ft.FontWeight.BOLD, size=12, color=interfaz.texto),
                                        ft.Text(desc, size=10, color=interfaz.secundario),
                                    ],
                                    spacing=2,
                                    expand=True,
                                ),
                                ft.Icon(ft.Icons.KEYBOARD_RETURN, size=14, color=interfaz.secundario),
                            ],
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                    )
                )

        # 2. Búsqueda de Productos (solo si no es master)
        if rol != "master" and hasattr(interfaz, "product_store"):
            try:
                productos_encontrados = interfaz.product_store.buscar_productos(q)[:5]
                if productos_encontrados:
                    resultados_lista.controls.append(
                        ft.Text("PRODUCTOS EN STOCK", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_400)
                    )
                    for prod in productos_encontrados:
                        total_encontrados += 1
                        p_code = str(prod["code"] if hasattr(prod, "__getitem__") else getattr(prod, "codigo", getattr(prod, "code", "")))
                        p_name = str(prod["name"] if hasattr(prod, "__getitem__") else getattr(prod, "descripcion", getattr(prod, "name", "")))
                        p_stock = int(prod["stock"] if hasattr(prod, "__getitem__") else getattr(prod, "stock_actual", getattr(prod, "stock", 0)))
                        p_ubic = str(prod["ubicacion"] if hasattr(prod, "__getitem__") else getattr(prod, "ubicacion", "") or "")

                        stk_color = ft.Colors.GREEN_400 if p_stock > 5 else (ft.Colors.AMBER_400 if p_stock > 0 else ft.Colors.RED_400)
                        loc_txt = f" · Ubic: {p_ubic}" if p_ubic else ""

                        def copiar_y_notificar(cod_val=p_code):
                            if hasattr(interfaz, "copiar_al_portapapeles"):
                                interfaz.copiar_al_portapapeles(cod_val)
                            elif hasattr(interfaz.page, "set_clipboard"):
                                interfaz.page.set_clipboard(cod_val)
                            interfaz.notificar(f"Código copiado al portapapeles: {cod_val}")

                        resultados_lista.controls.append(
                            ft.Container(
                                bgcolor=interfaz.superficie,
                                border=ft.Border.all(1, interfaz.borde),
                                border_radius=8,
                                padding=ft.Padding.symmetric(horizontal=10, vertical=7),
                                ink=True,
                                tooltip=f"Clic para copiar código [{p_code}]",
                                on_click=lambda _e, cod=p_code: copiar_y_notificar(cod),
                                content=ft.Row(
                                    [
                                        ft.Icon(ft.Icons.INVENTORY_2, size=18, color=ft.Colors.BLUE_400),
                                        ft.Column(
                                            [
                                                ft.Text(f"[{p_code}] {p_name}", weight=ft.FontWeight.BOLD, size=12, color=interfaz.texto),
                                                ft.Text(f"Stock: {p_stock} un.{loc_txt}", size=10, color=stk_color),
                                            ],
                                            spacing=2,
                                            expand=True,
                                        ),
                                        ft.Container(
                                            content=ft.Text(f"{p_stock} un.", size=10, weight=ft.FontWeight.BOLD, color=stk_color),
                                            bgcolor=ft.Colors.with_opacity(0.12, stk_color),
                                            padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                                            border_radius=4,
                                        ),
                                    ],
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                ),
                            )
                        )
            except Exception:
                pass

        # 3. Búsqueda de Clientes (solo si no es master)
        if rol != "master" and hasattr(interfaz, "order_store"):
            try:
                clientes_encontrados = interfaz.order_store.buscar_clientes(q)[:4]
                if clientes_encontrados:
                    resultados_lista.controls.append(
                        ft.Text("CLIENTES", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.TEAL_400)
                    )
                    for cli in clientes_encontrados:
                        total_encontrados += 1
                        dir_txt = f" · {cli.direccion}" if cli.direccion else ""
                        cod_txt = f"[{cli.codigo}] " if cli.codigo else ""
                        resultados_lista.controls.append(
                            ft.Container(
                                bgcolor=interfaz.superficie,
                                border=ft.Border.all(1, interfaz.borde),
                                border_radius=8,
                                padding=ft.Padding.symmetric(horizontal=10, vertical=7),
                                ink=True,
                                on_click=lambda _e: ejecutar_accion(interfaz.mostrar_gestion_clientes),
                                content=ft.Row(
                                    [
                                        ft.Icon(ft.Icons.PEOPLE_ALT, size=18, color=ft.Colors.TEAL_400),
                                        ft.Column(
                                            [
                                                ft.Text(f"{cod_txt}{cli.nombre}", weight=ft.FontWeight.BOLD, size=12, color=interfaz.texto),
                                                ft.Text(f"Cliente activo{dir_txt}", size=10, color=interfaz.secundario),
                                            ],
                                            spacing=2,
                                            expand=True,
                                        ),
                                    ],
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                ),
                            )
                        )
            except Exception:
                pass

        # 4. Búsqueda de Pedidos (solo si no es master)
        if rol != "master" and hasattr(interfaz, "order_store"):
            try:
                peds_todos = interfaz.order_store.listar_pedidos(limit=150)
                pedidos_match = [
                    p for p in peds_todos
                    if q in (p.cliente or "").lower()
                    or q in (p.nota_pedido or "").lower()
                    or q in str(getattr(p, "numero_pedido", "") or "").lower()
                    or q in str(getattr(p, "numero_guia", "") or "").lower()
                ][:5]
                if pedidos_match:
                    resultados_lista.controls.append(
                        ft.Text("PEDIDOS Y REMITOS", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.AMBER_400)
                    )
                    for p in pedidos_match:
                        total_encontrados += 1
                        n_ped_txt = f"Pedido #{p.numero_pedido} · " if getattr(p, "numero_pedido", "") else ""
                        guia_str = f" · Guía: {p.numero_guia}" if getattr(p, "numero_guia", "") else ""
                        
                        def abrir_ped(ped_obj=p):
                            interfaz.page.pop_dialog()
                            if rol == "operador":
                                interfaz.mostrar_dialogo_editar_pedido(ped_obj, al_final=interfaz.actualizar_listas)
                            else:
                                interfaz.mostrar_detalle_pedido_modal(ped_obj)

                        resultados_lista.controls.append(
                            ft.Container(
                                bgcolor=interfaz.superficie,
                                border=ft.Border.all(1, interfaz.borde),
                                border_radius=8,
                                padding=ft.Padding.symmetric(horizontal=10, vertical=7),
                                ink=True,
                                on_click=lambda _e, ped_obj=p: abrir_ped(ped_obj),
                                content=ft.Row(
                                    [
                                        ft.Icon(ft.Icons.RECEIPT_LONG, size=18, color=ft.Colors.AMBER_400),
                                        ft.Column(
                                            [
                                                ft.Text(f"{n_ped_txt}Remito: {p.nota_pedido} ({p.cliente})", weight=ft.FontWeight.BOLD, size=12, color=interfaz.texto),
                                                ft.Text(f"{p.bultos} bulto(s) · {p.logistica}{guia_str}", size=10, color=interfaz.secundario),
                                            ],
                                            spacing=2,
                                            expand=True,
                                        ),
                                        ft.Container(
                                            content=ft.Text(p.estado_despacho.upper(), size=9, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                                            bgcolor=ROJO if p.estado_despacho == "armado" else (ft.Colors.BLUE_600 if p.estado_despacho == "despachado" else ft.Colors.GREEN_600),
                                            padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                                            border_radius=4,
                                        ),
                                    ],
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                ),
                            )
                        )
            except Exception:
                pass

        if total_encontrados == 0:
            resultados_lista.controls.append(
                ft.Container(
                    padding=25,
                    alignment=ft.Alignment.CENTER,
                    content=ft.Column(
                        [
                            ft.Icon(ft.Icons.SEARCH_OFF, size=32, color=interfaz.secundario),
                            ft.Text(f"No se encontraron resultados para '{query}'.", size=12, color=interfaz.secundario),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=6,
                    ),
                )
            )
            indicador_estado.value = "Sin coincidencias."
        else:
            indicador_estado.value = f"Mostrando {total_encontrados} resultado(s) encontrado(s):"

        if interfaz.page:
            interfaz.page.update()

    campo_busqueda = ft.TextField(
        hint_text="Buscar productos, clientes, remitos o acciones...",
        prefix_icon=ft.Icons.SEARCH,
        autofocus=True,
        dense=True,
        on_change=lambda e: renderizar_resultados(e.control.value),
    )

    dialogo = ft.AlertDialog(
        modal=True,
        title=ft.Row(
            [
                ft.Icon(ft.Icons.TERMINAL, color=ROJO, size=20),
                ft.Text("Menú Rápido y Buscador Global", weight=ft.FontWeight.BOLD, size=15),
                ft.Container(
                    content=ft.Text("F2 / Ctrl+K", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                    bgcolor=ROJO,
                    padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                    border_radius=4,
                ),
            ],
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        content=ft.Container(
            width=580,
            content=ft.Column(
                [
                    campo_busqueda,
                    indicador_estado,
                    ft.Divider(height=10),
                    resultados_lista,
                ],
                tight=True,
                spacing=8,
            ),
        ),
        actions=[
            interfaz.boton_dialogo("Cerrar (Esc)", lambda _e: interfaz.page.pop_dialog()),
        ],
    )

    renderizar_resultados("")
    interfaz.page.show_dialog(dialogo)
