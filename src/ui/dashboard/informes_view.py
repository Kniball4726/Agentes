"""Vista y renderizado de informes generados y comprobantes en el Dashboard."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
import flet as ft
from ..theme import ROJO


def renderizar_informes_generados(interfaz: Any, informes: list[Path], mtimes_informes: dict[Path, float]) -> None:
    """Renderiza el listado de comprobantes, hojas de ruta y balances emitidos."""
    interfaz.lista_informes.controls.clear()
    if not informes:
        interfaz.lista_informes.controls.append(
            ft.Text("Todavía no hay informes.", size=12, color=interfaz.secundario)
        )
        return

    for ruta in informes[:30]:
        es_fabrica = ruta.name.startswith("Pedido_Fabrica")
        es_comparativa = ruta.name.startswith("Comparativa_Stock_Fisico")
        if es_comparativa:
            icono = ft.Icons.COMPARE_ARROWS
            color_icono = ft.Colors.BLUE_400
            tipo_txt = "Comparativa stock físico"
        elif es_fabrica:
            icono = ft.Icons.INVENTORY_2
            color_icono = ft.Colors.AMBER_400
            tipo_txt = "Pedido a fábrica"
        else:
            icono = ft.Icons.DESCRIPTION
            color_icono = ROJO
            tipo_txt = "Informe de descuentos"
        try:
            ts = mtimes_informes.get(ruta)
            if ts is None:
                ts = ruta.stat().st_mtime
            mtime = datetime.fromtimestamp(ts)
            fecha_fmt = mtime.strftime("%d/%m/%Y %H:%M")
        except Exception:
            fecha_fmt = ""

        subtitulo_txt = f"{tipo_txt} · {fecha_fmt}" if fecha_fmt else tipo_txt

        subtitulo = ft.Text(
            subtitulo_txt,
            size=10,
            no_wrap=True,
            max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS,
            color=ft.Colors.BLUE_300
            if (es_comparativa and interfaz.modo_oscuro)
            else (
                ft.Colors.BLUE_700
                if es_comparativa
                else (
                    ft.Colors.AMBER_300
                    if (es_fabrica and interfaz.modo_oscuro)
                    else (ft.Colors.AMBER_700 if es_fabrica else interfaz.secundario)
                )
            ),
        )
        interfaz.lista_informes.controls.append(
            ft.ListTile(
                leading=ft.Icon(icono, color=color_icono, size=19),
                title=ft.Text(
                    ruta.name,
                    size=12,
                    color=interfaz.texto,
                    weight=ft.FontWeight.W_500,
                    no_wrap=True,
                    max_lines=1,
                    overflow=ft.TextOverflow.ELLIPSIS,
                    tooltip=ruta.name,
                ),
                subtitle=subtitulo,
                dense=True,
                content_padding=ft.Padding.symmetric(horizontal=8, vertical=0),
                on_click=lambda _e, archivo=ruta: interfaz.seleccionar_informe(archivo),
                trailing=ft.Row(
                    [
                        *(
                            [
                                ft.IconButton(
                                    icon=ft.Icons.PRINT,
                                    tooltip="Imprimir comprobante de descuento",
                                    icon_color=ROJO,
                                    icon_size=18,
                                    on_click=lambda _e, r=ruta: interfaz.mostrar_imprimir_descuentos(),
                                )
                            ]
                            if (not es_comparativa and not es_fabrica)
                            else []
                        ),
                        ft.IconButton(
                            icon=ft.Icons.VISIBILITY_OUTLINED,
                            tooltip="Ver informe",
                            icon_color=ft.Colors.BLUE_400,
                            icon_size=18,
                            on_click=lambda _e, r=ruta: interfaz.abrir_informe(ruta_especifica=r),
                        ),
                        ft.IconButton(
                            icon=ft.Icons.FOLDER_OPEN,
                            tooltip="Abrir carpeta contenedora",
                            icon_color=interfaz.secundario,
                            icon_size=18,
                            on_click=lambda _e, r=ruta: interfaz.abrir_carpeta_informe(ruta_especifica=r),
                        ),
                    ],
                    spacing=0,
                    tight=True,
                    alignment=ft.MainAxisAlignment.END,
                ),
            )
        )
