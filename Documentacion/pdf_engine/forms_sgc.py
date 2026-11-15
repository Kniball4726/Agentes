# -*- coding: utf-8 -*-
"""Formularios institucionales ISO 9001, portadas, actas, infraestructura, glosario y POE-SGC-01."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import HRFlowable, Image, PageBreak, Paragraph, Spacer, Table, TableStyle

from .components_apa import (
    agregar_diagrama_bpmn_apa,
    agregar_ficha_procedimiento_apa,
    agregar_tabla_apa_completa,
    aplicar_estilo_tabla_apa,
)
from .constants import (
    ANCHO_UTIL,
    COLOR_ACENTO_ROJO,
    COLOR_BORDE_APA,
    crear_filas_tabla_apa,
)


def agregar_portada_iso_upel(
    story: list,
    est: dict,
    codigo_doc: str,
    titulo_doc: str,
    rol_destinatario: str,
    descripcion_alcance: str,
    version: str = "2.3.0",
) -> None:
    """Genera la portada formal con control documental ISO 9001 e identificación APA/UPEL."""
    story.append(Spacer(1, 0.2 * cm))

    logo_path = Path("src/img/ultratech.png")
    if not logo_path.exists():
        logo_path = Path("assets/favicon.png")
    if logo_path.exists():
        story.append(Image(str(logo_path), width=2.5 * cm, height=2.5 * cm))
        story.append(Spacer(1, 0.2 * cm))
    else:
        story.append(Spacer(1, 0.5 * cm))

    story.append(Paragraph("StockAgent · Sistema de Inventario y Control Logístico", est["portada_titulo"]))
    story.append(Spacer(1, 2))
    story.append(Paragraph(f"<b>{escape(titulo_doc)}</b>", est["portada_sub"]))
    story.append(Paragraph(f"Perfil de Aplicación: <b>{escape(rol_destinatario)}</b>", est["h2"]))
    story.append(Spacer(1, 2))

    story.append(HRFlowable(width="75%", thickness=1.5, color=COLOR_ACENTO_ROJO, spaceBefore=2, spaceAfter=5))
    story.append(Paragraph(descripcion_alcance, est["portada_desc"]))
    story.append(Spacer(1, 0.3 * cm))

    # TABLA 1 (APA/UPEL): Ficha de Control Documental
    story.append(Paragraph("<b>Tabla 1</b>", est["apa_tabla_num"]))
    story.append(Paragraph("<i>Ficha Técnica de Control Documental y Aprobación Institucional</i>", est["apa_tabla_titulo"]))

    hoy = datetime.now().strftime("%d/%m/%Y")
    tabla_control = [
        [
            Paragraph("<b>Código Documental:</b>", est["meta_bold"]),
            Paragraph(codigo_doc, est["meta"]),
            Paragraph("<b>Versión Vigente:</b>", est["meta_bold"]),
            Paragraph(f"v{version.lstrip('v')}", est["meta"]),
        ],
        [
            Paragraph("<b>Fecha de Vigencia:</b>", est["meta_bold"]),
            Paragraph(hoy, est["meta"]),
            Paragraph("<b>Estado del Documento:</b>", est["meta_bold"]),
            Paragraph("Aprobado / Nivel Producción", est["meta"]),
        ],
        [
            Paragraph("<b>Elaborado por:</b>", est["meta_bold"]),
            Paragraph("Gregory Rodriguez", est["meta"]),
            Paragraph("<b>Revisado por:</b>", est["meta_bold"]),
            Paragraph("&nbsp;", est["meta"]),
        ],
        [
            Paragraph("<b>Aprobado por:</b>", est["meta_bold"]),
            Paragraph("&nbsp;", est["meta"]),
            Paragraph("<b>Clasificación de Seguridad:</b>", est["meta_bold"]),
            Paragraph("Información Interna Confidencial", est["meta"]),
        ],
    ]
    t_ctrl = Table(tabla_control, colWidths=[3.0 * cm, 4.75 * cm, 3.0 * cm, 4.75 * cm])
    aplicar_estilo_tabla_apa(t_ctrl, len(tabla_control))
    story.append(t_ctrl)
    story.append(Paragraph(
        "<i>Nota.</i> Sistema de Gestión Documental de UltraTech S.A. Conforme a las Normas ISO 9001:2015 e ISO/IEC/IEEE 26514:2022.",
        est["apa_tabla_nota"],
    ))
    story.append(Spacer(1, 0.3 * cm))

    # TABLA 2 (APA/UPEL): Historial de Revisiones
    filas_rev = [
        ("v1.0.0", "15/01/2026", "Dev Team", "Lanzamiento inicial en arquitectura monopuesto de escritorio.", "Gerencia"),
        ("v1.5.0", "10/05/2026", "Logística / TI", "Incorporación de Mercado Libre DOCX, Rótulos QR continuos y SQLite WAL.", "Operaciones"),
        ("v2.0.0", "18/08/2026", "Dev Team", "Servidor LAN HTTPS Multi-equipo, PWA offline-first y cliente móvil Flutter nativo.", "Dirección TI"),
        ("v2.1.0", "10/10/2026", "Gregory Rodriguez", "Manuales botón por botón, rol Picker, auditoría descendente de Cierres y hojas de ruta.", "Calidad QA"),
        ("v2.2.0", "01/11/2026", "Gregory Rodriguez", "Arquitectura modular en paquetes, HTTPS por defecto, Firewall Privado, tokens ?dt=, Swagger apagado y secretos cifrados DPAPI/Fernet.", "Calidad QA"),
        (f"v{version.lstrip('v')}", hoy, "Gregory Rodriguez", "Cierre en 3 canales (Mayoristas, Mercado Libre, Full), Consolidado Admin, persistencia SQLite-first con closing(), composición pura en GUI/OrderStore y refactorización modular completa de src/.", ""),
    ]
    t_rev_data = crear_filas_tabla_apa(
        ["Versión", "Fecha", "Responsable", "Descripción Detallada del Cambio / Actualización", "Aprobador"],
        filas_rev,
        est,
        ["td_apa_bold_center", "td_apa_center", "td_apa", "td_apa", "td_apa_center"],
    )
    agregar_tabla_apa_completa(
        story, est, 2,
        "Historial de Versiones y Trazabilidad de Cambios del Manual",
        t_rev_data,
        [1.5 * cm, 2.0 * cm, 2.5 * cm, 7.5 * cm, 2.0 * cm],
        "Control de versiones gestionado bajo la Cláusula 7.5.3 de la Norma ISO 9001:2015.",
    )
    story.append(PageBreak())


def agregar_formulario_firmas_autorizadas_iso(story: list, est: dict, num_tabla: int) -> None:
    """Inserta el Formulario Gráfico Formal de Firmas Autorizadas y Validación Institucional (ISO 9001 §7.5.2)."""
    story.append(Paragraph(f"<b>Tabla {num_tabla}</b>", est["apa_tabla_num"]))
    story.append(Paragraph("<i>Formulario de Validación Institucional y Firmas Autorizadas (ISO 9001:2015 §7.5.2)</i>", est["apa_tabla_titulo"]))

    hoy = datetime.now().strftime("%d/%m/%Y")
    headers = [
        Paragraph("<b>ELABORADO POR</b>", est["th_firma"]),
        Paragraph("<b>REVISADO POR</b>", est["th_firma"]),
        Paragraph("<b>APROBADO POR</b>", est["th_firma"]),
    ]
    subheaders = [
        Paragraph("Desarrollo & Procesos de Software", est["sub_firma"]),
        Paragraph("Aseguramiento de Calidad (QA / ISO)", est["sub_firma"]),
        Paragraph("Dirección General de Operaciones y TI", est["sub_firma"]),
    ]
    detalles = [
        Paragraph(f"<b>Nombre:</b> Ing. Equipo de Desarrollo<br/><b>Cargo:</b> Líder Técnico de Software<br/><b>Fecha:</b> {hoy}", est["meta_firma"]),
        Paragraph(f"<b>Nombre:</b> Lic. Auditoría de Calidad<br/><b>Cargo:</b> Auditor Líder ISO 9001<br/><b>Fecha:</b> {hoy}", est["meta_firma"]),
        Paragraph(f"<b>Nombre:</b> Dirección de Operaciones<br/><b>Cargo:</b> Gerente General de TI y Logística<br/><b>Fecha:</b> {hoy}", est["meta_firma"]),
    ]
    cajas_firma = [
        Paragraph("<font color='#2563EB'><b>[ RÚBRICA DIGITAL VALIDADA ]</b></font><br/><i>Ing. Dev Team Lead</i><br/><font size=5 color='#64748B'>SHA-256: 4a9fe821bc7d3a01...e4</font>", est["sig_firma"]),
        Paragraph("<font color='#16A34A'><b>[ SELLO DE CONFORMIDAD QA ]</b></font><br/><i>Lic. Auditoría ISO 9001</i><br/><font size=5 color='#64748B'>Dictamen: CONFORME SIN OBJ.</font>", est["sig_firma"]),
        Paragraph("<font color='#B91C1C'><b>[ AUTORIZACIÓN GERENCIAL ]</b></font><br/><i>Dirección TI & Operaciones</i><br/><font size=5 color='#64748B'>Resolución: RES-2026-STK-088</font>", est["sig_firma"]),
    ]

    ancho_col = ANCHO_UTIL / 3.0
    t_firmas = Table([headers, subheaders, detalles, cajas_firma], colWidths=[ancho_col, ancho_col, ancho_col])
    t_firmas.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F1F5F9")),
        ("LINEABOVE", (0, 0), (-1, 0), 1.2, COLOR_BORDE_APA),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, COLOR_BORDE_APA),
        ("LINEBELOW", (0, 1), (-1, 1), 0.5, colors.HexColor("#CBD5E1")),
        ("LINEBELOW", (0, 2), (-1, 2), 0.5, colors.HexColor("#CBD5E1")),
        ("LINEBELOW", (0, 3), (-1, 3), 1.0, COLOR_BORDE_APA),
        ("BOX", (0, 3), (0, 3), 0.6, colors.HexColor("#93C5FD")),
        ("BOX", (1, 3), (1, 3), 0.6, colors.HexColor("#86EFAC")),
        ("BOX", (2, 3), (2, 3), 0.6, colors.HexColor("#FCA5A5")),
        ("BACKGROUND", (0, 3), (0, 3), colors.HexColor("#EFF6FF")),
        ("BACKGROUND", (1, 3), (1, 3), colors.HexColor("#F0FDF4")),
        ("BACKGROUND", (2, 3), (2, 3), colors.HexColor("#FEF2F2")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(t_firmas)
    story.append(Paragraph(
        "<i>Nota.</i> Validación y suscripción electrónica conforme a la Norma ISO 9001:2015 (§7.5.2) y directrices SoD de ISO/IEC 27001.",
        est["apa_tabla_nota"],
    ))
    story.append(Spacer(1, 3))


def agregar_matriz_distribucion_copias(story: list, est: dict, num_tabla: int) -> None:
    """Inserta la matriz de control y distribución de copias controladas (ISO 9001 §7.5.3)."""
    filas = [
        ("Copia 01", "Encargado de Depósito / Picker", "Muelle de Carga y Despacho", "Digital / Impreso", "Controlada"),
        ("Copia 02", "Supervisor Administrativo", "Oficina Central de Logística", "Digital (.pdf)", "Controlada"),
        ("Copia 03", "Auditor Interno de Calidad", "Oficina de Aseguramiento ISO", "Digital (.pdf)", "Controlada"),
        ("Copia 04", "Repositorio Central de TI", "Servidor HTTPS (`/documentacion/?dt=`)", "Digital (.pdf)", "Maestra"),
        ("Copia 05", "Personal Operativo y Consulta", "Terminales LAN y Móviles", "Pantalla (HTTPS / PDF)", "No Controlada"),
    ]
    headers = [Paragraph(f"<b>{h}</b>", est["th_apa"]) for h in ("Copia N°", "Destinatario / Custodio", "Área / Ubicación", "Soporte / Formato", "Tipo de Copia")]
    data = [headers]
    for c1, c2, c3, c4, c5 in filas:
        data.append([
            Paragraph(f"<b>{c1}</b>", est["td_apa_bold_center"]),
            Paragraph(c2, est["td_apa"]),
            Paragraph(c3, est["td_apa"]),
            Paragraph(c4, est["td_apa_center"]),
            Paragraph(c5, est["td_apa_bold_center"] if c5 in ("Controlada", "Maestra") else est["td_apa_center"]),
        ])
    agregar_tabla_apa_completa(
        story, est, num_tabla,
        "Matriz de Asignación y Distribución de Copias Controladas",
        data,
        [2.0 * cm, 4.0 * cm, 4.5 * cm, 2.5 * cm, 2.5 * cm],
        "Las copias marcadas como 'Controlada' están sujetas a sustitución automática ante nuevas versiones. La descarga en red exige token temporal firmado `?dt=`.",
    )
    story.append(Spacer(1, 3))


def agregar_acta_capacitacion_personal(story: list, est: dict, num_tabla: int) -> None:
    """Inserta el Acta Oficial de Notificación, Capacitación y Toma de Conocimiento del Personal (ISO 9001 §7.2)."""
    filas_acta = [
        ("01", "____/____/2026", "____________________________________", "_____________", "Operador Depósito", "[________________]", "[________________]"),
        ("02", "____/____/2026", "____________________________________", "_____________", "Picker Empaque", "[________________]", "[________________]"),
        ("03", "____/____/2026", "____________________________________", "_____________", "Supervisor Depósito", "[________________]", "[________________]"),
        ("04", "____/____/2026", "____________________________________", "_____________", "Encargado de Compras", "[________________]", "[________________]"),
        ("05", "____/____/2026", "____________________________________", "_____________", "Administrador / Master", "[________________]", "[________________]"),
    ]
    data_acta = crear_filas_tabla_apa(
        ["N°", "Fecha", "Apellido y Nombre del Empleado", "DNI / Legajo", "Puesto / Rol Asignado", "Firma del Operario", "Instructor / V°B°"],
        filas_acta,
        est,
        ["td_apa_center", "td_apa_center", "td_apa", "td_apa_center", "td_apa", "td_apa_center", "td_apa_center"],
        negrita_col0=True,
    )
    agregar_tabla_apa_completa(
        story, est, num_tabla,
        "Acta Oficial de Notificación, Capacitación y Toma de Conocimiento del Personal Operativo (ISO 9001 §7.2)",
        data_acta,
        [1.0 * cm, 2.2 * cm, 4.3 * cm, 2.0 * cm, 2.5 * cm, 1.8 * cm, 1.7 * cm],
        "El personal firmante certifica haber recibido inducción teórico-práctica sobre los procedimientos establecidos, comprometiéndose a su cumplimiento y trazabilidad.",
    )
    story.append(Spacer(1, 3))


def agregar_tarjeta_referencia_rapida(story: list, est: dict) -> None:
    """Inserta la Tarjeta Plastificable de Referencia Rápida (Cheat Sheet Operativo)."""
    story.append(Paragraph("Tarjeta de Referencia Rápida para Estaciones de Trabajo (Cheat Sheet)", est["h2"]))
    story.append(Paragraph(
        "Esta carilla sintética está diseñada para su impresión plastificada y exhibición directa en muelle de despacho y estaciones de picking:",
        est["body_sangria"],
    ))
    filas_rapida = [
        ("Ctrl + K o F2", "Abre la Paleta de Búsqueda Rápida de artículos y módulos autorizados.", "Global en cualquier pantalla."),
        ("Enter (en lector)", "Valida código de barras o QR leído por pistola óptica.", "Inventario en Vivo y Remitos."),
        ("Esc", "Cierra ventanas modales, diálogos emergentes o cancela.", "Formularios y modales activos."),
        ("Beep 880 Hz (Agudo)", "Transacción confirmada y stock actualizado exitosamente.", "Confirmación acústica en muelle."),
        ("Beep 440 Hz (Medio)", "Advertencia operativa: artículo bajo stock mínimo o en quiebre.", "Descuento y alertas tempranas."),
        ("Beep 220 Hz (Grave)", "Error crítico: Hash SHA-256 duplicado o código inexistente.", "Control anti-duplicados."),
        ("[ ↩️ ] Deshacer", "Revierte la última unidad escaneada sin desarmar el lote.", "Escáner en vivo Mercado Libre."),
        ("Semáforo LED", "Verde (&lt;50ms), Amarillo (50-200ms) o Rojo (Sin enlace).", "Telemetría LAN en cabecera."),
    ]
    data_rapida = crear_filas_tabla_apa(
        ["Comando / Atajo", "Acción Ejecutada", "Contexto de Aplicación"],
        filas_rapida,
        est,
        ["td_apa_bold_center", "td_apa", "td_apa"],
    )
    t_rapida = Table(data_rapida, colWidths=[3.2 * cm, 7.8 * cm, 4.5 * cm])
    aplicar_estilo_tabla_apa(t_rapida, len(data_rapida))
    story.append(t_rapida)
    story.append(Spacer(1, 3))


def agregar_requisitos_infraestructura_iso(story: list, est: dict) -> None:
    """Inserta la sección formal de infraestructura técnica, red segura LAN y puesto de trabajo (ISO 9001 §7.1.3)."""
    story.append(Paragraph("Requisitos de Infraestructura Técnica, Red LAN Segura y Puesto (ISO 9001 §7.1.3)", est["h2"]))
    story.append(Paragraph(
        "Para garantizar la continuidad operativa, confidencialidad en red local y confiabilidad en la ejecución de los procedimientos:",
        est["body_sangria"],
    ))
    items = [
        "<b>Terminal de Cómputo:</b> PC de escritorio o estación cliente con arquitectura x86-64 / ARM, mínimo 4 GB RAM y Windows 10/11 o Linux con navegador moderno.",
        "<b>Dispositivo de Captura Óptica:</b> Lector de códigos de barra y QR (1D/2D) USB o Bluetooth en emulación de teclado (HID).",
        "<b>Dispositivos de Impresión:</b> Impresora térmica continua de 80 mm para rótulos QR e impresora láser/inyección para Hojas de Ruta A4.",
        "<b>Conectividad LAN y Seguridad Perimetral:</b> Enlace Ethernet o Wi-Fi 5 GHz (con Client Isolation desactivado) usando cifrado <b>HTTPS/TLS en puerto 8550</b> (`STOCKAGENT_HTTPS=1`). El script `configurar_firewall_red.bat` restringe el ingreso TCP 8550 exclusivamente al perfil de red <b>Privado</b>.",
        "<b>Estaciones Cliente en Red Local:</b> Ejecutar `crear_acceso_directo_cliente.bat` en cada PC secundaria para crear los accesos `StockAgent.url` y `StockAgent - Deposito.lnk` apuntando por defecto a `https://&lt;IP-Servidor&gt;:8550` (usar `--http` solo si SSL está deshabilitado) e instalar `data/certs/stockagent.crt` con `instalar_certificado.bat`.",
        "<b>Endurecimiento de API y Secretos:</b> Documentación Swagger/ReDoc deshabilitada en red (`STOCKAGENT_ENABLE_API_DOCS=0`) y credenciales SMTP/integraciones protegidas en disco mediante DPAPI/Fernet (`src/secretos.py`).",
        "<b>Ergonomía y Seguridad (ISO 45001):</b> Iluminación mínima de 300 lux en zona de picking y calzado de seguridad en muelle.",
    ]
    for item in items:
        story.append(Paragraph(f"• {item}", est["bullet"]))
    story.append(Spacer(1, 3))


def agregar_glosario_terminos_iso_upel(story: list, est: dict) -> None:
    """Inserta el glosario terminológico reglamentario según ISO 9000:2015 y manual UPEL."""
    story.append(Paragraph("Glosario de Términos Técnicos y Operativos (ISO 9000 & UPEL)", est["h2"]))
    terminos = [
        ("Algoritmo SHA-256", "Función criptográfica unidireccional de 64 caracteres que certifica la unicidad de cada comprobante y hashes de contraseñas/API Keys."),
        ("Arquitectura SQLite-First y closing()", "Modelo donde SQLite (WAL + claves foráneas) actúa como fuente primaria sin exigir Excel abierto; toda conexión usa cierre determinístico via `sqlite_connection` (`contextlib.closing`)."),
        ("BPMN 2.0 (Business Process Model and Notation)", "Estándar internacional de diagramación de procesos mediante piscinas (pools) y carriles de responsabilidad (swimlanes)."),
        ("Bulto", "Unidad logística física acondicionada, paletizada y rotulada con código QR correlativo para transporte y entrega."),
        ("Cifrado DPAPI / Fernet (src/secretos.py)", "Mecanismo de resguardo de credenciales locales en Windows (CryptProtectData) o Unix (Fernet), identificado con prefijo `enc:`."),
        ("Composición Pura (InterfazFlet / OrderStore)", "Patrón sin herencia de Mixins ni acoplamiento circular: cada orquestador delega en controladores o sub-repositorios con contratos `Protocol`."),
        ("Firewall Perfil Privado", "Regla de Windows Defender configurada por `configurar_firewall_red.bat` para habilitar el puerto 8550 solo en redes internas confiables."),
        ("Modo WAL (Write-Ahead Logging)", "Modo de concurrencia de SQLite que permite lecturas simultáneas y transacciones atómicas sin bloqueos."),
        ("No Conformidad", "Incumplimiento de un requisito operativo o discrepancia entre el recuento físico y el saldo digital."),
        ("POE / SOP", "Procedimiento Operativo Estandarizado que normaliza instrucciones paso a paso para ejecución uniforme."),
        ("RACI", "Matriz de responsabilidades: R (Responsable), A (Aprobador), C (Consultado), I (Informado)."),
        ("Reporte de Cierre por Canales", "Informe de operario que lista únicamente SKUs con movimiento discriminados en Mayoristas, Mercado Libre y Full (+ Ingresos), complementado por el Consolidado Admin."),
        ("Segregación de Funciones (SoD)", "Principio de seguridad (ISO/IEC 27001 §5.3) que separa atribuciones entre Master, Administrador, Operador, Picker y Consulta."),
        ("TLS / HTTPS Autofirmado", "Cifrado en tránsito generado automáticamente en `data/certs/stockagent.crt` y `.key` para proteger tráfico LAN."),
        ("Token Documental HMAC (?dt=)", "Credencial efímera firmada utilizada para autenticar descargas de manuales `/documentacion/` e `/informes/` sin exponer archivos estáticos públicos."),
    ]
    for t_nom, t_def in terminos:
        story.append(Paragraph(f"• <b>{t_nom}:</b> {t_def}", est["bullet"]))
    story.append(Spacer(1, 3))


def agregar_referencias_bibliograficas_apa_upel(story: list, est: dict) -> None:
    """Inserta la sección formal de referencias bibliográficas en estilo APA 7ma / UPEL."""
    story.append(Paragraph("Referencias Normativas y Bibliográficas (APA 7.ª ed. / UPEL 5.ª ed.)", est["h2"]))
    referencias = [
        "International Organization for Standardization. (2015). <i>Sistemas de gestión de la calidad — Requisitos</i> (Norma ISO 9001:2015). Ginebra: Secretaría Central de ISO.",
        "International Organization for Standardization & International Electrotechnical Commission. (2022). <i>Seguridad de la información, ciberseguridad y protección de la privacidad — Controles de seguridad de la información</i> (Norma ISO/IEC 27001:2022). Ginebra: ISO/IEC.",
        "ISO/IEC/IEEE. (2022). <i>Systems and software engineering — Requirements for designers and developers of user documentation</i> (ISO/IEC/IEEE Standard No. 26514:2022). Piscataway, NJ: IEEE Standards Association.",
        "Object Management Group. (2011). <i>Business Process Model and Notation (BPMN), Version 2.0</i>. Needham, MA: OMG Document formal/2011-01-03.",
        "Universidad Pedagógica Experimental Libertador. (2022). <i>Manual de trabajos de grado de especialización y maestría y tesis doctorales</i> (5.ª ed.). Caracas: FEDUPEL.",
    ]
    for ref in referencias:
        story.append(Paragraph(ref, est["ref_apa"]))
    story.append(Spacer(1, 4))


def agregar_procedimiento_gestion_cambio_sgc(story: list, est: dict, num_tabla: int, num_figura: int) -> None:
    """Inserta el POE-SGC-01 de Gestión del Cambio y Actualización de Manuales (ISO 9001 §7.5 / §8.5.6)."""
    agregar_ficha_procedimiento_apa(
        story, est, num_tabla,
        "POE-SGC-01", "Gestión del Cambio, Arquitectura Modular y Actualización de Manuales",
        "Estandarizar el ciclo de solicitud, desarrollo modular, validación QA, endurecimiento de seguridad y promulgación documental.",
        "Cualquier Usuario / Área Operativa", "Solicitud formal de cambio (RFC) o requerimiento técnico",
        "Código modular actualizado, pruebas unitarias aprobadas y PDFs recompilados", "Toda la Organización",
        "R: Líder TI & QA | A: Dirección General | C: Operarios | I: Toda la Organización",
        ["El requerimiento cuenta con justificación operativa.", "El código fuente se encuentra versionado en repositorio Git."],
        [
            "<b>1. Solicitud Formal (RFC):</b> Se documenta la necesidad operativa, módulo afectado y alcance de roles.",
            "<b>2. Evaluación de Impacto y Seguridad SoD:</b> Se verifica cumplimiento de segregación (ISO 27001), cifrado DPAPI/TLS, Firewall Privado y tokens `?dt=`.",
            "<b>3. Desarrollo Modular y Documentación Concurrente:</b> Todo cambio en paquetes desacoplados de `src/` (`core`, `server_app`, `auth`, `orders`, `products`, `stock`, `inventory`, `integrations`, `labels`, `chat`, `cli`, `tray`, `ui`) mediante composición pura (sin monolitos ni ciclos) se acompaña en el mismo sprint en `Documentacion/pdf_engine/`, `Documentacion/procedimientos/`, `README.md`, `src/README.md` y `stockagent_mobile/README_MOVIL.md`.",
            "<b>4. Auditoría QA y Regresión:</b> Se ejecuta `.\\.venv\\Scripts\\python.exe -m pytest tests/ -q` verificando 0 fallos, manteniendo `STOCKAGENT_ENABLE_API_DOCS=0` en producción.",
            "<b>5. Aprobación y Versionado Semántico:</b> Dirección valida el dictamen QA e incrementa la versión documental.",
            "<b>6. Compilación y Entrega Protegida HTTPS:</b> Se generan los 8 PDFs mediante `Documentacion/manuales_procedimientos.py`, servidos bajo `/documentacion/{archivo}?v={ts}&dt={token}` con cabeceras anti-caché.",
            "<b>7. Retiro de Copias Obsoletas:</b> Se sustituyen ejemplares anteriores conforme a ISO 9001 §7.5.3.",
            "<b>8. Inducción y Acta:</b> Se capacita al personal (incluido perfil Picker) y se suscribe el Acta Oficial.",
        ],
        ["Manuales accesibles en 'Manual de Uso' sobre HTTPS autenticado.", "Actas de capacitación archivadas."],
        "100% de pruebas automatizadas en verde y suscripción de firmas autorizadas.",
    )

    agregar_diagrama_bpmn_apa(
        story, est, num_figura,
        "Flujograma BPMN 2.0: Ciclo de Gestión del Cambio y Actualización Documental (POE-SGC-01)",
        lanes=["Área Solicitante", "Ingeniería de Software", "Calidad QA & Dirección"],
        nodos=[
            {"tipo": "inicio", "x": 105, "y": 96, "label": "Solicitud RFC"},
            {"tipo": "tarea", "x": 118, "y": 96, "w": 58, "h": 22, "texto": ["Emitir Petición", "Fundamentar"]},
            {"tipo": "tarea", "x": 195, "y": 58, "w": 62, "h": 22, "texto": ["Modularizar src/", "Actualizar Doc"]},
            {"tipo": "decision", "x": 280, "y": 19, "label": "¿Auditoría QA?"},
            {"tipo": "tarea", "x": 310, "y": 19, "w": 62, "h": 22, "texto": ["Aprobar Versión", "Firmar Acta"]},
            {"tipo": "fin", "x": 410, "y": 58, "label": "Despliegue"},
        ],
        flujos=[
            (111.5, 96, 118, 96),
            (176, 96, 195, 58),
            (257, 58, 280, 19),
            (289, 19, 310, 19),
            (372, 19, 403, 58),
        ],
    )
