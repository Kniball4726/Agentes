"""Fachada de compatibilidad para la generación de Hoja de Ruta y Manifiesto de Despacho."""

from .stock.manifest_pdf import _NumberedCanvas, generar_hoja_ruta_pdf

__all__ = ["_NumberedCanvas", "generar_hoja_ruta_pdf"]
