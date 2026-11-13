"""Fachada de compatibilidad para el motor local de intenciones del chat interno."""

from .chat import (
    detectar_intencion,
    extraer_termino_busqueda,
    formatear_diagnostico_archivos,
    formatear_respuesta_criticos,
    formatear_respuesta_stock,
    formatear_ultimo_informe,
    normalizar_texto,
    obtener_chips_configuracion,
    obtener_comandos_ayuda,
    obtener_mensaje_bienvenida,
    obtener_pie_ayuda,
)

__all__ = [
    "normalizar_texto",
    "detectar_intencion",
    "extraer_termino_busqueda",
    "formatear_respuesta_stock",
    "formatear_respuesta_criticos",
    "formatear_diagnostico_archivos",
    "formatear_ultimo_informe",
    "obtener_mensaje_bienvenida",
    "obtener_comandos_ayuda",
    "obtener_chips_configuracion",
    "obtener_pie_ayuda",
]
