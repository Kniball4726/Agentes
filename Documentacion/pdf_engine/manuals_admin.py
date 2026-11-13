# -*- coding: utf-8 -*-
"""Generador de manual ISO/BPMN/APA y POEs para el rol Administrador."""

from __future__ import annotations

from pathlib import Path

from reportlab.lib.units import cm
from reportlab.platypus import PageBreak, Paragraph, Spacer

from .canvas_iso import crear_canvas_iso_upel
from .components_apa import (
    agregar_diagrama_bpmn_apa,
    agregar_ficha_procedimiento_apa,
    agregar_tabla_apa_completa,
    crear_caja_alerta_iso,
)
from .constants import (
    VERSION_SOP_ACTUAL,
    agregar_titulo_capitulo,
    crear_documento_iso,
    crear_filas_tabla_apa,
)
from .forms_sgc import (
    agregar_acta_capacitacion_personal,
    agregar_formulario_firmas_autorizadas_iso,
    agregar_glosario_terminos_iso_upel,
    agregar_matriz_distribucion_copias,
    agregar_portada_iso_upel,
    agregar_referencias_bibliograficas_apa_upel,
    agregar_requisitos_infraestructura_iso,
    agregar_tarjeta_referencia_rapida,
)


def agregar_poes_administrador(
    story: list,
    est: dict,
    tabla_inicio: int = 3,
    figura_inicio: int = 1,
) -> None:
    """Inserta los 4 Procedimientos de Supervisión Logística (POE-ADM-01..04) con sus diagramas BPMN."""
    agregar_ficha_procedimiento_apa(
        story, est, tabla_inicio,
        "POE-ADM-01", "Gestión del Catálogo Maestro y Parámetros de Seguridad",
        "Mantener actualizadas las fichas técnicas de productos, códigos de barra, precios y niveles de stock de seguridad.",
        "Compras / Proveedores", "Ficha técnica de producto, alta de nuevos códigos",
        "Catálogo maestro actualizado en SQLite y respaldo en Productos.xlsx", "Depósito / Ventas",
        "R: Administrador | A: Gerencia | I: Operarios",
        ["Sesión de Administrador activa.", "Respaldo automático previo de Productos.xlsx en disco."],
        [
            "En la sección 'Gestionar productos', se procede a dar de alta artículos indicando SKU, descripción y barras.",
            "Se define el <b>Stock Mínimo</b> (disparador automático de alertas de compra) y el <b>Stock Máximo</b>.",
            "Se asigna la ubicación física en estantería (Rack A-D, Módulo 1-4, Nivel 1-3) para optimizar el picking.",
            "Se pulsa el botón <b>'Sincronizar con Excel'</b> para volcar todos los saldos atómicamente a Productos.xlsx.",
        ],
        ["Artículos activos en SQLite y Excel.", "Trazabilidad de alta asentada en auditoría forense."],
        "Correspondencia unívoca entre SKU y descripción sin solapamiento de registros.",
    )
    agregar_diagrama_bpmn_apa(
        story, est, figura_inicio,
        "Flujograma BPMN 2.0: Gestión de Catálogo y Parámetros (POE-ADM-01)",
        lanes=["Administrador", "Sistema StockAgent", "Almacén Central"],
        nodos=[
            {"tipo": "inicio", "x": 105, "y": 96, "label": "Alta SKU"},
            {"tipo": "tarea", "x": 118, "y": 96, "w": 58, "h": 22, "texto": ["Definir SKU/Barras", "Fijar Stock Mín."]},
            {"tipo": "tarea", "x": 195, "y": 58, "w": 62, "h": 22, "texto": ["Validar Duplicidad", "Guardar SQLite"]},
            {"tipo": "decision", "x": 280, "y": 58, "label": "¿Sincronizar?"},
            {"tipo": "tarea", "x": 310, "y": 58, "w": 62, "h": 22, "texto": ["Volcar a Excel", "Asentar Audit"]},
            {"tipo": "fin", "x": 410, "y": 19, "label": "Catálogo OK"},
        ],
        flujos=[(111.5, 96, 118, 96), (176, 96, 195, 58), (257, 58, 271, 58), (289, 58, 310, 58), (372, 58, 403, 19)],
    )

    story.append(PageBreak())

    agregar_ficha_procedimiento_apa(
        story, est, tabla_inicio + 1,
        "POE-ADM-02", "Recepción de Fábrica, Ajustes y Comparativa de Stock Físico",
        "Incorporar mercadería recibida y conciliar diferencias entre recuento físico y saldo digital.",
        "Fábrica / Proveedores", "Remito de fábrica (.xlsx, .xls o .pdf) o planilla de recuento",
        "Stock incrementado, reporte comparativo (COINCIDE/FALTANTE/SOBRANTE)", "Auditoría / Contabilidad",
        "R: Administrador | A: Gerencia",
        ["La mercadería física se encuentra en muelle de carga debidamente paletizada."],
        [
            "En 'Ajustar stock / Entrada Fábrica', se carga la planilla del proveedor para sumar existencias en lote.",
            "Para mermas o roturas, se ingresa el código y cantidad negativa adjuntando motivo justificatorio.",
            "Para inventarios masivos: se adjunta la planilla de recuento en 'Comparativa stock físico' y se presiona 'Comparar'.",
            "Se exporta el reporte comparativo oficial en PDF/Excel para sustento contable y auditoría de inventarios.",
        ],
        ["Existencias actualizadas en SQLite.", "Asiento de movimiento registrado en `stock_movements`."],
        "Ausencia de discrepancias no justificadas entre comprobante mayorista y stock digital.",
    )
    agregar_diagrama_bpmn_apa(
        story, est, figura_inicio + 1,
        "Flujograma BPMN 2.0: Entrada de Fábrica y Comparativa (POE-ADM-02)",
        lanes=["Administrador", "Sistema StockAgent", "Auditoría Contable"],
        nodos=[
            {"tipo": "inicio", "x": 105, "y": 96, "label": "Recepción"},
            {"tipo": "tarea", "x": 118, "y": 96, "w": 58, "h": 22, "texto": ["Adjuntar Remito", "Ejecutar Entrada"]},
            {"tipo": "tarea", "x": 195, "y": 58, "w": 62, "h": 22, "texto": ["Incrementar Saldo", "Generar Asiento"]},
            {"tipo": "decision", "x": 280, "y": 58, "label": "¿Discrepancia?"},
            {"tipo": "tarea", "x": 310, "y": 19, "w": 62, "h": 22, "texto": ["Emitir Comparativo", "Reportar Merma"]},
            {"tipo": "fin", "x": 410, "y": 58, "label": "Stock Ajustado"},
        ],
        flujos=[(111.5, 96, 118, 96), (176, 96, 195, 58), (257, 58, 271, 58), (289, 58, 310, 19), (372, 19, 403, 58)],
    )

    agregar_ficha_procedimiento_apa(
        story, est, tabla_inicio + 2,
        "POE-ADM-03", "Generación Automática de Pedido a Fábrica (Planilla de Reposición)",
        "Calcular la reposición óptima de artículos en quiebre o cercanos al stock mínimo.",
        "Bases SQLite (saldos vigentes)", "Umbrales de stock mínimo/máximo configurados",
        "Planilla Excel oficial con formato corporativo de pedido a proveedores", "Proveedores / Compras",
        "R: Administrador | A: Gerencia Operaciones",
        ["Catálogo maestro debidamente parametrizado con niveles de stock de seguridad."],
        [
            "En el menú de navegación lateral, se pulsa <b>'Generar pedido fábrica (Excel)'</b>.",
            "El sistema filtra automáticamente los artículos en quiebre o con saldo inferior al stock mínimo.",
            "Se examinan las cantidades calculadas y se efectúan ajustes estacionales si correspondiere.",
            "Se presiona el comando <b>'Generar Pedido a Fábrica'</b> y se descarga la planilla oficial para compras.",
        ],
        ["Planilla formal exportada en la carpeta Descuentos/.", "Registro de la solicitud en el historial."],
        "Cantidad sugerida suficiente para cubrir el período de abastecimiento sin superar el stock máximo.",
    )
    agregar_diagrama_bpmn_apa(
        story, est, figura_inicio + 2,
        "Flujograma BPMN 2.0: Pedido Automático a Proveedores (POE-ADM-03)",
        lanes=["Administrador", "Sistema StockAgent", "Área de Compras"],
        nodos=[
            {"tipo": "inicio", "x": 105, "y": 96, "label": "Quiebre"},
            {"tipo": "tarea", "x": 118, "y": 58, "w": 58, "h": 22, "texto": ["Filtrar Saldos", "Calcular Brechas"]},
            {"tipo": "decision", "x": 195, "y": 58, "label": "¿Demanda OK?"},
            {"tipo": "tarea", "x": 230, "y": 96, "w": 62, "h": 22, "texto": ["Revisión Supervisor", "Ajuste Estacional"]},
            {"tipo": "tarea", "x": 315, "y": 19, "w": 62, "h": 22, "texto": ["Exportar Excel", "Despachar a Fab."]},
            {"tipo": "fin", "x": 410, "y": 19, "label": "Pedido Listo"},
        ],
        flujos=[(111.5, 96, 118, 58), (176, 58, 186, 58), (204, 58, 230, 96), (292, 96, 315, 19), (377, 19, 403, 19)],
    )

    story.append(PageBreak())

    agregar_ficha_procedimiento_apa(
        story, est, tabla_inicio + 3,
        "POE-ADM-04", "Analítica, Radar de Anomalías y Optimización de Picking (Slotting ABC)",
        "Supervisar desvíos de demanda y optimizar la disposición espacial ergonómica del depósito.",
        "Historial de movimientos (`stock_movements`)", "Historial de pedidos despachados",
        "Alertas tempranas de agotamiento, mapa de calor térmico, plan de reubicación", "Jefatura de Depósito",
        "R: Administrador | I: Operarios / Pickers",
        ["Registro histórico mínimo de 14 días para análisis estadístico representativo."],
        [
            "En 'Radar de anomalías', se monitorean picos de demanda (> μ + 2σ) y coberturas críticas menores a tres días.",
            "En 'Heatmap y Picking', se inspecciona la matriz Pareto ABC (75% A, 15% B, 10% C).",
            "Se constata la ubicación de artículos Clase A. Se pulsa <b>'Reubicar'</b> hacia la <i>Golden Zone</i> ergonómica.",
        ],
        ["Ubicaciones físicas actualizadas en SQLite.", "Disminución comprobada en los tiempos de recorrido de operarios."],
        "Índice de eficiencia de slotting superior al 85% y reducción de fatiga en operarios.",
    )
    agregar_diagrama_bpmn_apa(
        story, est, figura_inicio + 3,
        "Flujograma BPMN 2.0: Radar de Anomalías y Slotting (POE-ADM-04)",
        lanes=["Administrador", "Sistema StockAgent", "Depósito Operativo"],
        nodos=[
            {"tipo": "inicio", "x": 105, "y": 96, "label": "Supervisión"},
            {"tipo": "tarea", "x": 118, "y": 58, "w": 58, "h": 22, "texto": ["Evaluar Pareto ABC", "Detectar Desvíos"]},
            {"tipo": "decision", "x": 195, "y": 58, "label": "¿Anomalía?"},
            {"tipo": "tarea", "x": 230, "y": 96, "w": 62, "h": 22, "texto": ["Ajustar Slotting", "Golden Zone"]},
            {"tipo": "tarea", "x": 315, "y": 19, "w": 62, "h": 22, "texto": ["Reubicar Racks", "Notificar Operador"]},
            {"tipo": "fin", "x": 410, "y": 19, "label": "Picking OK"},
        ],
        flujos=[(111.5, 96, 118, 58), (176, 58, 186, 58), (204, 58, 230, 96), (292, 96, 315, 19), (377, 19, 403, 19)],
    )


def construir_manual_administrador(ruta_destino: Path) -> Path:
    """Compila el Manual del Rol Administrador bajo Normas ISO, BPMN y APA/UPEL."""
    doc, est, story = crear_documento_iso(ruta_destino)
    codigo_doc = "SOP-STK-ADM-2026-v2.2"
    titulo_doc = "Manual de Supervisión y Logística (Rol Administrador)"

    agregar_portada_iso_upel(
        story, est, codigo_doc, titulo_doc,
        "Rol Administrador (Jefatura de Depósito, Compras y Supervisión)",
        "Procedimientos Operativos Estandarizados (POE / SOP) según Normas ISO 9001:2015, ISO/IEC/IEEE 26514:2022,<br/>"
        "modelado BPMN 2.0 (Bizagi) y pautas UPEL para catálogo maestro, entradas de fábrica, analítica y gestión IAM",
        version=VERSION_SOP_ACTUAL,
    )

    agregar_titulo_capitulo(story, est, "1. Marco Normativo, Alcance y Responsabilidades (ISO 9001 §4.3 & §5.3)")
    story.append(Paragraph(
        "El presente documento normaliza las atribuciones de supervisión analítica, administración del catálogo maestro "
        "(`Productos.xlsx`), gestión de compras sugeridas, conciliación física y cuentas operativas.",
        est["body_sangria"],
    ))
    story.append(Spacer(1, 2))
    story.append(crear_caja_alerta_iso(
        "POLÍTICA SoD: DELEGACIÓN DE RESTAURACIÓN A MASTER (ISO 27001)",
        "Por inmutabilidad contable, la potestad de <b>Restauración de Documentos</b> pertenece exclusivamente al perfil "
        "<b>Master</b>. El Administrador supervisa y gestiona, sin revertir lotes históricos.",
        "sod",
    ))

    story.append(Spacer(1, 4))
    agregar_titulo_capitulo(story, est, "2. Procedimientos de Supervisión Estandarizados (SOP / POE)")
    agregar_poes_administrador(story, est, tabla_inicio=3, figura_inicio=1)

    agregar_titulo_capitulo(story, est, "3. Control de Registros y No Conformidades Administrativas (ISO 9001 §7.5.3 & §10.2)", page_break=True)
    filas_radm = [
        ("Planilla de Entrada de Fábrica", "Digital (.xlsx/.pdf)", "data/pedidos_archivos/", "5 Años", "Jefe de Depósito"),
        ("Planilla de Pedido a Fábrica", "Digital (.xlsx)", "Descuentos/", "3 Años", "Encargado de Compras"),
        ("Informe Comparativo Stock Físico", "PDF y XLS", "Descuentos/ y data/pedidos_archivos/", "5 Años", "Administrador"),
        ("Base de Datos Maestra de Productos", "SQLite (`productos.sqlite3`)", "data/productos.sqlite3", "Permanente", "Master / Admin"),
        ("Alertas de Demanda Anómala", "JSON (`admin_notifications`)", "data/pedidos.sqlite3", "1 Año", "Administrador"),
    ]
    agregar_tabla_apa_completa(
        story, est, 7,
        "Matriz de Control de Registros de Calidad para el Rol Administrador",
        crear_filas_tabla_apa(
            ["Registro de Calidad", "Soporte", "Ubicación de Custodia", "Retención", "Responsable"],
            filas_radm, est, ["td_apa", "td_apa_center", "td_apa", "td_apa_center", "td_apa"], negrita_col0=True,
        ),
        [3.8 * cm, 2.2 * cm, 4.2 * cm, 2.0 * cm, 3.3 * cm],
        "Control documental bajo Cláusula 7.5.3 de la Norma ISO 9001:2015.",
    )

    story.append(Spacer(1, 4))
    filas_err_adm = [
        ("NC-ADM-01: Discrepancia Físico", "Ajuste no registrado o merma.", "Aplicar ajuste justificado con remito interno.", "Capacitar en registro oportuno de mermas."),
        ("NC-ADM-02: Agotamiento Inesperado", "Pico extraordinario de ventas online.", "Emitir pedido urgente a fábrica con POE-ADM-03.", "Ajustar umbral de Stock Mínimo en catálogo."),
        ("NC-ADM-03: Bloqueo de Operario", "5 contraseñas erróneas consecutivas.", "En 'Gestionar usuarios', pulsar desbloqueo.", "Capacitar en uso de contraseñas seguras."),
    ]
    agregar_tabla_apa_completa(
        story, est, 8,
        "Tratamiento de No Conformidades Administrativas y Acciones Correctivas",
        crear_filas_tabla_apa(
            ["No Conformidad", "Causa Raíz", "Acción Inmediata (Corrección)", "Acción Preventiva"],
            filas_err_adm, est, ["td_apa_bold_center", "td_apa", "td_apa", "td_apa"],
        ),
        [3.0 * cm, 3.5 * cm, 4.5 * cm, 4.5 * cm],
        "Acciones correctivas formalizadas según la Cláusula 10.2 de la Norma ISO 9001:2015.",
    )

    agregar_titulo_capitulo(story, est, "4. Infraestructura de Supervisión y Control Institucional", page_break=True)
    agregar_requisitos_infraestructura_iso(story, est)
    agregar_matriz_distribucion_copias(story, est, 9)
    agregar_formulario_firmas_autorizadas_iso(story, est, 10)

    agregar_titulo_capitulo(story, est, "5. Registros de Inducción, Referencia Rápida y Terminología", page_break=True)
    agregar_acta_capacitacion_personal(story, est, 11)
    agregar_tarjeta_referencia_rapida(story, est)
    agregar_glosario_terminos_iso_upel(story, est)
    agregar_referencias_bibliograficas_apa_upel(story, est)

    doc.build(story, canvasmaker=crear_canvas_iso_upel(codigo_doc, titulo_doc, VERSION_SOP_ACTUAL))
    return ruta_destino
