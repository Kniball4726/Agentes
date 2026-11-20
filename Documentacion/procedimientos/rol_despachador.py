# -*- coding: utf-8 -*-
"""Generador de Manual de Procedimiento y Uso Botón por Botón para el Rol Despachador."""

from __future__ import annotations

from pathlib import Path

from .fichas import (
    VERSION_PROC_ACTUAL,
    agregar_fichas_modulo,
    construir_cierre_manual_rol,
    iniciar_manual_rol,
)


def construir_manual_despachador(ruta_destino: Path) -> Path:
    """Genera el Manual de Procedimiento y Uso Botón por Botón para el Rol Despachador."""
    codigo_doc = "MAN-PROC-DSP-2026"
    titulo_doc = "Manual de Procedimiento y Uso de Botones (Rol Despachador)"
    doc, est, story = iniciar_manual_rol(
        ruta_destino,
        codigo_doc,
        titulo_doc,
        "Rol Despachador (Control de Muelle, Escaneo QR de Bultos, Despacho y Entregas)",
        "Guía técnica y operativa botón por botón: módulo exclusivo de Despacho de Pedidos, verificación bulto a bulto "
        "por código QR, avance de estados logísticos (Armado -> Despachado -> Entregado) y operación móvil con cola FIFO offline.",
    )

    agregar_fichas_modulo(
        story,
        est,
        "1. Principios de Segregación SoD y Responsabilidades del Rol Despachador",
        [],
        intro_texto=(
            "El perfil <b>Despachador</b> está diseñado exclusivamente para el control físico de salida en muelle de carga y expedición. "
            "Bajo el principio de Segregación de Funciones (ISO/IEC 27001 §5.3), el Despachador verifica y libera bultos de pedidos ya "
            "preparados por Operadores o Pickers, sin permisos para alterar existencias del catálogo maestro, crear remitos, "
            "modificar usuarios IAM ni revertir pedidos despachados hacia el estado Armado (facultad reservada a Administrador/Master)."
        ),
    )

    agregar_fichas_modulo(
        story,
        est,
        "2. Módulo Principal: DESPACHO DE PEDIDOS Y CONTROL DE BULTOS",
        [
            {
                "nombre_boton": "🚚 Despacho de Pedidos (Consola de Muelle)",
                "icono_str": "[🚚 Despacho]",
                "modulo": "DESPACHO Y LOGÍSTICA",
                "proposito_funcional": "Consola centralizada de expedición con pestañas de Pedidos Pendientes (Armados) y Despachados, buscador con debounce (250 ms), filtro por empresa de transporte y progreso de bultos escaneados.",
                "datos_modificados": "Actualiza `estado_despacho` (`armado` -> `despachado` -> `entregado`) y registra cada bulto verificado en `pedidos_bultos_despacho` y `logs_auditoria`.",
                "pasos_procedimiento": [
                    "Pulsar <b>'Despacho de Pedidos'</b> en la barra de acceso rápido o barra inferior móvil.",
                    "Filtrar por cliente, número de remito o empresa de logística.",
                    "Inspeccionar la cantidad de bultos requeridos (`X / N bultos`) de cada pedido listo en muelle.",
                ],
                "resultado_obtenido": "Control visual en tiempo real de todos los pedidos pendientes de carga a transporte.",
                "validaciones_advertencias": "No permite despachar pedidos anulados ni retroceder estados ya despachados sin autorización de Administrador.",
            },
            {
                "nombre_boton": "📷 Escaneo de Rótulos QR Bulto a Bulto",
                "icono_str": "[📷 Escanear QR]",
                "modulo": "DESPACHO Y LOGÍSTICA",
                "proposito_funcional": "Verifica cada caja o bulto mediante lectura óptica del rótulo QR (`REMITO:...|BULTO:i/N`). El pedido transiciona automáticamente a `DESPACHADO` únicamente cuando se completan los `N` bultos del remito.",
                "datos_modificados": "Tabla `pedidos_bultos_despacho` (control anti-duplicado por índice de bulto) y transición automática en `pedidos` al completar `N/N`.",
                "pasos_procedimiento": [
                    "En el campo de escaneo superior (o desde la app móvil `stockagent_mobile`), apuntar el lector láser o cámara al código QR del bulto.",
                    "Confirmar la señal acústica aguda (880 Hz) y el indicador de progreso `Bulto i de N verificado`.",
                    "Repetir con los bultos restantes hasta completar la totalidad del pedido.",
                ],
                "resultado_obtenido": "Garantía física 100% libre de bultos olvidados en muelle antes de la salida del camión.",
                "validaciones_advertencias": "Si se intenta escanear dos veces el mismo número de bulto (`i/N`), el sistema emite alerta sonora grave y rechaza el duplicado.",
            },
            {
                "nombre_boton": "✋ Despacho Manual con Confirmación de Bultos",
                "icono_str": "[✔ Despachar]",
                "modulo": "DESPACHO Y LOGÍSTICA",
                "proposito_funcional": "Permite registrar la salida de un pedido cuando la etiqueta QR física se encuentra dañada, exigiendo confirmación explícita de la cantidad exacta de bultos contados físicamente.",
                "datos_modificados": "Transiciona el pedido a `despachado` o `entregado` y asienta auditoría forense con el usuario Despachador.",
                "pasos_procedimiento": [
                    "Ubicar el pedido en la lista de pendientes y pulsar <b>'Despachar'</b>.",
                    "Ingresar o confirmar la cantidad exacta de bultos verificados físicamente.",
                    "Confirmar la operación en el diálogo de validación.",
                ],
                "resultado_obtenido": "Pedido marcado como despachado con trazabilidad de usuario y hora exacta.",
                "validaciones_advertencias": "Si la cantidad ingresada no coincide con los bultos declarados en el remito, la operación es bloqueada.",
            },
        ],
    )

    agregar_fichas_modulo(
        story,
        est,
        "3. App Móvil Nativa (`stockagent_mobile`), Modo Lector Láser y Herramientas",
        [
            {
                "nombre_boton": "📱 Despacho Móvil con Cola FIFO y Persistencia Offline",
                "icono_str": "[📱 App Móvil]",
                "modulo": "TERMINAL MÓVIL ANDROID / iOS",
                "proposito_funcional": "Operación en muelle desde colectores de datos (Zebra/Sunmi/Urovo) o smartphones sobre HTTPS con Certificate Pinning (TOFU), cola FIFO para ráfagas de escaneo y sincronización automática al recuperar Wi-Fi.",
                "datos_modificados": "Almacén seguro `AndroidKeyStore`, cola persistente `colaOffline` por usuario y endpoint `/api/v1/despacho/escanear-lote`.",
                "pasos_procedimiento": [
                    "Ingresar a la pestaña <b>'Despacho'</b> de la app móvil; activar <b>'Modo Lector Láser'</b> si se utiliza colector físico o <b>'Modo Claro Alto Contraste'</b> bajo luz solar directa.",
                    "Pistolear los rótulos QR de forma continua (la cola FIFO procesa cada lectura en orden sin descartar disparos rápidos).",
                    "Si el muelle pierde cobertura Wi-Fi, continuar escaneando: al reconectar, la app sincroniza automáticamente el lote acumulado.",
                ],
                "resultado_obtenido": "Expedición continua en muelle exterior o interior con 0 pérdida de lecturas.",
                "validaciones_advertencias": "Los errores de negocio o permisos (400/403/404) se informan al instante y no contaminan la cola offline.",
            },
            {
                "nombre_boton": "🔍 Historial de Pedidos, Chat Interno y Paleta F2",
                "icono_str": "[💬 / F2]",
                "modulo": "HERRAMIENTAS DE APOYO",
                "proposito_funcional": "Consulta de comprobantes y rótulos QR, comunicación en tiempo real con Operadores y Administración, y acceso al manual oficial firmado con `?dt=`.",
                "datos_modificados": "Mensajes en `chat_messages` y preferencias visuales del usuario.",
                "pasos_procedimiento": [
                    "Presionar <b>F2</b> o <b>Ctrl + K</b> para abrir rápidamente el módulo de Despacho o Escáner QR.",
                    "Usar <b>'Chat Interno'</b> mencionando `#REMITO` para reportar discrepancias en muelle.",
                    "Pulsar <b>'Manual de Uso'</b> para consultar este instructivo actualizado sobre HTTPS.",
                ],
                "resultado_obtenido": "Coordinación fluida entre preparación de pedidos y muelle de expedición.",
                "validaciones_advertencias": "La barra de navegación móvil adapta automáticamente sus destinos a las funciones autorizadas al Despachador.",
            },
        ],
        page_break=True,
    )

    return construir_cierre_manual_rol(
        doc,
        story,
        est,
        codigo_doc,
        titulo_doc,
        ruta_destino,
        incluir_distribucion=True,
        incluir_acta=True,
        version=VERSION_PROC_ACTUAL,
    )
