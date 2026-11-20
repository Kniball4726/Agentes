"""Utilidades modulares de sanitización de salida para ReportLab PDF, Excel y Telegram HTML."""

from __future__ import annotations

import html
from typing import Any, Iterable

_PREFIJOS_FORMULA_EXCEL = ("=", "+", "-", "@", "\t", "\r")


def escapar_texto_reportlab(valor: Any) -> str:
    """Escapa caracteres XML/HTML para uso seguro dentro de ReportLab Paragraph(...)."""
    if valor is None:
        return ""
    return html.escape(str(valor), quote=True)


def escapar_html_telegram(valor: Any) -> str:
    """Escapa texto dinámico para mensajes de Telegram con parse_mode='HTML'."""
    if valor is None:
        return ""
    return html.escape(str(valor), quote=False)


def sanitizar_celda_excel(valor: Any) -> Any:
    """Neutraliza CSV/Excel Formula Injection sin alterar tipos numéricos ni placeholders '-'."""
    if not isinstance(valor, str) or not valor or valor == "-":
        return valor
    texto_sin_esp = valor.lstrip(" ")
    if texto_sin_esp == "-":
        return valor
    if valor.startswith(_PREFIJOS_FORMULA_EXCEL) or (
        texto_sin_esp and texto_sin_esp.startswith(_PREFIJOS_FORMULA_EXCEL)
    ):
        return "'" + valor
    return valor


def sanitizar_fila_excel(fila: Iterable[Any]) -> list[Any]:
    """Sanitiza todos los valores de texto en una fila antes de escribirla en Excel."""
    return [sanitizar_celda_excel(v) for v in fila]
