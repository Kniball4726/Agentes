# -*- coding: utf-8 -*-
"""Generador del Manual Maestro Integral Imprimible y funciones de enlace."""

from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib.units import cm
from reportlab.platypus import PageBreak, Paragraph, Spacer

from .canvas_iso import crear_canvas_iso_upel
from .components_apa import agregar_tabla_apa_completa
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
    agregar_procedimiento_gestion_cambio_sgc,
    agregar_referencias_bibliograficas_apa_upel,
    agregar_requisitos_infraestructura_iso,
    agregar_tarjeta_referencia_rapida,
)
from .manuals_admin import agregar_poes_administrador
from .manuals_master_consulta import agregar_poes_consulta, agregar_poes_master
from .manuals_operador import agregar_poes_operador


def construir_manual_maestro_imprimible(ruta_destino: Path) -> Path:
    """Compila el Manual Maestro Integral Imprimible para entrega final al usuario o auditorías."""
    doc, est, story = crear_documento_iso(ruta_destino)
    codigo_doc = "SOP-STK-MAE-2026-v2.3"
    titulo_doc = "Manual Maestro de Procedimientos del Sistema (Compendio Integral Imprimible)"

    agregar_portada_iso_upel(
        story, est, codigo_doc, titulo_doc,
        "Todos los Roles (Master, Administrador, Operador, Picker, Consulta y Auditoría)",
        "Compendio general exhaustivo de Procedimientos Operativos Estandarizados (POE / SOP) según Normas ISO 9001:2015,<br/>"
        "ISO/IEC/IEEE 26514:2022 e ISO/IEC 27001:2022 bajo modelado BPMN 2.0 (Bizagi), pautas UPEL y arquitectura modular",
        version=VERSION_SOP_ACTUAL,
    )

    # TABLA DE CONTENIDOS (SUMARIO GENERAL)
    agregar_titulo_capitulo(story, est, "Índice General de Contenidos del Manual Maestro")
    toc_filas = [
        ("1. Marco Estratégico, Arquitectura Modular y Alcance", "Paquetes src/ y Documentacion/, seguridad LAN y trazabilidad.", "ISO 9001 §4.3"),
        ("2. Matriz SoD Oficial de 5 Roles y Endurecimiento LAN", "Segregación Master / Admin / Operador / Picker / Consulta.", "ISO 27001 §5.3"),
        ("3. Procedimientos de Depósito (Operador y Picker)", "Remitos, Mercado Libre, Mercado Full, QR y Cierre.", "POE-OPE 01..04"),
        ("4. Procedimientos de Supervisión (Rol Admin)", "Catálogo, Entrada Fábrica, Compras y Slotting ABC.", "POE-ADM 01..04"),
        ("5. Procedimientos Técnicos (Rol Master)", "IAM Supremo, Rollback SoD, TLS/DPAPI y Respaldo 3-2-1.", "POE-MAS 01..03"),
        ("6. Procedimientos de Consulta (Rol Consulta)", "Búsqueda en tiempo real e inspección de reportes.", "POE-CON 01"),
        ("7. Gestión del Cambio y Nuevos Módulos", "Ciclo de desarrollo modular y actualización documental.", "POE-SGC 01"),
        ("8. Control de Registros y Evidencias", "Matriz unificada de retención y custodia.", "ISO 9001 §7.5.3"),
        ("9. Gestión de No Conformidades y Errores", "Tratamiento de fallas, causa raíz y corrección.", "ISO 9001 §10.2"),
        ("10. Indicadores Clave de Desempeño (KPIs)", "Medición de tiempos, precisión y disponibilidad.", "ISO 9001 §9.1"),
        ("11. Infraestructura Técnica, TLS LAN y Copias", "HTTPS 8550, Firewall Privado, accesos y firmas.", "ISO 9001 §7.1.3"),
        ("12. Capacitación, Cheat Sheet, Glosario y Bibliografía", "Inducción del personal y referencias APA/UPEL.", "ISO 9001 §7.2"),
    ]
    from reportlab.platypus import Table
    from .components_apa import aplicar_estilo_tabla_apa

    t_toc_data = crear_filas_tabla_apa(
        ["Capítulo / Sección Temática", "Alcance Operativo y Normativo", "Referencia"],
        toc_filas, est, ["td_apa", "td_apa", "td_apa_center"],
    )
    t_toc = Table(t_toc_data, colWidths=[5.5 * cm, 7.5 * cm, 2.5 * cm])
    aplicar_estilo_tabla_apa(t_toc, len(t_toc_data))
    story.append(t_toc)
    story.append(Spacer(1, 4))

    # CAPÍTULO 1: MARCO ESTRATÉGICO Y ARQUITECTURA MODULAR
    agregar_titulo_capitulo(story, est, "1. Marco Estratégico, Arquitectura Modular y Alcance (ISO 9001 §4.3)", page_break=True)
    story.append(Paragraph(
        "StockAgent constituye la plataforma logística troncal para control de inventario SQLite-first, despacho mayorista/e-commerce "
        "y trazabilidad física. Su arquitectura modular sin archivos monolíticos organiza el código por composición pura bajo `src/` "
        "(`core` con cierre determinístico `closing()`, `server_app`, `auth`, `orders`, `products`, `stock`, `inventory`, `labels`, `chat`, "
        "`cli`, `tray`, `integrations`, `parsers`, `api` y `ui`) y los generadores documentales en `Documentacion/pdf_engine/` y `Documentacion/procedimientos/`.",
        est["body_sangria"],
    ))

    # CAPÍTULO 2: ARQUITECTURA Y MATRIZ SOD OFICIAL (5 ROLES INCLUYENDO PICKER)
    story.append(Spacer(1, 4))
    agregar_titulo_capitulo(story, est, "2. Matriz Oficial de Segregación de Funciones (SoD - 5 Roles, ISO/IEC 27001)")
    story.append(Paragraph(
        "La Tabla 3 delimita con rigor las atribuciones de los cinco roles activos (`Master`, `Administrador`, `Operador`, "
        "`Picker` y `Consulta`) junto con las medidas vigentes de seguridad perimetral en red LAN:",
        est["body_sangria"],
    ))

    headers_sod = [
        Paragraph(f"<b>{h}</b>", est["th_apa"])
        for h in ("Funcionalidad / Módulo", "Master", "Admin", "Operador", "Picker", "Consulta", "Regla de Seguridad SoD")
    ]
    matriz_data = [headers_sod]
    filas_permisos = [
        ("Carga Pedidos (Remitos / Canjes)", "❌ No", "❌ No", "✅ Exclusivo", "❌ No", "❌ No", "Solo Operador registra remitos de despacho."),
        ("Descuento Mercado Libre (Escáner/DOCX)", "❌ No", "✅ Sí", "✅ Sí", "✅ Sí", "❌ No", "Habilitado para empaque ágil y supervisión."),
        ("Descuento Mercado Full (Excel)", "❌ No", "✅ Sí", "✅ Sí", "✅ Sí", "❌ No", "Procesamiento rápido hacia bodega Full."),
        ("Movimientos Rápidos (+ / − Stock)", "✅ Sí", "✅ Sí", "✅ Sí", "✅ Sí", "❌ No", "Trazabilidad obligatoria con motivo y auditoría."),
        ("Modificar / Desarmar Pedidos", "❌ No", "❌ Lectura", "✅ Exclusivo", "❌ No", "❌ No", "Evita colisión remota con mercadería empaquetada."),
        ("Cierre de Jornada y Hojas de Ruta", "❌ No", "❌ Audita", "✅ Exclusivo", "❌ No", "❌ No", "Operador cierra en 3 canales; Admin audita Consolidado."),
        ("Ingreso de Fábrica (Escáner / Lote)", "❌ No", "✅ Sí", "✅ Sí", "✅ Sí", "❌ No", "Sobrescribir stock reservado a Administrador."),
        ("Catálogo, Ped. Fábrica y Comparativa", "❌ No", "✅ Exclusivo", "❌ No", "❌ No", "❌ No", "Administración maestra de SKUs y arqueos."),
        ("Analítica, Radar y Heatmap Slotting", "✅ Lectura", "✅ Sí", "❌ No", "❌ No", "❌ No", "Inteligencia operativa y ergonomía de depósito."),
        ("Gestión Usuarios (Op./Picker/Cons.)", "✅ Sí", "✅ Sí", "❌ No", "❌ No", "❌ No", "Solo Master promueve o gestiona Administradores."),
        ("Auditoría, API Docs/Keys, SMTP, Rollback", "✅ Exclusivo", "❌ No", "❌ No", "❌ No", "❌ No", "SoD estricto: control IAM, TLS, DPAPI y recuperación."),
        ("Copias de Seguridad (.zip)", "✅ Sí", "✅ Sí", "❌ No", "❌ No", "❌ No", "Respaldos íntegros de SQLite y Productos.xlsx."),
    ]
    for f_nom, m_st, a_st, o_st, p_st, c_st, regla in filas_permisos:
        matriz_data.append([
            Paragraph(f"<b>{escape(f_nom)}</b>", est["td_apa"]),
            Paragraph(m_st, est["td_apa_bold_center"] if "Exclusivo" in m_st else est["td_apa_center"]),
            Paragraph(a_st, est["td_apa_bold_center"] if "Exclusivo" in a_st else est["td_apa_center"]),
            Paragraph(o_st, est["td_apa_bold_center"] if "Exclusivo" in o_st else est["td_apa_center"]),
            Paragraph(p_st, est["td_apa_bold_center"] if "Exclusivo" in p_st else est["td_apa_center"]),
            Paragraph(c_st, est["td_apa_center"]),
            Paragraph(escape(regla), est["td_apa"]),
        ])
    agregar_tabla_apa_completa(
        story, est, 3,
        "Matriz Consolidada de Permisos por Rol y Controles de Segregación SoD",
        matriz_data,
        [3.8 * cm, 1.3 * cm, 1.35 * cm, 1.45 * cm, 1.3 * cm, 1.4 * cm, 4.9 * cm],
        "Control de segregación bajo ISO/IEC 27001 §5.3. Las descargas de manuales `/documentacion/` e `/informes/` requieren token HMAC `?dt=`; HTTPS y Firewall Privado aplican por defecto.",
        repeat_rows=1,
    )

    # CAPÍTULO 3..6: PROCEDIMIENTOS POR ROL (REUTILIZANDO FUENTE ÚNICA)
    agregar_titulo_capitulo(story, est, "3. Procedimientos Operativos de Depósito (Operador y Picker)", page_break=True)
    agregar_poes_operador(story, est, tabla_inicio=4, figura_inicio=1)

    agregar_titulo_capitulo(story, est, "4. Procedimientos de Supervisión Logística y Compras (Rol Administrador)", page_break=True)
    agregar_poes_administrador(story, est, tabla_inicio=8, figura_inicio=5)

    agregar_titulo_capitulo(story, est, "5. Procedimientos Técnicos, IAM y Auditoría Forense (Rol Master)", page_break=True)
    agregar_poes_master(story, est, tabla_inicio=12, figura_inicio=9, salto_entre_mas1_y_2=True)

    agregar_titulo_capitulo(story, est, "6. Procedimientos de Consulta Externa (Rol Consulta)", page_break=True)
    agregar_poes_consulta(story, est, tabla_inicio=15, figura_inicio=12)

    # CAPÍTULO 7: GESTIÓN DEL CAMBIO
    agregar_titulo_capitulo(story, est, "7. Gestión del Cambio, Nuevos Módulos y Actualización Documental (ISO 9001 §8.5.6)", page_break=True)
    agregar_procedimiento_gestion_cambio_sgc(story, est, 16, 13)

    # CAPÍTULO 8: MATRIZ CONSOLIDADA DE REGISTROS DE CALIDAD
    agregar_titulo_capitulo(story, est, "8. Matriz Consolidada de Control de Registros de Calidad (ISO 9001 §7.5.3)", page_break=True)
    filas_reg_mae = [
        ("Transacción de Pedido y Descuento", "Digital (SQLite)", "data/pedidos.sqlite3 (`pedidos`)", "5 Años", "Administrador / Master"),
        ("Comprobante Digitalizado (PDF/Excel)", "Archivo binario", "data/pedidos_archivos/", "5 Años", "Administrador"),
        ("Hoja de Ruta Firmada por Chofer", "Documento papel", "Archivador Logística Depósito", "2 Años", "Encargado Despacho"),
        ("Informe Consolidado de Cierre", "PDF y XLS", "Descuentos/ y data/pedidos_archivos/", "5 Años", "Jefe de Depósito"),
        ("Base de Datos Maestra Productos", "SQLite", "data/productos.sqlite3", "Permanente", "Master / Admin"),
        ("Auditoría Forense y Secretos DPAPI", "SQLite / Cifrado", "logs_auditoria + data/.clave_secretos", "10 Años", "Master"),
        ("Copia de Seguridad Integral", "Archivo .zip", "data/backups/ y Mirror en Red", "1 Año (Rot. 30)", "Master"),
    ]
    agregar_tabla_apa_completa(
        story, est, 17,
        "Matriz Consolidada de Información Documentada y Tiempos de Retención Legal",
        crear_filas_tabla_apa(
            ["Registro de Calidad", "Soporte", "Ubicación de Custodia", "Retención", "Responsable"],
            filas_reg_mae, est, ["td_apa", "td_apa_center", "td_apa", "td_apa_center", "td_apa"], negrita_col0=True,
        ),
        [3.8 * cm, 2.2 * cm, 4.2 * cm, 2.0 * cm, 3.3 * cm],
        "Control documental bajo Cláusula 7.5.3 de ISO 9001:2015 y 8.15 de ISO/IEC 27001.",
    )

    # CAPÍTULO 9: NO CONFORMIDADES
    story.append(Spacer(1, 4))
    agregar_titulo_capitulo(story, est, "9. Gestión de No Conformidades y Acciones Correctivas (ISO 9001 §10.2)")
    filas_err_mae = [
        ("NC-OPE-01: Hash Duplicado", "Reingreso involuntario de comprobante.", "Rechaza la carga informando fecha previa.", "Revisar Historial. Renombrar no evade SHA-256."),
        ("NC-OPE-02: Quiebre de Stock", "Demanda superior al saldo en SQLite.", "Abre advertencia previa de confirmación.", "Autorizar solo si hay ingreso o pedir a Compras."),
        ("NC-OPE-03: Desarme por Rechazo", "Cancelación de pedido por cliente.", "Presionar botón ámbar 'Desarmar pedido'.", "El stock retorna al instante a SQLite y Excel."),
        ("NC-ADM-01: Discrepancia Físico", "Ajuste no registrado o merma.", "Aplicar ajuste justificado con motivo.", "Capacitar en registro oportuno de mermas."),
        ("NC-SEC-01: Alerta Certificado LAN", "Navegador cliente sin raíz local.", "Ejecutar `instalar_certificado.bat` como Admin.", "Usar `crear_acceso_directo_cliente.bat` en LAN."),
    ]
    agregar_tabla_apa_completa(
        story, est, 18,
        "Matriz Maestra de Contingencias, Causa Raíz y Acciones Correctivas",
        crear_filas_tabla_apa(
            ["No Conformidad", "Causa Raíz", "Acción Inmediata (Corrección)", "Acción Preventiva"],
            filas_err_mae, est, ["td_apa_bold_center", "td_apa", "td_apa", "td_apa"],
        ),
        [3.0 * cm, 3.5 * cm, 4.5 * cm, 4.5 * cm],
        "Acciones correctivas formalizadas según la Cláusula 10.2 de ISO 9001:2015.",
    )

    # CAPÍTULO 10: KPIS
    story.append(Spacer(1, 4))
    agregar_titulo_capitulo(story, est, "10. Indicadores Clave de Desempeño Operacional (KPIs - ISO 9001 §9.1)")
    filas_kpi_m = [
        ("Tiempo de Carga Remito", "Velocidad de procesamiento.", "Desde subida hasta rotulación.", "< 45 seg.", "Continua"),
        ("Filtro SHA-256", "Efectividad anti-duplicados.", "(Duplicados bloqueados / Intentos) * 100", "100%", "Por Jornada"),
        ("Exactitud Empaque", "Concordancia bultos físicos vs remito.", "(Modificados / Total pedidos) * 100", "< 2%", "Mensual"),
        ("Disponibilidad Servidor TLS", "Continuidad de servicio HTTPS LAN.", "(Horas activas / Horas operación) * 100", "> 99.8%", "Mensual"),
    ]
    agregar_tabla_apa_completa(
        story, est, 19,
        "Indicadores Clave de Desempeño de Calidad y Logística Integral",
        crear_filas_tabla_apa(
            ["Indicador (KPI)", "Objetivo", "Fórmula de Medición", "Meta", "Frecuencia"],
            filas_kpi_m, est, ["td_apa_bold_center", "td_apa", "td_apa", "td_apa_center", "td_apa_center"],
        ),
        [3.2 * cm, 3.5 * cm, 4.2 * cm, 2.3 * cm, 2.3 * cm],
        "Medición evaluada mensualmente por Calidad y Dirección de Operaciones.",
    )

    # CAPÍTULOS 11 y 12
    agregar_titulo_capitulo(story, est, "11. Infraestructura, Control de Distribución y Firmas Autorizadas", page_break=True)
    agregar_requisitos_infraestructura_iso(story, est)
    agregar_matriz_distribucion_copias(story, est, 20)
    agregar_formulario_firmas_autorizadas_iso(story, est, 21)

    agregar_titulo_capitulo(story, est, "12. Registros de Inducción, Tarjeta de Referencia y Anexos Finales", page_break=True)
    agregar_acta_capacitacion_personal(story, est, 22)
    agregar_tarjeta_referencia_rapida(story, est)
    agregar_glosario_terminos_iso_upel(story, est)
    agregar_referencias_bibliograficas_apa_upel(story, est)

    doc.build(story, canvasmaker=crear_canvas_iso_upel(codigo_doc, titulo_doc, VERSION_SOP_ACTUAL))
    return ruta_destino


def construir_manual_general(ruta_destino: Path) -> Path:
    """Función para compilar el Manual General Consolidado (invoca el compendio maestro)."""
    return construir_manual_maestro_imprimible(ruta_destino)


def construir_pdf(ruta_destino: Path) -> Path:
    """Función de enlace para compilar el manual general consolidado."""
    return construir_manual_maestro_imprimible(ruta_destino)
