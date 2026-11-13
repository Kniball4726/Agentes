"""Fachada de compatibilidad para la generación de rótulos A4 y térmicos con QR."""

from .labels import (
    COLUMNAS_POR_HOJA,
    ETIQUETAS_POR_HOJA,
    FILAS_POR_HOJA,
    _construir_tarjeta_etiqueta,
    _crear_qr_drawing,
    _es_pedido_agregado,
    _formatear_cliente_etiqueta,
    generar_etiquetas_bultos_pdf,
    generar_etiquetas_lote_pedidos_pdf,
    generar_etiquetas_termicas_pdf,
)

__all__ = [
    "ETIQUETAS_POR_HOJA",
    "FILAS_POR_HOJA",
    "COLUMNAS_POR_HOJA",
    "_crear_qr_drawing",
    "_es_pedido_agregado",
    "_formatear_cliente_etiqueta",
    "_construir_tarjeta_etiqueta",
    "generar_etiquetas_bultos_pdf",
    "generar_etiquetas_lote_pedidos_pdf",
    "generar_etiquetas_termicas_pdf",
]
