"""Registro y catálogo de comandos y accesos rápidos por rol para la Paleta de Comandos."""

from __future__ import annotations

from typing import Any, Callable
import flet as ft
from ..theme import ROJO

# Tipo: (Titulo, Descripcion, Icono, Color, Callback)
TipoComando = tuple[str, str, Any, Any, Callable[[], Any]]


def obtener_comandos_rol(rol: str, interfaz: Any) -> list[TipoComando]:
    """Retorna los comandos específicos según el rol del usuario."""
    comandos: list[TipoComando] = []

    if rol == "operador":
        comandos.extend([
            ("Ver Stock", "Consulta de existencias y niveles en tiempo real", ft.Icons.VISIBILITY, ft.Colors.CYAN_400, interfaz.mostrar_ver_stock),
            ("Cargar / Armar Pedido", "Formulario rápido de remitos y canjes", ft.Icons.POST_ADD, ft.Colors.BLUE_400, interfaz.mostrar_crear_pedido),
            ("Ingreso de Fábrica", "Escáner rápido de recepción de mercadería", ft.Icons.INVENTORY_2, ft.Colors.ORANGE_400, interfaz.mostrar_ingreso_fabrica),
            ("Inventario en Vivo (Escáner)", "Conteo con cámara de celular o lector USB", ft.Icons.DOCUMENT_SCANNER, ft.Colors.GREEN_400, interfaz.mostrar_dialogo_inventario_vivo),
            ("Cierre de Jornada", "Consolidar turnos y generar hoja de ruta PDF", ft.Icons.TASK_ALT, ROJO, interfaz.mostrar_cierre_jornada),
            ("Centro de Reportes", "Generar reportes en PDF y Excel para ver o imprimir", ft.Icons.ASSESSMENT, ft.Colors.RED_400, interfaz.mostrar_centro_reportes),
            ("Historial de Pedidos", "Buscar, reimprimir y ver pedidos del turno", ft.Icons.RECEIPT_LONG, ft.Colors.AMBER_400, interfaz.mostrar_historial_pedidos),
            ("Gestión de Clientes", "Directorio y consulta de clientes", ft.Icons.PEOPLE_ALT, ft.Colors.TEAL_400, interfaz.mostrar_gestion_clientes),
            ("Descontar Mercado Libre", "Escaneo rápido de paquetes y etiquetas ML", ft.Icons.STOREFRONT, ft.Colors.AMBER_600, interfaz.mostrar_descuento_mercado_libre),
            ("Planificar Mercado Full", "Subir Excel de Full y monitorear avance en vivo", ft.Icons.ADD_TASK, ft.Colors.RED_400, interfaz.mostrar_planificar_full),
            ("Preparar Mercado Full", "Picking guiado por código de barras de envío Full", ft.Icons.LOCAL_SHIPPING, ft.Colors.ORANGE_400, interfaz.mostrar_picking_guiado_full),
            ("Descontar Mercado Full", "Procesamiento directo de envíos Mercado Libre Full", ft.Icons.FILE_DOWNLOAD, ft.Colors.ORANGE_400, interfaz.mostrar_descuento_mercado_full),
            ("Abrir Informe", "Descargar o visualizar el último informe generado", ft.Icons.OPEN_IN_NEW, ft.Colors.INDIGO_400, interfaz.abrir_informe),
            ("Compartir por Correo", "Enviar informes de stock por correo electrónico", ft.Icons.EMAIL, ft.Colors.BLUE_300, interfaz.compartir_correo),
            ("WhatsApp Web", "Compartir remitos o estado de pedidos por WhatsApp", ft.Icons.CHAT, ft.Colors.GREEN_600, interfaz.compartir_whatsapp),
            ("Manual de Uso", "Documentación oficial del operario en PDF", ft.Icons.MENU_BOOK, ft.Colors.CYAN_400, interfaz.mostrar_manual_usuario),
        ])
    elif rol == "administrador":
        comandos.extend([
            ("Despacho (Pedidos Despachados)", "Consulta en solo lectura de pedidos despachados", ft.Icons.LOCAL_SHIPPING, ROJO, interfaz.mostrar_modulo_despacho),
            ("Ver Stock", "Consulta de existencias y niveles en tiempo real", ft.Icons.VISIBILITY, ft.Colors.CYAN_400, interfaz.mostrar_ver_stock),
            ("Gestionar Productos", "Catálogo maestro y existencias en Productos.xlsx", ft.Icons.ADD_BOX, ft.Colors.BLUE_400, interfaz.mostrar_gestion_productos),
            ("Métricas y Rendimiento", "Dashboard ejecutivo, rotación y volumen", ft.Icons.INSIGHTS, ft.Colors.PURPLE_400, interfaz.mostrar_dashboard_metricas),
            ("Centro de Reportes", "Generar reportes en PDF y Excel para ver o imprimir", ft.Icons.ASSESSMENT, ft.Colors.RED_400, interfaz.mostrar_centro_reportes),
            ("Historial de Pedidos", "Supervisión, reimpresión y rótulos en lote", ft.Icons.RECEIPT_LONG, ft.Colors.AMBER_400, interfaz.mostrar_historial_pedidos),
            ("Cierres de Operarios", "Historial descendente de cierres creados por operarios", ft.Icons.FACT_CHECK, ft.Colors.ORANGE_400, interfaz.mostrar_historial_cierres_admin),
            ("Planificar Ingreso de Fábrica", "Subir remito Excel/PDF y monitorear control del picker", ft.Icons.ADD_TASK, ft.Colors.GREEN_400, interfaz.mostrar_planificar_ingreso_fabrica),
            ("Control de Ingreso de Fábrica", "Verificación y escaneo de remito de fábrica por picker", ft.Icons.INVENTORY_2, ft.Colors.GREEN_600, interfaz.mostrar_control_ingreso_fabrica),
            ("Ajustar Stock / Fábrica", "Ingresos de mercadería y remitos de fábrica", ft.Icons.INVENTORY_2, ft.Colors.GREEN_400, interfaz.mostrar_ingreso_fabrica),
            ("Copia de Seguridad", "Respaldos .ZIP y espejo en red / nube", ft.Icons.BACKUP, ROJO, interfaz.mostrar_dialogo_backup),
            ("Comparativa Stock Físico", "Contraste de conteos físicos contra inventario", ft.Icons.COMPARE_ARROWS, ft.Colors.TEAL_400, interfaz.mostrar_comparativa_stock_fisico_admin),
            ("Sincronizar con Excel", "Volcar catálogo SQLite a Productos.xlsx", ft.Icons.SYNC, ft.Colors.LIGHT_BLUE_400, interfaz.sincronizar_catalogo_excel),
            ("Generar Pedido Fábrica (Excel)", "Cálculo de sugerido y planilla de reposición", ft.Icons.FACT_CHECK, ft.Colors.AMBER_400, interfaz.generar_pedido_fabrica),
            ("Gestión de Clientes", "Directorio y consulta de clientes mayoristas", ft.Icons.PEOPLE_ALT, ft.Colors.TEAL_400, interfaz.mostrar_gestion_clientes),
            ("Descontar Mercado Libre", "Escaneo rápido de paquetes y etiquetas ML", ft.Icons.STOREFRONT, ft.Colors.AMBER_600, interfaz.mostrar_descuento_mercado_libre),
            ("Sincronizar Mercado Libre (API)", "Conexión y credenciales de Mercado Libre", ft.Icons.CLOUD_SYNC, ft.Colors.AMBER_600, interfaz.mostrar_sincronizacion_mercadolibre),
            ("Planificar Mercado Full", "Subir Excel de Full y monitorear avance en vivo", ft.Icons.ADD_TASK, ft.Colors.RED_400, interfaz.mostrar_planificar_full),
            ("Preparar Mercado Full", "Picking guiado por código de barras de envío Full", ft.Icons.LOCAL_SHIPPING, ft.Colors.ORANGE_400, interfaz.mostrar_picking_guiado_full),
            ("Descontar Mercado Full", "Procesamiento directo de envíos Mercado Libre Full", ft.Icons.FILE_DOWNLOAD, ft.Colors.ORANGE_400, interfaz.mostrar_descuento_mercado_full),
            ("Estadísticas de Salida", "Gráficos de ventas y flujo histórico de bultos", ft.Icons.BAR_CHART, ft.Colors.BLUE_GREY_400, interfaz.mostrar_estadisticas),
            ("Radar de Anomalías", "Detección estadística de saltos bruscos y desvíos", ft.Icons.AUTO_GRAPH, ft.Colors.RED_400, interfaz.mostrar_dialogo_anomalias),
            ("Heatmap y Picking", "Distribución en planta y optimización de recorrido", ft.Icons.GRID_VIEW_ROUNDED, ft.Colors.PINK_400, interfaz.mostrar_dialogo_heatmap),
            ("Abrir Informe", "Descargar o visualizar informes y balances", ft.Icons.OPEN_IN_NEW, ft.Colors.INDIGO_400, interfaz.abrir_informe),
            ("Compartir por Correo", "Enviar informes y balances por correo", ft.Icons.EMAIL, ft.Colors.BLUE_300, interfaz.compartir_correo),
            ("WhatsApp Web", "Compartir balances o remitos vía WhatsApp", ft.Icons.CHAT, ft.Colors.GREEN_600, interfaz.compartir_whatsapp),
            ("Gestionar Usuarios", "Control de cuentas y credenciales IAM", ft.Icons.GROUP, ft.Colors.BLUE_400, interfaz.mostrar_gestion_usuarios),
            ("Manual de Uso", "Documentación oficial del administrador en PDF", ft.Icons.MENU_BOOK, ft.Colors.CYAN_400, interfaz.mostrar_manual_usuario),
        ])
    elif rol == "master":
        comandos.extend([
            ("Gestión de Claves API", "Administrar tokens y claves de integración externa", ft.Icons.VPN_KEY, ft.Colors.CYAN_400, interfaz.mostrar_gestion_api_keys),
            ("Documentación y Estado API", "Swagger UI, ReDoc y estado del servidor REST", ft.Icons.API, ft.Colors.BLUE_400, interfaz.mostrar_estado_api),
            ("Sesiones de API Activas", "Ver y revocar sesiones REST conectadas", ft.Icons.DEVICES, ft.Colors.TEAL_400, interfaz.mostrar_sesiones_api),
            ("Gestión de Ambientes", "Conmutar entre Producción y QA / Pruebas", ft.Icons.TUNE, ft.Colors.AMBER_400, interfaz.mostrar_gestion_ambientes),
            ("Registro de Auditoría", "Trazabilidad forense e historial de eventos", ft.Icons.SECURITY, ROJO, interfaz.mostrar_registro_auditoria),
            ("Copia de Seguridad", "Gestión de respaldos y espejo en red", ft.Icons.BACKUP, ft.Colors.PURPLE_400, interfaz.mostrar_dialogo_backup),
            ("Gestionar Usuarios", "Control de cuentas y credenciales IAM", ft.Icons.MANAGE_ACCOUNTS, ft.Colors.BLUE_400, interfaz.mostrar_gestion_usuarios),
            ("Configuración SMTP", "Servidor de correo para reportes", ft.Icons.SETTINGS_APPLICATIONS, ft.Colors.TEAL_400, interfaz.mostrar_configuracion_smtp),
            ("Alertas Telegram", "Configuración de bot de avisos proactivos", ft.Icons.SEND, ft.Colors.CYAN_400, interfaz.mostrar_configuracion_telegram),
            ("Restaurar Documentos", "Recuperación de base de datos desde copias de seguridad", ft.Icons.RESTORE, ft.Colors.DEEP_ORANGE_400, interfaz.confirmar_restaurar),
            ("Archivado Histórico", "Archivar pedidos antiguos y compactar base de datos", ft.Icons.AUTO_DELETE, ft.Colors.BROWN_400, interfaz.mostrar_dialogo_archivo_historico),
            ("Mercado Libre API (Credenciales)", "Configuración OAuth y sincronización API", ft.Icons.CLOUD_SYNC, ft.Colors.AMBER_600, interfaz.mostrar_sincronizacion_mercadolibre),
            ("Manual de Uso", "Documentación oficial del usuario master en PDF", ft.Icons.MENU_BOOK, ft.Colors.CYAN_400, interfaz.mostrar_manual_usuario),
        ])
    elif rol == "despachador":
        comandos.extend([
            ("Despacho", "Control de despacho QR por bultos y confirmación manual", ft.Icons.LOCAL_SHIPPING, ROJO, interfaz.mostrar_modulo_despacho),
        ])
    elif rol == "picker":
        comandos.extend([
            ("Descontar Mercado Libre", "Escaneo rápido de paquetes y etiquetas ML", ft.Icons.STOREFRONT, ft.Colors.AMBER_600, interfaz.mostrar_descuento_mercado_libre),
            ("Planificar Mercado Full", "Subir Excel de Full y monitorear avance en vivo", ft.Icons.ADD_TASK, ft.Colors.RED_400, interfaz.mostrar_planificar_full),
            ("Preparar Mercado Full", "Picking guiado por código de barras de envío Full", ft.Icons.LOCAL_SHIPPING, ft.Colors.ORANGE_400, interfaz.mostrar_picking_guiado_full),
            ("Descontar Mercado Full", "Procesamiento directo de envíos Mercado Libre Full", ft.Icons.FILE_DOWNLOAD, ft.Colors.ORANGE_400, interfaz.mostrar_descuento_mercado_full),
            ("Ingreso de Mercadería", "Entrada rápida de stock", ft.Icons.INPUT, ft.Colors.GREEN_400, interfaz.mostrar_dialogo_ingreso_rapido),
            ("Ingreso de Fábrica", "Escáner rápido de recepción de mercadería", ft.Icons.INVENTORY_2, ft.Colors.ORANGE_400, interfaz.mostrar_ingreso_fabrica),
            ("Egreso de Mercadería", "Salida rápida de stock", ft.Icons.OUTPUT, ft.Colors.RED_400, interfaz.mostrar_dialogo_salida_rapida),
            ("Manual de Uso", "Documentación oficial en PDF", ft.Icons.MENU_BOOK, ft.Colors.CYAN_400, interfaz.mostrar_manual_usuario),
        ])
    else:  # rol == "consulta" u otros
        comandos.extend([
            ("Abrir Informe", "Descargar o visualizar informes y balances", ft.Icons.OPEN_IN_NEW, ft.Colors.INDIGO_400, interfaz.abrir_informe),
            ("Compartir por Correo", "Enviar informes por correo", ft.Icons.EMAIL, ft.Colors.BLUE_300, interfaz.compartir_correo),
            ("WhatsApp Web", "Compartir informes vía WhatsApp", ft.Icons.CHAT, ft.Colors.GREEN_600, interfaz.compartir_whatsapp),
            ("Manual de Uso", "Documentación oficial de consulta en PDF", ft.Icons.MENU_BOOK, ft.Colors.CYAN_400, interfaz.mostrar_manual_usuario),
        ])

    return comandos


def obtener_comandos_sistema(interfaz: Any) -> list[TipoComando]:
    """Retorna los comandos globales de personalización de entorno, temas y vistas."""
    return [
        ("Mover Barra: A la Izquierda", "Ubicar el panel de menú en el lateral izquierdo", ft.Icons.DOCK, ft.Colors.LIGHT_BLUE_300, lambda: getattr(interfaz, "cambiar_posicion_sidebar", lambda _p: None)("izquierda")),
        ("Mover Barra: A la Derecha", "Ubicar el panel de menú en el lateral derecho", ft.Icons.DOCK, ft.Colors.LIGHT_BLUE_300, lambda: getattr(interfaz, "cambiar_posicion_sidebar", lambda _p: None)("derecha")),
        ("Mover Barra: Arriba (Horizontal)", "Ubicar el menú superior de forma horizontal", ft.Icons.HORIZONTAL_SPLIT, ft.Colors.TEAL_300, lambda: getattr(interfaz, "cambiar_posicion_sidebar", lambda _p: None)("arriba")),
        ("Mover Barra: Abajo (Horizontal)", "Ubicar el menú inferior de forma horizontal", ft.Icons.HORIZONTAL_SPLIT, ft.Colors.TEAL_300, lambda: getattr(interfaz, "cambiar_posicion_sidebar", lambda _p: None)("abajo")),
        ("Ocultar Barra (Pantalla Completa)", "Modo enfoque sin barra lateral (usa F2 o el header)", ft.Icons.FULLSCREEN, ft.Colors.AMBER_300, lambda: getattr(interfaz, "cambiar_posicion_sidebar", lambda _p: None)("oculto")),
        ("Alternar Modo Claro / Oscuro", "Cambiar entre apariencia diurna y nocturna", ft.Icons.DARK_MODE, ft.Colors.PURPLE_300, interfaz.alternar_tema),
        ("Abrir Asistente / Chat de Equipo", "Panel interactivo de consultas y chat interno", ft.Icons.SMART_TOY, ft.Colors.GREEN_300, interfaz.alternar_chat_flotante),
        ("Actualizar Todo (Refrescar)", "Recargar pedidos, contadores y métricas", ft.Icons.REFRESH, ft.Colors.ORANGE_300, interfaz.actualizar_estado),
    ]


def obtener_catalogo_completo_comandos(rol: str, interfaz: Any) -> list[TipoComando]:
    """Retorna la lista unificada de comandos por rol más comandos globales."""
    return obtener_comandos_rol(rol, interfaz) + obtener_comandos_sistema(interfaz)
