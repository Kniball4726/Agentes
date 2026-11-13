# -*- coding: utf-8 -*-
"""Generador de Manual de Procedimiento y Uso Botón por Botón para el Rol Administrador."""

from __future__ import annotations

from pathlib import Path

from .fichas import (
    VERSION_PROC_ACTUAL,
    agregar_fichas_modulo,
    construir_cierre_manual_rol,
    iniciar_manual_rol,
)


def construir_manual_administrador(ruta_destino: Path) -> Path:
    """Genera el Manual de Procedimiento y Uso Botón por Botón para el Rol Administrador."""
    codigo_doc = "MAN-PROC-ADM-2026"
    titulo_doc = "Manual de Procedimiento y Uso de Botones (Rol Administrador)"
    doc, est, story = iniciar_manual_rol(
        ruta_destino, codigo_doc, titulo_doc,
        "Rol Administrador (Jefatura de Depósito, Compras, Catálogo y Supervisión)",
        "Guía técnica y operativa botón por botón: administración del catálogo maestro, entradas de fábrica, "
        "auditoría descendente de Cierres de Operarios, radar de anomalías, heatmap de picking y usuarios.",
    )

    agregar_fichas_modulo(
        story, est,
        "1. Responsabilidades y Alcance del Rol Administrador", [],
        intro_texto=(
            "El Administrador ejerce la supervisión integral de existencias, compras y desempeño operativo del depósito. "
            "Este manual detalla los comandos organizados en: Catálogo y Stock, Ventas y Despachos (con <b>auditoría descendente "
            "de Cierres de Operarios</b>), Analítica y Picking, Resguardo e IAM."
        ),
    )

    agregar_fichas_modulo(
        story, est,
        "2. Panel de Acceso Rápido Express (Entrada, Salida, Gestionar Productos y Ver Stock)",
        [
            {
                "nombre_boton": "⚡ Entrada Rápida",
                "icono_str": "[➕ Entrada]",
                "modulo": "ACCESO RÁPIDO (CABECERA)",
                "proposito_funcional": "Recepción express de mercadería por devoluciones, transferencias o sobrantes con lector y motivo obligatorio.",
                "datos_modificados": "Incrementa stock en `productos.sqlite3` y `Productos.xlsx`; registra `stock_movements` y `logs_auditoria`.",
                "pasos_procedimiento": [
                    "Pulsar <b>'Entrada'</b> en la cabecera.",
                    "Escanear código de barras o SKU y definir cantidad.",
                    "Elegir motivo obligatorio y presionar <b>'Confirmar Entrada'</b>.",
                ],
                "resultado_obtenido": "Incremento inmediato en existencias y registro en auditoría.",
                "validaciones_advertencias": "Motivo y cantidad estrictamente obligatorios.",
            },
            {
                "nombre_boton": "⚡ Salida Rápida",
                "icono_str": "[➖ Salida]",
                "modulo": "ACCESO RÁPIDO (CABECERA)",
                "proposito_funcional": "Egreso express por roturas, mermas, muestras comerciales, consumo interno o devoluciones a proveedor con motivo obligatorio.",
                "datos_modificados": "Descuento en SQLite y `Productos.xlsx`; asiento en `stock_movements` y `logs_auditoria`.",
                "pasos_procedimiento": [
                    "Pulsar <b>'Salida'</b> en la cabecera, escanear código de barras/SKU e indicar cantidad.",
                    "Seleccionar motivo obligatorio y presionar <b>'Confirmar Salida'</b>.",
                ],
                "resultado_obtenido": "Baja inmediata de stock con trazabilidad.",
                "validaciones_advertencias": "Alerta preventiva en rojo si el saldo proyectado queda negativo.",
            },
            {
                "nombre_boton": "⚡ Gestionar Productos (Acceso Rápido)",
                "icono_str": "[📦 Catálogo]",
                "modulo": "ACCESO RÁPIDO (CABECERA)",
                "proposito_funcional": "Apertura instantánea del catálogo maestro de productos para altas de urgencia, ubicación en racks y stock mínimo.",
                "datos_modificados": "Tabla `productos` en SQLite y sincronización con `Productos.xlsx`.",
                "pasos_procedimiento": [
                    "Pulsar <b>'Gestionar Productos'</b> en la barra superior de acceso rápido.",
                    "Localizar el artículo o dar de alta un nuevo SKU y guardar.",
                ],
                "resultado_obtenido": "Catálogo actualizado al instante en todas las terminales LAN.",
                "validaciones_advertencias": "Requiere rol Administrador.",
            },
            {
                "nombre_boton": "⚡ Ver Stock en Tiempo Real",
                "icono_str": "[📊 Ver Stock]",
                "modulo": "ACCESO RÁPIDO Y CATÁLOGO",
                "proposito_funcional": "Consulta consolidada en vivo de todas las existencias con semáforo de quiebre, punto de reorden y ubicación física.",
                "datos_modificados": "Ninguno (consulta de solo lectura optimizada).",
                "pasos_procedimiento": [
                    "Pulsar <b>'Ver Stock'</b> en la cabecera o menú CATÁLOGO.",
                    "Filtrar por SKU, descripción o código de barras e inspeccionar semáforo (Normal/Bajo/Crítico).",
                ],
                "resultado_obtenido": "Radiografía en tiempo real del inventario sin bloquear despachos.",
                "validaciones_advertencias": "Permite refrescar saldos al instante con 'Actualizar'.",
            },
        ],
    )

    agregar_fichas_modulo(
        story, est,
        "3. Módulo: STOCK Y CATÁLOGO (Botón por Botón)",
        [
            {
                "nombre_boton": "Gestionar productos",
                "icono_str": "[📦]",
                "modulo": "CATÁLOGO E INVENTARIO",
                "proposito_funcional": "Administración maestra de productos: altas, modificaciones, EAN-13, stock mínimo/máximo y ubicación en estanterías.",
                "datos_modificados": "Tabla `productos` en SQLite, sincronización a `Productos.xlsx` y registro de auditoría.",
                "pasos_procedimiento": [
                    "Pulsar <b>'Gestionar productos'</b> en el panel lateral.",
                    "Para crear: presionar <b>'Nuevo Producto'</b>, ingresar SKU, descripción, código de barras, mínimos y ubicación (Rack/Módulo/Nivel).",
                    "Para editar: localizar el artículo, pulsar <b>'Editar'</b> y confirmar con <b>'Guardar'</b>.",
                ],
                "resultado_obtenido": "Ficha de producto actualizada en tiempo real para operarios y pickers.",
                "validaciones_advertencias": "No admite SKU duplicados ni stock mínimo negativo.",
            },
            {
                "nombre_boton": "Ajustar stock / Fábrica",
                "icono_str": "[📥]",
                "modulo": "INVENTARIO Y REPOSICIÓN",
                "proposito_funcional": "Recepción con escáner (múltiplos x12 y ajustes +/-), carga masiva de remitos de fábrica (.xlsx/.pdf) y sobrescritura controlada exclusiva de Administrador.",
                "datos_modificados": "Actualización de `productos.sqlite3` y `Productos.xlsx`; trazabilidad en `stock_movements`.",
                "pasos_procedimiento": [
                    "Pulsar <b>'Ajustar stock / Fábrica'</b>.",
                    "Usar pestaña Escáner Rápido o pestaña Por Archivo para remitos de fábrica.",
                    "(Solo arqueos formales) Marcar <b>'Sobrescribir stock'</b> y pulsar <b>'Aplicar a stock'</b>.",
                ],
                "resultado_obtenido": "Existencias regularizadas con respaldo documental.",
                "validaciones_advertencias": "La sobrescritura directa está bloqueada para Operador y Picker por principio SoD.",
            },
            {
                "nombre_boton": "Comparativa stock físico",
                "icono_str": "[🔄]",
                "modulo": "INVENTARIO Y REPOSICIÓN",
                "proposito_funcional": "Concilia planillas de recuento físico contra saldos digitales clasificando COINCIDE, FALTANTE o SOBRANTE.",
                "datos_modificados": "Genera informes comparativos PDF/Excel en `StockFisico/Comparativas/` sin mutar el saldo hasta aprobación.",
                "pasos_procedimiento": [
                    "Pulsar <b>'Comparativa stock físico'</b>, adjuntar planilla Excel y ejecutar comparación.",
                    "Exportar el reporte oficial en PDF o Excel para contabilidad.",
                ],
                "resultado_obtenido": "Balance formal de discrepancias físicas vs digitales.",
                "validaciones_advertencias": "Detecta mermas antes del cierre contable.",
            },
            {
                "nombre_boton": "Sincronizar con Excel / Generar pedido fábrica",
                "icono_str": "[🔁]",
                "modulo": "CATÁLOGO E INVENTARIO",
                "proposito_funcional": "Sincronización bidireccional SQLite <-> `Productos.xlsx` con backup previo y cálculo automático de reposición para SKUs bajo stock mínimo.",
                "datos_modificados": "Actualiza `Productos.xlsx`, crea `Productos_backup.xlsx` y genera planilla sugerida en `Fabrica/Pedidos_Sugeridos/`.",
                "pasos_procedimiento": [
                    "Usar <b>'Sincronizar con Excel'</b> tras ediciones masivas (cerrar Excel previamente).",
                    "Usar <b>'Generar pedido fábrica (Excel)'</b>, ajustar cantidades sugeridas y descargar la planilla.",
                ],
                "resultado_obtenido": "Catálogo Excel sincronizado y orden de reposición lista para Compras.",
                "validaciones_advertencias": "Evitar bloqueos manteniendo `Productos.xlsx` cerrado en Windows.",
            },
        ],
    )

    agregar_fichas_modulo(
        story, est,
        "4. Módulo: VENTAS Y DESPACHOS (Botón por Botón)",
        [
            {
                "nombre_boton": "Historial de Pedidos y Gestión de Clientes",
                "icono_str": "[🧾]",
                "modulo": "VENTAS Y DESPACHOS",
                "proposito_funcional": "Supervisión global de pedidos paginados en servidor (10/25/50/100) con soft-locking TTL 5 min, impresión en lote A4/térmico y administración del padrón de clientes.",
                "datos_modificados": "Consulta tabla `pedidos`; actualiza padrón `clientes` (CUIT, domicilio, logística).",
                "pasos_procedimiento": [
                    "Pulsar <b>'Historial de Pedidos'</b> para filtrar por cliente, logística o fecha e imprimir rótulos.",
                    "Pulsar <b>'Gestión de Clientes'</b> para alta o edición de destinatarios comerciales.",
                ],
                "resultado_obtenido": "Trazabilidad integral de despachos y padrón comercial al día.",
                "validaciones_advertencias": "La edición de bultos en pedidos abiertos permanece reservada al Operador.",
            },
            {
                "nombre_boton": "Cierres de Operarios",
                "icono_str": "[📋]",
                "modulo": "VENTAS Y DESPACHOS",
                "proposito_funcional": "Auditoría descendente (Cierre #ID más reciente arriba) de los cierres de jornada ejecutados por operarios, con resumen de pedidos, Hoja de Ruta, PDF, Excel y reenvío por correo.",
                "datos_modificados": "Consulta inmutable sobre tabla `cierres_jornada` y emisión/consulta de comprobantes.",
                "pasos_procedimiento": [
                    "Pulsar <b>'Cierres de Operarios'</b> en el panel lateral.",
                    "Filtrar por nombre de operario, número de cierre o fecha.",
                    "Usar acciones: <b>Ver Pedidos</b>, <b>Hoja de Ruta</b>, <b>PDF</b>, <b>Excel</b> o <b>Correo</b>.",
                ],
                "resultado_obtenido": "Control administrativo completo de cada cierre de turno.",
                "validaciones_advertencias": "Solo Operador ejecuta el cierre; Administrador audita de forma inmutable.",
            },
            {
                "nombre_boton": "Descontar Mercado Libre / Full / Sincronizar API",
                "icono_str": "[🏪]",
                "modulo": "VENTAS Y DESPACHOS",
                "proposito_funcional": "Ejecución y supervisión de canales Mercado Libre (escáner en vivo/DOCX), envíos a bodega Mercado Full (.xlsx) y sincronización OAuth 2.0 con la API oficial.",
                "datos_modificados": "Decrementos atómicos en SQLite y `Productos.xlsx` con hash SHA-256 e idempotencia.",
                "pasos_procedimiento": [
                    "Seleccionar 'Descontar Mercado Libre', 'Descontar Mercado Full' o 'Sincronizar Mercado Libre (API)'.",
                    "Revisar ítems extraídos y confirmar la deducción en tiempo real.",
                ],
                "resultado_obtenido": "Prevención de sobreventa online entre depósito físico y e-commerce.",
                "validaciones_advertencias": "Credenciales API resguardadas por rol Master.",
            },
        ],
        page_break=True,
    )

    agregar_fichas_modulo(
        story, est,
        "5. Módulos: ANALÍTICA, PICKING, USUARIOS Y RESGUARDO",
        [
            {
                "nombre_boton": "Métricas, Estadísticas, Radar de Anomalías y Heatmap",
                "icono_str": "[📈]",
                "modulo": "ANALÍTICA Y PICKING",
                "proposito_funcional": "Tablero KPI ejecutivo, ranking de rotación de salidas, detección estadística de anomalías (> mu + 2 sigma) y mapa térmico ABC para reubicación Golden Zone.",
                "datos_modificados": "Solo lectura analítica y actualización opcional de ubicaciones Rack/Nivel en slotting.",
                "pasos_procedimiento": [
                    "Consultar <b>'Métricas y Rendimiento'</b> o <b>'Estadísticas de salida'</b> por rango temporal.",
                    "Abrir <b>'Radar de anomalías'</b> para alertas tempranas y <b>'Heatmap y Picking'</b> para slotting.",
                ],
                "resultado_obtenido": "Reducción de tiempos de caminata y prevención de quiebres.",
                "validaciones_advertencias": "Requiere historial mínimo y ubicaciones de estantería asignadas.",
            },
            {
                "nombre_boton": "Centro de Reportes, Copia de Seguridad y Gestionar Usuarios",
                "icono_str": "[👥]",
                "modulo": "INFORMES, RESGUARDO E IAM",
                "proposito_funcional": "Acceso protegido (`?dt=`) a informes, respaldo `.zip` en `data/backups/` y alta/reseteo de cuentas Operador, Picker y Consulta.",
                "datos_modificados": "Tabla `users` (PBKDF2-SHA256) y archivos `Backup_StockAgent_*.zip`.",
                "pasos_procedimiento": [
                    "En <b>'Gestionar usuarios'</b>, crear o resetear cuentas Operador, Picker o Consulta.",
                    "En <b>'Copia de Seguridad'</b>, generar respaldo manual antes de inventarios anuales.",
                ],
                "resultado_obtenido": "Gestión delegada de personal y continuidad operativa.",
                "validaciones_advertencias": "Un Administrador NO puede crear ni modificar Administradores ni la cuenta Master (SoD).",
            },
            {
                "nombre_boton": "Docking Adaptativo (5 Posiciones), F2 y Semáforo LAN",
                "icono_str": "[📡]",
                "modulo": "INTERFAZ Y TELEMETRÍA",
                "proposito_funcional": "Reubicación del menú (Izquierda/Derecha/Arriba/Abajo/Oculto), lanzador F2 / Ctrl+K y monitor de latencia RTT en red HTTPS Privada.",
                "datos_modificados": "Preferencias locales de sesión.",
                "pasos_procedimiento": [
                    "Pulsar <b>F2</b> para navegar sin mouse y ajustar el docking según la pantalla.",
                    "Verificar LED verde (<50 ms) antes de importaciones masivas.",
                ],
                "resultado_obtenido": "Operación ergonómica y monitoreo constante de red LAN.",
                "validaciones_advertencias": "La paleta F2 solo muestra comandos autorizados al perfil activo.",
            },
        ],
        page_break=True,
    )

    return construir_cierre_manual_rol(
        doc, story, est, codigo_doc, titulo_doc, ruta_destino,
        incluir_distribucion=True, incluir_acta=True, version=VERSION_PROC_ACTUAL,
    )
