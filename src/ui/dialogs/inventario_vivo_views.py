"""Componentes visuales y modales auxiliares para el inventario en vivo."""

from __future__ import annotations

import asyncio
import inspect
import webbrowser
from pathlib import Path
from typing import Any, Callable

import flet as ft

from ..design import grilla_tarjetas_responsiva, par_accion_tarjeta
from ..theme import ROJO


def abrir_url_en_navegador(page: Any, url: str) -> None:
    """Abre una URL de forma compatible tanto en Flet moderno (UrlLauncher) como clásico y fallback."""
    if hasattr(page, "launch_url") and callable(page.launch_url):
        try:
            page.launch_url(url, web_window_name="_blank")
            return
        except Exception:
            pass

    try:
        launcher = None
        if hasattr(page, "services") and isinstance(page.services, list):
            for s in page.services:
                if isinstance(s, ft.UrlLauncher):
                    launcher = s
                    break
            if not launcher:
                launcher = ft.UrlLauncher()
                page.services.append(launcher)
                try:
                    page.update()
                except Exception:
                    pass

        if launcher:
            if hasattr(page, "run_task") and callable(page.run_task):
                page.run_task(launcher.launch_url, url, web_only_window_name="_blank")
            else:
                coro = launcher.launch_url(url, web_only_window_name="_blank")
                if inspect.iscoroutine(coro):
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            asyncio.create_task(coro)
                        else:
                            loop.run_until_complete(coro)
                    except Exception:
                        coro.close()
            return
    except Exception:
        pass

    try:
        webbrowser.open(url)
    except Exception:
        pass


def construir_estado_vacio_inventario(interfaz: Any) -> ft.Container:
    """Construye la vista vacía inicial cuando aún no hay productos escaneados."""
    return ft.Container(
        padding=24,
        alignment=ft.Alignment.CENTER,
        content=ft.Column(
            [
                ft.Icon(ft.Icons.DOCUMENT_SCANNER, size=40, color=interfaz.secundario),
                ft.Text(
                    "No hay productos contados todavía en esta sesión.\n"
                    "Usa la pistola lectora, la cámara móvil o ingresa el código arriba.",
                    text_align=ft.TextAlign.CENTER,
                    color=interfaz.secundario,
                    size=12,
                ),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=8,
        ),
    )


def construir_tarjeta_producto_contado(
    interfaz: Any,
    cod: str,
    cant: int,
    info: dict[str, Any],
    on_ajustar: Callable[[str, int], None],
    on_eliminar: Callable[[str], None],
) -> ft.Container:
    """Construye la tarjeta de un producto contado en la sesión de inventario."""
    stk_dig = info["stock"]
    dif = cant - stk_dig
    if dif == 0:
        dif_txt, dif_color = "COINCIDE", ft.Colors.GREEN_400
    elif dif < 0:
        dif_txt, dif_color = f"{dif} FALTANTE", ft.Colors.RED_400
    else:
        dif_txt, dif_color = f"+{dif} SOBRANTE", ft.Colors.AMBER_400

    barras_tag = info["cod_barras"]

    return ft.Container(
        padding=ft.Padding.all(8),
        border=ft.Border.all(1, interfaz.borde),
        border_radius=8,
        bgcolor=interfaz.superficie,
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Row(
                            [
                                ft.Text(cod, weight=ft.FontWeight.BOLD, size=13, color=interfaz.texto),
                                ft.Container(
                                    content=ft.Text(
                                        f"🏷️ {barras_tag}" if barras_tag else "Sin código barras",
                                        size=10,
                                        color=ft.Colors.WHITE if barras_tag else interfaz.secundario,
                                    ),
                                    bgcolor=ft.Colors.BLUE_GREY_700 if barras_tag else ft.Colors.TRANSPARENT,
                                    padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                                    border_radius=4,
                                ),
                            ],
                            spacing=6,
                            wrap=True,
                        ),
                        ft.Container(
                            content=ft.Text(dif_txt, size=10, weight=ft.FontWeight.BOLD, color=dif_color),
                            padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                            border=ft.Border.all(1, dif_color),
                            border_radius=4,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Text(
                    info["name"],
                    size=12,
                    weight=ft.FontWeight.W_500,
                    color=interfaz.texto,
                    max_lines=2,
                    overflow=ft.TextOverflow.ELLIPSIS,
                ),
                par_accion_tarjeta(
                    interfaz,
                    ft.Column(
                        [
                            ft.Text(f"Stock Digital: {stk_dig} un.", size=11, color=interfaz.secundario),
                            ft.Text(f"Relevado: {cant} un.", size=11, weight=ft.FontWeight.BOLD, color=interfaz.texto),
                        ],
                        spacing=1,
                    ),
                    ft.Row(
                        [
                            ft.IconButton(
                                icon=ft.Icons.REMOVE_CIRCLE_OUTLINE,
                                icon_size=20,
                                tooltip="Restar 1",
                                on_click=lambda _e, c=cod: on_ajustar(c, -1),
                            ),
                            ft.Text(str(cant), weight=ft.FontWeight.BOLD, size=14, color=interfaz.texto),
                            ft.IconButton(
                                icon=ft.Icons.ADD_CIRCLE_OUTLINE,
                                icon_size=20,
                                tooltip="Sumar 1",
                                on_click=lambda _e, c=cod: on_ajustar(c, 1),
                            ),
                            ft.IconButton(
                                icon=ft.Icons.DELETE_OUTLINE,
                                icon_size=20,
                                icon_color=ft.Colors.RED_400,
                                tooltip="Quitar del conteo",
                                on_click=lambda _e, c=cod: on_eliminar(c),
                            ),
                        ],
                        spacing=1,
                        tight=True,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    umbral=460.0,
                    spacing=8,
                ),
            ],
            spacing=5,
        ),
    )


def mostrar_dialogo_asociar_codigo_barras(
    interfaz: Any,
    sm: Any,
    cache_productos: dict[str, dict[str, Any]],
    conteo_fisico: dict[str, int],
    page_w: float,
    codigo_leido: str,
    cant_a_sumar: int,
    on_asociado: Callable[[str], None],
) -> None:
    """Permite asociar un código de barras nuevo a un producto del catálogo."""
    filtro_asoc = ft.TextField(
        label="Buscar producto para asociar este código de barras",
        hint_text="Escribe el nombre o SKU...",
        autofocus=True,
        dense=True,
    )
    lista_opciones = ft.ListView(expand=True, spacing=4, height=180)

    def confirmar_asociacion(cod_prod: str) -> None:
        sm.asignar_codigo_barras(cod_prod, codigo_leido)
        if cod_prod in cache_productos:
            cache_productos[cod_prod]["cod_barras"] = codigo_leido
        conteo_fisico[cod_prod] = conteo_fisico.get(cod_prod, 0) + cant_a_sumar
        interfaz.page.pop_dialog()
        on_asociado(cod_prod)

    def render_opciones() -> None:
        lista_opciones.controls.clear()
        filtro = (filtro_asoc.value or "").strip().casefold()
        coincidencias = [
            p for p in cache_productos.values()
            if not filtro or filtro in f"{p['code']} {p['name']}".casefold()
        ]
        for p in coincidencias[:20]:
            cod_prod = p["code"]
            nom_prod = p["name"]
            lista_opciones.controls.append(
                ft.ListTile(
                    title=ft.Text(f"{cod_prod} - {nom_prod}", size=12, weight=ft.FontWeight.BOLD),
                    subtitle=ft.Text(f"Stock actual: {p['stock']} un.", size=11, color=interfaz.secundario),
                    trailing=ft.Button("Asociar", on_click=lambda _e, c=cod_prod: confirmar_asociacion(c)),
                    dense=True,
                )
            )
        interfaz.page.update()

    filtro_asoc.on_change = lambda _e: render_opciones()
    render_opciones()

    dlg_asoc = ft.AlertDialog(
        modal=True,
        title=ft.Row(
            [
                ft.Icon(ft.Icons.LINK, color=ft.Colors.BLUE_400),
                ft.Text(f"Código no registrado: {codigo_leido}", size=14, weight=ft.FontWeight.BOLD),
            ],
            spacing=8,
        ),
        content=ft.Container(
            width=min(480, max(300, int(page_w - 24))),
            content=ft.Column(
                [
                    ft.Text(
                        "Este código no está registrado en el catálogo. Puedes vincularlo "
                        "ahora mismo a un producto existente:",
                        size=12,
                        color=interfaz.secundario,
                    ),
                    filtro_asoc,
                    lista_opciones,
                ],
                tight=True,
                spacing=8,
            ),
        ),
        actions=[interfaz.boton_dialogo("Cancelar", lambda _e: interfaz.page.pop_dialog())],
    )
    interfaz.page.show_dialog(dlg_asoc)


def _tarjeta_balance(interfaz: Any, etiqueta: str, valor: int, bg_dark: str, bg_light: str, color_fg: str) -> ft.Container:
    """Construye una tarjeta resumen de coincidencias, faltantes o sobrantes."""
    return ft.Container(
        bgcolor=bg_dark if interfaz.modo_oscuro else bg_light,
        padding=10,
        border_radius=8,
        expand=True,
        content=ft.Column(
            [
                ft.Text(etiqueta, size=10, color=color_fg, weight=ft.FontWeight.BOLD),
                ft.Text(str(valor), size=20, weight=ft.FontWeight.BOLD, color=color_fg),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=2,
        ),
    )


def mostrar_resumen_inventario_finalizado(
    interfaz: Any,
    usuario_operario: str,
    page_w: float,
    ruta_doc: Path,
    comparativa: list,
) -> None:
    """Muestra el diálogo final con el balance de inventario y accesos de exportación."""
    coinciden = sum(1 for i in comparativa if i["diferencia"] == 0 and i["en_catalogo"])
    faltantes = sum(1 for i in comparativa if i["diferencia"] < 0 and i["en_catalogo"])
    sobrantes = sum(1 for i in comparativa if i["diferencia"] > 0 and i["en_catalogo"])

    contenido_resumen = ft.Column(
        [
            ft.Row(
                [
                    ft.Icon(ft.Icons.CHECK_CIRCLE, color=ft.Colors.GREEN_400, size=32),
                    ft.Column(
                        [
                            ft.Text("¡Relevamiento finalizado con éxito!", weight=ft.FontWeight.BOLD, size=15, color=interfaz.texto),
                            ft.Text(f"Operario: {usuario_operario} · Archivo: {ruta_doc.name}", size=12, color=interfaz.secundario),
                        ],
                        spacing=2,
                    ),
                ],
                spacing=12,
            ),
            ft.Divider(height=14),
            grilla_tarjetas_responsiva(
                [
                    _tarjeta_balance(interfaz, "COINCIDEN", coinciden, ft.Colors.GREEN_900, ft.Colors.GREEN_50, ft.Colors.GREEN_400),
                    _tarjeta_balance(interfaz, "FALTANTES", faltantes, ft.Colors.RED_900, ft.Colors.RED_50, ft.Colors.RED_400),
                    _tarjeta_balance(interfaz, "SOBRANTES", sobrantes, ft.Colors.AMBER_900, ft.Colors.AMBER_50, ft.Colors.AMBER_400),
                ],
                interfaz=interfaz,
                compacto=True,
                spacing=8,
                run_spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.START,
            ),
            ft.Divider(height=14),
            ft.Container(
                bgcolor=interfaz.superficie,
                border=ft.Border.all(1, interfaz.borde),
                border_radius=8,
                padding=10,
                content=ft.Column(
                    [
                        ft.Text("Planilla Excel comparativa generada:", size=11, color=interfaz.secundario, weight=ft.FontWeight.BOLD),
                        ft.Text(str(ruta_doc.name), size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_400),
                        ft.Text("El administrador ha sido notificado automáticamente.", size=11, color=interfaz.secundario),
                    ],
                    spacing=3,
                ),
            ),
        ],
        tight=True,
        width=min(520, max(300, int(page_w - 24))),
        spacing=8,
    )

    dlg_res = ft.AlertDialog(
        modal=True,
        title=ft.Row(
            [
                ft.Icon(ft.Icons.FACT_CHECK, color=ROJO),
                ft.Text("Balance de Relevamiento de Inventario", weight=ft.FontWeight.BOLD),
            ],
            spacing=8,
        ),
        content=contenido_resumen,
        actions=[
            interfaz.boton_dialogo("Cerrar", lambda _e: interfaz.page.pop_dialog()),
            interfaz.boton_dialogo("Abrir Excel", lambda _e: (interfaz.page.pop_dialog(), interfaz.abrir_informe(ruta_especifica=ruta_doc))),
            interfaz.boton_dialogo("Compartir Correo", lambda _e: (interfaz.page.pop_dialog(), interfaz.compartir_correo(ruta_especifica=ruta_doc))),
            interfaz.boton_dialogo("WhatsApp", lambda _e: (interfaz.page.pop_dialog(), interfaz.compartir_whatsapp(ruta_especifica=ruta_doc))),
        ],
    )
    interfaz.page.show_dialog(dlg_res)
