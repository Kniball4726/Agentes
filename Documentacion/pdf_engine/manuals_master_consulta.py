# -*- coding: utf-8 -*-
"""Generadores de manuales ISO/BPMN/APA para los roles Master y Consulta."""

from __future__ import annotations

from pathlib import Path

from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, Spacer

from .canvas_iso import crear_canvas_iso_upel
from .components_apa import (
    agregar_diagrama_bpmn_apa,
    agregar_ficha_procedimiento_apa,
    agregar_tabla_apa_completa,
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


def agregar_poes_master(
    story: list,
    est: dict,
    tabla_inicio: int = 3,
    figura_inicio: int = 1,
    salto_entre_mas1_y_2: bool = True,
) -> None:
    """Inserta los Procedimientos Técnicos de Seguridad y Continuidad (POE-MAS-01..03)."""
    from reportlab.platypus import PageBreak

    # POE-MAS-01
    agregar_ficha_procedimiento_apa(
        story, est, tabla_inicio,
        "POE-MAS-01", "Gestión Global de Identidades y Accesos (IAM Supremo)",
        "Administrar el ciclo de vida de credenciales, roles privilegiados y desbloqueos administrativos.",
        "Dirección TI / RRHH", "Solicitud de alta o reseteo de cuenta",
        "Cuentas activas en tabla `users`, claves con hash PBKDF2-SHA256 (600.000 iter.)", "Administradores y depósito",
        "R: Master | A: Dirección TI",
        ["Verificación formal de identidad Master y políticas SoD vigentes."],
        [
            "En la sección 'Gestionar usuarios', se da de alta o edita cuentas para los roles Administrador, Operador, Picker o Consulta.",
            "Para reseteo de claves: se asigna contraseña temporal activando `must_change_password = 1`.",
            "Se desbloquean de forma inmediata las cuentas bloqueadas por fuerza bruta (5 fallos) sin aguardar los 15 minutos.",
        ],
        ["Registro inmutable en `logs_auditoria` con usuario, dirección IP y sello de tiempo."],
        "Las contraseñas cumplen longitud mínima de 10 caracteres con complejidad alfanumérica.",
    )
    agregar_diagrama_bpmn_apa(
        story, est, figura_inicio,
        "Flujograma BPMN 2.0: Gestión de Identidades IAM (POE-MAS-01)",
        lanes=["Solicitante / RRHH", "Usuario Master", "Motor de Seguridad IAM"],
        nodos=[
            {"tipo": "inicio", "x": 105, "y": 96, "label": "Solicitud"},
            {"tipo": "tarea", "x": 118, "y": 58, "w": 58, "h": 22, "texto": ["Validar Legajo", "Asignar Perfil"]},
            {"tipo": "decision", "x": 195, "y": 58, "label": "¿Aprobado?"},
            {"tipo": "tarea", "x": 230, "y": 19, "w": 62, "h": 22, "texto": ["Generar PBKDF2", "Asentar Audit"]},
            {"tipo": "tarea", "x": 315, "y": 96, "w": 62, "h": 22, "texto": ["Entregar Clave", "Forzar Cambio"]},
            {"tipo": "fin", "x": 410, "y": 96, "label": "Cuenta OK"},
        ],
        flujos=[(111.5, 96, 118, 58), (176, 58, 186, 58), (204, 58, 230, 19), (292, 19, 315, 96), (377, 96, 403, 96)],
    )

    if salto_entre_mas1_y_2:
        story.append(PageBreak())

    # POE-MAS-02
    agregar_ficha_procedimiento_apa(
        story, est, tabla_inicio + 1,
        "POE-MAS-02", "Restauración Documental y Rollback de Lotes (Exclusivo Master)",
        "Revertir operaciones erróneas o lotes históricos recomponiendo atómicamente el catálogo.",
        "Solicitud formal de Administrador", "Fecha de descuento y número de comprobante",
        "Catálogo Productos.xlsx y SQLite reconstituidos al estado previo exacto", "Contabilidad / Auditoría",
        "R: Master | A: Dirección Operaciones",
        ["Solicitud fundamentada por escrito y autorizada por la Gerencia de Operaciones."],
        [
            "En la barra lateral bajo <i>Datos y Resguardo</i>, se pulsa el comando <b>'Restaurar documentos'</b>.",
            "Se selecciona con precisión la fecha y el lote histórico que se requiere deshacer.",
            "Se presiona <b>'Previsualizar Rollback'</b> para constatar las unidades que retornarán al inventario.",
            "Se confirma la operación mediante <b>'Restaurar Catálogo'</b>: el motor recompone SQLite y Productos.xlsx.",
        ],
        ["Existencias físicas incrementadas en el inventario.", "Registro forense inmutable de rollback."],
        "Verificación de integridad estructural de base de datos ejecutando `PRAGMA integrity_check`.",
    )
    agregar_diagrama_bpmn_apa(
        story, est, figura_inicio + 1,
        "Flujograma BPMN 2.0: Restauración y Rollback SoD (POE-MAS-02)",
        lanes=["Administrador", "Usuario Master (SoD)", "Motor Criptográfico"],
        nodos=[
            {"tipo": "inicio", "x": 105, "y": 96, "label": "Petición"},
            {"tipo": "tarea", "x": 118, "y": 58, "w": 58, "h": 22, "texto": ["Analizar Motivo", "Previsualizar"]},
            {"tipo": "decision", "x": 195, "y": 58, "label": "¿Auditoría OK?"},
            {"tipo": "tarea", "x": 230, "y": 19, "w": 62, "h": 22, "texto": ["Eliminar Hash", "Reponer Stock"]},
            {"tipo": "tarea", "x": 315, "y": 58, "w": 62, "h": 22, "texto": ["Registrar Log", "Notificar Admin"]},
            {"tipo": "fin", "x": 410, "y": 96, "label": "Rollback OK"},
        ],
        flujos=[(111.5, 96, 118, 58), (176, 58, 186, 58), (204, 58, 230, 19), (292, 19, 315, 58), (377, 58, 403, 96)],
    )

    # POE-MAS-03
    agregar_ficha_procedimiento_apa(
        story, est, tabla_inicio + 2,
        "POE-MAS-03", "Continuidad del Negocio, Seguridad Perimetral y Respaldos (Disaster Recovery)",
        "Asegurar disponibilidad mediante respaldos comprimidos, secretos cifrados DPAPI/Fernet y tráfico TLS en LAN Privada.",
        "Sistema StockAgent en producción", "Bases SQLite (`pedidos`, `usuarios`, `productos`) y catálogo Excel",
        "Archivo `.zip` en `data/backups/`, certificados X.509 y réplica en red NAS", "Toda la Organización",
        "R: Master | A: Gerencia TI",
        [
            "Regla de Respaldo 3-2-1 activa y Firewall configurado en perfil Privado (`configurar_firewall_red.bat`).",
            "Conexiones SQLite encapsuladas con cierre determinístico `contextlib.closing()` (`src/core/sqlite_utils.py`), Swagger deshabilitado (`STOCKAGENT_ENABLE_API_DOCS=0`) y secretos cifrados (`src/secretos.py`).",
        ],
        [
            "En 'Copia de Seguridad', se acciona el respaldo manual o se valida la ejecución automática del cierre.",
            "Se verifica la réplica atómica del `.zip` hacia almacenamiento secundario y la política de rotación (30 versiones).",
            "Se supervisan en 'Documentación y Estado' las sesiones HTTPS activas, tokens API y certificados `data/certs/`.",
        ],
        ["Respaldo íntegro en dos ubicaciones físicas y perímetro LAN cifrado bajo TLS."],
        "Prueba periódica de restauración en Sandbox y verificación de ausencia de exposición en perfil Público.",
    )
    agregar_diagrama_bpmn_apa(
        story, est, figura_inicio + 2,
        "Flujograma BPMN 2.0: Continuidad y Respaldo 3-2-1 (POE-MAS-03)",
        lanes=["Usuario Master", "Sistema StockAgent", "Almacenamiento Red NAS"],
        nodos=[
            {"tipo": "inicio", "x": 105, "y": 96, "label": "Disparador"},
            {"tipo": "tarea", "x": 118, "y": 58, "w": 58, "h": 22, "texto": ["Comprimir Bases", "Verificar Integridad"]},
            {"tipo": "decision", "x": 195, "y": 58, "label": "¿Check OK?"},
            {"tipo": "tarea", "x": 230, "y": 19, "w": 62, "h": 22, "texto": ["Replicar Espejo", "Rotar Versiones"]},
            {"tipo": "tarea", "x": 315, "y": 96, "w": 62, "h": 22, "texto": ["Auditar Sandbox", "Firmar Acta"]},
            {"tipo": "fin", "x": 410, "y": 96, "label": "Backup OK"},
        ],
        flujos=[(111.5, 96, 118, 58), (176, 58, 186, 58), (204, 58, 230, 19), (292, 19, 315, 96), (377, 96, 403, 96)],
    )


def agregar_poes_consulta(
    story: list,
    est: dict,
    tabla_inicio: int = 3,
    figura_inicio: int = 1,
) -> None:
    """Inserta el Procedimiento de Consulta Rápida (POE-CON-01) y su diagrama BPMN."""
    agregar_ficha_procedimiento_apa(
        story, est, tabla_inicio,
        "POE-CON-01", "Búsqueda de Existencias y Ubicación de Artículos en Tiempo Real",
        "Consultar saldos disponibles, descripción y posición física en estanterías.",
        "Vendedores / Clientes", "Código SKU, código de barras o descripción",
        "Información de stock disponible y ubicación física en estantería (Rack/Nivel)", "Cliente / Mostrador",
        "R: Vendedor / Auditor | I: Depósito",
        ["Sesión de Consulta debidamente autenticada sobre HTTPS."],
        [
            "Se acciona la combinación <code>Ctrl + K</code> o la tecla <code>F2</code> para abrir la Paleta de Búsqueda Rápida.",
            "Se ingresa el código o término de búsqueda. El motor de consulta filtra en vivo en menos de 0.05 segundos.",
            "Se verifica el saldo disponible y se visualiza la ubicación física en estantería (ej. <code>Rack B, Mod 2, Niv 1</code>).",
        ],
        ["Consulta registrada en logs sin alteración de datos contables."],
        "Concordancia exacta entre el saldo visualizado en pantalla y el registro activo en SQLite.",
    )
    agregar_diagrama_bpmn_apa(
        story, est, figura_inicio,
        "Flujograma BPMN 2.0: Consulta Rápida de Inventario (POE-CON-01)",
        lanes=["Usuario Consulta", "Motor StockAgent", "Mostrador Comercial"],
        nodos=[
            {"tipo": "inicio", "x": 105, "y": 96, "label": "Consulta"},
            {"tipo": "tarea", "x": 118, "y": 96, "w": 58, "h": 22, "texto": ["Presionar F2", "Ingresar SKU"]},
            {"tipo": "tarea", "x": 195, "y": 58, "w": 62, "h": 22, "texto": ["Búsqueda SQLite", "Localizar Rack"]},
            {"tipo": "decision", "x": 280, "y": 58, "label": "¿Hay Saldo?"},
            {"tipo": "tarea", "x": 310, "y": 19, "w": 62, "h": 22, "texto": ["Mostrar Stock", "Informar Cliente"]},
            {"tipo": "fin", "x": 410, "y": 19, "label": "Fin Consulta"},
        ],
        flujos=[(111.5, 96, 118, 96), (176, 96, 195, 58), (257, 58, 271, 58), (289, 58, 310, 19), (372, 19, 403, 19)],
    )


def construir_manual_master(ruta_destino: Path) -> Path:
    """Compila el Manual del Rol Master bajo Normas ISO, BPMN y APA/UPEL."""
    doc, est, story = crear_documento_iso(ruta_destino)
    codigo_doc = "SOP-STK-MAS-2026-v2.3"
    titulo_doc = "Manual Técnico, IAM y Auditoría Forense (Rol Master)"

    agregar_portada_iso_upel(
        story, est, codigo_doc, titulo_doc,
        "Rol Master (Desarrollo, Seguridad, Auditoría y Continuidad)",
        "Procedimientos Operativos Estandarizados (POE / SOP) según ISO 9001:2015, ISO/IEC 27001 e ISO/IEC/IEEE 26514:2022,<br/>"
        "modelado BPMN 2.0 (Bizagi) y pautas UPEL para identidades IAM, auditoría inmutable, TLS/DPAPI y disaster recovery",
        version=VERSION_SOP_ACTUAL,
    )

    agregar_titulo_capitulo(story, est, "1. Principios de Seguridad SoD y Menor Privilegio (ISO/IEC 27001)")
    story.append(Paragraph(
        "El perfil Master (`Auditoria`) constituye la autoridad técnica y de seguridad de StockAgent. En estricto apego al "
        "Control 5.3 de la Norma ISO/IEC 27001 (Segregación de Funciones), este rol permanece desacoplado de la operativa "
        "diaria de pedidos para garantizar absoluta imparcialidad en auditorías forenses.",
        est["body_sangria"],
    ))
    story.append(Paragraph(
        "La cuenta Master es inmutable: no puede ser eliminada, bloqueada ni degradada de rol.",
        est["body_sangria"],
    ))

    story.append(Spacer(1, 4))
    agregar_titulo_capitulo(story, est, "2. Procedimientos de Seguridad y Continuidad (SOP / POE)")
    agregar_poes_master(story, est, tabla_inicio=3, figura_inicio=1, salto_entre_mas1_y_2=True)

    agregar_titulo_capitulo(story, est, "3. Registros de Auditoría y Trazabilidad Forense (ISO 27001 & ISO 9001)", page_break=True)
    filas_rmas = [
        ("Registro de Auditoría Forense", "SQLite inmutable", "data/pedidos.sqlite3 (`logs_auditoria`)", "10 Años", "Master"),
        ("Intentos de Acceso / Ataques", "SQLite (`login_attempts`)", "data/usuarios.sqlite3", "2 Años", "Master"),
        ("Secretos Cifrados Locales", "DPAPI / Fernet (`enc:`)", "data/.clave_secretos + config SMTP/API", "Permanente", "Master"),
        ("Logs de Servidor Web y Conexiones", "Archivo rotativo", "data/logs/stockagent.log", "1 Año", "Master"),
        ("Certificados SSL/HTTPS X.509", "Criptográfico PEM", "data/certs/stockagent.crt / .key", "Permanente / Renovable", "Master"),
    ]
    agregar_tabla_apa_completa(
        story, est, 6,
        "Matriz de Registros Forenses e Información de Seguridad de Infraestructura",
        crear_filas_tabla_apa(
            ["Registro Forense", "Soporte", "Ubicación", "Retención", "Responsable"],
            filas_rmas, est, ["td_apa", "td_apa_center", "td_apa", "td_apa_center", "td_apa"], negrita_col0=True,
        ),
        [3.8 * cm, 2.2 * cm, 4.2 * cm, 2.0 * cm, 3.3 * cm],
        "Custodia inmutable bajo la Cláusula 8.15 de la Norma ISO/IEC 27001:2022.",
    )

    agregar_titulo_capitulo(story, est, "4. Infraestructura de Servidor y Control Institucional", page_break=True)
    agregar_requisitos_infraestructura_iso(story, est)
    agregar_matriz_distribucion_copias(story, est, 7)
    agregar_formulario_firmas_autorizadas_iso(story, est, 8)

    agregar_titulo_capitulo(story, est, "5. Registros de Inducción, Referencia Rápida y Terminología Forense", page_break=True)
    agregar_acta_capacitacion_personal(story, est, 9)
    agregar_tarjeta_referencia_rapida(story, est)
    agregar_glosario_terminos_iso_upel(story, est)
    agregar_referencias_bibliograficas_apa_upel(story, est)

    doc.build(story, canvasmaker=crear_canvas_iso_upel(codigo_doc, titulo_doc, VERSION_SOP_ACTUAL))
    return ruta_destino


def construir_manual_consulta(ruta_destino: Path) -> Path:
    """Compila el Manual del Rol Consulta bajo Normas ISO, BPMN y APA/UPEL."""
    doc, est, story = crear_documento_iso(ruta_destino)
    codigo_doc = "SOP-STK-CON-2026-v2.3"
    titulo_doc = "Manual de Procedimientos de Consulta Externa (Rol Consulta)"

    agregar_portada_iso_upel(
        story, est, codigo_doc, titulo_doc,
        "Rol Consulta (Vendedores, Auditorías Externas y Supervisión)",
        "Procedimientos Operativos Estandarizados (POE / SOP) según Normas ISO 9001:2015 e ISO/IEC/IEEE 26514:2022,<br/>"
        "modelado BPMN 2.0 (Bizagi) y pautas metodológicas UPEL para búsqueda de existencias en tiempo real e inspección de reportes",
        version=VERSION_SOP_ACTUAL,
    )

    agregar_titulo_capitulo(story, est, "1. Alcance y Restricciones de Solo Lectura (ISO 26514)")
    story.append(Paragraph(
        "El perfil de Consulta provee acceso seguro de solo lectura a vendedores, auditores y supervisores comerciales "
        "para corroborar existencias y reportes oficiales sin comprometer la integridad transaccional del catálogo.",
        est["body_sangria"],
    ))
    story.append(Paragraph(
        "Se prohíbe de forma irrestricta emitir descuentos, modificar bultos o ejecutar cierres desde este nivel.",
        est["body_sangria"],
    ))

    story.append(Spacer(1, 4))
    agregar_titulo_capitulo(story, est, "2. Procedimientos de Consulta Estandarizados (SOP / POE)")
    agregar_poes_consulta(story, est, tabla_inicio=3, figura_inicio=1)

    agregar_titulo_capitulo(story, est, "3. Infraestructura de Puesto, Distribución y Firmas Autorizadas", page_break=True)
    agregar_requisitos_infraestructura_iso(story, est)
    agregar_matriz_distribucion_copias(story, est, 4)
    agregar_formulario_firmas_autorizadas_iso(story, est, 5)

    agregar_titulo_capitulo(story, est, "4. Registros de Inducción, Referencia Rápida y Glosario", page_break=True)
    agregar_acta_capacitacion_personal(story, est, 6)
    agregar_tarjeta_referencia_rapida(story, est)
    agregar_glosario_terminos_iso_upel(story, est)
    agregar_referencias_bibliograficas_apa_upel(story, est)

    doc.build(story, canvasmaker=crear_canvas_iso_upel(codigo_doc, titulo_doc, VERSION_SOP_ACTUAL))
    return ruta_destino
