# -*- coding: utf-8 -*-
"""Generador de Manual de Procedimiento y Uso Botón por Botón para el Rol Consulta."""

from __future__ import annotations

from pathlib import Path

from .fichas import (
    VERSION_PROC_ACTUAL,
    agregar_fichas_modulo,
    construir_cierre_manual_rol,
    iniciar_manual_rol,
)


def construir_manual_consulta(ruta_destino: Path) -> Path:
    """Genera el Manual de Procedimiento y Uso Botón por Botón para el Rol Consulta."""
    codigo_doc = "MAN-PROC-CON-2026"
    titulo_doc = "Manual de Procedimiento y Uso de Botones (Rol Consulta)"
    doc, est, story = iniciar_manual_rol(
        ruta_destino, codigo_doc, titulo_doc,
        "Rol Consulta (Auditores, Ventas Mostrador y Personal de Solo Lectura)",
        "Guía operativa botón por botón: inspección segura de informes oficiales, consulta de historial de pedidos "
        "en solo lectura, envío por correo/WhatsApp y búsqueda rápida en tiempo real sobre HTTPS.",
    )

    agregar_fichas_modulo(
        story, est,
        "1. Ámbito de Aplicación y Permisos de Solo Lectura", [],
        intro_texto=(
            "El perfil <b>Consulta</b> permite a auditores, vendedores o personal administrativo verificar existencias, "
            "pedidos e informes sin facultades de modificación de inventario ni carga/edición de órdenes."
        ),
    )

    agregar_fichas_modulo(
        story, est,
        "2. Módulos e Instrucciones Botón por Botón",
        [
            {
                "nombre_boton": "Centro de Reportes / Abrir informe",
                "icono_str": "[↗️]",
                "modulo": "INFORMES",
                "proposito_funcional": "Permite explorar, visualizar y descargar informes oficiales PDF o Excel a través de rutas autenticadas con token temporal `?dt=`.",
                "datos_modificados": "Ninguno (modo lectura segura sobre HTTPS).",
                "pasos_procedimiento": [
                    "Hacer clic en <b>'Centro de Reportes'</b> o <b>'Abrir informe'</b> en el panel lateral.",
                    "Seleccionar el archivo oficial; el sistema lo abre firmado con token efímero en el visor.",
                ],
                "resultado_obtenido": "Visualización o descarga segura del informe vigente.",
                "validaciones_advertencias": "No requiere permisos de escritura. Los enlaces firmados `?dt=` caducan por seguridad.",
            },
            {
                "nombre_boton": "Historial de Pedidos (Solo Lectura)",
                "icono_str": "[🧾]",
                "modulo": "INFORMES",
                "proposito_funcional": "Permite consultar en tarjetas responsivas (móvil/tablet/PC) el estado de preparación/despacho de pedidos históricos, bultos y transporte asignado sin poder alterarlos.",
                "datos_modificados": "Ninguno (consulta paginada de tabla `pedidos`).",
                "pasos_procedimiento": [
                    "Pulsar <b>'Historial de Pedidos'</b> y filtrar por cliente, remito o logística.",
                    "Inspeccionar el detalle del pedido y su estado actual.",
                ],
                "resultado_obtenido": "Seguimiento comercial e informativo al cliente sin riesgo operativo.",
                "validaciones_advertencias": "Los botones de edición, anulación y desarme permanecen deshabilitados para el rol Consulta.",
            },
            {
                "nombre_boton": "Compartir por correo / WhatsApp Web",
                "icono_str": "[✉️]",
                "modulo": "INFORMES",
                "proposito_funcional": "Reenvía el informe activo por SMTP o abre WhatsApp Web con resumen prediseñado de despacho.",
                "datos_modificados": "Ninguno en la base de existencias.",
                "pasos_procedimiento": [
                    "Pulsar <b>'Compartir por correo'</b> o <b>'WhatsApp Web'</b>.",
                    "Ingresar destinatario y confirmar envío.",
                ],
                "resultado_obtenido": "Comprobante remitido al destinatario autorizado.",
                "validaciones_advertencias": "Valida formato estándar de email o sesión activa en WhatsApp Web.",
            },
            {
                "nombre_boton": "Búsqueda Rápida (Ctrl+K / F2), Docking y Semáforo LAN",
                "icono_str": "[🔍]",
                "modulo": "HERRAMIENTAS Y ESTADO",
                "proposito_funcional": "Paleta universal para consultar stock/ubicación física, ajuste de posición del menú (5 orientaciones), Chat Interno y monitoreo de latencia RTT en cabecera.",
                "datos_modificados": "Ninguno en inventario.",
                "pasos_procedimiento": [
                    "Presionar <b>Ctrl + K</b> o <b>F2</b> e ingresar código SKU, barras o descripción.",
                    "Comprobar indicador verde (<50 ms) en cabecera para certeza de datos en vivo.",
                ],
                "resultado_obtenido": "Consulta instantánea de stock y ubicación en estantería.",
                "validaciones_advertencias": "Si el servidor no permite descarga directa por política LAN, usar `crear_acceso_directo_cliente.bat` con conexión HTTPS Privada.",
            },
        ],
    )

    return construir_cierre_manual_rol(
        doc, story, est, codigo_doc, titulo_doc, ruta_destino,
        incluir_distribucion=False, incluir_acta=False, version=VERSION_PROC_ACTUAL,
    )
