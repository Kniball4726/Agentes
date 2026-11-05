"""Componentes visuales y módulos de interfaz para Flet."""

from .sidebar import construir_sidebar_controls
from .floating_chat import crear_ventana_chat_flotante, procesar_mensaje_chat_agente
from .header import construir_encabezado
from .panels import construir_panel_metricas, construir_panel_informes_actividad
from .audio_manager import reproducir_sonido_web
from .network_heartbeat import actualizar_estado_conexion_ui, iniciar_heartbeat_red_daemon
from .mobile_nav import construir_navigation_bar_movil, manejar_cambio_navegacion_movil
from .docking_manager import aplicar_posicion_sidebar_ui, cambiar_posicion_sidebar_ui
from .print_labels import (
    imprimir_rotulos_termicos_pedido_ui,
    imprimir_rotulos_pedido_ui,
    imprimir_rotulos_lote_ui,
)

__all__ = [
    "construir_sidebar_controls",
    "crear_ventana_chat_flotante",
    "procesar_mensaje_chat_agente",
    "construir_encabezado",
    "construir_panel_metricas",
    "construir_panel_informes_actividad",
    "reproducir_sonido_web",
    "actualizar_estado_conexion_ui",
    "iniciar_heartbeat_red_daemon",
    "construir_navigation_bar_movil",
    "manejar_cambio_navegacion_movil",
    "aplicar_posicion_sidebar_ui",
    "cambiar_posicion_sidebar_ui",
    "imprimir_rotulos_termicos_pedido_ui",
    "imprimir_rotulos_pedido_ui",
    "imprimir_rotulos_lote_ui",
]
