"""Diálogo modal interactivo para documentos: Opciones de Windows para descargar o imprimir."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import flet as ft

from ..theme import ROJO
from ..components.print_labels import imprimir_directo_spooler, listar_impresoras_sistema

logger = logging.getLogger("stockagent.ui.dialogs")


def _formatear_tamano(bytes_cant: int) -> str:
    if bytes_cant < 1024:
        return f"{bytes_cant} B"
    elif bytes_cant < 1024 * 1024:
        return f"{bytes_cant / 1024:.1f} KB"
    return f"{bytes_cant / (1024 * 1024):.1f} MB"


def mostrar_dialogo_opciones_documento(interfaz: Any, ruta_archivo: str | Path) -> None:
    """Muestra el diálogo de opciones de Windows (Descargar o Imprimir) para cualquier documento."""
    ruta = Path(ruta_archivo)
    if not ruta.exists() or not ruta.is_file():
        interfaz.notificar(f"El documento '{ruta.name}' no se encuentra disponible en disco.")
        return

    st = ruta.stat()
    tamano_str = _formatear_tamano(st.st_size)
    fecha_str = datetime.fromtimestamp(st.st_mtime).strftime("%d/%m/%Y %H:%M")
    sufijo = ruta.suffix.lower()

    # Icono y tipo según extensión
    if sufijo in (".xlsx", ".xls"):
        icono_tipo = ft.Icons.TABLE_CHART
        color_tipo = ft.Colors.GREEN_600
        tipo_badge = "Planilla Excel"
    elif sufijo == ".pdf":
        icono_tipo = ft.Icons.PICTURE_AS_PDF
        color_tipo = ROJO
        tipo_badge = "Documento PDF"
    elif sufijo in (".docx", ".doc"):
        icono_tipo = ft.Icons.ARTICLE
        color_tipo = ft.Colors.BLUE_600
        tipo_badge = "Documento Word"
    else:
        icono_tipo = ft.Icons.DESCRIPTION
        color_tipo = ft.Colors.BLUE_400
        tipo_badge = sufijo.replace(".", "").upper()

    es_movil = bool(getattr(interfaz, "es_pantalla_movil", False))
    es_oscuro = bool(getattr(interfaz, "modo_oscuro", True))
    es_web = bool(getattr(interfaz.page, "web", False))

    # Detección de impresoras de Windows instaladas
    impresoras_disponibles = listar_impresoras_sistema() if sys.platform == "win32" else []

    dropdown_impresoras: ft.Dropdown | None = None
    if impresoras_disponibles:
        opciones_imp = [ft.DropdownOption(key="", text="-- Impresora predeterminada de Windows --")]
        opciones_imp.extend(ft.DropdownOption(key=imp, text=imp) for imp in impresoras_disponibles)
        dropdown_impresoras = ft.Dropdown(
            label="Seleccionar impresora de Windows",
            options=opciones_imp,
            value="",
            dense=True,
            expand=True,
            border_radius=8,
        )

    # Handlers de acción
    def _accion_imprimir_windows(_e: Any) -> None:
        impresora_sel = dropdown_impresoras.value if dropdown_impresoras else ""
        try:
            if impresora_sel:
                exito = imprimir_directo_spooler(ruta, impresora_sel)
                if exito:
                    interfaz.notificar(f"✅ Enviado a imprimir a '{impresora_sel}'.")
                    interfaz.page.pop_dialog()
                    return
            # Fallback a verbo print de Windows
            if sys.platform == "win32":
                os.startfile(str(ruta.resolve()), "print")  # type: ignore[attr-defined]
                interfaz.notificar("✅ Diálogo de impresión de Windows iniciado.")
                interfaz.page.pop_dialog()
                return
        except Exception as exc:
            logger.warning("Fallo al imprimir directamente en Windows: %s", exc)

        # Fallback a vista previa en navegador si no se pudo imprimir directo
        _accion_vista_previa_impresion(_e)

    def _accion_vista_previa_impresion(_e: Any) -> None:
        interfaz.page.pop_dialog()
        if es_web:
            import time
            ts = int(time.time())
            url_visor = f"/descargas/informes/{ruta.name}?v={ts}&print=1"
            try:
                if hasattr(interfaz.page, "launch_url"):
                    interfaz.page.launch_url(url_visor, web_window_name="_blank")
                return
            except Exception as exc:
                logger.warning("Fallo al abrir vista de impresión web: %s", exc)
        try:
            if sys.platform == "win32":
                os.startfile(str(ruta.resolve()))  # type: ignore[attr-defined]
            else:
                import webbrowser
                webbrowser.open(ruta.resolve().as_uri())
        except Exception as exc:
            interfaz.notificar(f"No se pudo abrir el documento para imprimir: {exc}")

    def _accion_descargar(_e: Any) -> None:
        interfaz.page.pop_dialog()
        if hasattr(interfaz, "abrir_informe"):
            interfaz.abrir_informe(ruta_especifica=ruta, directo=True)
        else:
            interfaz.notificar(f"Descargando {ruta.name}...")

    def _accion_abrir_windows(_e: Any) -> None:
        interfaz.page.pop_dialog()
        try:
            if sys.platform == "win32":
                os.startfile(str(ruta.resolve()))  # type: ignore[attr-defined]
                interfaz.notificar(f"Abierto en Windows: {ruta.name}")
            else:
                import webbrowser
                webbrowser.open(ruta.resolve().as_uri())
        except Exception as exc:
            interfaz.notificar(f"No se pudo abrir en Windows: {exc}")

    def _accion_abrir_carpeta(_e: Any) -> None:
        interfaz.page.pop_dialog()
        try:
            if hasattr(interfaz, "abrir_carpeta_informe"):
                interfaz.abrir_carpeta_informe(ruta)
            elif sys.platform == "win32":
                subprocess.Popen(["explorer.exe", f"/select,{str(ruta.resolve())}"])
        except Exception as exc:
            interfaz.notificar(f"No se pudo abrir el explorador de Windows: {exc}")

    # Construcción de la UI del diálogo
    filas_contenido = [
        # Encabezado del documento
        ft.Container(
            bgcolor=ft.Colors.with_opacity(0.06 if es_oscuro else 0.03, color_tipo),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.18, color_tipo)),
            border_radius=10,
            padding=ft.Padding.symmetric(horizontal=14, vertical=12),
            content=ft.Row(
                [
                    ft.Container(
                        width=44,
                        height=44,
                        border_radius=10,
                        bgcolor=ft.Colors.with_opacity(0.16, color_tipo),
                        alignment=ft.Alignment.CENTER,
                        content=ft.Icon(icono_tipo, color=color_tipo, size=24),
                    ),
                    ft.Column(
                        [
                            ft.Text(
                                ruta.name,
                                size=14,
                                weight=ft.FontWeight.BOLD,
                                color=interfaz.texto,
                                overflow=ft.TextOverflow.ELLIPSIS,
                                max_lines=2,
                            ),
                            ft.Row(
                                [
                                    ft.Container(
                                        content=ft.Text(tipo_badge, size=11, color=color_tipo, weight=ft.FontWeight.W_500),
                                        padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                                        border_radius=4,
                                        bgcolor=ft.Colors.with_opacity(0.12, color_tipo),
                                    ),
                                    ft.Text(f"• {tamano_str}", size=11, color=interfaz.secundario),
                                    ft.Text(f"• {fecha_str}", size=11, color=interfaz.secundario),
                                ],
                                spacing=6,
                            ),
                        ],
                        spacing=2,
                        expand=True,
                    ),
                ],
                spacing=12,
            ),
        ),
        ft.Divider(height=16, color=ft.Colors.TRANSPARENT),
        ft.Text(
            "Selecciona la opción de Windows que deseas realizar:",
            size=12,
            weight=ft.FontWeight.W_500,
            color=interfaz.secundario,
        ),
    ]

    # Sección de Impresión
    if dropdown_impresoras is not None:
        filas_contenido.append(dropdown_impresoras)

    # Botones principales de acción
    botones_acciones = [
        # Botón 1: Imprimir en Windows
        ft.Button(
            "Imprimir en Windows",
            icon=ft.Icons.PRINT,
            style=ft.ButtonStyle(
                bgcolor=ROJO,
                color=ft.Colors.WHITE,
                shape=ft.RoundedRectangleBorder(radius=8),
                padding=ft.Padding.symmetric(horizontal=16, vertical=12),
            ),
            on_click=_accion_imprimir_windows,
        ),
        # Botón 2: Vista previa e impresión
        ft.Button(
            "Vista previa de impresión (Ctrl+P)",
            icon=ft.Icons.PREVIEW,
            style=ft.ButtonStyle(
                color=interfaz.texto,
                shape=ft.RoundedRectangleBorder(radius=8),
                padding=ft.Padding.symmetric(horizontal=14, vertical=12),
            ),
            on_click=_accion_vista_previa_impresion,
        ),
        # Botón 3: Descargar / Guardar
        ft.Button(
            "Descargar / Guardar archivo",
            icon=ft.Icons.DOWNLOAD,
            style=ft.ButtonStyle(
                bgcolor=ft.Colors.BLUE_GREY_700,
                color=ft.Colors.WHITE,
                shape=ft.RoundedRectangleBorder(radius=8),
                padding=ft.Padding.symmetric(horizontal=16, vertical=12),
            ),
            on_click=_accion_descargar,
        ),
    ]

    # Botón 4: Abrir con programa asociado en Windows si no es exclusivamente web remoto
    if sys.platform == "win32":
        botones_acciones.append(
            ft.Button(
                "Abrir con programa de Windows (Excel / Acrobat)",
                icon=ft.Icons.OPEN_IN_NEW,
                style=ft.ButtonStyle(
                    color=interfaz.texto,
                    shape=ft.RoundedRectangleBorder(radius=8),
                    padding=ft.Padding.symmetric(horizontal=14, vertical=12),
                ),
                on_click=_accion_abrir_windows,
            )
        )

    for btn in botones_acciones:
        filas_contenido.append(btn)

    dialogo = ft.AlertDialog(
        modal=True,
        title=ft.Row(
            [
                ft.Icon(ft.Icons.PRINT_ROUNDED, color=ROJO, size=24),
                ft.Text("Opciones de Documento: Descargar o Imprimir", size=16, weight=ft.FontWeight.BOLD),
            ],
            spacing=10,
        ),
        content=ft.Container(
            width=540 if not es_movil else 340,
            content=ft.Column(filas_contenido, tight=True, spacing=10),
        ),
        actions=[
            ft.IconButton(
                icon=ft.Icons.FOLDER_OPEN,
                tooltip="Mostrar archivo en el Explorador de Windows",
                on_click=_accion_abrir_carpeta,
            ),
            ft.Button(
                "Cancelar",
                on_click=lambda _e: interfaz.page.pop_dialog(),
            ),
        ],
        actions_alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
    )

    interfaz.page.show_dialog(dialogo)
