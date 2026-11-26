"""Utilidades de casteo y normalización para códigos de barras y SKUs.

Centraliza la conversión segura de tipos (``int``, ``float`` provenientes de Excel
o SQLite), limpieza de caracteres de control de pistolas lectoras (HID/AIM) y
generación de variantes tolerantes a distribución de teclado US->ES/LA y ceros
a la izquierda (UPC-A <-> EAN-13).
"""

from __future__ import annotations

import math
import re


def normalizar_codigo_lector(raw: object) -> str:
    """Castea, limpia y normaliza lecturas de pistolas lectoras y colectores.

    Convierte de forma segura tipos numéricos (int/float provenientes de Excel o
    SQLite, eliminando sufijos ``.0``), elimina caracteres de control (CR, LF, TAB),
    espacios residuales, delimitadores Code-39 (``*...*``) y prefijos estándar AIM
    Symbology Identifier (ej. ``]C1``, ``]e0``, ``]E0``).
    """
    if raw is None or isinstance(raw, bool):
        return ""

    if isinstance(raw, float):
        if not math.isfinite(raw):
            return ""
        texto = str(int(raw)) if raw.is_integer() else str(raw)
    else:
        texto = str(raw)

    texto = texto.strip()
    if not texto:
        return ""

    # Eliminar prefijos estándar AIM (']' seguido de letra y dígito)
    texto = re.sub(r"^\][A-Za-z][0-9]", "", texto)
    # Eliminar caracteres ASCII de control no imprimibles (0x00 a 0x1F y 0x7F)
    texto = "".join(ch for ch in texto if 32 <= ord(ch) <= 126 or ord(ch) > 127).strip()

    # Eliminar delimitadores Start/Stop de Code 39 (*CODIGO*) cuando envuelven el valor
    if len(texto) >= 3 and texto.startswith("*") and texto.endswith("*"):
        texto = texto[1:-1].strip()

    # Eliminar sufijo decimal artificial ".0" de números serializados desde float/Excel
    texto = re.sub(r"^(-?\d+)\.0+$", r"\1", texto)
    return texto.strip()


def generar_variantes_codigo_lector(raw: object) -> list[str]:
    """Genera variantes ordenadas de coincidencia para lecturas de pistola o catálogo.

    Incluye la forma normalizada exacta, correcciones por distribución de teclado
    HID US -> Español/Latinoamérica (ej. ``'`` por ``-``, ``?`` por ``_``,
    prefijo AIM ``+C1``) y equivalencias numéricas con/sin ceros a la izquierda
    (EAN-13 <-> UPC-A y códigos numéricos).
    """
    base = normalizar_codigo_lector(raw)
    if not base:
        return []

    variantes: list[str] = []
    vistos: set[str] = set()

    def _agregar(candidato: str) -> None:
        limpio = candidato.strip()
        if limpio and limpio not in vistos:
            vistos.add(limpio)
            variantes.append(limpio)

    _agregar(base)

    # Guardar variantes cuando el lector HID US escribe en Windows con teclado ES/LA
    bases_teclado = [base]
    sin_aim_es = re.sub(r"^[+}´][A-Za-z][0-9]", "", base).strip()
    if sin_aim_es and sin_aim_es != base:
        _agregar(sin_aim_es)
        bases_teclado.append(sin_aim_es)

    for origen in list(bases_teclado):
        if "'" in origen or "?" in origen:
            corregido = origen.replace("'", "-").replace("?", "_")
            _agregar(corregido)
            bases_teclado.append(corregido)

        sin_espacios = re.sub(r"\s+", "", origen)
        if sin_espacios != origen:
            _agregar(sin_espacios)
            bases_teclado.append(sin_espacios)

    # Equivalencias numéricas: ceros a la izquierda y UPC-A (12) <-> EAN-13 (13)
    for cand in list(variantes):
        if cand.isdigit():
            if len(cand) == 13 and cand.startswith("0"):
                _agregar(cand[1:])
            elif len(cand) == 12:
                _agregar(f"0{cand}")
            sin_ceros = cand.lstrip("0") or "0"
            _agregar(sin_ceros)

    return variantes


def coincide_codigo_o_barras(producto: object, raw_query: object) -> bool:
    """Evalúa en memoria si un producto (dict o sqlite3.Row) coincide con una lectura.

    Soporta tipos heterogéneos (int/float/str), mayúsculas/minúsculas, variantes de
    teclado US->ES/LA y ceros a la izquierda en códigos numéricos.
    """
    variantes_query = generar_variantes_codigo_lector(raw_query)
    if not variantes_query:
        return False

    if hasattr(producto, "keys"):
        keys = set(producto.keys())
        code_raw = producto["code"] if "code" in keys else ""
        bar_raw = (
            producto["cod_barras"]
            if "cod_barras" in keys
            else (producto["barcode"] if "barcode" in keys else "")
        )
    else:
        code_raw = getattr(producto, "code", "")
        bar_raw = getattr(producto, "cod_barras", "") or getattr(producto, "barcode", "")

    candidatos_prod = set()
    for campo in (code_raw, bar_raw):
        for var in generar_variantes_codigo_lector(campo):
            candidatos_prod.add(var.casefold())

    return any(v.casefold() in candidatos_prod for v in variantes_query)
