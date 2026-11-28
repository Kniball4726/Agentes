"""Botones con jerarquía visual coherente (primario · peligro · neutro).

Regla del sistema de diseño:
- **Neutro** (Cancelar / Cerrar / Omitir / Volver): botón contorneado sin relleno,
  nunca rojo, para no competir con la acción principal ni sugerir peligro.
- **Primario**: rojo de marca sólido; una sola acción principal por diálogo.
- **Peligro**: rojo oscuro con ícono de advertencia, reservado a acciones
  destructivas o irreversibles (eliminar, revocar, anular, purgar).
"""

from __future__ import annotations

import unicodedata
from typing import Any, Callable, Literal

import flet as ft

from ..theme import ROJO

VarianteBoton = Literal["auto", "primario", "peligro", "neutro"]

MARCA_NEUTRO = "ds:neutro"
MARCA_PRIMARIO = "ds:primario"
MARCA_PELIGRO = "ds:peligro"

# Prefijos inequívocamente neutros ("Cancelar y Revisar", "Cerrar (Esc)", "Volver al listado").
# "Cancelar pedido" o "Cerrar jornada" NO son neutros: ejecutan una operación.
_PREFIJOS_NEUTROS = (
    "cancelar y ",
    "cerrar (",
    "volver a",
    "salir sin",
)
_TEXTOS_NEUTROS_EXACTOS = {
    "no",
    "atras",
    "cancelar",
    "cerrar",
    "cerrar menu",
    "cerrar ventana",
    "omitir",
    "volver",
    "descartar",
    "ahora no",
    "mas tarde",
    "entendido",
}
_PREFIJOS_PELIGRO = (
    "eliminar",
    "borrar",
    "revocar",
    "anular",
    "purgar",
    "si, revocar",
    "si, eliminar",
    "si, anular",
    "desactivar",
    "restaurar",
)

COLOR_PELIGRO = ft.Colors.RED_900
_RADIO = 8


def _normalizar(texto: Any) -> str:
    base = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode("ascii")
    return " ".join(base.strip().lower().split())


def es_accion_neutra(texto: Any) -> bool:
    """Indica si el rótulo corresponde a una acción de cierre/cancelación sin efectos."""
    norm = _normalizar(texto)
    if not norm:
        return False
    return norm in _TEXTOS_NEUTROS_EXACTOS or norm.startswith(_PREFIJOS_NEUTROS)


def es_accion_peligrosa(texto: Any) -> bool:
    """Indica si el rótulo describe una acción destructiva o irreversible."""
    norm = _normalizar(texto)
    return bool(norm) and norm.startswith(_PREFIJOS_PELIGRO)


def _forma() -> ft.RoundedRectangleBorder:
    return ft.RoundedRectangleBorder(radius=_RADIO)


def boton_cancelar(texto: str, accion: Callable[..., Any] | None, **kwargs: Any) -> ft.Button:
    """Botón neutro contorneado (hereda el color de texto del tema activo)."""
    return ft.Button(
        content=texto,
        on_click=accion,
        bgcolor=ft.Colors.TRANSPARENT,
        color=ft.Colors.ON_SURFACE,
        elevation=0,
        style=ft.ButtonStyle(
            shape=_forma(),
            side=ft.BorderSide(1, ft.Colors.with_opacity(0.45, ft.Colors.ON_SURFACE)),
            overlay_color=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE),
        ),
        data=MARCA_NEUTRO,
        **kwargs,
    )


def boton_primario(
    texto: str,
    accion: Callable[..., Any] | None,
    icono: ft.IconData | None = None,
    **kwargs: Any,
) -> ft.Button:
    """Acción principal del diálogo en rojo de marca."""
    return ft.Button(
        content=texto,
        icon=icono,
        on_click=accion,
        bgcolor=ROJO,
        color=ft.Colors.WHITE,
        style=ft.ButtonStyle(shape=_forma()),
        data=MARCA_PRIMARIO,
        **kwargs,
    )


def boton_peligro(
    texto: str,
    accion: Callable[..., Any] | None,
    icono: ft.IconData | None = ft.Icons.WARNING_AMBER_ROUNDED,
    **kwargs: Any,
) -> ft.Button:
    """Acción destructiva: rojo oscuro + ícono de advertencia para diferenciarla del primario."""
    return ft.Button(
        content=texto,
        icon=icono,
        on_click=accion,
        bgcolor=COLOR_PELIGRO,
        color=ft.Colors.WHITE,
        style=ft.ButtonStyle(shape=_forma()),
        data=MARCA_PELIGRO,
        **kwargs,
    )


def boton_dialogo_semantico(
    texto: str,
    accion: Callable[..., Any] | None,
    variante: VarianteBoton = "auto",
) -> ft.Button:
    """Crea el botón adecuado según la variante o, en ``auto``, según el rótulo."""
    if variante == "auto":
        if es_accion_neutra(texto):
            variante = "neutro"
        elif es_accion_peligrosa(texto):
            variante = "peligro"
        else:
            variante = "primario"
    if variante == "neutro":
        return boton_cancelar(texto, accion)
    if variante == "peligro":
        return boton_peligro(texto, accion)
    return boton_primario(texto, accion)


def fijar_ocupado(boton: Any, ocupado: bool, texto_ocupado: str | None = None) -> None:
    """Deshabilita un botón mientras corre una operación para evitar doble envío.

    Guarda el contenido original para restaurarlo al finalizar.
    """
    if boton is None:
        return
    try:
        if ocupado:
            if not hasattr(boton, "_ds_contenido_original"):
                boton._ds_contenido_original = getattr(boton, "content", None)
            boton.disabled = True
            if texto_ocupado:
                boton.content = texto_ocupado
        else:
            boton.disabled = False
            if hasattr(boton, "_ds_contenido_original"):
                boton.content = boton._ds_contenido_original
                delattr(boton, "_ds_contenido_original")
    except Exception:
        pass
