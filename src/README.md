# Arquitectura Modular del Backend y Frontend (src/)

Este directorio contiene el código fuente principal de **StockAgent**, estructurado bajo principios de arquitectura limpia, separación de responsabilidades (SRP), alta mantenibilidad y resiliencia ante errores.

---

## 🏛️ Visión General de la Arquitectura

```text
src/
├── core/                       # Núcleo de excepciones y contratos de dominio
│   ├── __init__.py             # Exportaciones públicas de excepciones y entorno
│   ├── exceptions.py           # Jerarquía unificada de errores tipados
│   ├── environment.py          # Aislamiento de perfiles de ejecución (Producción vs QA Sandbox)
│   └── system_reset.py         # Restablecimiento controlado a estado virgen (Clean Slate)
│
├── api/                        # API REST v1 desacoplada (FastAPI)
│   ├── deps.py                 # Autenticación Bearer/API Key, sesiones SQLite y tokens ?dt=
│   ├── schemas.py              # Esquemas Pydantic de entrada/salida
│   └── v1/                     # Endpoints por dominio (auth, despacho, documentos, inventario, productos, sistema, router)
│
├── server_app/                 # Servidor web ASGI/FastAPI modularizado (reemplaza server.py monolítico)
│   ├── __init__.py             # Orquestación FastAPI, lifespan y parcheo Flet
│   ├── flet_patch.py           # Integración Flet WebApp y manejo seguro de subidas/sesiones
│   ├── middleware.py           # CORS LAN privada, cabeceras HTTP de seguridad y tracking activo
│   ├── network_utils.py        # Resolución IP LAN/Tailscale y sondeo de puertos
│   ├── protected_docs_routes.py# Endpoints /documentacion/ y /informes/ protegidos con sesión o ?dt=
│   └── static_routes.py        # PWA (/manifest.json, /sw.js, /offline.html), escáner y OTA APK
│
├── auth/                       # Dominio de autenticación, seguridad y usuarios
│   ├── models.py               # Dataclasses inmutables (User, ApiKey, UserRole, USER_ROLES)
│   ├── password.py             # Hashing PBKDF2-HMAC-SHA256 (600,000 iteraciones) y hmac.compare_digest
│   ├── schema.py               # Inicialización y migración de esquema SQLite (incluye rol picker)
│   ├── validators.py           # Validadores de rol, nombre, correo y políticas de clave
│   ├── events.py               # Emisión desacoplada de eventos y alertas de seguridad
│   ├── lockout_repo.py         # Mixin de bloqueo por intentos fallidos (5 intentos / 15 min)
│   ├── api_tokens_repo.py      # Mixin de api_sessions (SHA-256) y API Keys
│   └── store.py                # Repositorio SQLite UserStore ensamblado con mixins
│
├── orders/                     # Dominio de pedidos, clientes y trazabilidad
│   ├── models.py               # Modelos Pedido, Cliente, MensajeChat, LogAuditoria, CierreJornada
│   ├── schema.py               # Creación de tablas e índices de pedidos.sqlite3
│   ├── client_repo.py          # Mixin CRUD de clientes y autogeneración de códigos CLI-XXXXXX
│   ├── chat_repo.py            # Mixin de canal colaborativo y menciones #PED-XXXX
│   ├── concurrency_repo.py     # Mixin de soft-locking temporal (TTL) e idempotencia SHA-256
│   ├── dispatch_repo.py        # Mixin de estados de despacho y hojas de ruta
│   ├── audit_repo.py           # Mixin de bitácora transaccional y auditoría forense
│   ├── closure_repo.py         # Mixin de cierres de jornada y consolidación documental
│   ├── factory_plan_repo.py    # Mixin de planes y verificación de ingresos de fábrica
│   ├── full_plan_repo.py       # Mixin de planes y picking guiado para Mercado Envíos Full
│   ├── stock_flow_repo.py      # Mixin de analítica ejecutiva y agregaciones de stock en vivo
│   └── store.py                # Repositorio SQLite OrderStore unificado
│
├── products/                   # Dominio modular de productos, catálogo y despachos
│   ├── barcode_utils.py        # Normalización EAN-13 / SKU y lectura Barcode Wedge
│   ├── catalog_read_repo.py    # Consultas optimizadas de catálogo, caché SKU y paginación
│   ├── catalog_write_repo.py   # CRUD de catálogo, precios, umbrales y ubicaciones slotting
│   ├── catalog_repo.py         # Fachada combinada de lectura/escritura del catálogo
│   ├── movements_repo.py       # Historial de movimientos, despachos y enriquecimiento atómico
│   ├── physical_repo.py        # Conteo físico de operarios y comparativas de discrepancia
│   ├── notifications_repo.py   # Notificaciones administrativas y alertas v_analisis_reposicion
│   └── store.py                # Repositorio SQLite ProductStore unificado
│
├── inventory/                  # Dominio modular de inventario y sincronización Excel
│   ├── manager.py              # StockManager central (adaptable a Producción y QA Sandbox)
│   ├── catalog_loader.py       # Carga fast-path desde SQLite / importación inicial Productos.xlsx
│   ├── discount_engine.py      # Motor transaccional de descuentos y cálculo de lotes
│   ├── excel_sync.py           # Exportación y refresco de filas en Excel
│   └── template_sync.py        # Sincronización atómica preservando estilos de Productos.xlsx
│
├── qa/                         # Módulo de Aseguramiento de Calidad y Pruebas Aisladas
│   ├── __init__.py             # Exportaciones del paquete QA
│   └── seeder.py               # Sembrador de datos sintéticos realistas para testing seguro
│
├── stock/                      # Dominio de stock, reposición y reportes
│   ├── models.py               # Dataclasses RegistroDescuento y ReporteStock
│   ├── report_styles.py        # Paletas, tipografías y estilos ReportLab/XLS
│   ├── reports_stock.py        # Renderizado de reportes de existencias y movimientos
│   ├── reports_ops.py          # Reportes de operaciones, cierres y despachos
│   ├── xls_exporter.py         # Exportador binario Excel (.xls)
│   ├── pdf_exporter.py         # Exportador PDF vectorial (ReportLab)
│   ├── manifest_pdf.py         # Hoja de Ruta de transporte en PDF
│   ├── replenishment.py        # Algoritmos de sugerencia y armado de pedidos a fábrica
│   ├── physical_inventory.py   # Reconciliación de inventario físico vs. digital
│   ├── reportes_service.py     # Servicio central de generación e indexación de reportes
│   └── reports.py              # Fachada retrocompatible de exportadores
│
├── labels/                     # Generación modular de rótulos con QR y códigos de barras
│   ├── utils.py                # Utilidades de renderizado QR y normalización
│   ├── thermal_labels.py       # Etiquetas térmicas continuas (100x150 mm)
│   └── a4_labels.py            # Planchas compactas A4 para bultos
│
├── parsers/                    # Parsers modulares de comprobantes (PDF, Excel, DOCX)
│   ├── remito_parser.py        # Parser de remitos mayoristas PDF
│   ├── canjes_parser.py        # Parser de planillas de canjes Excel
│   ├── mercado_libre_parser.py # Parser de órdenes DOCX de Mercado Libre
│   ├── mercado_full_parser.py  # Parser de envíos Mercado Envíos Full
│   ├── factory_parser.py       # Parser de remitos de ingreso de fábrica
│   └── physical_stock_parser.py# Parser de planillas de relevamiento físico
│
├── integrations/               # Integraciones externas y canales de notificación
│   ├── email_sender.py         # Envío SMTP con credenciales cifradas
│   ├── mercado_libre_api.py    # Conector OAuth 2.0 y órdenes REST Mercado Libre
│   ├── sheets_manager.py       # Integración opcional con Google Sheets
│   └── telegram_notifier.py    # Notificador asíncrono de alertas por Telegram Bot
│
├── chat/                       # Asistente interno e intenciones semánticas por rol
│   ├── intent_parser.py        # Clasificación de consultas e intenciones de chat
│   ├── role_help.py            # Respuestas y chips contextuales según SoD del rol
│   └── formatters.py           # Formateo de respuestas, pedidos y métricas en chat
│
├── cli/                        # Operaciones CLI e interactive_flows desacoplados
│   ├── archive_ops.py          # Procesamiento y archivado por consola
│   └── interactive_flows.py    # Flujos interactivos de menú CLI
│
├── tray/                       # Icono en Bandeja del Sistema (System Tray de Windows)
│   ├── net_and_images.py       # Obtención de IP LAN y badges de estado PIL
│   ├── service.py              # Ciclo de vida global del icono y notificaciones de red
│   └── tray_controller.py      # Controlador pystray y menú contextual
│
├── ui/                         # Capa de presentación gráfica y vistas (Flet)
│   ├── theme.py                # Paleta de colores corporativos Ultratech y tokens visuales
│   ├── app_config.py           # Constantes de configuración GUI
│   ├── protocols.py            # Contratos tipados (Protocol) e inyección de AppDependencies
│   ├── user_preferences.py     # Persistencia desacoplada de preferencias UI por usuario
│   ├── dashboard_presenter.py  # Presentador desacoplado del Dashboard reactivo
│   ├── controllers/            # Controladores desacoplados por composición pura:
│   │                           # auth_controller, batch_controller, chat_controller,
│   │                           # dialog_coordinator, document_viewer_service, file_transfer_service,
│   │                           # responsive_controller, session_sync_service, theme_controller
│   ├── components/             # admin_flow_analytics, admin_operations_bar, audio_manager,
│   │                           # debounce, docking_manager, floating_chat, floating_chat_intents,
│   │                           # header, mobile_nav, network_heartbeat, panels, print_labels,
│   │                           # sidebar, sidebar_horizontal, sidebar_sections, window_manager
│   └── dialogs/                # Módulos desacoplados por caso de uso:
│                               # auth_* + dlg_auth, analytics_* + dlg_analytics, api_panel_tabs + dlg_api + dlg_api_keys,
│                               # cierre/ + dlg_cierre, dlg_clientes, dlg_command_palette, dlg_email,
│                               # dlg_escaner, dlg_anomalias, dlg_archivo_historico, dlg_backup,
│                               # dlg_control_ingreso_fabrica, dlg_gestion_ambientes, dlg_picking_guiado_full,
│                               # dlg_planificar_full, dlg_planificar_ingreso_fabrica,
│                               # dlg_heatmap + heatmap_render, historial_* + dlg_historial_pedidos,
│                               # dlg_informes, dlg_ingreso_fabrica + ingreso_fabrica_archivo,
│                               # dlg_inventario_vivo + inventario_vivo_views, dlg_mercado_full,
│                               # dlg_mercadolibre, dlg_mercadolibre_descuento + ml_*, dlg_movimientos_rapidos + *_ops,
│                               # dlg_pedido_fabrica, pedidos_crear + pedidos_gestion + dlg_pedidos,
│                               # dlg_preferencias, dlg_productos + productos_modales, dlg_quiebre,
│                               # dlg_reportes, dlg_restaurar, dlg_smtp, dlg_stock_fisico + stock_fisico_views,
│                               # dlg_stock_ops (fachada), dlg_telegram, dlg_usuarios, dlg_ver_stock
│
├── secretos.py                 # Cifrado de secretos en disco (Windows DPAPI enc:dpapi: / Fernet enc:fernet:)
├── ssl_manager.py              # Autogeneración de certificados X.509 SAN en data/certs/
├── webhook_manager.py          # Despacho asíncrono de webhooks salientes con validación anti-SSRF
├── anomaly_detector.py         # Detector Z-score de consumo anómalo y proyección de agotamiento
├── warehouse_slotting.py       # Matriz de rotación ABC y mapa de calor del depósito
├── system_telemetry.py         # Diagnóstico de salud del servidor (RAM, disco, proceso)
├── alertas_programadas.py      # Planificador de alertas diarias por correo
├── archive_manager.py          # Archivado cronológico en data/historico/YYYY/MM/
├── backup_manager.py           # Respaldos .zip verificados con PRAGMA integrity_check
├── paths.py                    # Resolución segura de rutas relativas a la aplicación
├── logger_config.py            # Configuración de logging rotativo en data/logs/stockagent.log
├── menu.py / agent.py          # Orquestación CLI y de procesamiento por lotes
└── flet_gui.py                 # Orquestador UI por composición pura (delegación a controladores)
```

---

## 🛡️ 1. Jerarquía Unificada de Excepciones (`src/core/exceptions.py`)

Para evitar capturas genéricas silenciosas y mejorar la resiliencia operativa, se implementó una jerarquía estructurada de excepciones de dominio:

```mermaid
classDiagram
    StockAgentError <|-- DomainError
    StockAgentError <|-- InfrastructureError
    StockAgentError <|-- ValidationError
    DomainError <|-- AuthError
    DomainError <|-- OrderStoreError
    DomainError <|-- StockError
    DomainError <|-- DocumentError
    AuthError <|-- UserNotFoundError
    AuthError <|-- AuthenticationError
    AuthError <|-- AccountLockedError
    OrderStoreError <|-- OrderNotFoundError
    OrderStoreError <|-- OrderLockError
    StockError <|-- ProductNotFoundError
    StockError <|-- InsufficientStockError
    InfrastructureError <|-- NetworkError
    InfrastructureError <|-- DatabaseConnectionError
```

### Características Principales:
* **`code`:** Código de error estandarizado (ej: `AUTH_ACCOUNT_LOCKED`, `ORDER_LOCKED_BY_USER`).
* **`status_code`:** Código HTTP equivalente (400, 401, 403, 404, 409, 500) para mapeo inmediato en la API REST.
* **`context`:** Diccionario de metadatos contextuales (usuario, SKU, ID de pedido, IP) que se incluye automáticamente en los registros de auditoría y logs.

---

## 🔐 2. Paquete de Autenticación y Seguridad (`src/auth/`)

Reemplaza el antiguo archivo monolítico `user_store.py` (anteriormente de más de 1,000 líneas), separando responsabilidades:

* **`models.py`:** Define los modelos de datos tipados:
  * `User`: Información de cuenta, rol (`operador`, `picker`, `administrador`, `master`, `consulta`), estado, bloqueo por intentos y preferencias de UI.
  * `ApiKey`: Token de acceso para la API REST con permisos granulares y fecha de expiración.
* **`password.py`:** Seguridad criptográfica:
  * Algoritmo `PBKDF2-HMAC-SHA256` con sal aleatoria criptográfica de 16 bytes (32 caracteres hexadecimales) y `600,000` iteraciones (`PASSWORD_ITERATIONS = 600_000`).
  * Verificación en tiempo constante `hmac.compare_digest` para mitigar ataques de temporización (*timing attacks*).
  * Validación estricta de política de longitud mínima (10 caracteres).
* **`store.py`:** Repositorio transaccional `UserStore`:
  * Gestión en SQLite con modo WAL (`usuarios.sqlite3`).
  * Conteo de intentos fallidos y bloqueo temporal tras 5 fallos consecutivos.
  * Registro de sesiones activas concurrentes y auditoría de accesos.
* *(Las importaciones de este dominio se realizan directamente desde el paquete canónico `src.auth`.)*

---

## 📦 3. Paquete de Pedidos, Auditoría y Concurrencia (`src/orders/`)

Reemplaza el antiguo archivo monolítico `orders_store.py` (anteriormente de más de 1,690 líneas), organizando las operaciones en repositorios mixin especializados:

* **`models.py`:** Define las entidades centrales: `Pedido`, `Cliente`, `MensajeChat`, `LogAuditoria`, `CierreJornada`.
* **`client_repo.py` (`ClientRepositoryMixin`):** CRUD de clientes mayoristas y minoristas, gestión de teléfonos, direcciones y autogeneración de códigos únicos (`CLI-XXXXXX`).
* **`chat_repo.py` (`ChatRepositoryMixin`):** Mensajería interna de equipo, conteo de mensajes no leídos por usuario y enriquecimiento automático de referencias a pedidos (`#PED-1234`).
* **`concurrency_repo.py` (`ConcurrencyRepositoryMixin`):**
  * Soft-locking temporal (Lease/TTL de 5 minutos) en edición de pedidos para evitar colisiones entre operarios.
  * Registro de idempotencia con tokens SHA-256 para prevenir procesamientos duplicados por microcortes de red.
* **`audit_repo.py` (`AuditRepositoryMixin`):** Bitácora transaccional inmutable (`pedidos_auditoria`) con trazabilidad completa de usuario, rol, IP y detalles del cambio.
* **`closure_repo.py` (`ClosureRepositoryMixin`):** Consolidación de cierres de turno, cálculo de métricas de bultos y archivo seguro de informes.
* **`store.py` (`OrderStore`):** Repositorio central que compone los repositorios y garantiza la inicialización de esquemas y migraciones automáticas.
* *(Las importaciones de este dominio se realizan directamente desde el paquete canónico `src.orders`.)*

---

## 🏷️ 4. Paquete de Productos y Catálogo (`src/products/`)

Reemplaza el antiguo archivo monolítico `product_store.py` (más de 1,410 líneas), distribuyendo el modelo de datos y consultas en mixins orientados a subdominios:

* **`catalog_repo.py` (`CatalogRepositoryMixin`):** Carga rápida en una sola consulta (`load_catalog_fast`), búsqueda difusa por SKU o código de barras, paginación, inserción y reordenamiento topológico en catálogo.
* **`movements_repo.py` (`MovementsRepositoryMixin`):** Historial paginado de movimientos de inventario (`stock_movements`), registro de despachos con trazabilidad a nivel de ítem (`despachos`, `despacho_detalles`) y cálculo de KPIs.
* **`physical_repo.py` (`PhysicalRepositoryMixin`):** Registro de conteos físicos de operarios, cálculo de diferencias vs. stock digital y almacenamiento de comparativas históricas.
* **`notifications_repo.py` (`NotificationsRepositoryMixin`):** Notificaciones operativas para administradores y consulta a la vista `v_analisis_reposicion` para alertas de quiebre o sobrestock.
* **`store.py` (`ProductStore`):** Orquesta los repositorios de catálogo, el caché de SKU en memoria protegido por `threading.Lock` y el trigger automático `trg_auditoria_stock`.
* *(Las importaciones de este dominio se realizan directamente desde el paquete canónico `src.products`.)*

---

## 📊 5. Paquete de Inventario y Sincronización Excel (`src/inventory/`)

Reemplaza el antiguo archivo monolítico `stock_manager.py` (más de 1,500 líneas):

* **`excel_sync.py`:** Aísla la manipulación de bajo nivel con `openpyxl`: detección de esquemas dinámicos, normalización de encabezados, copiado exacto de estilos visuales y construcción de informes idénticos a la plantilla de producción.
* **`template_sync.py`:** Sincronización transaccional bidireccional (`SQLite ➔ Excel` y `Excel ➔ SQLite`). Incluye la regla de integridad de catálogo: los productos ausentes en `Productos.xlsx` quedan automáticamente inactivos (`active = 0`) en SQLite, y los productos presentes se reactivan.
* **`manager.py` (`StockManager`):** Orquestación del catálogo, sincronización atómica con debounce entre SQLite y `Productos.xlsx`, aplicación de remitos mayoristas, canjes y despachos de Mercado Envíos Full.
* *(Las importaciones de este dominio se realizan directamente desde el paquete canónico `src.inventory`.)*

---

## 🎨 6. Controladores por Composición y Componentes UI (`src/ui/`)

### Arquitectura por Composición Pura (`src/ui/protocols.py` + `src/ui/controllers/`):
`InterfazFlet` (`src/flet_gui.py`) delega sus capacidades mediante inyección de dependencias (`AppDependencies`), contratos estructurales `Protocol` y controladores dedicados sin herencia de mixins ni shims intermedios:
1. **`ResponsiveController` (`responsive_controller.py`):** Detección precisa de viewports móviles (< 768px), redimensionamiento dinámico y drawer táctil.
2. **`DocumentViewerService` (`document_viewer_service.py`):** Previsualización inline de informes, manuales SOP en PDF según rol y compartición.
3. **`SessionSyncService` (`session_sync_service.py`):** Sincronización de eventos en tiempo real entre múltiples terminales LAN, carga de catálogo/informes y avisos colaborativos.
4. **`DialogCoordinator` (`dialog_coordinator.py`):** Despacho centralizado de diálogos modales e impresión de rótulos térmicos/A4.
5. **Resto de controladores especializados:** `AuthController`, `BatchController`, `ChatController`, `FileTransferService` y `ThemeController`.

### Componentes y Mejoras UX/UI:
* **`Debouncer` (`src/ui/components/debounce.py`):** Temporizador reactivo para campos de búsqueda (ej. 200 ms en visor de stock e historial de pedidos), evitando re-renderizados innecesarios y garantizando fluidez a 60 FPS.
* **Validación Inline (`error_text`):** Mensajes de error en tiempo real debajo de los campos de texto en `dlg_clientes.py` y `dlg_productos.py` (nombre, SKU, stock), sin necesidad de modales intrusivos.
* **Acción Interactiva "Deshacer" en SnackBar:** Ventana de 6 segundos tras un ajuste de stock rápido en `dlg_movimientos_rapidos.py` para revertir la operación con un solo clic y registrar la reversión en la auditoría.
* **Barra de Progreso Reactiva con Porcentaje:** Integrada en el dashboard (`self.progreso_barra`) para tareas pesadas de importación, sincronización y generación de reportes.

---

## 🔒 7. Seguridad y Resiliencia

* **HTTPS por Defecto y Endurecimiento Perimetral (`src/server_app/`, `src/ssl_manager.py`):** Tráfico web cifrado mediante certificados X.509 autogenerados (`STOCKAGENT_HTTPS=1`), documentación OpenAPI/Swagger (`/docs`, `/redoc`, `/openapi.json`) deshabilitada por defecto (`STOCKAGENT_ENABLE_API_DOCS=0`) y cabeceras HTTP de seguridad (`X-Content-Type-Options`, `X-Frame-Options`).
* **Rutas de Documentación e Informes Protegidas (`protected_docs_routes.py`, `src/api/deps.py`):** Los endpoints `/documentacion/`, `/informes/` y `/documentos/ver` exigen sesión activa, API Key o token HMAC temporal firmado (`?dt=`).
* **Cifrado de Secretos en Disco (`src/secretos.py`):** Credenciales SMTP, tokens de Telegram y claves de Mercado Libre protegidas mediante Windows DPAPI (`enc:dpapi:`) o Fernet (`enc:fernet:`).
* **Límite Estricto de Carga de Archivos:** Validación de tamaño máximo (`25 MB`) en la transferencia de archivos, impidiendo ataques de denegación de servicio (DoS) por agotamiento de memoria.
* **Limpieza Periódica de Sesiones Expiradas:** Integrada de forma autónoma en el demonio de latencia `network_heartbeat.py`, purgando tokens de API y sesiones inactivas periódicamente sin impacto en el rendimiento.
* **Protección de Descargas y Rutas:** Resolución estricta de rutas mediante `application_root()` evitando vulnerabilidades de Directory Traversal (`../`), junto con validación anti-SSRF en `webhook_manager.py`.

---

## 🤖 8. Integración Continua (CI Workflow)

Ubicado en `.github/workflows/ci.yml`:
* **Matriz de Ejecución:** Windows Server ejecutando en paralelo bajo **Python 3.11, 3.12 y 3.13**.
* **Paso a Paso:** Clonado del repositorio, instalación de dependencias desde `requirements.txt` y ejecución de la suite completa de pruebas unitarias e integración con `pytest`.
* **Garantía de Calidad:** Bloquea regresiones y garantiza que cada commit o pull request cumpla con el 100% de tests aprobados.

---

## 🧪 9. Verificación y Cobertura de Pruebas

Toda la arquitectura modular ha sido verificada contra la suite completa de pruebas automatizadas (`.\.venv\Scripts\python.exe -m pytest tests/ -q --tb=short`):
* **Total de módulos de prueba:** 53 archivos en `tests/` (`331 pruebas` unitarias y de integración, más subtests).
* **Tasa de éxito:** 100% pasando (`331 passed`).
* **Retrocompatibilidad:** Cero rupturas de contratos; todas las fachadas y objetivos de parches existentes quedan preservados.
