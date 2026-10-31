"""Componentes visuales y módulos de interfaz para Flet."""

from .sidebar import construir_sidebar_controls
from .floating_chat import crear_ventana_chat_flotante, procesar_mensaje_chat_agente
from .header import construir_encabezado
from .panels import construir_panel_metricas, construir_panel_informes_actividad

__all__ = [
    "construir_sidebar_controls",
    "crear_ventana_chat_flotante",
    "procesar_mensaje_chat_agente",
    "construir_encabezado",
    "construir_panel_metricas",
    "construir_panel_informes_actividad",
]
