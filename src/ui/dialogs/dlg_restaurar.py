"""Diálogo de restauración de documentos de prueba y contingencia (Exclusivo Rol Master)."""

from datetime import datetime
from typing import Any
import flet as ft


def confirmar_restaurar(interfaz: Any, _evento: ft.Event | None = None) -> None:
    """Muestra el diálogo modal para seleccionar la fecha de documentos a restaurar."""
    if not interfaz.exigir_roles("master"):
        return
    fechas = interfaz.menu.fechas_descuento_disponibles()
    if not fechas:
        interfaz.notificar(
            "No hay documentos archivados asociados a informes de descuento."
        )
        return
    seleccion_fecha = ft.Dropdown(
        label="Fecha de descuento",
        value=fechas[0],
        options=[
            ft.DropdownOption(
                key=fecha,
                text=datetime.strptime(fecha, "%Y-%m-%d").strftime("%d/%m/%Y"),
            )
            for fecha in fechas
        ],
        width=250,
    )
    interfaz.seleccion_fecha_restauracion = seleccion_fecha
    dialogo = ft.AlertDialog(
        modal=True,
        title=ft.Text("Restaurar documentos"),
        content=ft.Column(
            [
                ft.Text(
                    "Selecciona la fecha de descuento de los documentos "
                    "que quieres restaurar. Si ya existe un archivo con el "
                    "mismo nombre en pendientes, será reemplazado."
                ),
                seleccion_fecha,
            ],
            tight=True,
            spacing=12,
        ),
        actions=[
            interfaz.boton_dialogo("Cancelar", lambda _e: interfaz.page.pop_dialog()),
            interfaz.boton_dialogo("Restaurar", lambda e: restaurar_documentos(interfaz, e)),
        ],
    )
    interfaz.page.show_dialog(dialogo)


async def restaurar_documentos(interfaz: Any, _evento: ft.Event | None = None) -> None:
    """Ejecuta la restauración de documentos de la fecha seleccionada."""
    if not interfaz.exigir_roles("master"):
        return
    if interfaz.seleccion_fecha_restauracion is None:
        interfaz.notificar("No se cargó la selección de fecha.")
        return
    fecha = interfaz.seleccion_fecha_restauracion.value
    if not fecha:
        interfaz.notificar("Selecciona una fecha de descuento.")
        return
    interfaz.page.pop_dialog()
    await interfaz.ejecutar_tarea(
        "Restauración de documentos",
        lambda: interfaz.menu.restaurar_para_pruebas(fecha),
    )
