# -*- coding: utf-8 -*-
"""Generador de Manual de Procedimiento y Uso Botón por Botón para el Rol Picker."""

from __future__ import annotations

from pathlib import Path

from .fichas import (
    VERSION_PROC_ACTUAL,
    agregar_fichas_modulo,
    construir_cierre_manual_rol,
    iniciar_manual_rol,
)


def construir_manual_picker(ruta_destino: Path) -> Path:
    """Genera el Manual de Procedimiento y Uso Botón por Botón para el Rol Picker."""
    codigo_doc = "MAN-PROC-PCK-2026"
    titulo_doc = "Manual de Procedimiento y Uso de Botones (Rol Picker)"
    doc, est, story = iniciar_manual_rol(
        ruta_destino, codigo_doc, titulo_doc,
        "Rol Picker (Preparación Express, Escaneo ML, Movimientos Rápidos y Fábrica)",
        "Guía técnica y operativa botón por botón: botonera trío express (Descontar ML, Ingreso y Egreso), "
        "despacho masivo a Mercado Full, recepción de planta mediante Ingreso de Fábrica y herramientas de productividad.",
    )

    agregar_fichas_modulo(
        story, est,
        "1. Principios de Segregación SoD y Responsabilidades del Rol Picker", [],
        intro_texto=(
            "El perfil <b>Picker</b> está especializado en la agilidad de movimientos físicos y preparación e-commerce. "
            "Bajo Segregación de Funciones (ISO/IEC 27001), el Picker opera exclusivamente sobre <b>Descontar Mercado Libre</b>, "
            "<b>Descontar Mercado Full</b>, <b>Ingreso/Egreso Rápido de Mercadería</b>, <b>Ingreso de Fábrica</b> y herramientas "
            "comunes (Chat Interno, Preferencias, Manual y Búsqueda F2). Tiene restringido el acceso a Cierre de Jornada, Catálogo maestro, "
            "Clientes, Usuarios IAM y Auditoría."
        ),
    )

    agregar_fichas_modulo(
        story, est,
        "2. Panel de Acceso Rápido (Botonera Trío Express)",
        [
            {
                "nombre_boton": "⚡ Descontar Mercado Libre",
                "icono_str": "[🏷️ Descontar ML]",
                "modulo": "ACCESO RÁPIDO (CABECERA)",
                "proposito_funcional": "Apertura prioritaria del módulo de escaneo en vivo por código de barras o procesamiento de órdenes DOCX de Mercado Libre.",
                "datos_modificados": "Descuenta existencias SQLite-first en `productos.sqlite3` (exportable a `Productos.xlsx`); registra pedido y hash SHA-256.",
                "pasos_procedimiento": [
                    "Pulsar <b>'Descontar Mercado Libre'</b> en primera posición de cabecera (o en menú DESPACHO).",
                    "Escanear etiquetas/EAN-13 con pistola (usar <b>'↩️ Deshacer Último'</b> ante error) o cargar archivo `.docx`.",
                    "Pulsar <b>'Confirmar y Descontar'</b> para asentar la baja e imprimir rótulos si corresponde.",
                ],
                "resultado_obtenido": "Stock descontado de inmediato con trazabilidad por usuario Picker.",
                "validaciones_advertencias": "Protección de soft-locking e idempotencia anti-duplicados.",
            },
            {
                "nombre_boton": "⚡ Ingreso de Mercadería (Entrada Rápida)",
                "icono_str": "[➕ Ingreso]",
                "modulo": "ACCESO RÁPIDO Y MOVIMIENTOS",
                "proposito_funcional": "Recepción express por devoluciones de clientes, traslados internos o ajustes positivos con motivo tipificado obligatorio.",
                "datos_modificados": "Incrementa inventario SQLite-first en `productos.sqlite3` (sincronizable a `Productos.xlsx`); registra `stock_movements` (`ingreso_rapido`), auditoría y webhook.",
                "pasos_procedimiento": [
                    "Pulsar <b>'Ingreso de Stock'</b> en cabecera (o 'Ingreso de Mercadería' en menú lateral).",
                    "Escanear código de barras o SKU, indicar cantidad y seleccionar motivo obligatorio.",
                    "Presionar <b>'Confirmar Entrada'</b>.",
                ],
                "resultado_obtenido": "Incremento atómico del saldo con registro del Picker actuante.",
                "validaciones_advertencias": "Cantidad positiva y motivo obligatorio.",
            },
            {
                "nombre_boton": "⚡ Egreso de Mercadería (Salida Rápida)",
                "icono_str": "[➖ Egreso]",
                "modulo": "ACCESO RÁPIDO Y MOVIMIENTOS",
                "proposito_funcional": "Baja inmediata por roturas, mermas de depósito, muestras comerciales o consumo interno con motivo obligatorio.",
                "datos_modificados": "Descuenta existencias SQLite-first en `productos.sqlite3` (sincronizable a `Productos.xlsx`); registra `stock_movements` (`salida_rapida`), auditoría y webhook.",
                "pasos_procedimiento": [
                    "Pulsar <b>'Egreso de Stock'</b> en cabecera (o 'Egreso de Mercadería' en menú lateral).",
                    "Escanear artículo, indicar cantidad, elegir motivo y pulsar <b>'Confirmar Salida'</b>.",
                ],
                "resultado_obtenido": "Descuento instantáneo con comprobante digital auditable.",
                "validaciones_advertencias": "Alerta visual en rojo si el saldo proyectado queda negativo.",
            },
        ],
    )

    agregar_fichas_modulo(
        story, est,
        "3. Módulos: DESPACHO, FÁBRICA Y HERRAMIENTAS PICKER",
        [
            {
                "nombre_boton": "Descontar Mercado Full",
                "icono_str": "[🚚]",
                "modulo": "DESPACHO",
                "proposito_funcional": "Procesa lotes de envío masivo hacia bodegas de Mercado Libre Full a partir de la planilla Excel oficial.",
                "datos_modificados": "Descuento en bloque SQLite-first en `productos.sqlite3` (exportable a `Productos.xlsx`) con registro de pedido Full.",
                "pasos_procedimiento": [
                    "Pulsar <b>'Descontar Mercado Full'</b> en el menú lateral.",
                    "Adjuntar la planilla `.xlsx`, verificar unidades totales y confirmar envío.",
                ],
                "resultado_obtenido": "Comprobante consolidado de transferencia a Mercado Full.",
                "validaciones_advertencias": "Valida disponibilidad de stock antes de descontar el lote.",
            },
            {
                "nombre_boton": "Ingreso de Fábrica (Escáner por Bultos)",
                "icono_str": "[🏭]",
                "modulo": "MOVIMIENTOS DE STOCK",
                "proposito_funcional": "Recepción rápida desde planta productora mediante pistola de barras o SKU, con botones múltiplos de 12 y ajuste fino (+/-).",
                "datos_modificados": "Suma unidades SQLite-first en `productos.sqlite3` (sincronizable a `Productos.xlsx`); registra `stock_movements` (`ingreso_fabrica`).",
                "pasos_procedimiento": [
                    "Pulsar <b>'Ingreso de Fábrica'</b> en MOVIMIENTOS DE STOCK.",
                    "Seleccionar bulto estándar ([12], [24], [36]...) o unidades sueltas y escanear ítems.",
                    "Pulsar <b>'Confirmar Ingreso a Depósito'</b>.",
                ],
                "resultado_obtenido": "Mercadería de planta incorporada de forma atómica al stock disponible.",
                "validaciones_advertencias": "El Picker únicamente suma existencias (no puede sobrescribir saldos globales ni cargar archivos masivos admin).",
            },
            {
                "nombre_boton": "Paleta Rápida (F2), Chat Interno y Manual HTTPS (?dt=)",
                "icono_str": "[⚡]",
                "modulo": "HERRAMIENTAS",
                "proposito_funcional": "Lanzador por teclado (`F2` / `Ctrl+K`), comunicación en vivo con equipo de depósito/supervisión, interfaz responsiva en tarjetas y modales, preferencias visuales y apertura de `Manual_Picker.pdf` autenticado mediante token `?dt=` sobre HTTPS.",
                "datos_modificados": "Mensajes internos en tabla `chat_messages` y preferencias locales de interfaz.",
                "pasos_procedimiento": [
                    "Presionar <b>F2</b> para saltar rápido entre Entrada, Salida, Mercado Libre, Full o Fábrica.",
                    "Usar <b>'Chat Interno'</b> para coordinar con Operadores/Administración.",
                    "Pulsar <b>'Manual de Uso'</b> para consultar esta guía protegida en red LAN Privada.",
                ],
                "resultado_obtenido": "Velocidad máxima de preparación y soporte coordinado.",
                "validaciones_advertencias": "La paleta F2 solo expone las funciones autorizadas al perfil Picker.",
            },
        ],
        page_break=True,
    )

    return construir_cierre_manual_rol(
        doc, story, est, codigo_doc, titulo_doc, ruta_destino,
        incluir_distribucion=True, incluir_acta=False, version=VERSION_PROC_ACTUAL,
    )
