"""Diálogo modal para la configuración de preferencias de interfaz del usuario."""

from __future__ import annotations

from typing import Any
import flet as ft

from ..components.print_labels import listar_impresoras_sistema
from ..theme import ROJO
from ..user_preferences import (
    guardar_preferencia_usuario,
    obtener_preferencias_usuario,
)

_POSICIONES_VALIDAS = ("izquierda", "derecha", "arriba", "abajo", "oculto")


def _construir_opciones_impresoras(
    impresoras: list[str],
    impresora_actual: str,
) -> tuple[list[ft.dropdown.Option], str]:
    """Genera opciones deduplicadas de impresoras y el valor seleccionado válido."""
    unicas = list(dict.fromkeys(impresoras))
    opciones = [ft.dropdown.Option("", "Abrir en visor PDF del sistema")]
    for imp in unicas:
        opciones.append(ft.dropdown.Option(imp, f"🖨️ {imp}"))
    valor = impresora_actual if impresora_actual in unicas else ""
    return opciones, valor


def mostrar_dialogo_preferencias(interfaz: Any, _evento: ft.Event | None = None) -> None:
    """Abre el panel de preferencias visuales, de navegación e impresión del usuario actual."""
    if not interfaz.usuario_actual or not interfaz.page:
        return

    username = interfaz.usuario_actual.username
    prefs = obtener_preferencias_usuario(username)

    pos_actual = getattr(interfaz, "posicion_sidebar", "") or prefs.get("posicion_sidebar", "izquierda")
    if pos_actual not in _POSICIONES_VALIDAS:
        pos_actual = "izquierda"

    impresora_actual = str(prefs.get("impresora_termica", "") or "")
    impresion_directa_actual = bool(prefs.get("impresion_directa", False))
    sonido_chat_actual = bool(
        prefs.get("sonido_chat_activo", getattr(interfaz, "sonido_chat_activo", True))
    )

    titulo_texto = ft.Text(
        "Preferencias de Interfaz",
        weight=ft.FontWeight.BOLD,
        size=18,
        color=interfaz.texto,
    )
    subtitulo_texto = ft.Text(
        "Personaliza la apariencia, navegación y dispositivos de tu usuario.",
        size=12,
        color=interfaz.secundario,
    )
    divisor_cabecera = ft.Divider(height=12, color=interfaz.borde)
    lbl_tema = ft.Text("TEMA VISUAL", size=11, weight=ft.FontWeight.BOLD, color=interfaz.secundario)
    lbl_navegacion = ft.Text("DISPOSICIÓN DE NAVEGACIÓN", size=11, weight=ft.FontWeight.BOLD, color=interfaz.secundario)
    lbl_impresion = ft.Text("IMPRESIÓN Y DISPOSITIVOS", size=11, weight=ft.FontWeight.BOLD, color=interfaz.secundario)
    lbl_notificaciones = ft.Text(
        "CHATBOT Y NOTIFICACIONES",
        size=11,
        weight=ft.FontWeight.BOLD,
        color=interfaz.secundario,
    )
    nota_pie = ft.Text(
        "Tus elecciones se guardan automáticamente para tus próximas sesiones.",
        size=11,
        italic=True,
        color=interfaz.secundario,
    )

    def _refrescar_colores_dialogo() -> None:
        titulo_texto.color = interfaz.texto
        subtitulo_texto.color = interfaz.secundario
        divisor_cabecera.color = interfaz.borde
        lbl_tema.color = interfaz.secundario
        lbl_navegacion.color = interfaz.secundario
        lbl_impresion.color = interfaz.secundario
        lbl_notificaciones.color = interfaz.secundario
        nota_pie.color = interfaz.secundario

    def al_cambiar_tema(e: Any) -> None:
        nuevo_oscuro = bool(e.control.value)
        if nuevo_oscuro != interfaz.modo_oscuro:
            interfaz.alternar_tema()
            guardar_preferencia_usuario(username, "modo_oscuro", nuevo_oscuro)
            _refrescar_colores_dialogo()
            try:
                interfaz.page.update()
            except Exception:
                pass

    def al_cambiar_posicion(e: Any) -> None:
        nueva_pos = str(e.control.value or "")
        if nueva_pos in _POSICIONES_VALIDAS:
            guardar_preferencia_usuario(username, "posicion_sidebar", nueva_pos)
            interfaz.cambiar_posicion_sidebar(nueva_pos)

    def al_cambiar_impresora(e: Any) -> None:
        imp = str(e.control.value or "")
        guardar_preferencia_usuario(username, "impresora_termica", imp)

    def al_cambiar_modo_impresion(e: Any) -> None:
        modo = bool(e.control.value)
        guardar_preferencia_usuario(username, "impresion_directa", modo)

    def al_cambiar_sonido_chat(e: Any) -> None:
        activo = bool(e.control.value)
        interfaz.sonido_chat_activo = activo
        guardar_preferencia_usuario(username, "sonido_chat_activo", activo)

    def al_cerrar(_e: Any) -> None:
        if interfaz.page and hasattr(interfaz.page, "pop_dialog"):
            try:
                interfaz.page.pop_dialog()
                interfaz.page.update()
            except Exception:
                pass

    switch_tema = ft.Switch(
        label="Modo oscuro activado",
        value=bool(interfaz.modo_oscuro),
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
    opciones_impresora, valor_impresora = _construir_opciones_impresoras(impresoras, impresora_actual)

    dropdown_impresora = ft.Dropdown(
        label="Impresora de rótulos térmicos",
        value=valor_impresora,
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

    switch_sonido_chat = ft.Switch(
        label="Sonido de campana breve en mensajes del chatbot",
        value=sonido_chat_actual,
        active_color=ROJO,
        on_change=al_cambiar_sonido_chat,
        tooltip="Reproduce una notificación campana breve al recibir respuestas o mensajes de equipo",
    )

    contenido = ft.Column(
        [
            subtitulo_texto,
            divisor_cabecera,
            lbl_tema,
            switch_tema,
            ft.Container(height=4),
            lbl_navegacion,
            dropdown_posicion,
            ft.Container(height=4),
            lbl_impresion,
            dropdown_impresora,
            switch_impresion_directa,
            ft.Container(height=4),
            lbl_notificaciones,
            switch_sonido_chat,
            ft.Container(height=4),
            nota_pie,
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
                titulo_texto,
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
    except Exception as error:
        if hasattr(interfaz, "notificar"):
            interfaz.notificar(f"No se pudo abrir Preferencias de Interfaz: {error}")
