"""Exportación de informes a formato Excel (.xls) mediante xlwt y copia de estilos openpyxl."""

from __future__ import annotations

from copy import copy
from pathlib import Path
from typing import Dict, Optional

import openpyxl
import xlwt


def copiar_estilo_fila(
    hoja_plantilla,
    hoja_salida,
    fila_plantilla: int,
    fila_salida: int,
    cantidad_columnas: int,
    columnas_plantilla: tuple[int, int, int, int],
) -> None:
    """Copia la altura y estilos de celda desde una fila de plantilla a la fila de salida."""
    hoja_salida.row_dimensions[fila_salida].height = (
        hoja_plantilla.row_dimensions[fila_plantilla].height
    )
    for columna in range(1, cantidad_columnas + 1):
        origen = hoja_plantilla.cell(
            fila_plantilla, columnas_plantilla[columna - 1]
        )
        destino = hoja_salida.cell(fila_salida, columna)
        if origen.has_style:
            destino.font = copy(origen.font)
            destino.fill = copy(origen.fill)
            destino.border = copy(origen.border)
            destino.alignment = copy(origen.alignment)
            destino.number_format = origen.number_format
            destino.protection = copy(origen.protection)


def _registrar_paleta_xls(libro_xls: xlwt.Workbook, hoja_origen) -> tuple[dict[str, int], dict[int, tuple[int, int, int]]]:
    """Registra la paleta corporativa base y los colores RGB adicionales en xlwt."""
    colores = {
        "17365D": 0x21,
        "1F4E78": 0x22,
        "D9EAF7": 0x23,
        "F3F7FB": 0x24,
        "D6DEE8": 0x25,
        "5B6573": 0x26,
        "E2F0D9": 0x27,
        "FCE4D6": 0x28,
        "9C0006": 0x29,
        "263445": 0x2A,
        "EAF0F6": 0x2B,
        "7F8995": 0x2C,
    }
    rgb_por_indice = {
        0x21: (23, 54, 93),
        0x22: (31, 78, 120),
        0x23: (217, 234, 247),
        0x24: (243, 247, 251),
        0x25: (214, 222, 232),
        0x26: (91, 101, 115),
        0x27: (226, 240, 217),
        0x28: (252, 228, 214),
        0x29: (156, 0, 6),
        0x2A: (38, 52, 69),
        0x2B: (234, 240, 246),
        0x2C: (127, 137, 149),
    }
    for indice, rgb in rgb_por_indice.items():
        libro_xls.set_colour_RGB(indice, *rgb)

    siguiente_color = 0x2D
    for fila in hoja_origen.iter_rows():
        for celda in fila:
            colores_celda = (
                celda.font.color,
                celda.fill.fgColor,
                celda.fill.bgColor,
                *(
                    getattr(getattr(celda.border, lado), "color", None)
                    for lado in ("left", "right", "top", "bottom")
                ),
            )
            for color in colores_celda:
                if color is None or color.type != "rgb" or not color.rgb:
                    continue
                codigo_rgb = str(color.rgb)[-6:].upper()
                if codigo_rgb in colores:
                    continue
                if siguiente_color > 0x3F:
                    break
                colores[codigo_rgb] = siguiente_color
                rgb = tuple(int(codigo_rgb[idx:idx + 2], 16) for idx in (0, 2, 4))
                rgb_por_indice[siguiente_color] = rgb  # type: ignore[assignment]
                libro_xls.set_colour_RGB(siguiente_color, *rgb)
                siguiente_color += 1
    return colores, rgb_por_indice


def guardar_informe_xls(libro: openpyxl.Workbook, ruta: Path) -> None:
    """Convierte un libro openpyxl al formato binario clásico .xls conservando estilos y márgenes."""
    hoja_origen = libro.active
    if hoja_origen.max_row > 65_536:
        raise ValueError("El informe supera el límite de 65.536 filas del formato XLS.")

    libro_xls = xlwt.Workbook(encoding="utf-8")
    hoja_xls = libro_xls.add_sheet(hoja_origen.title[:31])
    colores, rgb_por_indice = _registrar_paleta_xls(libro_xls, hoja_origen)

    colores_borde = {
        "hair": xlwt.Borders.HAIR,
        "thin": xlwt.Borders.THIN,
        "medium": xlwt.Borders.MEDIUM,
        "dashed": xlwt.Borders.DASHED,
        "dotted": xlwt.Borders.DOTTED,
        "thick": xlwt.Borders.THICK,
    }
    horizontal = {
        "left": xlwt.Alignment.HORZ_LEFT,
        "center": xlwt.Alignment.HORZ_CENTER,
        "right": xlwt.Alignment.HORZ_RIGHT,
    }
    vertical = {
        "top": xlwt.Alignment.VERT_TOP,
        "center": xlwt.Alignment.VERT_CENTER,
        "bottom": xlwt.Alignment.VERT_BOTTOM,
    }
    estilos: Dict[int, xlwt.XFStyle] = {}

    def color_index(color) -> Optional[int]:
        if color is None or color.type != "rgb" or not color.rgb:
            return None
        return colores.get(str(color.rgb)[-6:].upper())

    def estilo_para(celda) -> xlwt.XFStyle:
        estilo = estilos.get(celda.style_id)
        if estilo is not None:
            return estilo

        estilo = xlwt.XFStyle()
        fuente = xlwt.Font()
        fuente.name = celda.font.name or "Arial"
        fuente.height = int((celda.font.sz or 10) * 20)
        fuente.bold = bool(celda.font.bold)
        fuente.italic = bool(celda.font.italic)
        fuente.struck_out = bool(celda.font.strike)
        if celda.font.underline:
            fuente.underline = xlwt.Font.UNDERLINE_SINGLE
        indice_color = color_index(celda.font.color)
        if indice_color is not None:
            fuente.colour_index = indice_color
        estilo.font = fuente

        alineacion = xlwt.Alignment()
        alineacion.horz = horizontal.get(celda.alignment.horizontal, xlwt.Alignment.HORZ_GENERAL)
        alineacion.vert = vertical.get(celda.alignment.vertical, xlwt.Alignment.VERT_BOTTOM)
        alineacion.wrap = bool(celda.alignment.wrap_text)
        alineacion.shrink_to_fit = bool(celda.alignment.shrink_to_fit)
        estilo.alignment = alineacion

        bordes = xlwt.Borders()
        for nombre in ("left", "right", "top", "bottom"):
            borde = getattr(celda.border, nombre)
            setattr(bordes, nombre, colores_borde.get(getattr(borde, "style", None), xlwt.Borders.NO_LINE))
            indice_color = color_index(getattr(borde, "color", None))
            if indice_color is not None:
                setattr(bordes, f"{nombre}_colour", indice_color)
        estilo.borders = bordes

        patron = xlwt.Pattern()
        if celda.fill.fill_type == "solid":
            patron.pattern = xlwt.Pattern.SOLID_PATTERN
            indice_color = color_index(celda.fill.fgColor)
            rgb_relleno = rgb_por_indice.get(indice_color)  # type: ignore[arg-type]
            luminancia = (
                sum(peso * canal for peso, canal in zip((0.2126, 0.7152, 0.0722), rgb_relleno))
                if rgb_relleno
                else 255
            )
            patron.pattern_fore_colour = indice_color if indice_color is not None and luminancia >= 190 else 9
        estilo.pattern = patron
        estilo.num_format_str = celda.number_format or "General"
        estilos[celda.style_id] = estilo
        return estilo

    for columna in range(1, hoja_origen.max_column + 1):
        dimension = hoja_origen.column_dimensions[openpyxl.utils.get_column_letter(columna)]
        if dimension.width:
            hoja_xls.col(columna - 1).width = min(int(dimension.width * 256), 65_535)
        hoja_xls.col(columna - 1).hidden = dimension.hidden

    rangos_combinados = {}
    celdas_combinadas = set()
    for rango in hoja_origen.merged_cells.ranges:
        min_col, min_row, max_col, max_row = rango.bounds
        rangos_combinados[(min_row, min_col)] = (min_row - 1, max_row - 1, min_col - 1, max_col - 1)
        for fila in range(min_row, max_row + 1):
            for columna in range(min_col, max_col + 1):
                if (fila, columna) != (min_row, min_col):
                    celdas_combinadas.add((fila, columna))

    for fila in hoja_origen.iter_rows():
        for celda in fila:
            if (celda.row, celda.column) in celdas_combinadas:
                continue
            estilo = estilo_para(celda)
            valor = celda.value if celda.value is not None else ""
            rango = rangos_combinados.get((celda.row, celda.column))
            if rango:
                hoja_xls.write_merge(*rango, valor, estilo)
            else:
                hoja_xls.write(celda.row - 1, celda.column - 1, valor, estilo)

    for fila, dimension in hoja_origen.row_dimensions.items():
        if dimension.height is not None:
            hoja_xls.row(fila - 1).height = int(dimension.height * 20)

    hoja_xls.portrait = hoja_origen.page_setup.orientation == "portrait"
    hoja_xls.paper_size_code = int(hoja_origen.page_setup.paperSize)
    hoja_xls.left_margin = hoja_origen.page_margins.left
    hoja_xls.right_margin = hoja_origen.page_margins.right
    hoja_xls.top_margin = hoja_origen.page_margins.top
    hoja_xls.bottom_margin = hoja_origen.page_margins.bottom
    hoja_xls.fit_width_to_pages = hoja_origen.page_setup.fitToWidth
    hoja_xls.fit_height_to_pages = hoja_origen.page_setup.fitToHeight
    if hoja_origen.freeze_panes:
        fila_inm, col_inm = openpyxl.utils.cell.coordinate_to_tuple(hoja_origen.freeze_panes)
        if fila_inm > 1 or col_inm > 1:
            hoja_xls.set_panes_frozen(True)
            if fila_inm > 1:
                hoja_xls.set_horz_split_pos(fila_inm - 1)
            if col_inm > 1:
                hoja_xls.set_vert_split_pos(col_inm - 1)

    libro_xls.save(str(ruta))
