# -*- coding: utf-8 -*-
"""Datos estructurados para la Presentación Ejecutiva de Implementación StockAgent."""

from __future__ import annotations

META_EJECUTIVA: list[tuple[str, str]] = [
    ("Dirigido a:", "Jefatura Inmediata / Supervisión de Depósito, Logística y Administración"),
    (
        "Objetivo del documento:",
        "Presentar las mejoras operativas y arquitectónicas de StockAgent junto con un plan práctico "
        "de implementación en tres horizontes (corto, mediano y largo plazo).",
    ),
    (
        "Estado de la plataforma:",
        "Modularizada en 249 archivos src/ (composición pura sin mixins ni ciclos top-level), "
        "SQLite-first con closing() determinístico y 8 manuales PDF por rol actualizados (v2.3 / 3.2).",
    ),
    (
        "Cobertura verificada:",
        "67 módulos de prueba (409 definiciones def test_): 360 pruebas + 7 subtests aprobados "
        "en los 61 módulos ejecutables en sandbox y 6 módulos ASGI TestClient para entorno host.",
    ),
    (
        "Requisito de arranque:",
        "Opera sobre PC Windows existente en red local (LAN) sin costos de licencias externas, "
        "conservando exportación compatible hacia Descuentos/Productos.xlsx.",
    ),
]

KPIS_PORTADA: list[tuple[str, str, str]] = [
    ("USD 0", "Licencias Externas", "Sin costo por puesto LAN, móvil ni analítica"),
    ("5 Roles SoD", "Gobierno y Seguridad", "HTTPS TLS, DPAPI/Fernet y tokens ?dt="),
    ("SQLite-First", "Sin Bloqueos Excel", "Modo WAL + cierre closing() y 3 canales"),
    ("249 Archivos", "Arquitectura Limpia", "Composición pura, 0 mixins y 0 ciclos"),
]

BENEFICIOS_DIA_UNO: list[tuple[str, str]] = [
    (
        "1. Inventario Confiable SQLite-First",
        "Elimina bloqueos por planillas compartidas: toda operación lee y descuenta directamente "
        "sobre SQLite (modo WAL + closing()), con exportación atómica opcional hacia Productos.xlsx.",
    ),
    (
        "2. Cierre en 3 Canales y Trazabilidad",
        "Procesa remitos PDF, canjes Excel, Mercado Libre / Full e ingresos de fábrica. El operario "
        "recibe cierre compacto en 3 columnas (Mayoristas, Mercado Libre y Full + Ingresos) y "
        "Administración el Consolidado total por producto.",
    ),
    (
        "3. Trabajo Multi-Puesto LAN y Móvil",
        "Múltiples computadoras y celulares operan simultáneamente sobre la red local "
        "(HTTPS + PWA offline-first + app móvil Flutter Android/iOS) con anti-duplicados.",
    ),
    (
        "4. Control Interno y Respaldo",
        "Segregación estricta en 5 roles (Operador, Picker, Administrador, Master y Consulta), "
        "bitácora forense inmutable, contraseñas PBKDF2-600k y backups .zip automáticos.",
    ),
]

COMPARATIVA_DIAGNOSTICO: list[tuple[str, str]] = [
    (
        "Archivo Excel único bloqueado o desactualizado entre varios usuarios",
        "Arquitectura SQLite-first concurrente (WAL + closing()): el depósito y los reportes operan "
        "sin exigir Productos.xlsx cerrado o presente; la planilla se sincroniza bajo demanda.",
    ),
    (
        "Riesgo de descontar dos veces un mismo remito o archivo de venta",
        "Huella criptográfica SHA-256 antiduplicados, claves de idempotencia ante microcortes "
        "y bloqueo temporal (soft-lock TTL 5 min) mientras un operario edita un pedido.",
    ),
    (
        "Carga manual lenta de comprobantes variados (PDF, Excel, Word, Full)",
        "Parsers automáticos para remitos PDF, planillas de canjes, órdenes Mercado Libre "
        "(.docx o API OAuth 2.0), Mercado Full e ingreso de fábrica con lector de barras.",
    ),
    (
        "Desconocimiento sobre quién armó, modificó o despachó un pedido",
        "Bitácora de auditoría por usuario, fecha y origen, con estados logísticos "
        "(Armado -> Despachado -> Entregado) actualizables en lote o por lector QR.",
    ),
    (
        "Cierres del día largos y difíciles de conciliar por canal de venta",
        "Cierre de Jornada SQLite-first: genera reporte Operario discriminado en 3 columnas "
        "(Mayoristas / Mercado Libre / Full + Ingresos solo con ítems movidos), Consolidado Admin "
        "sumado por SKU y Hojas de Ruta por transporte.",
    ),
]

VENTAJAS_OPERATIVAS: list[tuple[str, str]] = [
    (
        "Escaneo Ágil (Pistola y Celular)",
        "Compatible con lectores USB/Bluetooth (normalización AIM/EAN-13) y cámara móvil desde "
        "la PWA o app Flutter, con confirmación acústica instantánea y botón Deshacer (6s).",
    ),
    (
        "Impresión de Rótulos QR y Hojas de Ruta",
        "Emite etiquetas con QR en rollo térmico continuo (100x150 mm directo al spooler Windows) "
        "o planchas A4 compactas de 10 rótulos sin desperdicio de papel.",
    ),
    (
        "Reversión Segura ante Cancelaciones",
        "Al desarmar un pedido anulado, cada artículo retorna atómicamente al inventario físico en "
        "SQLite (y se exporta si corresponde) dejando asiento en logs_auditoria.",
    ),
    (
        "Sin Costos por Puesto ni Curva Pesada",
        "Acceso en 1 clic desde PCs cliente (crear_acceso_directo_cliente.bat), paleta F2 / "
        "Ctrl+K, 8 manuales PDF por rol (v2.3 / 3.2) y mensajes guiados en español.",
    ),
]

MATRIZ_SOD_EJECUTIVA: list[tuple[str, str, str]] = [
    (
        "Operador",
        "Carga y modificación exclusiva de pedidos, remitos/canjes, ML/Full, ingreso de fábrica, "
        "rótulos QR, despacho y Cierre de Jornada en 3 canales.",
        "No gestiona catálogo maestro, métricas globales, usuarios ni bitácora forense.",
    ),
    (
        "Picker",
        "Despacho rápido Mercado Libre / Full, Ingreso de Fábrica e Ingreso/Egreso ágil de stock.",
        "Bloqueado en creación/edición/historial de pedidos, clientes, cierres y administración.",
    ),
    (
        "Administrador",
        "Catálogo SQLite-first y sincronización Excel, métricas 360°, Cierres de Operarios "
        "(Consolidado total), stock físico ciego, compras sugeridas y usuarios operativos.",
        "No accede a la bitácora forense técnica ni al rollback documental (imparcialidad SoD).",
    ),
    (
        "Master",
        "Auditoría forense inmutable, rollback documental de lotes, backups .zip, API Keys "
        "y credenciales cifradas (SMTP, Telegram y OAuth Mercado Libre).",
        "Excluido de cargar pedidos comerciales o alterar saldos operativos diarios.",
    ),
    (
        "Consulta",
        "Lectura de stock en vivo, ubicación en racks, historial e informes protegidos (?dt=).",
        "Sin permisos de escritura, descuento, edición ni ejecución de cierres.",
    ),
]

TARJETAS_ARQUITECTURA_SEGURIDAD: list[tuple[str, str]] = [
    (
        "Radar Predictivo de Anomalías (Z-score)",
        "Detecta estadísticamente picos atípicos (> media + 2s), salidas masivas (>=50% del "
        "stock disponible) y artículos con cobertura crítica menor a 3 días.",
    ),
    (
        "Mapa de Calor y Slotting ABC",
        "Clasifica Pareto (75% A / 15% B / 10% C) en 48 ubicaciones (Racks A-D, Módulos 1-4, "
        "Niveles 1-3) para mover alta rotación hacia la zona ergonómica (Golden Zone).",
    ),
    (
        "Red LAN Cifrada y Endurecimiento",
        "HTTPS/TLS por defecto en puerto 8550, Firewall restringido al perfil Privado, Swagger "
        "apagado por defecto, PBKDF2-600k, DPAPI/Fernet y tokens HMAC efímeros ?dt=.",
    ),
    (
        "Arquitectura Modular y Composición Pura",
        "Código en paquetes especializados (core, orders en 11 repos, products, inventory, stock, "
        "integrations, cli, ui con AppDependencies): 0 mixins, 0 ciclos top-level y 409 tests.",
    ),
]

PASOS_PIPELINE: list[tuple[str, str]] = [
    ("1. INGRESO / CARGA", "PDF, Canjes, ML/Full\no Fábrica"),
    ("2. VALIDACIÓN", "SKU, barras EAN-13\ny hash SHA-256"),
    ("3. SQLITE-FIRST", "WAL + closing()\ny exportación opcional"),
    ("4. DESPACHO QR", "Rótulos 100x150 / A4\ny estado logístico"),
    ("5. CIERRE 3 CANALES", "Operario + Admin,\nHoja Ruta y Backup"),
]

HORIZONTE_1: list[tuple[str, str, str]] = [
    (
        "1. Despliegue en PC Servidor y Red Privada",
        "Ejecutar configurar_firewall_red.bat (perfil Privado), iniciar el servidor HTTPS en "
        "puerto 8550 y crear accesos directos con crear_acceso_directo_cliente.bat.",
        "Cero inversión en servidores; múltiples puestos trabajando en red local al instante.",
    ),
    (
        "2. Ordenamiento IAM y Capacitación por Rol",
        "Cambiar la clave inicial Master, crear usuarios por función real (Operador, Picker, "
        "Administrador, Consulta) y entregar los 8 manuales PDF botón por botón (v2.3 / 3.2).",
        "Responsabilidad individual en cada transacción y curva de aprendizaje mínima.",
    ),
    (
        "3. Operación Unificada SQLite-First",
        "Canalizar remitos, canjes, Mercado Libre, Full y movimientos rápidos por StockAgent sin "
        "bloqueos por Excel; exportar Descuentos/Productos.xlsx atómicamente cuando se necesite.",
        "Fin del desfasaje entre stock real y planillas compartidas desde la primera semana.",
    ),
    (
        "4. Cierres en 3 Canales, QR y Backups",
        "Emitir rótulos QR, cerrar turno generando el reporte de 3 columnas + Consolidado Admin "
        "+ Hoja de Ruta y activar copias .zip automáticas.",
        "Conciliación diaria clara por canal, conformidad de choferes y respaldo garantizado.",
    ),
]

HORIZONTE_2: list[tuple[str, str, str]] = [
    (
        "1. Relevamiento y Despacho Móvil Wi-Fi",
        "Habilitar el cliente móvil Flutter (Android .APK con actualización OTA o PWA iOS) y el "
        "escáner web con cola offline (assets/scanner.html) para conteo en pasillos.",
        "Elimina anotaciones en papel y conserva lecturas en zonas con señal Wi-Fi intermitente.",
    ),
    (
        "2. Conteo Físico Ciego y Reposición",
        "Programar conteos cíclicos sin mostrar el saldo digital previo, ejecutar la comparativa "
        "de diferencias y generar la planilla sugerida de pedido a fábrica.",
        "Detecta mermas o sobrantes reales a tiempo y evita compras urgentes o sobrestock.",
    ),
    (
        "3. Conexión OAuth 2.0 con Mercado Libre",
        "Cargar credenciales en el perfil Master para que Administración sincronice órdenes "
        "pagadas vía API REST oficial y respaldo .docx automático.",
        "Reduce carga manual en picos de venta online y mitiga errores de emparejamiento SKU.",
    ),
    (
        "4. Alertas Proactivas y Slotting ABC",
        "Activar notificaciones SMTP/Telegram ante quiebres, bloqueos de acceso y anomalías "
        "Z-score, reubicando productos según el Mapa de Calor térmico.",
        "Anticipa desabastecimientos y acorta los recorridos diarios de picking.",
    ),
]

HORIZONTE_3: list[tuple[str, str, str]] = [
    (
        "1. Integración ERP / Facturación / Tienda",
        "Conectar sistemas administrativos o e-commerce con API Keys (X-API-Key), endpoint "
        "/api/v1/productos/{codigo}/stock y Webhooks salientes validados contra SSRF.",
        "Sincronización automática entre facturación, canales digitales y existencias físicas.",
    ),
    (
        "2. Acceso Remoto Corporativo sin Exposición",
        "Habilitar supervisión de gerencia o sucursales vía VPN mallada cifrada (Tailscale) "
        "sobre HTTPS sin abrir puertos del router hacia internet.",
        "Visibilidad gerencial segura desde cualquier ubicación manteniendo perímetro cerrado.",
    ),
    (
        "3. Escalamiento Multi-Depósito Seguro",
        "Aprovechar la composición pura en repositorios (src/auth, src/orders, src/products, "
        "src/inventory, src/stock) y la suite de pruebas para sumar sucursales o motor SQL central.",
        "Evolución sostenible con mínimo riesgo técnico al introducir nuevas reglas de negocio.",
    ),
    (
        "4. Inteligencia Histórica y Auditoría Anual",
        "Explotar el archivado histórico cronológico (data/historico/YYYY/MM/), métricas por "
        "transportista/armador y bitácora forense para negociar abastecimiento.",
        "Decisiones de compras y dotación respaldadas por datos históricos auditables.",
    ),
]

SINTESIS_HORIZONTES: list[tuple[str, str, str, str, str]] = [
    (
        "Corto Plazo\n(Semanas 1–4)",
        "Estabilidad y Cierre 3 Canales",
        "HTTPS LAN, Roles SoD, SQLite-first, QR, Consolidado Admin y Backups .zip",
        "Muy bajo (PC actual)",
        "Fin de bloqueos Excel y control real del turno",
    ),
    (
        "Mediano Plazo\n(Meses 2–4)",
        "Movilidad y Prevención",
        "App Android / PWA, Conteo Ciego, API ML, Alertas Telegram/SMTP y Slotting ABC",
        "Bajo–Medio (inducción puntual)",
        "Agilidad en pasillos y anticipación a quiebres",
    ),
    (
        "Largo Plazo\n(Meses 5+)",
        "Ecosistema Integrado",
        "API REST v1 (X-API-Key), Webhooks, Tailscale VPN y Escala Multi-Depósito",
        "Planificado por TI / Gerencia",
        "Plataforma logística integrada a toda la empresa",
    ),
]

PASOS_PILOTO: list[tuple[str, str, str]] = [
    (
        "Paso 1",
        "Definir PC Servidor y Red",
        "Designar la PC principal del depósito en red privada LAN y fijar su IP local estática.",
    ),
    (
        "Paso 2",
        "Configurar Seguridad Inicial",
        "Ejecutar configurar_firewall_red.bat (Privado), iniciar servidor HTTPS y cambiar claves "
        "por defecto de Master y cuentas por rol.",
    ),
    (
        "Paso 3",
        "Conectar Puestos del Equipo",
        "Generar accesos con crear_acceso_directo_cliente.bat e instalar el certificado local "
        "(instalar_certificado.bat) en cada terminal cliente.",
    ),
    (
        "Paso 4",
        "Operar Piloto (5 a 10 días)",
        "Procesar remitos PDF, Mercado Libre/Full, ingresos de fábrica y ejecutar Cierres de "
        "Jornada (3 canales + Consolidado Admin + Hoja de Ruta + backup .zip).",
    ),
    (
        "Paso 5",
        "Evaluación con Jefatura",
        "Medir tiempos de cierre, exactitud de stock en SQLite vs. conteo físico y conformidad "
        "operativa antes de habilitar el Horizonte 2.",
    ),
]
