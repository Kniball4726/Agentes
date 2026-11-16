# -*- coding: utf-8 -*-
"""Contenido estructurado en 12 diapositivas para la Presentación al Tren Ejecutivo."""

from __future__ import annotations

SLIDE_1_KPIS: list[tuple[str, str, str]] = [
    ("USD 0", "Licencias Externas", "Sin costo por terminal LAN, móvil ni analítica"),
    ("5 Roles SoD", "Control Interno", "Segregación Operador, Picker, Admin, Master y Consulta"),
    ("SQLite-First", "Operación Continua", "Modo WAL concurrente sin bloqueos de Excel"),
    ("3 Canales + QR", "Cierre Unificado", "Mayoristas, Mercado Libre, Full e Ingresos en 1 flujo"),
]

SLIDE_1_PILARES: list[tuple[str, str]] = [
    (
        "Cero Licencias sobre Infraestructura Actual",
        "Opera desde la PC Windows del depósito sobre red local HTTPS sin servidores en la nube ni abonos por puesto.",
    ),
    (
        "Continuidad Operativa Multi-Puesto",
        "Múltiples computadoras y celulares operan al mismo tiempo sobre stock real sin desfasajes ni archivos bloqueados.",
    ),
    (
        "Trazabilidad Completa Punta a Punta",
        "Cada unidad ingresada, descontada, reubicada o despachada queda asociada a usuario, rol, comprobante y auditoría.",
    ),
    (
        "Ecosistema Completo Listo para Escalar",
        "Incluye PWA offline-first, App Flutter Android/iOS, Mapa de Calor ABC, Radar de Anomalías y API REST v1.",
    ),
]

SLIDE_2_COMPARATIVA: list[tuple[str, str]] = [
    (
        "Planillas Productos.xlsx bloqueadas o desactualizadas entre puestos",
        "Persistencia transaccional SQLite (WAL) concurrente con exportación atómica compatible hacia Productos.xlsx.",
    ),
    (
        "Riesgo de descontar dos veces un mismo remito o archivo de venta",
        "Huella SHA-256 antiduplicados, idempotencia de red y bloqueo temporal de edición (soft-lock 5 min).",
    ),
    (
        "Carga lenta de comprobantes variados (PDF, Excel, Word, Full)",
        "Parsers automáticos multi-formato y flujos guiados por código de barras desde PC o cámara móvil.",
    ),
    (
        "Cierres diarios extensos y difíciles de conciliar por canal",
        "Cierre de Jornada en 3 columnas (Operario) + Consolidado total por SKU (Administración) + Hoja de Ruta.",
    ),
    (
        "Desconocimiento sobre quién armó, modificó o despachó un pedido",
        "Bitácora forense de auditoría y estados logísticos trazables: Armado -> Despachado -> Entregado.",
    ),
    (
        "Lecturas perdidas ante microcortes de Wi-Fi en pasillos",
        "PWA Offline-First con cola local (localStorage), banner de conectividad y sincronización automática al reconectar.",
    ),
]

SLIDE_3_PLATAFORMAS: list[tuple[str, str]] = [
    (
        "Servidor Central LAN HTTPS (Puerto 8550)",
        "Motor ASGI FastAPI + Starlette + Flet con certificados TLS, acceso remoto vía Tailscale VPN, arranque silencioso (.vbs), inicio automático Windows y control en System Tray.",
    ),
    (
        "Modo Escritorio y Procesamiento Desatendido",
        "Ejecución local directa (--desktop), procesamiento batch automático (--auto) y simulación segura de solo lectura (--simular).",
    ),
    (
        "PWA Web Instalable y Escáner Offline-First",
        "Escáner por cámara WebRTC / BarcodeDetector con cola offline en navegador, validado mediante TypeScript estático (checkJs + JSDoc sin build).",
    ),
    (
        "App Móvil Nativa Flutter y Multi-Ambiente",
        "Cliente Android (.APK) e iOS con actualizaciones OTA en LAN, sumado a separación de ambientes Producción y QA con generador de datos de prueba.",
    ),
]

SLIDE_4_ENTRADAS: list[tuple[str, str]] = [
    (
        "Ingreso de Fábrica Planificado y Guiado",
        "Importación de remitos/planillas de fábrica con emparejamiento automático de SKU y barras, validando cantidades esperadas vs. ingresadas paso a paso.",
    ),
    (
        "Movimientos Rápidos Tipificados",
        "Registro ágil de Ingresos y Egresos de mercadería con motivos operacionales controlados (devoluciones, rotura/merma, ajustes, muestras).",
    ),
    (
        "Modo Pistoleo Continuo",
        "Lectura consecutiva mediante lector USB/Bluetooth o cámara móvil: aplica el ajuste al instante al leer el código de barras sin clics adicionales.",
    ),
    (
        "Botón Deshacer (6s) y Reversión Segura",
        "Reversión inmediata ante lecturas accidentales con confirmación sonora; al anular un pedido, las unidades retornan atómicamente al stock en SQLite.",
    ),
]

SLIDE_5_PIPELINE: list[tuple[str, str]] = [
    ("1. INGRESO / CARGA", "Mayoristas PDF, Canjes\nML / Full y Fábrica"),
    ("2. VALIDACIÓN", "SKU, EAN-13 / AIM\ny huella SHA-256"),
    ("3. SQLITE-FIRST", "Descuento atómico WAL\ny soft-lock de edición"),
    ("4. RÓTULOS QR", "Térmico 100x150 mm\ny planchas A4 (x10)"),
    ("5. DESPACHO", "Armado -> Despachado\n-> Entregado en lote"),
]

SLIDE_5_CANALES: list[tuple[str, str]] = [
    (
        "Mayoristas (PDF) y Canjes (Excel)",
        "Parsers especializados para remitos PDF mayoristas y planillas Excel de canjes con vinculación directa al maestro de clientes.",
    ),
    (
        "Mercado Libre (.docx y API OAuth 2.0)",
        "Descuento desde etiquetas/remitos Word o sincronización automática de órdenes pagadas desde la API oficial de Mercado Libre.",
    ),
    (
        "Mercado Libre Full (Planificación y Picking)",
        "Módulo completo para planificar envíos Full, ejecutar Picking Guiado en depósito y cerrar despachos Full sin desvíos.",
    ),
    (
        "Impresión de Rótulos QR y Estados Logísticos",
        "Impresión desatendida directa al spooler Windows (100x150 mm, ej. Zebra) o en hojas A4 compactas (10 rótulos) y actualización masiva de entregas.",
    ),
]

SLIDE_6_INVENTARIO: list[tuple[str, str]] = [
    (
        "Inventario en Vivo con Escáner PC / Móvil",
        "Consulta y ajuste en tiempo real por código interno o de barras (normalización AIM/EAN-13) desde pistola física, webcam o celular.",
    ),
    (
        "Conteo Físico Ciego y Conciliación",
        "Auditoría física sin exhibir el saldo digital previo, cálculo de diferencias reales y generación automática de respaldo de ajuste.",
    ),
    (
        "Alertas de Quiebre y Compras Sugeridas",
        "Detección temprana de stock agotado o debajo del mínimo, banner preventivo y cálculo de reposición y pedidos a fábrica.",
    ),
    (
        "Kardex Histórico y Sincronización Excel",
        "Trazabilidad unitaria de cada entrada/salida en SQLite y exportación/sincronización bidireccional controlada con Descuentos/Productos.xlsx.",
    ),
]

SLIDE_7_CIERRES: list[tuple[str, str]] = [
    (
        "Cierre de Jornada SQLite-First en 3 Canales",
        "Consolida Mayoristas, Mercado Libre y Full + Ingresos desde la base transaccional sin depender de carpetas locales.",
    ),
    (
        "Reporte Operario vs. Consolidado Admin",
        "El Operario recibe una vista limpia en 3 columnas (solo ítems movidos); Administración obtiene el total sumado por SKU.",
    ),
    (
        "Cierre de Mercado, Cierres Admin y Hojas de Ruta",
        "Control dedicado de despachos de mercado, supervisión gerencial de turnos cerrados y Hojas de Ruta agrupadas por transporte.",
    ),
    (
        "Centro de Reportes y Envío Directo",
        "Acceso centralizado en PDF/Excel, enlaces de descarga protegidos con firma HMAC (?dt=) y envío por Correo SMTP o WhatsApp Web.",
    ),
]

SLIDE_8_ANALITICA: list[tuple[str, str]] = [
    (
        "Dashboard de Métricas y Rendimiento 360°",
        "Indicadores gerenciales en vivo de pedidos, bultos, promedio por despacho, pendientes vs. cerrados y estadísticas de salida por canal.",
    ),
    (
        "Radar Predictivo de Anomalías (Z-score)",
        "Detecta picos estadísticos (> media + 2 desviaciones estándar), egresos masivos (>= 50% del stock) y artículos con cobertura menor a 3 días.",
    ),
    (
        "Mapa de Calor de Depósito (48 Ubicaciones)",
        "Visualización térmica interactiva por Rack (A-D), Módulo (1-4) y Nivel (1-3) combinada con clasificación automática Pareto ABC.",
    ),
    (
        "Plan de Reubicación Ergonómica (1 Clic)",
        "Detecta artículos de alta rotación en zonas lejanas o en altura y permite reubicarlos a Zona Dorada en 1 clic con confirmación inmediata.",
    ),
]

SLIDE_9_COLABORACION: list[tuple[str, str]] = [
    (
        "Asistente Virtual Bot (NLP y Comandos)",
        "Responde en lenguaje natural o por comandos (/estado, /criticos, /stock, /reposicion, /diagnostico, /metricas, /simular) según el rol.",
    ),
    (
        "Chat de Equipo en Tiempo Real con Campana",
        "Canal general y mensajes privados (@usuario) con referencia automática a pedidos (#nota), campana breve Web Audio/Desktop y punto de no leídos independiente por usuario.",
    ),
    (
        "Interfaz Adaptable y Navegación Rápida",
        "5 disposiciones de barra (izquierda, derecha, arriba, abajo u oculta), barra inferior móvil (Zona del Pulgar), paleta rápida F2 / Ctrl+K y modo claro/oscuro.",
    ),
    (
        "Preferencias por Usuario y SOPs Integrados",
        "Cada usuario guarda tema, impresora térmica, impresión directa y silencio de campana; acceso directo al Manual de Uso PDF por rol.",
    ),
]

SLIDE_10_ROLES_SOD: list[tuple[str, str, str]] = [
    (
        "Operador",
        "Pedidos, Mayoristas, Canjes, ML/Full, Fábrica, Clientes, Rótulos QR, Inventario Vivo y Cierre de Jornada",
        "Sin acceso a catálogo maestro, analítica global, usuarios ni bitácora técnica",
    ),
    (
        "Picker",
        "Picking Guiado Full, Descuento ML/Full, Control e Ingreso de Fábrica e Ingreso/Egreso rápido",
        "Bloqueado en clientes, edición/historial de pedidos, cierres y configuración",
    ),
    (
        "Administrador",
        "Catálogo, sincronización Excel, Métricas 360°, Estadísticas, Heatmap ABC, Anomalías, Cierres y Usuarios",
        "Sin acceso a auditoría forense técnica ni a rollback documental Master",
    ),
    (
        "Master",
        "Auditoría forense, Rollback/Restauración, Backups, API Keys, Ambientes Prod/QA y credenciales externas",
        "Excluido de operar cargas diarias ni descuentos comerciales de stock",
    ),
    (
        "Consulta",
        "Lectura de stock en vivo, ubicaciones, historial de pedidos y descarga autorizada de informes",
        "Solo lectura: sin escritura, descuento, edición ni ejecución de cierres",
    ),
]

SLIDE_11_ECOSISTEMA: list[tuple[str, str]] = [
    (
        "API REST v1 (/api/v1/) y API Keys",
        "Endpoints autenticados para productos, inventario, despacho, documentos y sistema, con gestión de claves X-API-Key y monitor de sesiones activas.",
    ),
    (
        "Notificaciones Telegram, SMTP y Conectores",
        "Alertas automáticas ante quiebres de stock, anomalías estadísticas, bloqueos de seguridad y cierres; credenciales Mercado Libre OAuth y Google Sheets.",
    ),
    (
        "Backups .ZIP, Restauración y Archivo Histórico",
        "Copias automáticas y bajo demanda, rollback/restauración documental ante errores de carga y archivado cronológico para mantener bases ágiles.",
    ),
    (
        "Aseguramiento de Calidad y Ambientes Prod / QA",
        "Entorno QA aislado con seeder de pruebas, batería amplia de tests unitarios Pytest y verificación estática TypeScript (checkJs) en scripts PWA.",
    ),
]

SLIDE_12_HORIZONTES: list[tuple[str, str, str]] = [
    (
        "Corto Plazo\n(Semanas 1-2)",
        "Operación LAN HTTPS unificada, usuarios por rol SoD, Cierres en 3 canales, Rótulos QR y Backups diarios.",
        "Control inmediato del stock y fin de bloqueos Excel.",
    ),
    (
        "Mediano Plazo\n(Meses 1-2)",
        "Escáner móvil PWA / App Flutter en pasillos, Conteo Físico Ciego, OAuth Mercado Libre y Slotting ABC semanal.",
        "Agilidad en picking, detección de mermas y prevención.",
    ),
    (
        "Largo Plazo\n(Meses 3+)",
        "Integración ERP / facturación vía API REST v1, alertas ejecutivas Telegram y supervisión remota vía Tailscale VPN.",
        "Ecosistema logístico integrado para toda la organización.",
    ),
]
