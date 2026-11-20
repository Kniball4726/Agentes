"""Campos de formulario seguros y validación inline reutilizable.

Nota Flet 1.0.x: ``TextField.error_text`` / ``helper_text`` ya no existen y se
ignoran en silencio; las propiedades vigentes son ``error`` y ``helper``.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

import flet as ft

MASCARA_SECRETO = "••••••••"
HINT_SECRETO_GUARDADO = f"{MASCARA_SECRETO}  (guardado · dejar vacío para conservar)"
FORMATO_FECHA = "DD/MM/AAAA"
_PATRON_FECHA = re.compile(r"^\s*(\d{1,2})/(\d{1,2})/(\d{4})\s*$")


def campo_secreto_seguro(
    etiqueta: str,
    valor_guardado: str | None = None,
    **kwargs: Any,
) -> ft.TextField:
    """Campo de contraseña/token que **nunca** precarga el secreto ya guardado.

    Si existe un valor guardado, se indica con una máscara en el ``hint_text``;
    dejar el campo vacío conserva el secreto existente (ver ``resolver_secreto``).
    """
    tiene_guardado = bool(str(valor_guardado or "").strip())
    kwargs.setdefault("password", True)
    kwargs.setdefault("can_reveal_password", True)
    if tiene_guardado:
        kwargs.setdefault("hint_text", HINT_SECRETO_GUARDADO)
        kwargs.setdefault("helper", "Ya hay un valor guardado. Escribí uno nuevo solo para reemplazarlo.")
    campo = ft.TextField(label=etiqueta, value="", **kwargs)
    campo.data = {"secreto_guardado": tiene_guardado}
    return campo


def resolver_secreto(campo: Any, valor_guardado: str | None) -> str:
    """Devuelve el secreto nuevo escrito o, si quedó vacío, el previamente guardado."""
    nuevo = str(getattr(campo, "value", "") or "").strip()
    if nuevo and nuevo != MASCARA_SECRETO:
        return nuevo
    return str(valor_guardado or "")


def marcar_error(campo: Any, mensaje: str | None) -> None:
    """Muestra (o limpia con ``None``) el error inline de un campo (propiedad ``error`` de Flet 1.0)."""
    valor = mensaje or None
    try:
        campo.error = valor
    except Exception:
        pass
    try:
        campo.error_text = valor
    except Exception:
        pass


def limpiar_errores(*campos: Any) -> None:
    for campo in campos:
        marcar_error(campo, None)


def campo_numerico(etiqueta: str, valor: Any = "", **kwargs: Any) -> ft.TextField:
    """TextField numérico (teclado numérico en móvil y filtro de dígitos)."""
    kwargs.setdefault("keyboard_type", ft.KeyboardType.NUMBER)
    kwargs.setdefault("input_filter", ft.NumbersOnlyInputFilter())
    return ft.TextField(label=etiqueta, value="" if valor is None else str(valor), **kwargs)


def validar_entero_no_negativo(
    campo: Any,
    etiqueta: str = "El valor",
    *,
    permitir_vacio: bool = False,
    minimo: int = 0,
    maximo: int | None = None,
) -> int | None:
    """Valida un entero ≥ ``minimo``; marca el error inline y devuelve ``None`` si es inválido."""
    texto = str(getattr(campo, "value", "") or "").strip()
    if not texto:
        if permitir_vacio:
            marcar_error(campo, None)
            return None
        marcar_error(campo, f"{etiqueta} es obligatorio.")
        return None
    try:
        numero = int(texto)
    except ValueError:
        marcar_error(campo, f"{etiqueta} debe ser un número entero.")
        return None
    if numero < minimo:
        marcar_error(campo, f"{etiqueta} no puede ser menor a {minimo}.")
        return None
    if maximo is not None and numero > maximo:
        marcar_error(campo, f"{etiqueta} no puede superar {maximo}.")
        return None
    marcar_error(campo, None)
    return numero


def parsear_fecha_ddmmaaaa(texto: str) -> date | None:
    """Convierte ``DD/MM/AAAA`` en ``date`` (``None`` si el formato o la fecha son inválidos)."""
    m = _PATRON_FECHA.match(str(texto or ""))
    if not m:
        return None
    dia, mes, anio = (int(x) for x in m.groups())
    try:
        return datetime(anio, mes, dia).date()
    except ValueError:
        return None


def validar_fecha_ddmmaaaa(
    campo: Any,
    etiqueta: str = "La fecha",
    *,
    permitir_vacio: bool = True,
) -> date | None:
    """Valida el formato unificado ``DD/MM/AAAA`` con error inline."""
    texto = str(getattr(campo, "value", "") or "").strip()
    if not texto:
        if not permitir_vacio:
            marcar_error(campo, f"{etiqueta} es obligatoria ({FORMATO_FECHA}).")
        else:
            marcar_error(campo, None)
        return None
    fecha = parsear_fecha_ddmmaaaa(texto)
    if fecha is None:
        marcar_error(campo, f"Formato inválido. Usá {FORMATO_FECHA}.")
        return None
    marcar_error(campo, None)
    return fecha
