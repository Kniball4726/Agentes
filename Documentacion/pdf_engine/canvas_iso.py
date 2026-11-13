# -*- coding: utf-8 -*-
"""Canvas de doble pasada con encabezado y pie institucional ISO/APA/UPEL."""

from __future__ import annotations

from reportlab.lib.units import cm
from reportlab.pdfgen import canvas

from .constants import (
    ALTO_PAGINA,
    ANCHO_PAGINA,
    COLOR_BORDE_APA,
    COLOR_SECUNDARIO,
    COLOR_TEXTO_MUTED,
    MARGEN_DER,
    MARGEN_IZQ,
    VERSION_SOP_ACTUAL,
)


def crear_canvas_iso_upel(
    codigo_doc: str,
    titulo_doc: str,
    version: str = VERSION_SOP_ACTUAL,
):
    """Fábrica de Canvas con encabezados y pies de página normalizados ISO 26514 y UPEL/APA."""

    class ISOUPELNumberedCanvas(canvas.Canvas):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._saved_page_states = []

        def showPage(self):
            self._saved_page_states.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            num_paginas = len(self._saved_page_states)
            for estado in self._saved_page_states:
                self.__dict__.update(estado)
                self._dibujar_encabezado_y_pie(num_paginas)
                super().showPage()
            super().save()

        def _dibujar_encabezado_y_pie(self, total_paginas: int):
            if self._pageNumber == 1:
                return

            self.saveState()
            y_header = ALTO_PAGINA - 1.5 * cm
            self.setFont("Helvetica-Bold", 8.0)
            self.setFillColor(COLOR_SECUNDARIO)
            self.drawString(MARGEN_IZQ, y_header, f"StockAgent · {titulo_doc}")

            self.setFont("Helvetica", 7.5)
            self.setFillColor(COLOR_TEXTO_MUTED)
            self.drawRightString(
                ANCHO_PAGINA - MARGEN_DER,
                y_header,
                f"{codigo_doc} | {version} | ISO/APA/UPEL",
            )

            self.setStrokeColor(COLOR_BORDE_APA)
            self.setLineWidth(0.6)
            self.line(MARGEN_IZQ, y_header - 3, ANCHO_PAGINA - MARGEN_DER, y_header - 3)

            y_footer = 1.3 * cm
            self.line(MARGEN_IZQ, y_footer + 8, ANCHO_PAGINA - MARGEN_DER, y_footer + 8)

            self.setFont("Helvetica", 7.5)
            self.setFillColor(COLOR_TEXTO_MUTED)
            self.drawString(
                MARGEN_IZQ,
                y_footer,
                "CONFIDENCIAL — Sistema de Gestión Documental UltraTech S.A. · Control de Calidad",
            )

            texto_pag = f"Página {self._pageNumber} de {total_paginas}"
            self.drawRightString(ANCHO_PAGINA - MARGEN_DER, y_footer, texto_pag)
            self.restoreState()

    return ISOUPELNumberedCanvas
