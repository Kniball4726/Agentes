"""Diálogo modal para la Búsqueda Rápida Global y Paleta de Comandos (Ctrl+K / F2)."""

from typing import Any
import flet as ft
from ..theme import ROJO


def mostrar_command_palette(interfaz: Any, _evento: ft.Event | None = None) -> None:
    """Abre la paleta de comandos universal para búsqueda instantánea en todo el sistema."""
    if not interfaz.usuario_actual or not interfaz.page:
        return

    rol = interfaz.usuario_actual.role

    # Acciones y accesos rápidos según el rol del usuario
    accesos_rapidos = []
    if rol == "operador":
        accesos_rapidos.extend([
            ("Cargar / Armar Pedido", "Formulario rápido de remitos y canjes", ft.Icons.POST_ADD, ft.Colors.BLUE_400, interfaz.mostrar_crear_pedido),
            ("Inventario en Vivo (Escáner)", "Conteo con cámara de celular o lector USB", ft.Icons.DOCUMENT_SCANNER, ft.Colors.GREEN_400, interfaz.mostrar_dialogo_inventario_vivo),
            ("Cierre de Jornada", "Consolidar turnos y generar hoja de ruta PDF", ft.Icons.TASK_ALT, ROJO, interfaz.mostrar_cierre_jornada),
            ("Historial de Pedidos", "Buscar, reimprimir y ver pedidos del turno", ft.Icons.RECEIPT_LONG, ft.Colors.AMBER_400, interfaz.mostrar_historial_pedidos),
            ("Gestión de Clientes", "Directorio y consulta de clientes", ft.Icons.PEOPLE_ALT, ft.Colors.TEAL_400, interfaz.mostrar_gestion_clientes),
        ])
    elif rol == "administrador":
        accesos_rapidos.extend([
            ("Gestionar Productos", "Catálogo maestro y existencias en Productos.xlsx", ft.Icons.ADD_BOX, ft.Colors.BLUE_400, interfaz.mostrar_gestion_productos),
            ("Métricas y Rendimiento", "Dashboard ejecutivo, rotación y volumen", ft.Icons.INSIGHTS, ft.Colors.PURPLE_400, interfaz.mostrar_dashboard_metricas),
            ("Historial de Pedidos", "Supervisión, reimpresión y rótulos en lote", ft.Icons.RECEIPT_LONG, ft.Colors.AMBER_400, interfaz.mostrar_historial_pedidos),
            ("Ajustar Stock / Fábrica", "Ingresos de mercadería y remitos de fábrica", ft.Icons.INVENTORY_2, ft.Colors.GREEN_400, interfaz.mostrar_ingreso_fabrica),
            ("Copia de Seguridad", "Respaldos .ZIP y espejo en red / nube", ft.Icons.BACKUP, ROJO, interfaz.mostrar_dialogo_backup),
            ("Comparativa Stock Físico", "Contraste de conteos físicos contra inventario", ft.Icons.COMPARE_ARROWS, ft.Colors.TEAL_400, interfaz.mostrar_comparativa_stock_fisico_admin),
        ])
    elif rol == "master":
        accesos_rapidos.extend([
            ("Registro de Auditoría", "Trazabilidad forense e historial de eventos", ft.Icons.SECURITY, ROJO, interfaz.mostrar_registro_auditoria),
            ("Copia de Seguridad", "Gestión de respaldos y espejo en red", ft.Icons.BACKUP, ft.Colors.PURPLE_400, interfaz.mostrar_dialogo_backup),
            ("Gestionar Usuarios", "Control de cuentas y credenciales IAM", ft.Icons.MANAGE_ACCOUNTS, ft.Colors.BLUE_400, interfaz.mostrar_gestion_usuarios),
            ("Configuración SMTP", "Servidor de correo para reportes", ft.Icons.SETTINGS_APPLICATIONS, ft.Colors.TEAL_400, interfaz.mostrar_configuracion_smtp),
            ("Alertas Telegram", "Configuración de bot de avisos proactivos", ft.Icons.SEND, ft.Colors.CYAN_400, interfaz.mostrar_configuracion_telegram),
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
                        stk_color = ft.Colors.GREEN_400 if prod.stock_actual > 5 else (ft.Colors.AMBER_400 if prod.stock_actual > 0 else ft.Colors.RED_400)
                        loc_txt = f" · Ubic: {prod.ubicacion}" if getattr(prod, "ubicacion", "") else ""
                        resultados_lista.controls.append(
                            ft.Container(
                                bgcolor=interfaz.superficie,
                                border=ft.Border.all(1, interfaz.borde),
                                border_radius=8,
                                padding=ft.Padding.symmetric(horizontal=10, vertical=7),
                                ink=True,
                                tooltip=f"Clic para copiar código [{prod.codigo}]",
                                on_click=lambda _e, cod=prod.codigo: (
                                    interfaz.page.set_clipboard(cod),
                                    interfaz.notificar(f"Código copiado al portapapeles: {cod}")
                                ),
                                content=ft.Row(
                                    [
                                        ft.Icon(ft.Icons.INVENTORY_2, size=18, color=ft.Colors.BLUE_400),
                                        ft.Column(
                                            [
                                                ft.Text(f"[{prod.codigo}] {prod.descripcion}", weight=ft.FontWeight.BOLD, size=12, color=interfaz.texto),
                                                ft.Text(f"Stock: {prod.stock_actual} {prod.unidad}{loc_txt}", size=10, color=stk_color),
                                            ],
                                            spacing=2,
                                            expand=True,
                                        ),
                                        ft.Container(
                                            content=ft.Text(f"{prod.stock_actual} un.", size=10, weight=ft.FontWeight.BOLD, color=stk_color),
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
                ft.Text("Buscador Rápido Global", weight=ft.FontWeight.BOLD, size=15),
                ft.Container(
                    content=ft.Text("Ctrl + K", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
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
