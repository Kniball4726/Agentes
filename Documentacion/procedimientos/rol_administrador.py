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
        "2. Botonera Operativa Principal del Administrador (Orden Oficial de Comandos)",
        [
            {
                "nombre_boton": "1. Gestionar inventario",
                "icono_str": "[📊 Inventario]",
                "modulo": "BOTONERA PRINCIPAL",
                "proposito_funcional": "Consulta consolidada en tiempo real de todas las existencias con semáforo de existencias (Normal/Bajo/Crítico), filtros por código/descripción y punto de reorden.",
                "datos_modificados": "Ninguno (consulta de solo lectura optimizada).",
                "pasos_procedimiento": [
                    "Pulsar <b>'Gestionar inventario'</b> (primer botón rojo del panel lateral o barra superior).",
                    "Filtrar por SKU, descripción o código de barras e inspeccionar el semáforo de disponibilidad.",
                    "Presionar 'Actualizar' para refrescar el conteo instantáneo.",
                ],
                "resultado_obtenido": "Visibilidad 360° del stock físico sin interrumpir despachos activos.",
                "validaciones_advertencias": "Accesible para consulta rápida sin requerir permisos de modificación.",
            },
            {
                "nombre_boton": "2. Planificar ingreso de fábrica",
                "icono_str": "[📥 Plan Fábrica]",
                "modulo": "BOTONERA PRINCIPAL",
                "proposito_funcional": "Carga y estructuración de remitos de planta, definición de tandas de recepción y cantidades esperadas para el equipo operativo.",
                "datos_modificados": "Registra el plan en `factory_plans` y prepara la recepción física en depósito.",
                "pasos_procedimiento": [
                    "Pulsar <b>'Planificar ingreso de fábrica'</b>.",
                    "Adjuntar la planilla de remito o ingresar los productos y cantidades enviadas por planta.",
                    "Confirmar la planificación para habilitar el control de ingreso al personal de depósito.",
                ],
                "resultado_obtenido": "Tanda de recepción planificada y visible en el Seguimiento Operativo en Vivo.",
                "validaciones_advertencias": "Evita ingresos desordenados cotejando unidades previstas vs reales.",
            },
            {
                "nombre_boton": "3. Planificar mercado full",
                "icono_str": "[🚚 Plan Full]",
                "modulo": "BOTONERA PRINCIPAL",
                "proposito_funcional": "Armado y estructuración de tandas de envío masivo hacia los centros de distribución de Mercado Envíos Full.",
                "datos_modificados": "Crea el plan de envío en `full_plans` con desglose de ítems y bultos requeridos.",
                "pasos_procedimiento": [
                    "Pulsar <b>'Planificar mercado full'</b>.",
                    "Cargar la planilla Excel suministrada por Mercado Libre.",
                    "Validar existencias y habilitar el picking guiado bulto a bulto.",
                ],
                "resultado_obtenido": "Plan operativo listo para el armado y escaneo por el personal de picking.",
                "validaciones_advertencias": "Verifica suficiencia de stock antes de iniciar la preparación física.",
            },
            {
                "nombre_boton": "4. Gestionar productos",
                "icono_str": "[📦 Catálogo]",
                "modulo": "BOTONERA PRINCIPAL",
                "proposito_funcional": "Administración maestra del catálogo: altas, bajas, modificación de códigos de barra EAN-13, umbrales y ubicación en racks (Slotting).",
                "datos_modificados": "Tabla `products` en SQLite, sincronización a `Productos.xlsx` y registro de auditoría.",
                "pasos_procedimiento": [
                    "Pulsar <b>'Gestionar productos'</b> en la botonera principal.",
                    "Para crear: presionar <b>'Nuevo Producto'</b>, ingresar SKU, descripción, código de barras, mínimos y ubicación.",
                    "Para editar: localizar el artículo, pulsar <b>'Editar'</b> y confirmar con <b>'Guardar'</b>.",
                ],
                "resultado_obtenido": "Catálogo maestro sincronizado y actualizado para todos los puestos de trabajo.",
                "validaciones_advertencias": "No admite códigos SKU duplicados.",
            },
            {
                "nombre_boton": "5. Ajuste de inventario",
                "icono_str": "[🔧 Ajuste Stock]",
                "modulo": "BOTONERA PRINCIPAL",
                "proposito_funcional": "Recepción controlada con lector (múltiplos x12 y ajustes +/-), arqueos de stock y regularizaciones de mercadería.",
                "datos_modificados": "Actualización de `productos.sqlite3` y `Productos.xlsx`; trazabilidad en `stock_movements`.",
                "pasos_procedimiento": [
                    "Pulsar <b>'Ajuste de inventario'</b>.",
                    "Escanear el artículo o seleccionarlo de la lista, indicar las unidades a ajustar (+ o -).",
                    "Ingresar el motivo del ajuste y confirmar la operación.",
                ],
                "resultado_obtenido": "Existencias regularizadas con trazabilidad auditable inmediata.",
                "validaciones_advertencias": "Los ajustes quedan asentados en la bitácora de auditoría con fecha y responsable.",
            },
            {
                "nombre_boton": "6. Generar Pedido",
                "icono_str": "[📝 Pedido Fábrica]",
                "modulo": "BOTONERA PRINCIPAL",
                "proposito_funcional": "Cálculo automatizado de reposición para productos bajo stock de seguridad y exportación de orden de compra a proveedores.",
                "datos_modificados": "Genera planilla sugerida en `Fabrica/Pedidos_Sugeridos/`.",
                "pasos_procedimiento": [
                    "Pulsar <b>'Generar Pedido'</b>.",
                    "Revisar el listado de sugerencias de compra calculadas según stock mínimo y rotación.",
                    "Descargar la orden generada en Excel para remitir a Compras o Planta.",
                ],
                "resultado_obtenido": "Planilla formal de pedido a proveedores lista para su procesamiento.",
                "validaciones_advertencias": "Permite ajustar manualmente las cantidades antes de emitir la orden.",
            },
            {
                "nombre_boton": "7. Sincronizar",
                "icono_str": "[🔁 Sincronizar]",
                "modulo": "BOTONERA PRINCIPAL",
                "proposito_funcional": "Gestión de catálogo Excel (SQLite-First): Importación masiva desde planillas hacia SQLite y exportación completa con pestaña de Inactivos. La operación diaria funciona autónomamente en SQLite sin bloqueos de archivo.",
                "datos_modificados": "Actualiza `productos.sqlite3` o exporta a `Productos.xlsx` según la acción seleccionada.",
                "pasos_procedimiento": [
                    "Pulsar <b>'Sincronizar'</b>.",
                    "Elegir <b>'Volcar Catálogo a Excel'</b> para generar la planilla actualizada con hojas de activos e inactivos, o <b>'Importar desde Excel'</b> para incorporar cambios externos.",
                ],
                "resultado_obtenido": "Control total entre la base de datos de producción y los archivos de intercambio en Excel.",
                "validaciones_advertencias": "Para volcar o exportar a Excel, asegurarse de tener cerrado el archivo en Microsoft Excel para evitar bloqueos del sistema operativo.",
            },
            {
                "nombre_boton": "8. Entrada y Salida Rápida (Botonera Dúo)",
                "icono_str": "[➕ Entrada / ➖ Salida]",
                "modulo": "BOTONERA PRINCIPAL (DEBAJO DE SINCRONIZAR)",
                "proposito_funcional": "Ingresos y egresos express por escaneo continuo para devoluciones, mermas, muestras comerciales o traslados.",
                "datos_modificados": "Ajuste directo en SQLite y Excel; asiento en `stock_movements`.",
                "pasos_procedimiento": [
                    "Pulsar <b>'Entrada'</b> o <b>'Salida'</b> según el movimiento a registrar.",
                    "Escanear el código de barras con lector óptico o teclado.",
                    "Indicar cantidad, motivo obligatorio y confirmar.",
                ],
                "resultado_obtenido": "Impacto inmediato en existencias y en los KPIs de flujo en tiempo real.",
                "validaciones_advertencias": "Motivo y cantidad estrictamente obligatorios.",
            },
        ],
    )

    agregar_fichas_modulo(
        story, est,
        "3. Centro de Control Ejecutivo y Analítica 360° en Tiempo Real",
        [
            {
                "nombre_boton": "Tablero de Flujo y KPIs en Vivo",
                "icono_str": "[📊 Centro de Control]",
                "modulo": "PANEL PRINCIPAL EJECUTIVO",
                "proposito_funcional": "Monitoreo integral de la jornada en tiempo real: Entradas Hoy, Salidas Hoy, Balance Neto (superávit o sobredemanda), Bultos Totales y Salud de Stock (Semáforo de Catálogo).",
                "datos_modificados": "Lectura en tiempo real sobre transacciones activas de SQLite.",
                "pasos_procedimiento": [
                    "El tablero se actualiza automáticamente con cada operación de depósito.",
                    "Hacer clic en la tarjeta <b>'Salud de Stock'</b> para abrir el catálogo consolidado.",
                ],
                "resultado_obtenido": "Visibilidad ejecutiva instantánea sin necesidad de generar reportes manuales.",
                "validaciones_advertencias": "El balance neto se destaca en verde (superávit) o rojo (demanda mayor a ingresos).",
            },
            {
                "nombre_boton": "Banner Adaptativo de Alerta de Quiebre de Stock",
                "icono_str": "[⚠️ Alerta Quiebre]",
                "modulo": "PANEL PRINCIPAL EJECUTIVO",
                "proposito_funcional": "Notificación destacada inteligente y 100% responsiva (móvil, tablet y escritorio) que alerta sobre productos sin stock o por debajo del umbral de seguridad, con desglose cuantitativo y sugerencia de compra a fábrica.",
                "datos_modificados": "Consulta en tiempo real sobre existencias y umbrales mínimos del catálogo.",
                "pasos_procedimiento": [
                    "Visualizar los badges dinámicos: <b>Agotados</b> (rojo), <b>En Quiebre</b> (amarillo) y <b>Sugerido</b> (azul).",
                    "Hacer clic en <b>'Vista rápida'</b> para desplegar/colapsar los productos más críticos directamente en el panel sin abrir ventanas emergentes.",
                    "Presionar <b>'Ver detalle'</b> para abrir el modal responsivo con buscador en vivo y filtros por estado.",
                    "Utilizar el acceso directo <b>'Generar pedido fábrica'</b> para descargar la orden en Excel (el operario realizará el control por escaneo en depósito).",
                ],
                "resultado_obtenido": "Acción preventiva inmediata ante riesgos de desabastecimiento en cualquier dispositivo.",
                "validaciones_advertencias": "El panel se auto-adapta al ancho de pantalla (apilamiento vertical en móviles y fila balanceada en PC).",
            },
            {
                "nombre_boton": "Mix por Canal, Evolución 7 Días y Productividad",
                "icono_str": "[📈 Gráficos de Flujo]",
                "modulo": "PANEL PRINCIPAL EJECUTIVO",
                "proposito_funcional": "Gráficas de barras de distribución por canal de venta (Mercado Libre, Full, Mayoristas, Canjes), historial de pedidos de los últimos 7 días, productividad de armadores en vivo y Radar de Reposición (Stock Crítico).",
                "datos_modificados": "Consulta analítica sobre pedidos despachados y vista `v_analisis_reposicion`.",
                "pasos_procedimiento": [
                    "Inspeccionar el <b>Mix de Salidas por Canal</b> para evaluar la presión logística.",
                    "Consultar la <b>Productividad de Armadores</b> para balancear cargas operativas.",
                    "Revisar el <b>Radar de Reposición</b> para identificar artículos agotados o en quiebre inminente.",
                ],
                "resultado_obtenido": "Detección temprana de cuellos de botella y prevención de quiebres de inventario.",
                "validaciones_advertencias": "El radar crítico calcula y exhibe automáticamente la cantidad sugerida a pedir.",
            },
            {
                "nombre_boton": "Gestión de Ambientes (Producción vs QA Sandbox)",
                "icono_str": "[🧪 Ambientes]",
                "modulo": "SUPERVISIÓN Y PRUEBAS",
                "proposito_funcional": "Aislamiento seguro para pruebas y capacitación sin riesgo de alterar la base de datos de producción de la empresa.",
                "datos_modificados": "Alterna entre directorios `data/` y `data_qa/`, así como `Descuentos/` y `Descuentos_QA/`.",
                "pasos_procedimiento": [
                    "Hacer clic en el botón <b>'Ambientes'</b> en la cabecera.",
                    "Seleccionar 'Ambiente QA' para pruebas de operarios o 'Producción' para operación real.",
                    "Confirmar el cambio (se refleja en el badge visual amarillo del encabezado).",
                ],
                "resultado_obtenido": "Entorno de pruebas totalmente estanco y seguro.",
                "validaciones_advertencias": "En ambiente QA los datos son sintéticos y no afectan existencias reales.",
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
                "proposito_funcional": "Auditoría descendente (Cierre #ID más reciente arriba) de los cierres de jornada ejecutados por operarios, con resumen de pedidos, Consolidado Administrador (suma total por producto de Mayoristas + Mercado Libre + Full + Salidas Rápidas), Hoja de Ruta, PDF, Excel y reenvío por correo.",
                "datos_modificados": "Consulta inmutable sobre tabla `cierres_jornada` y emisión/consulta de comprobantes (`Cierre_Admin_Consolidado` PDF/Excel).",
                "pasos_procedimiento": [
                    "Pulsar <b>'Cierres de Operarios'</b> en el panel lateral.",
                    "Filtrar por nombre de operario, número de cierre o fecha.",
                    "Usar acciones: <b>Ver Pedidos</b>, <b>Consolidado Admin</b> (suma total por SKU), <b>Hoja de Ruta</b>, <b>PDF</b>, <b>Excel</b> o <b>Correo</b>.",
                ],
                "resultado_obtenido": "Control administrativo completo de cada cierre de turno con sumatoria consolidada por producto.",
                "validaciones_advertencias": "Solo Operador ejecuta el cierre; Administrador audita de forma inmutable.",
            },
            {
                "nombre_boton": "Descontar Mercado Libre / Full / Sincronizar API",
                "icono_str": "[🏪]",
                "modulo": "VENTAS Y DESPACHOS",
                "proposito_funcional": "Ejecución y supervisión de canales Mercado Libre (escáner en vivo/DOCX), envíos a bodega Mercado Full (.xlsx) y sincronización OAuth 2.0 con la API oficial.",
                "datos_modificados": "Decrementos atómicos en base de datos SQLite principal (con exportación opcional a Excel) usando hash SHA-256 e idempotencia.",
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
                "proposito_funcional": "Centro Unificado de Reportes SQLite (`Movimientos Estándar`, `Descuentos por Canal`, `Planilla Toma de Inventario Físico` ciega/valorizada, `Auditoría Física`, `Kardex SKU`, `Rotación y Cobertura`), acceso protegido (`?dt=`), respaldo `.zip` en `data/backups/` y alta/reseteo de cuentas Operador, Picker y Consulta.",
                "datos_modificados": "Consultas SQLite de solo lectura, reportes PDF A4/Excel, tabla `users` (PBKDF2-SHA256) y archivos `Backup_StockAgent_*.zip`.",
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
