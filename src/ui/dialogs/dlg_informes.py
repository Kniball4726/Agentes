"""Diálogo interactivo para listar, consultar y abrir informes generados."""

from datetime import datetime
from pathlib import Path
from typing import Any
import flet as ft
from ..theme import ROJO


def mostrar_dialogo_informes(interfaz: Any) -> None:
    """Muestra el explorador interactivo de informes y reportes generados."""
    if not interfaz.usuario_actual:
        interfaz.notificar("Debes iniciar sesión para acceder a los informes.")
        return

    # Actualizar lista de informes disponibles
    archivos: list[Path] = []
    if getattr(interfaz, "menu", None) and hasattr(interfaz.menu, "_obtener_generados"):
        try:
            archivos = interfaz.menu._obtener_generados()
        except Exception:
            archivos = []

    if not archivos and getattr(interfaz, "informes", None):
        archivos = [Path(p) for p in interfaz.informes if Path(p).exists()]

    if not archivos:
        interfaz.notificar("Todavía no hay informes generados.")
        return

    # Invertir para que los más recientes aparezcan primero
    archivos_recientes = list(reversed(archivos))
    interfaz.informes = archivos

    es_movil = bool(getattr(interfaz, "es_pantalla_movil", False))
    es_oscuro = bool(getattr(interfaz, "modo_oscuro", True))
    es_web = bool(getattr(interfaz.page, "web", False))

    filtro_input = ft.TextField(
        hint_text="Filtrar informes por nombre o fecha...",
        prefix_icon=ft.Icons.SEARCH,
        expand=True,
        dense=True,
        border_radius=8,
    )

    columna_archivos = ft.Column(spacing=6, scroll=ft.ScrollMode.AUTO, expand=True)

    def _formatear_tamano(bytes_cant: int) -> str:
        if bytes_cant < 1024:
            return f"{bytes_cant} B"
        elif bytes_cant < 1024 * 1024:
            return f"{bytes_cant / 1024:.1f} KB"
        return f"{bytes_cant / (1024 * 1024):.1f} MB"

    def actualizar_lista() -> None:
        termino = (filtro_input.value or "").strip().lower()
        filtrados = []
        for a in archivos_recientes:
            if not a.exists():
                continue
            if termino:
                st = a.stat()
                fecha_str = datetime.fromtimestamp(st.st_mtime).strftime("%d/%m/%Y %H:%M")
                if termino not in a.name.lower() and termino not in fecha_str:
                    continue
            filtrados.append(a)

        tarjetas = []
        for r in filtrados:
            st = r.stat()
            fecha_str = datetime.fromtimestamp(st.st_mtime).strftime("%d/%m/%Y %H:%M")
            tamano_str = _formatear_tamano(st.st_size)
            sufijo = r.suffix.lower()

            if sufijo in (".xlsx", ".xls"):
                icono = ft.Icons.TABLE_CHART
                color_icono = ft.Colors.GREEN_600
                tipo_badge = "EXCEL"
            elif sufijo == ".pdf":
                icono = ft.Icons.PICTURE_AS_PDF
                color_icono = ROJO
                tipo_badge = "PDF"
            else:
                icono = ft.Icons.DESCRIPTION
                color_icono = ft.Colors.BLUE_400
                tipo_badge = sufijo.replace(".", "").upper()

            botones_item = [
                ft.Button(
                    "Abrir" if not es_web else "Descargar",
                    icon=ft.Icons.OPEN_IN_NEW if not es_web else ft.Icons.DOWNLOAD,
                    style=ft.ButtonStyle(
                        bgcolor=ft.Colors.with_opacity(0.12, color_icono),
                        color=color_icono,
                    ),
                    on_click=lambda _e, ruta_sel=r: (
                        interfaz.page.pop_dialog(),
                        interfaz.abrir_informe(ruta_especifica=ruta_sel),
                    ),
                )
            ]

            if not es_web:
                botones_item.append(
                    ft.IconButton(
                        icon=ft.Icons.FOLDER_OPEN,
                        tooltip="Abrir carpeta contenedora",
                        icon_color=interfaz.secundario,
                        on_click=lambda _e, ruta_sel=r: interfaz.abrir_carpeta_informe(ruta_sel),
                    )
                )

            card = ft.Container(
                bgcolor=ft.Colors.with_opacity(0.04 if es_oscuro else 0.02, interfaz.texto),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.12, interfaz.borde)),
                border_radius=10,
                padding=ft.Padding.symmetric(horizontal=12, vertical=10),
                content=ft.Row(
                    [
                        ft.Container(
                            width=38,
                            height=38,
                            border_radius=8,
                            bgcolor=ft.Colors.with_opacity(0.15, color_icono),
                            alignment=ft.Alignment.CENTER,
                            content=ft.Icon(icono, color=color_icono, size=20),
                        ),
                        ft.Column(
                            [
                                ft.Text(
                                    r.name,
                                    size=13,
                                    weight=ft.FontWeight.BOLD,
                                    color=interfaz.texto,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                    max_lines=1,
                                ),
                                ft.Row(
                                    [
                                        ft.Container(
                                            content=ft.Text(tipo_badge, size=9, weight=ft.FontWeight.BOLD, color=color_icono),
                                            bgcolor=ft.Colors.with_opacity(0.1, color_icono),
                                            padding=ft.Padding.symmetric(horizontal=5, vertical=1),
                                            border_radius=4,
                                        ),
                                        ft.Text(f"{fecha_str} · {tamano_str}", size=11, color=interfaz.secundario),
                                    ],
                                    spacing=6,
                                ),
                            ],
                            spacing=3,
                            expand=True,
                        ),
                        ft.Row(botones_item, spacing=4, tight=True),
                    ],
                    spacing=12,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            )
            tarjetas.append(card)

        if not tarjetas:
            tarjetas.append(
                ft.Container(
                    content=ft.Text("No se encontraron informes coincidentes.", color=interfaz.secundario),
                    padding=20,
                    alignment=ft.Alignment.CENTER,
                )
            )

        columna_archivos.controls = tarjetas
        if hasattr(interfaz, "page") and interfaz.page:
            try:
                interfaz.page.update()
            except Exception:
                pass

    filtro_input.on_change = lambda _e: actualizar_lista()
    actualizar_lista()

    ultimo_informe = archivos_recientes[0] if archivos_recientes else None

    header_row = ft.Row(
        [
            ft.Icon(ft.Icons.ASSESSMENT, color=ROJO, size=24),
            ft.Column(
                [
                    ft.Text("Informes y Reportes Generados", size=17, weight=ft.FontWeight.BOLD, color=interfaz.texto),
                    ft.Text(f"{len(archivos_recientes)} documentos disponibles en el sistema", size=11, color=interfaz.secundario),
                ],
                spacing=1,
                expand=True,
            ),
        ],
        spacing=10,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    btn_abrir_ultimo = ft.Button(
        "⚡ Abrir Más Reciente",
        icon=ft.Icons.FLASH_ON,
        style=ft.ButtonStyle(
            bgcolor=ft.Colors.with_opacity(0.18, ROJO),
            color=ROJO,
        ),
        on_click=lambda _e: (
            interfaz.page.pop_dialog(),
            interfaz.abrir_informe(ruta_especifica=ultimo_informe),
        ),
    ) if ultimo_informe else ft.Container()

    ancho_modal = interfaz.ancho_adaptable(720)
    alto_modal = interfaz.alto_adaptable(520)

    dialogo = ft.AlertDialog(
        modal=True,
        title=header_row,
        content=ft.Container(
            width=ancho_modal,
            height=alto_modal,
            content=ft.Column(
                [
                    ft.Row([filtro_input, btn_abrir_ultimo], spacing=8),
                    columna_archivos,
                ],
                spacing=10,
                expand=True,
            ),
        ),
        actions=[
            ft.TextButton("Cerrar", on_click=lambda _e: interfaz.page.pop_dialog()),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )

    interfaz.page.show_dialog(dialogo)
