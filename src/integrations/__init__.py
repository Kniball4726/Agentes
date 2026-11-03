"""Módulo centralizado de integraciones y servicios externos."""

from .telegram_notifier import (
    enviar_mensaje_telegram,
    cargar_config_telegram,
    guardar_config_telegram,
    notificar_quiebre_stock_telegram,
    notificar_seguridad_bloqueo_telegram,
    notificar_cierre_jornada_telegram,
    notificar_anomalia_demanda_telegram,
)
from .email_sender import (
    obtener_config_email,
    guardar_config_email,
    probar_conexion_smtp,
    enviar_via_smtp,
    abrir_en_cliente_mapi,
    abrir_fallback_correo,
    despachar_correo,
)
from .mercado_libre_api import (
    cargar_config_mercadolibre,
    guardar_config_mercadolibre,
    renovar_token_ml,
    verificar_credenciales_ml,
    consultar_ordenes_ml,
    mapear_orden_ml_a_items,
    generar_documento_orden_ml_docx,
    descontar_orden_ml_api,
)
from .sheets_manager import GoogleSheetsStockManager

__all__ = [
    "enviar_mensaje_telegram",
    "cargar_config_telegram",
    "guardar_config_telegram",
    "notificar_quiebre_stock_telegram",
    "notificar_seguridad_bloqueo_telegram",
    "notificar_cierre_jornada_telegram",
    "notificar_anomalia_demanda_telegram",
    "obtener_config_email",
    "guardar_config_email",
    "probar_conexion_smtp",
    "enviar_via_smtp",
    "abrir_en_cliente_mapi",
    "abrir_fallback_correo",
    "despachar_correo",
    "cargar_config_mercadolibre",
    "guardar_config_mercadolibre",
    "renovar_token_ml",
    "verificar_credenciales_ml",
    "consultar_ordenes_ml",
    "mapear_orden_ml_a_items",
    "generar_documento_orden_ml_docx",
    "descontar_orden_ml_api",
    "GoogleSheetsStockManager",
]
