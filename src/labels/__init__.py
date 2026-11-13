"""Subpaquete modular para la generación de rótulos A4 y etiquetas térmicas con QR."""

from .a4_labels import (
    _construir_tarjeta_etiqueta,
    generar_etiquetas_bultos_pdf,
    generar_etiquetas_lote_pedidos_pdf,
)
from .thermal_labels import generar_etiquetas_termicas_pdf
from .utils import (
    COLUMNAS_POR_HOJA,
    ETIQUETAS_POR_HOJA,
    FILAS_POR_HOJA,
    _crear_qr_drawing,
    _es_pedido_agregado,
    _formatear_cliente_etiqueta,
    compilar_grilla_a4_pdf,
)

__all__ = [
    "ETIQUETAS_POR_HOJA",
    "FILAS_POR_HOJA",
    "COLUMNAS_POR_HOJA",
    "_crear_qr_drawing",
    "_es_pedido_agregado",
    "_formatear_cliente_etiqueta",
    "_construir_tarjeta_etiqueta",
    "compilar_grilla_a4_pdf",
    "generar_etiquetas_bultos_pdf",
    "generar_etiquetas_lote_pedidos_pdf",
    "generar_etiquetas_termicas_pdf",
]
