"""Subpaquete modular para el parser de intenciones y respuestas del asistente interno."""

from .formatters import (
    formatear_diagnostico_archivos,
    formatear_respuesta_criticos,
    formatear_respuesta_stock,
    formatear_ultimo_informe,
)
from .intent_parser import (
    detectar_intencion,
    extraer_termino_busqueda,
    normalizar_texto,
)
from .role_help import (
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
