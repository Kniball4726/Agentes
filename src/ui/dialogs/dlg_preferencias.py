"""Diálogo modal para la configuración de preferencias de interfaz del usuario."""

from typing import Any
import flet as ft
from ..theme import ROJO
from ..user_preferences import (
    obtener_preferencias_usuario,
    guardar_preferencia_usuario,
)


def mostrar_dialogo_preferencias(interfaz: Any, _evento: ft.Event | None = None) -> None:
    """Abre el panel de preferencias visuales, de navegación e impresión del usuario actual."""
    if not interfaz.usuario_actual or not interfaz.page:
        return

    username = interfaz.usuario_actual.username
    prefs = obtener_preferencias_usuario(username)

    pos_actual = getattr(interfaz, "posicion_sidebar", "izquierda")
    if not pos_actual:
        pos_actual = prefs.get("posicion_sidebar", "izquierda")

    impresora_actual = prefs.get("impresora_termica", "")
    impresion_directa_actual = bool(prefs.get("impresion_directa", False))

    def al_cambiar_tema(e: Any) -> None:
        nuevo_oscuro = bool(e.control.value)
        if nuevo_oscuro != interfaz.modo_oscuro:
            interfaz.alternar_tema()
            guardar_preferencia_usuario(username, "modo_oscuro", nuevo_oscuro)

    def al_cambiar_posicion(e: Any) -> None:
        nueva_pos = str(e.control.value)
        if nueva_pos in ("izquierda", "derecha", "arriba", "abajo", "oculto"):
            guardar_preferencia_usuario(username, "posicion_sidebar", nueva_pos)
            interfaz.cambiar_posicion_sidebar(nueva_pos)

    def al_cambiar_impresora(e: Any) -> None:
        imp = str(e.control.value or "")
        guardar_preferencia_usuario(username, "impresora_termica", imp)

    def al_cambiar_modo_impresion(e: Any) -> None:
        modo = bool(e.control.value)
        guardar_preferencia_usuario(username, "impresion_directa", modo)

    def al_cerrar(_e: Any) -> None:
        if interfaz.page and hasattr(interfaz.page, "pop_dialog"):
            try:
                interfaz.page.pop_dialog()
            except Exception:
                pass

    switch_tema = ft.Switch(
        label="Modo oscuro activado",
        value=interfaz.modo_oscuro,
        active_color=ROJO,
        on_change=al_cambiar_tema,
    )

    dropdown_posicion = ft.Dropdown(
        label="Ubicación del menú",
        value=pos_actual,
        options=[
            ft.dropdown.Option("izquierda", "Barra lateral izquierda (predeterminado)"),
            ft.dropdown.Option("derecha", "Barra lateral derecha"),
            ft.dropdown.Option("arriba", "Barra superior horizontal (con menús desplegables)"),
            ft.dropdown.Option("abajo", "Barra inferior horizontal (con menús desplegables)"),
            ft.dropdown.Option("oculto", "Ocultar barra (Pantalla completa · F2 para buscar)"),
        ],
        on_select=al_cambiar_posicion,
        width=380,
    )

    impresoras = listar_impresoras_sistema()
    opciones_impresora = [ft.dropdown.Option("", "Abrir en visor PDF del sistema")]
    for imp in impresoras:
        opciones_impresora.append(ft.dropdown.Option(imp, f"🖨️ {imp}"))

    dropdown_impresora = ft.Dropdown(
        label="Impresora de rótulos térmicos",
        value=impresora_actual if impresora_actual in impresoras else "",
        options=opciones_impresora,
        on_select=al_cambiar_impresora,
        width=380,
    )

    switch_impresion_directa = ft.Switch(
        label="Impresión directa desatendida (Windows Spooler)",
        value=impresion_directa_actual,
        active_color=ROJO,
        on_change=al_cambiar_modo_impresion,
        tooltip="Envía los rótulos a la impresora térmica sin abrir ventana previa",
    )

    contenido = ft.Column(
        [
            ft.Text("Personaliza la apariencia, navegación y dispositivos de tu usuario.", size=12, color=interfaz.secundario),
            ft.Divider(height=12, color=interfaz.borde),
            ft.Text("TEMA VISUAL", size=11, weight=ft.FontWeight.BOLD, color=interfaz.secundario),
            switch_tema,
            ft.Container(height=4),
            ft.Text("DISPOSICIÓN DE NAVEGACIÓN", size=11, weight=ft.FontWeight.BOLD, color=interfaz.secundario),
            dropdown_posicion,
            ft.Container(height=4),
            ft.Text("IMPRESIÓN Y DISPOSITIVOS", size=11, weight=ft.FontWeight.BOLD, color=interfaz.secundario),
            dropdown_impresora,
            switch_impresion_directa,
            ft.Container(height=4),
            ft.Text("Tus elecciones se guardan automáticamente para tus próximas sesiones.", size=11, italic=True, color=interfaz.secundario),
        ],
        spacing=6,
        tight=True,
        width=420,
    )

    dialogo = ft.AlertDialog(
        modal=True,
        title=ft.Row(
            [
                ft.Icon(ft.Icons.TUNE, color=ROJO, size=24),
                ft.Text("Preferencias de Interfaz", weight=ft.FontWeight.BOLD, size=18, color=interfaz.texto),
            ],
            spacing=10,
        ),
        content=contenido,
        actions=[
            ft.Button("Cerrar", on_click=al_cerrar, bgcolor=ROJO, color=ft.Colors.WHITE),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )

    try:
        interfaz.page.show_dialog(dialogo)
        interfaz.page.update()
    except Exception:
        pass
