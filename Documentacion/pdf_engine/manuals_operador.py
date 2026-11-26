# -*- coding: utf-8 -*-
"""Generador de manual ISO/BPMN/APA y POEs para el rol Operador."""

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


def agregar_poes_operador(
    story: list,
    est: dict,
    tabla_inicio: int = 3,
    figura_inicio: int = 1,
) -> None:
    """Inserta los 4 Procedimientos Operativos Estandarizados (POE-OPE-01..04) con sus diagramas BPMN."""
    agregar_ficha_procedimiento_apa(
        story, est, tabla_inicio,
        "POE-OPE-01", "Carga y Descuento de Remitos Mayoristas (PDF) y Canjes (Excel)",
        "Descontar existencias y asentar el pedido en la jornada de forma atómica en SQLite y Productos.xlsx.",
        "Área Comercial / Clientes", "Remito digital (.pdf) o Planilla de Canje (.xlsx)",
        "Pedido registrado, stock decrementado, hash SHA-256 asentado", "Transporte / Empaque",
        "R: Operario | A: Administrador | I: Chofer",
        ["El servidor HTTPS se encuentra activo en el puerto 8550 (red LAN Privada).", "El catálogo maestro se encuentra plenamente sincronizado."],
        [
            "Se procede a pulsar el comando <b>'Seleccionar archivo'</b> para adjuntar el comprobante (.pdf o .xlsx).",
            "Se constata que el sistema haya extraído y separado con exactitud el código numérico de la razón social (ej. <code>00714 - DIETETICA SABORES</code>).",
            "Se gradúa la cantidad de bultos acondicionados mediante los pulsadores <code>[-]</code> y <code>[+]</code> (mínimo un bulto).",
            "Se selecciona con carácter obligatorio la empresa de transporte en el menú desplegable de logística.",
            "Se valida la fecha de retiro, la cual es pre-completada por el motor a partir de la fecha de despacho del documento.",
            "Se pulsa el botón <b>'Cargar y Descontar'</b>. El sistema emite una señal acústica en 880 Hz que certifica la transacción.",
        ],
        ["El pedido se asienta en la tabla `pedidos` con cierre_id = NULL.", "El archivo binario se almacena en `data/pedidos_archivos/`."],
        "El comprobante no debe registrar coincidencia previa de hash SHA-256 y el inventario resultante debe ser mayor o igual a cero.",
    )
    agregar_diagrama_bpmn_apa(
        story, est, figura_inicio,
        "Flujograma BPMN 2.0: Carga y Descuento de Remitos (POE-OPE-01)",
        lanes=["Operario Depósito", "Sistema StockAgent", "Muelle / Despacho"],
        nodos=[
            {"tipo": "inicio", "x": 105, "y": 96, "label": "Remito"},
            {"tipo": "tarea", "x": 118, "y": 96, "w": 58, "h": 22, "texto": ["Adjuntar Remito", "Ajustar Bultos"]},
            {"tipo": "tarea", "x": 195, "y": 58, "w": 62, "h": 22, "texto": ["Validar SHA-256", "Descontar Stock"]},
            {"tipo": "decision", "x": 280, "y": 58, "label": "¿Duplicado?"},
            {"tipo": "tarea", "x": 310, "y": 96, "w": 60, "h": 22, "texto": ["Imprimir Rótulo", "Paletizar Bulto"]},
            {"tipo": "fin", "x": 410, "y": 19, "label": "Muelle OK"},
        ],
        flujos=[(111.5, 96, 118, 96), (176, 96, 195, 58), (257, 58, 271, 58), (289, 58, 310, 96), (370, 96, 403, 19)],
    )

    story.append(PageBreak())

    agregar_ficha_procedimiento_apa(
        story, est, tabla_inicio + 1,
        "POE-OPE-02", "Descuento Masivo de Mercado Libre Full (Planilla Excel)",
        "Procesar planillas oficiales de despacho Full directamente desde el menú lateral de depósito.",
        "Mercado Libre / Depósito", "Planilla oficial de despacho Full (.xlsx / .xls)",
        "Descuento consolidado en bloque, actualización de Productos.xlsx", "Jefatura de Operaciones",
        "R: Operario / Picker | A: Administrador | I: Depósito Full",
        ["La planilla oficial de Mercado Libre Full ha sido descargada de la plataforma.", "Sesión autenticada con rol Operador, Picker o Administrador."],
        [
            "En la barra de navegación lateral, se pulsa el botón <b>'Descontar Mercado Full'</b>.",
            "Se selecciona el archivo Excel oficial suministrado por Mercado Libre.",
            "El sistema procesa automáticamente las columnas y muestra la vista previa con el total de artículos a descontar.",
            "Se confirma la operación. El motor descuenta el inventario de forma consolidada en una sola transacción.",
            "Se verifica el mensaje de éxito en pantalla y se actualiza la copia de Productos.xlsx.",
        ],
        ["Existencias actualizadas en SQLite (`productos.sqlite3`) y en `Productos.xlsx`.", "Movimiento registrado en `stock_movements`."],
        "Concordancia entre los totales de la planilla y las unidades decrementadas sin errores de lectura.",
    )
    agregar_diagrama_bpmn_apa(
        story, est, figura_inicio + 1,
        "Flujograma BPMN 2.0: Descuento Masivo Mercado Libre Full (POE-OPE-02)",
        lanes=["Operario Depósito", "Sistema StockAgent", "Mercado Libre Full"],
        nodos=[
            {"tipo": "inicio", "x": 105, "y": 96, "label": "Planilla"},
            {"tipo": "tarea", "x": 118, "y": 96, "w": 58, "h": 22, "texto": ["Abrir Menú Full", "Adjuntar Excel"]},
            {"tipo": "tarea", "x": 195, "y": 58, "w": 62, "h": 22, "texto": ["Parsear Columnas", "Verificar Stock"]},
            {"tipo": "decision", "x": 280, "y": 58, "label": "¿Stock OK?"},
            {"tipo": "tarea", "x": 310, "y": 58, "w": 62, "h": 22, "texto": ["Descuento Bloque", "Actualizar Excel"]},
            {"tipo": "fin", "x": 410, "y": 19, "label": "Full Listo"},
        ],
        flujos=[(111.5, 96, 118, 96), (176, 96, 195, 58), (257, 58, 271, 58), (289, 58, 310, 58), (372, 58, 403, 19)],
    )

    agregar_ficha_procedimiento_apa(
        story, est, tabla_inicio + 2,
        "POE-OPE-03", "Rotulación Térmica Continua y Validación de Códigos QR",
        "Generar e imprimir etiquetas adhesivas individuales por cada bulto acondicionado.",
        "Pedido descontado en POE-OPE-01", "Identificador de pedido (`pedido_id`) y cantidad de bultos",
        "Rótulos QR impresos (80 mm continuo), bultos identificados", "Transportista / Cliente",
        "R: Operario | I: Transporte",
        ["La impresora térmica de 80 mm se encuentra encendida y con papel continuo cargado."],
        [
            "En la vista de Pedidos Preparados, se ubica el comprobante y se pulsa el botón <b>'Ver Rótulos'</b>.",
            "El sistema genera una secuencia de etiquetas optimizada para rollo térmico continuo (ancho 80 mm).",
            "Cada etiqueta incluye código QR de alta resolución con el remito y el correlativo del bulto (ej. <code>Bulto 1 de 3</code>).",
            "Se adhiere cada rótulo sobre la cara superior visible del bulto correspondiente.",
            "Se efectúa un escaneo de prueba con la pistola óptica o celular para certificar legibilidad inmediata.",
        ],
        ["Código QR legible mediante pistola óptica o dispositivo móvil."],
        "Lectura satisfactoria del código QR constatando número de remito y correlativo de bulto.",
    )
    agregar_diagrama_bpmn_apa(
        story, est, figura_inicio + 2,
        "Flujograma BPMN 2.0: Rotulación Térmica y Validación QR (POE-OPE-03)",
        lanes=["Operario Depósito", "Sistema StockAgent", "Paletizado Físico"],
        nodos=[
            {"tipo": "inicio", "x": 105, "y": 96, "label": "Bultos"},
            {"tipo": "tarea", "x": 118, "y": 96, "w": 58, "h": 22, "texto": ["Ubicar Pedido", "Pulsar Ver QR"]},
            {"tipo": "tarea", "x": 195, "y": 58, "w": 62, "h": 22, "texto": ["Generar Vector QR", "Correlativo 1..N"]},
            {"tipo": "tarea", "x": 280, "y": 96, "w": 60, "h": 22, "texto": ["Impresión 80mm", "Validar Pistola"]},
            {"tipo": "fin", "x": 410, "y": 19, "label": "Rotulado OK"},
        ],
        flujos=[(111.5, 96, 118, 96), (176, 96, 195, 58), (257, 58, 280, 96), (340, 96, 403, 19)],
    )

    story.append(PageBreak())

    agregar_ficha_procedimiento_apa(
        story, est, tabla_inicio + 3,
        "POE-OPE-04", "Despacho en Lote, Notificación WhatsApp y Cierre de Jornada",
        "Controlar la entrega formal al transportista y consolidar los movimientos del turno directamente desde SQLite.",
        "Tarimas de empaque listas", "Pedidos preparados pendientes de retiro",
        "Cierre por Canales (Mayoristas / Mercado Libre / Full + Ingresos), Consolidado Admin (PDF/Excel) y Hojas de Ruta firmadas", "Gerencia / Administración",
        "R: Operario | A: Administrador | I: Chofer / Transportista",
        ["El turno operacional ha finalizado.", "La totalidad de pedidos preparados ha sido verificada en muelle."],
        [
            "En el Historial de Pedidos, se filtra la vista por 'Pendientes de Cierre'. Se marcan los pedidos entregados al chofer.",
            "Se pulsa el botón <b>'Despachar Seleccionados'</b> para transicionar los pedidos a estado DESPACHADO.",
            "Se ingresa el N° de guía del expreso y se pulsa el icono de WhatsApp para despachar el mensaje formal al cliente.",
            "Se acciona el comando <b>'Cierre de Jornada'</b>. El motor lee SQLite (sin requerir `Productos.xlsx`), emite el reporte del operario discriminado en 3 canales (solo SKUs movidos) y el Consolidado Administrador sin doble descuento.",
            "Se imprimen las Hojas de Ruta individuales por transporte y se recaba la firma de conformidad del chofer.",
            "Se verifica que los contadores del panel principal retornen a cero para la recepción del siguiente turno.",
        ],
        ["Los pedidos quedan vinculados al número único de cierre (`cierre_id`).", "Se genera el respaldo automático en `data/backups/`."],
        "Conformidad física del transportista estampada en la Hoja de Ruta con firma, aclaración y fecha legible.",
    )
    agregar_diagrama_bpmn_apa(
        story, est, figura_inicio + 3,
        "Flujograma BPMN 2.0: Despacho en Lote y Cierre de Jornada (POE-OPE-04)",
        lanes=["Operario Depósito", "Sistema StockAgent", "Transportista / Chofer"],
        nodos=[
            {"tipo": "inicio", "x": 105, "y": 96, "label": "Fin Turno"},
            {"tipo": "tarea", "x": 118, "y": 96, "w": 58, "h": 22, "texto": ["Marcar Salida", "Cierre Jornada"]},
            {"tipo": "tarea", "x": 195, "y": 58, "w": 62, "h": 22, "texto": ["Asignar CierreID", "Generar Hojas"]},
            {"tipo": "tarea", "x": 280, "y": 19, "w": 60, "h": 22, "texto": ["Recibir Carga", "Firmar Hoja Ruta"]},
            {"tipo": "fin", "x": 410, "y": 58, "label": "Backup OK"},
        ],
        flujos=[(111.5, 96, 118, 96), (176, 96, 195, 58), (257, 58, 280, 19), (340, 19, 403, 58)],
    )


def construir_manual_operador(ruta_destino: Path) -> Path:
    """Compila el Manual del Rol Operador bajo Normas ISO, BPMN y APA/UPEL."""
    doc, est, story = crear_documento_iso(ruta_destino)
    codigo_doc = "SOP-STK-OPE-2026-v2.3"
    titulo_doc = "Manual de Procedimientos de Depósito (Rol Operador)"

    agregar_portada_iso_upel(
        story, est, codigo_doc, titulo_doc,
        "Rol Operador (Preparación de Pedidos, Rotulación y Despacho)",
        "Procedimientos Operativos Estandarizados (POE / SOP) según Normas ISO 9001:2015, ISO/IEC/IEEE 26514:2022,<br/>"
        "modelado BPMN 2.0 estilo Bizagi y pautas metodológicas UPEL para el procesamiento de remitos, Mercado Libre y cierre",
        version=VERSION_SOP_ACTUAL,
    )

    agregar_titulo_capitulo(story, est, "1. Marco Normativo, Alcance y Responsabilidades (ISO 9001 §4.3 & §5.3)")
    story.append(Paragraph(
        "El presente manual formaliza y estandariza las actividades operativas de recepción de comprobantes, "
        "validación criptográfica anti-duplicados (SHA-256), descuento atómico de inventario, rotulación de bultos "
        "mediante códigos ópticos QR y despacho controlado hacia los transportistas.",
        est["body_sangria"],
    ))
    story.append(Paragraph(
        "Su alcance comprende al personal de depósito asignado a preparación, empaque y entrega en muelle, conforme a "
        "la Norma ISO 9001:2015 (§8.1 y §8.5.2) y los lineamientos metodológicos UPEL.",
        est["body_sangria"],
    ))
    story.append(Spacer(1, 2))
    story.append(crear_caja_alerta_iso(
        "EXCLUSIVIDAD OPERACIONAL SoD (ISO/IEC 27001 §5.3)",
        "Por control interno y segregación de funciones (SoD), el operario posee la facultad <b>exclusiva</b> de modificar "
        "bultos, transportes, clientes y fechas en pedidos preparados, evitando discordancias con la mercadería física.",
        "sod",
    ))

    story.append(Spacer(1, 4))
    agregar_titulo_capitulo(story, est, "2. Procedimientos Operativos Estandarizados (SOP / POE)")
    agregar_poes_operador(story, est, tabla_inicio=3, figura_inicio=1)

    agregar_titulo_capitulo(story, est, "3. Control de Registros de Calidad y Evidencias (ISO 9001:2015 §7.5.3)", page_break=True)
    story.append(Paragraph(
        "Matriz de control de información documentada generada durante los procedimientos de depósito:",
        est["body_sangria"],
    ))
    filas_reg = [
        ("Transacción de Pedido y Descuento", "Digital (SQLite)", "data/pedidos.sqlite3 (tabla `pedidos`)", "5 Años", "Administrador / Master"),
        ("Comprobante Digitalizado (PDF/Excel)", "Archivo binario", "data/pedidos_archivos/", "5 Años", "Administrador"),
        ("Hoja de Ruta Firmada por Chofer", "Documento papel", "Archivador de Logística en Depósito", "2 Años", "Encargado de Despacho"),
        ("Informe Consolidado de Cierre", "PDF y XLS", "Descuentos/ y data/pedidos_archivos/", "5 Años", "Jefe de Depósito"),
        ("Copia de Seguridad Integral", "Archivo .zip", "data/backups/ y Mirror en Red", "1 Año (Rotación 30)", "Master"),
    ]
    agregar_tabla_apa_completa(
        story, est, 7,
        "Matriz de Control y Retención de Registros de Calidad Operacionales",
        crear_filas_tabla_apa(
            ["Registro de Calidad", "Soporte", "Ubicación de Custodia", "Retención", "Responsable"],
            filas_reg, est, ["td_apa", "td_apa_center", "td_apa", "td_apa_center", "td_apa"], negrita_col0=True,
        ),
        [3.8 * cm, 2.2 * cm, 4.2 * cm, 2.0 * cm, 3.3 * cm],
        "Tiempos de retención fijados según requerimientos legales fiscales y auditoría interna.",
    )

    story.append(Spacer(1, 4))
    agregar_titulo_capitulo(story, est, "4. Gestión de No Conformidades y Errores (ISO 9001:2015 §10.2)")
    filas_err = [
        ("NC-OPE-01: Hash Duplicado", "Reingreso involuntario de comprobante.", "El sistema rechaza la carga informando fecha previa.", "Revisar Historial. Renombrar archivos no evade SHA-256."),
        ("NC-OPE-02: Quiebre de Stock", "Demanda superior al saldo en SQLite.", "El sistema abre advertencia previa de confirmación.", "Autorizar solo si hay ingreso pendiente o solicitar a Compras."),
        ("NC-OPE-03: Desarme o Eliminación", "Cancelación de cliente o carga errónea.", "Botón naranja 'Desarmar pedido' (lógico) o rojo 'Eliminar' (físico).", "El stock retorna a SQLite sin duplicar; Eliminar habilita recargar remito."),
        ("NC-OPE-04: Falla de Red Wi-Fi", "Microcorte o zona ciega en depósito.", "Continuar escaneando en 'Inventario en Vivo'.", "El búfer local transmite las lecturas al reconectar."),
    ]
    agregar_tabla_apa_completa(
        story, est, 8,
        "Matriz de Tratamiento de No Conformidades y Acciones Correctivas",
        crear_filas_tabla_apa(
            ["No Conformidad", "Causa Raíz", "Acción Inmediata (Corrección)", "Acción Preventiva"],
            filas_err, est, ["td_apa_bold_center", "td_apa", "td_apa", "td_apa"],
        ),
        [3.0 * cm, 3.5 * cm, 4.5 * cm, 4.5 * cm],
        "Procedimiento alineado con la Cláusula 10.2 de la Norma ISO 9001:2015.",
    )

    story.append(Spacer(1, 4))
    agregar_titulo_capitulo(story, est, "5. Indicadores de Desempeño y Calidad Operacional (KPIs - ISO 9001 §9.1)")
    filas_kpi = [
        ("Tiempo de Carga", "Velocidad de procesamiento por remito.", "Minutos desde subida hasta rotulación.", "< 45 seg.", "Continua"),
        ("Filtro SHA-256", "Efectividad anti-duplicados.", "(Duplicados interceptados / Total intentos) * 100", "100%", "Por Jornada"),
        ("Exactitud Empaque", "Concordancia bultos físicos vs remito.", "(Pedidos modificados / Total pedidos) * 100", "< 2%", "Mensual"),
    ]
    agregar_tabla_apa_completa(
        story, est, 9,
        "Indicadores Clave de Desempeño Operacional de Depósito",
        crear_filas_tabla_apa(
            ["Indicador (KPI)", "Objetivo", "Fórmula de Medición", "Meta", "Frecuencia"],
            filas_kpi, est, ["td_apa_bold_center", "td_apa", "td_apa", "td_apa_center", "td_apa_center"],
        ),
        [3.2 * cm, 3.5 * cm, 4.2 * cm, 2.3 * cm, 2.3 * cm],
        "Medición evaluada mensualmente por Calidad y Operaciones.",
    )

    agregar_titulo_capitulo(story, est, "6. Marco Técnico de Infraestructura y Control Institucional", page_break=True)
    agregar_requisitos_infraestructura_iso(story, est)
    agregar_matriz_distribucion_copias(story, est, 10)
    agregar_formulario_firmas_autorizadas_iso(story, est, 11)

    agregar_titulo_capitulo(story, est, "7. Registros de Inducción, Referencia Rápida y Terminología", page_break=True)
    agregar_acta_capacitacion_personal(story, est, 12)
    agregar_tarjeta_referencia_rapida(story, est)
    agregar_glosario_terminos_iso_upel(story, est)
    agregar_referencias_bibliograficas_apa_upel(story, est)

    doc.build(story, canvasmaker=crear_canvas_iso_upel(codigo_doc, titulo_doc, VERSION_SOP_ACTUAL))
    return ruta_destino
