"""Mensajes de bienvenida, ayuda de comandos y chips rápidos parametrizados por rol."""

from __future__ import annotations

_COMANDOS_POR_ROL: dict[str, str] = {
    "operador": (
        "📋 Comandos disponibles para Operador:\n"
        "• /stock <código o nombre>: Consulta existencias y ubicación en tiempo real.\n"
        "• /pedidos: Resumen de pedidos cargados y armados durante la jornada.\n"
        "• /cierre: Información sobre descuentos y estado del cierre de jornada.\n"
        "• /mercadolibre: Guía para descontar remitos de Mercado Libre (DOCX).\n"
        "• /msg [@usuario] <mensaje>: Envía un mensaje interno a un compañero o a todo el equipo.\n"
        "• /equipo: Abre el canal de comunicación interna entre usuarios.\n"
        "• /limpiar: Limpia la pantalla del chat."
    ),
    "master": (
        "📋 Comandos disponibles para Master (Seguridad & Auditoría):\n"
        "• /auditoria: Consulta los últimos eventos registrados en auditoría del sistema.\n"
        "• /backup: Estado y ruta del último respaldo de bases de datos.\n"
        "• /estado: Resumen de estado de servicios y almacenamiento.\n"
        "• /msg [@usuario] <mensaje>: Envía un mensaje interno a un usuario o al equipo.\n"
        "• /equipo: Abre el canal de comunicación interna entre usuarios.\n"
        "• /limpiar: Limpia la pantalla del chat.\n"
        "• /ayuda: Muestra esta ayuda técnica."
    ),
    "administrador": (
        "📋 Comandos disponibles para Administrador (Gestión Operativa):\n"
        "• /stock <código o nombre>: Consulta stock y estado en tiempo real.\n"
        "• /criticos: Lista productos con stock bajo o agotados.\n"
        "• /reposicion: Sugiere cantidades a pedir a fábrica para evitar quiebres.\n"
        "• /diagnostico: Analiza remitos, canjes, ML, fábrica y full pendientes.\n"
        "• /estado: Muestra resumen de pendientes y archivados.\n"
        "• /informes: Lista todos los informes generados.\n"
        "• /ultimo: Muestra información del informe más reciente.\n"
        "• /simular: Ejecuta una simulación de prueba sin alterar stock.\n"
        "• /pedidos: Resumen de pedidos del sistema.\n"
        "• /cierre: Resumen de cierres y descuentos acumulados.\n"
        "• /metricas: Panel de rendimiento, bultos y estadísticas de despacho.\n"
        "• /backup: Estado y ruta del último respaldo del sistema.\n"
        "• /msg [@usuario] <mensaje>: Envía un mensaje interno a un compañero o a todo el equipo.\n"
        "• /equipo: Abre el canal de comunicación interna entre usuarios.\n"
        "• /limpiar: Limpia la pantalla del chat."
    ),
    "consulta": (
        "📋 Comandos disponibles (Modo Consulta):\n"
        "• /stock <código o nombre>: Consulta stock y estado en tiempo real.\n"
        "• /criticos: Lista productos con stock bajo o agotados.\n"
        "• /informes: Lista los informes generados.\n"
        "• /ultimo: Muestra el informe más reciente.\n"
        "• /msg [@usuario] <mensaje>: Envía un mensaje interno al equipo.\n"
        "• /equipo: Abre el canal de comunicación interna entre usuarios.\n"
        "• /limpiar: Limpia la pantalla del chat."
    ),
}

_CHIPS_POR_ROL: dict[str, list[tuple[str, str, str]]] = {
    "operador": [
        ("Chat Equipo", "/equipo", "CHAT"),
        ("Consultar Stock", "/stock", "SEARCH"),
        ("Historial Pedidos", "/pedidos", "INVENTORY_2"),
        ("Cierre de Jornada", "/cierre", "POINT_OF_SALE"),
        ("Mercado Libre", "/mercadolibre", "LOCAL_SHIPPING"),
        ("Ayuda Comandos", "/ayuda", "HELP_OUTLINE"),
    ],
    "master": [
        ("Chat Equipo", "/equipo", "CHAT"),
        ("Copia Backup", "/backup", "BACKUP"),
        ("Estado General", "/estado", "DASHBOARD"),
        ("Ayuda Comandos", "/ayuda", "HELP_OUTLINE"),
    ],
    "administrador": [
        ("Chat Equipo", "/equipo", "CHAT"),
        ("Consultar Stock", "/stock", "SEARCH"),
        ("Stock Crítico", "/criticos", "WARNING_AMBER_ROUNDED"),
        ("Pedido Reposición", "/reposicion", "PRECISION_MANUFACTURING"),
        ("Métricas Depósito", "/metricas", "ANALYTICS"),
        ("Copia Backup", "/backup", "BACKUP"),
        ("Diagnóstico Archivos", "/diagnostico", "FACT_CHECK"),
        ("Estado General", "/estado", "DASHBOARD"),
        ("Último Informe", "/ultimo", "DESCRIPTION"),
        ("Simular Descuentos", "/simular", "SCIENCE"),
        ("Ayuda Comandos", "/ayuda", "HELP_OUTLINE"),
    ],
    "consulta": [
        ("Chat Equipo", "/equipo", "CHAT"),
        ("Consultar Stock", "/stock", "SEARCH"),
        ("Stock Crítico", "/criticos", "WARNING_AMBER_ROUNDED"),
        ("Ver Informes", "/informes", "FOLDER_OPEN"),
        ("Último Informe", "/ultimo", "DESCRIPTION"),
        ("Ayuda Comandos", "/ayuda", "HELP_OUTLINE"),
    ],
}

_PIES_POR_ROL: dict[str, str] = {
    "operador": "Usa /stock <cód>, /pedidos, /cierre, /mercadolibre o /ayuda",
    "master": "Usa /auditoria, /backup, /estado, /equipo o /ayuda",
    "administrador": "Usa /stock <cód>, /criticos, /reposicion, /diagnostico, /estado o /ayuda",
    "consulta": "Usa /stock <cód>, /criticos, /informes o /ayuda",
}


def obtener_mensaje_bienvenida(rol: str, nombre_usuario: str = "") -> str:
    """Genera un mensaje de bienvenida contextualizado al rol del usuario."""
    nombre = f" {nombre_usuario}" if nombre_usuario else ""
    plantillas = {
        "operador": (
            f"¡Hola{nombre}! 👋 Soy tu asistente de depósito.\n"
            "Puedo ayudarte a consultar stock y existencias en tiempo real (/stock <código>), "
            "ver el estado de pedidos del día (/pedidos), guiarte con remitos DOCX (/mercadolibre) "
            "o consultar el cierre de jornada (/cierre).\n"
            "Escribe /ayuda para ver todos tus comandos."
        ),
        "master": (
            f"¡Hola{nombre}! 👋 Consola de Seguridad y Auditoría Activa.\n"
            "Puedes auditar eventos del sistema (/auditoria), consultar respaldos (/backup), "
            "verificar el estado de servicios (/estado) o comunicarte por el canal interno (/equipo).\n"
            "Escribe /ayuda para ver el listado de comandos."
        ),
        "administrador": (
            f"¡Hola{nombre}! 👋 Asistente de Gestión Operativa Activo.\n"
            "Puedes supervisar stock crítico (/criticos), calcular reposición para fábrica (/reposicion), "
            "verificar archivos pendientes (/diagnostico), simular remitos (/simular) y auditar inventario (/stock).\n"
            "Escribe /ayuda para ver el listado de comandos."
        ),
    }
    return plantillas.get(
        rol,
        (
            f"¡Hola{nombre}! 👋 Asistente de Consulta y Auditoría.\n"
            "Puedes consultar existencias en tiempo real (/stock <código>), verificar productos críticos (/criticos) "
            "o revisar informes (/informes).\n"
            "Escribe /ayuda para más información."
        ),
    )


def obtener_comandos_ayuda(rol: str) -> str:
    """Retorna la lista de comandos permitidos según el rol."""
    return _COMANDOS_POR_ROL.get(rol, _COMANDOS_POR_ROL["consulta"])


def obtener_chips_configuracion(rol: str) -> list[tuple[str, str, str]]:
    """Devuelve tuplas `(nombre_funcionalidad, comando, icono)` para los botones rápidos."""
    return list(_CHIPS_POR_ROL.get(rol, _CHIPS_POR_ROL["consulta"]))


def obtener_pie_ayuda(rol: str) -> str:
    """Texto de ayuda en el pie de la ventana de chat según el rol."""
    return _PIES_POR_ROL.get(rol, _PIES_POR_ROL["consulta"])
