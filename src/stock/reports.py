"""Fachada de generación y exportación de informes en Excel (.xls) y PDF (ReportLab)."""

from .pdf_exporter import guardar_informe_pdf
from .xls_exporter import copiar_estilo_fila, guardar_informe_xls

__all__ = [
    "copiar_estilo_fila",
    "guardar_informe_xls",
    "guardar_informe_pdf",
]
