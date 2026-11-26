# Arquitectura Modular del Backend y Frontend (src/)

Este directorio contiene el código fuente principal de **StockAgent**, estructurado bajo principios de arquitectura limpia, separación de responsabilidades (SRP), alta mantenibilidad y resiliencia ante errores.

---

## 🏛️ Visión General de la Arquitectura

```text
src/
├── core/                       # Núcleo de excepciones, migraciones SQLite, seguridad, sanitización y delegación
│   ├── __init__.py             # Exportaciones públicas de excepciones, seguridad y entorno
│   ├── delegation.py           # Descriptor no-datos DelegadoAtributo para composición en stores/fachadas
│   ├── exceptions.py           # Jerarquía unificada de errores tipados
│   ├── environment.py          # Aislamiento de perfiles de ejecución (Producción vs QA Sandbox)
│   ├── network_security.py     # Protección anti-SSRF, TLS estricto, HMAC-SHA256 y sanitización MIME
│   ├── sanitize_utils.py       # Sanitización anti-fórmulas Excel/CSV y escape HTML/XML (Telegram/ReportLab)
│   ├── security_utils.py       # Confinamiento de rutas, validación de impresoras y URLs seguras
│   ├── sqlite_migrations.py    # Migraciones versionadas idempotentes mediante PRAGMA user_version
│   ├── sqlite_utils.py         # Apertura configurada y cierre determinista (closing) de SQLite
│   ├── stock_order_tx.py       # Orquestación transaccional entre reservas/stock y órdenes de pedido
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
│   ├── lockout_repo.py         # Repositorio de bloqueo por intentos fallidos (5 intentos / 15 min)
│   ├── api_tokens_repo.py      # Repositorio de api_sessions (SHA-256) y API Keys
│   └── store.py                # Repositorio SQLite UserStore por composición pura
│
├── orders/                     # Dominio de pedidos, clientes y trazabilidad
│   ├── models.py               # Modelos Pedido, Cliente, MensajeChat, LogAuditoria, CierreJornada
│   ├── schema.py               # Creación de tablas e índices de pedidos.sqlite3
│   ├── protocols.py            # Contratos Protocol y callbacks para composición de repositorios
│   ├── order_core_repo.py      # Repositorio núcleo CRUD de pedidos, ítems y no coincidencias
│   ├── client_repo.py          # Repositorio CRUD de clientes y códigos CLI-XXXXXX
│   ├── chat_repo.py            # Repositorio de canal colaborativo y menciones #PED-XXXX
│   ├── concurrency_repo.py     # Repositorio de soft-locking temporal (TTL) e idempotencia SHA-256
│   ├── dispatch_repo.py        # Repositorio de estados de despacho y hojas de ruta
│   ├── audit_repo.py           # Repositorio de bitácora transaccional y auditoría forense
│   ├── closure_repo.py         # Repositorio de cierres de jornada y consolidación documental
│   ├── channel_report_repo.py  # Repositorio de descuentos por canal y ventanas de cierre
│   ├── factory_plan_closure.py # Helpers de recálculo, cierre parcial y cierre final de planes fábrica
│   ├── factory_plan_repo.py    # Repositorio de planes y verificación de ingresos de fábrica
│   ├── full_plan_repo.py       # Repositorio de planes y picking guiado para Mercado Envíos Full
│   ├── stock_flow_repo.py      # Repositorio de analítica ejecutiva y balance de stock en vivo
│   └── store.py                # Repositorio SQLite OrderStore unificado por composición (11 repos)
│
├── products/                   # Dominio modular de productos, multi-ubicación, FEFO, reservas y despachos
│   ├── barcode_utils.py        # Normalización EAN-13 / SKU y lectura Barcode Wedge
│   ├── schema.py               # Creación y migración versionada SQLite v4 (PRAGMA user_version) de productos
│   ├── protocols.py            # Contratos Protocol para caché de catálogo y escrituras SQLite
│   ├── catalog_read_repo.py    # Consultas optimizadas de catálogo, caché SKU y paginación
│   ├── catalog_write_repo.py   # CRUD de catálogo, precios, umbrales y ubicaciones slotting
│   ├── catalog_repo.py         # Fachada combinada de lectura/escritura del catálogo
│   ├── locations_repo.py       # Repositorio especializado de multi-ubicación por zona y transferencias bin-a-bin
│   ├── lots_fefo_repo.py       # Repositorio de lotes, vencimientos, alertas y consumo estricto FEFO
│   ├── locations_lots_repo.py  # Fachada compuesta (DelegadoAtributo) sobre locations_repo y lots_fefo_repo
│   ├── reservations_repo.py    # Repositorio transaccional de reservas de stock (pedido / ola_picking) y disponible neto
│   ├── movements_repo.py       # Historial de movimientos, despachos y enriquecimiento atómico
│   ├── movements_report_repo.py # Consultas consolidadas para reportes de movimientos diarios
│   ├── physical_repo.py        # Conteo físico de operarios y comparativas de discrepancia
│   ├── notifications_repo.py   # Notificaciones administrativas y alertas v_analisis_reposicion
│   └── store.py                # Repositorio SQLite ProductStore por composición declarativa (DelegadoAtributo)
│
├── inventory/                  # Dominio modular de inventario y sincronización Excel
│   ├── protocols.py            # Contratos Protocol para host de inventario e informes
│   ├── manager.py              # StockManager central por composición de servicios
│   ├── catalog_loader.py       # Servicio de carga fast-path desde SQLite / Productos.xlsx
│   ├── discount_engine.py      # Servicio transaccional de descuentos y cálculo de lotes
│   ├── excel_sync.py           # Exportación y refresco de filas en Excel
│   └── template_sync.py        # Servicio de sincronización atómica con Productos.xlsx
│
├── qa/                         # Módulo de Aseguramiento de Calidad y Pruebas Aisladas
│   ├── __init__.py             # Exportaciones del paquete QA
│   └── seeder.py               # Sembrador de datos sintéticos realistas para testing seguro
│
├── stock/                      # Dominio de stock, reposición, slotting y reportes
│   ├── models.py               # Dataclasses RegistroDescuento y ReporteStock
│   ├── slotting_models.py      # Constantes de racks, dataclasses y heurística de slotting
│   ├── report_styles.py        # Paletas, tipografías y estilos ReportLab/XLS
│   ├── reports_stock.py        # Renderizado de reportes de existencias y movimientos
│   ├── reports_movements_common.py  # Helpers PDF/Excel compartidos para reportes de movimientos
│   ├── reports_movements_canales.py # Reporte de cierre discriminado en 3 canales (Operador)
│   ├── reports_movements.py    # Reporte consolidado de movimientos por producto (Admin)
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
├── parsers/                    # Parsers modulares de comprobantes (PDF, Excel, DOCX) con límites anti-DoS
│   ├── safe_loader.py          # Validación anti-DoS de tamaño/páginas/celdas y mitigación Zip-Bomb (defusedxml)
│   ├── remito_parser.py        # Parser de remitos mayoristas PDF
│   ├── canjes_parser.py        # Parser de planillas de canjes Excel
│   ├── mercado_libre_parser.py # Parser de órdenes DOCX de Mercado Libre
│   ├── mercado_full_parser.py  # Parser de envíos Mercado Envíos Full
│   ├── factory_parser.py       # Parser de remitos de ingreso de fábrica
│   └── physical_stock_parser.py# Parser de planillas de relevamiento físico
│
├── integrations/               # Integraciones externas y canales de notificación
│   ├── email_sender.py         # Envío SMTP con credenciales cifradas
│   ├── mercado_libre_auth.py   # Autenticación OAuth 2.0, cifrado de tokens y búsqueda REST ML
│   ├── mercado_libre_api.py    # Conector de órdenes Mercado Libre, respaldo DOCX y descuento
│   ├── sheets_manager.py       # Integración opcional con Google Sheets
│   └── telegram_notifier.py    # Notificador asíncrono de alertas por Telegram Bot
│
├── chat/                       # Asistente interno e intenciones semánticas por rol
│   ├── intent_parser.py        # Clasificación de consultas e intenciones de chat
│   ├── role_help.py            # Respuestas y chips contextuales según SoD del rol
│   └── formatters.py           # Formateo de respuestas, pedidos y métricas en chat
│
├── cli/                        # Operaciones CLI e interactive_flows desacoplados
│   ├── protocols.py            # Contratos Protocol para servicios de CLI
│   ├── archive_ops.py          # Servicio de procesamiento y archivado por consola
│   ├── admin_flows.py          # Flujos CLI administrativos (catálogo, fábrica, Full, físico)
│   └── interactive_flows.py    # Servicio orquestador de menú interactivo CLI
│
├── tray/                       # Icono en Bandeja del Sistema (System Tray de Windows)
│   ├── net_and_images.py       # Obtención de IP LAN y badges de estado PIL
│   ├── service.py              # Ciclo de vida global del icono y notificaciones de red
│   └── tray_controller.py      # Controlador pystray y menú contextual
│
├── ui/                         # Capa de presentación gráfica y vistas (Flet 1.0.x)
│   ├── design/                 # Sistema de Diseño Unificado (tokens WCAG AA, botones semánticos, diálogos, forms)
│   ├── theme.py                # Paleta de colores corporativos Ultratech y tokens visuales
│   ├── app_config.py           # Constantes de configuración GUI
│   ├── protocols.py            # Contratos tipados (Protocol) e inyección de AppDependencies
│   ├── user_preferences.py     # Persistencia desacoplada de preferencias UI por usuario
│   ├── dashboard_presenter.py  # Presentador desacoplado del Dashboard reactivo
│   ├── controllers/            # Controladores desacoplados por composición pura:
│   │                           # auth_controller, batch_controller, chat_controller,
│   │                           # dialog_coordinator, document_viewer_service, file_transfer_service,
│   │                           # responsive_controller, session_sync_service, theme_controller
│   ├── components/             # admin_flow_analytics, admin_flow_widgets, admin_operations_bar,
│   │                           # audio_manager, debounce, docking_manager, floating_chat,
│   │                           # floating_chat_intents, header, mobile_nav, network_heartbeat,
│   │                           # panels, print_labels, sidebar, sidebar_horizontal,
│   │                           # sidebar_quick_actions, sidebar_sections, window_manager
│   ├── shell_builder.py        # Constructor de shell visual responsive y barra móvil por rol
│   └── dialogs/                # Módulos desacoplados por caso de uso:
│                               # _shared (re-exporta src/ui/design), auth_* + dlg_auth,
│                               # analytics_widgets + analytics_rotacion + analytics_metricas + dlg_analytics,
│                               # api_panel_tabs + dlg_api + dlg_api_keys (unificado),
│                               # cierre/ (incl. cierre_mercado_cards) + dlg_cierre,
│                               # despacho_componentes + dlg_modulo_despacho, dlg_clientes,
│                               # dlg_command_palette, dlg_email, dlg_escaner, dlg_anomalias,
│                               # dlg_archivo_historico, dlg_backup,
│                               # picking_plan_shared + dlg_control_ingreso_fabrica +
│                               # dlg_picking_guiado_full + dlg_planificar_full + dlg_planificar_ingreso_fabrica,
│                               # dlg_gestion_ambientes, dlg_heatmap + heatmap_render + heatmap_fefo_render,
│                               # historial_cards + historial_* + dlg_historial_pedidos, dlg_informes,
│                               # dlg_ingreso_fabrica + ingreso_fabrica_archivo,
│                               # dlg_inventario_vivo + inventario_vivo_views, dlg_mercado_full,
│                               # dlg_mercadolibre + mercadolibre_api_cards,
│                               # dlg_mercadolibre_descuento + ml_*, dlg_movimientos_rapidos + *_ops,
│                               # dlg_ola_picking, dlg_pedido_fabrica, pedidos_baja + pedidos_baja_ops,
│                               # pedidos_crear + pedidos_crear_componentes +
│                               # pedidos_crear_modales + pedidos_gestion + dlg_pedidos, dlg_preferencias,
│                               # dlg_productos + productos_modales, dlg_quiebre + quiebre_banner,
│                               # dlg_reportes, dlg_restaurar, dlg_sincronizar_excel, dlg_smtp,
│                               # dlg_stock_fisico + stock_fisico_views, dlg_stock_ops (fachada),
│                               # dlg_telegram, dlg_ubicaciones_lotes, dlg_usuarios + usuarios_modales, dlg_ver_stock
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

Reemplaza el antiguo archivo monolítico `orders_store.py` (anteriormente de más de 1,690 líneas), organizando las operaciones mediante composición explícita e inyección de dependencias (`protocols.py`):

* **`models.py` / `schema.py`:** Definen las entidades centrales (`Pedido`, `Cliente`, `MensajeChat`, `LogAuditoria`, `CierreJornada`) y la inicialización transaccional de tablas/índices SQLite.
* **`protocols.py`:** Define contratos `Protocol` y callbacks tipados (`OrderConnectFn`, `MapPedidoFn`, `AuditLogFn`, `LookupOrderFn`, `OrderAuditableProtocol`).
* **`order_core_repo.py` (`OrderCoreRepository`):** Operaciones CRUD núcleo de pedidos, búsqueda por hash SHA-256, registro de ítems no coincidentes y actualizaciones operativas.
* **`client_repo.py` (`ClientRepository`):** CRUD de clientes mayoristas y minoristas, gestión de teléfonos, direcciones y autogeneración de códigos únicos (`CLI-XXXXXX`).
* **`chat_repo.py` (`ChatRepository`):** Mensajería interna de equipo, conteo de mensajes no leídos por usuario y enriquecimiento automático de referencias a pedidos (`#PED-1234`).
* **`concurrency_repo.py` (`ConcurrencyRepository`):**
  * Soft-locking temporal (Lease/TTL de 5 minutos) en edición de pedidos para evitar colisiones entre operarios.
  * Registro de idempotencia con tokens SHA-256 para prevenir procesamientos duplicados por microcortes de red.
* **`audit_repo.py` (`AuditRepository`):** Bitácora transaccional inmutable (`pedidos_auditoria`) con trazabilidad completa de usuario, rol, IP y detalles del cambio.
* **`closure_repo.py` (`ClosureRepository`):** Consolidación de cierres de turno y Mercado Libre/Full, cálculo de métricas de bultos y archivo seguro de informes.
* **`dispatch_repo.py`, `channel_report_repo.py`, `factory_plan_repo.py` (+ `factory_plan_closure.py`), `full_plan_repo.py` y `stock_flow_repo.py`:** Repositorios desacoplados para estados de despacho, consolidación en 3 canales (Mayoristas, Mercado Libre, Full), planes/cierres de fábrica, planes Full y flujo diario de stock.
* **`store.py` (`OrderStore`):** Repositorio central que compone los **11 repositorios especializados** mediante delegación explícita y garantiza la inicialización de esquemas SQLite con cierre determinístico (`sqlite_connection`).
* *(Las importaciones de este dominio se realizan directamente desde el paquete canónico `src.orders`.)*

---

## 🏷️ 4. Paquete de Productos y Catálogo (`src/products/`)

Reemplaza el antiguo archivo monolítico `product_store.py` (más de 1,410 líneas), distribuyendo el modelo de datos y consultas en repositorios desacoplados por composición:

* **`schema.py`, `sqlite_migrations.py` y `protocols.py`:** Inicialización y migraciones incrementales versionadas mediante `PRAGMA user_version` (`PRODUCTS_SCHEMA_VERSION = 4` en `inicializar_esquema_productos`) y contratos estructurales `CatalogCacheHostProtocol` y `CatalogWriteHostProtocol`.
* **`catalog_read_repo.py` / `catalog_write_repo.py` / `catalog_repo.py` (`CatalogRepository`):** Carga rápida en una sola consulta (`load_catalog_fast`), búsqueda difusa por SKU o código de barras, paginación, inserción y caché SKU.
* **`locations_repo.py` (`WarehouseLocationsRepository`):** Multi-ubicación logística por zona (`picking`, `pulmon`, `pallet`, `recepcion`, `cuarentena`), sincronización de ubicación principal en `products` y transferencias atómicas bin-a-bin (`pulmon -> picking`).
* **`lots_fefo_repo.py` (`FefoLotsRepository`):** Registro de lotes con fecha de vencimiento, planificación/consumo ordenado por FEFO (First Expired, First Out) y clasificación de alertas (`VENCIDO`, `CRITICO`, `PROXIMO`).
* **`locations_lots_repo.py` (`LocationsLotsRepository`):** Fachada compuesta que integra `WarehouseLocationsRepository` y `FefoLotsRepository` mediante `DelegadoAtributo` preservando 100% los imports históricos.
* **`reservations_repo.py` (`StockReservationsRepository`):** Reservas atómicas previas al picking (`pedido` y `ola_picking`), cálculo de `Disponible Neto` (`Físico - Reservado` y vista `v_stock_disponible`), consolidación en despacho FEFO y liberación sin doble devolución.
* **`movements_repo.py` / `movements_report_repo.py` (`MovementsRepository`, `MovementsReportRepository`):** Historial paginado de movimientos de inventario (`stock_movements`), registro de despachos con trazabilidad (`despachos`, `despacho_detalles`), reportes de jornada y KPIs.
* **`physical_repo.py` (`PhysicalRepository`):** Registro de conteos físicos de operarios, cálculo de diferencias vs. stock digital y almacenamiento de comparativas históricas.
* **`notifications_repo.py` (`NotificationsRepository`):** Notificaciones administrativas y consulta a la vista `v_analisis_reposicion` para alertas de quiebre o sobrestock.
* **`store.py` (`ProductStore`):** Orquesta los repositorios compuestos usando descriptores declarativos `DelegadoAtributo`, el caché de SKU en memoria protegido por `threading.Lock` y el trigger automático `trg_auditoria_stock`.
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

### Componentes, Modularidad UI y Reportes por Canal:
* **`shell_builder.py`, `admin_flow_widgets.py` y `sidebar_quick_actions.py`:** Construyen la cáscara responsive, widgets de flujo administrativo y accesos rápidos de barra lateral sin recargar `flet_gui.py`.
* **Diálogos Modulares sin Monolitos (`src/ui/dialogs/`):** Subcomponentes cohesivos como `analytics_widgets.py` / `analytics_rotacion.py` / `analytics_metricas.py`, `pedidos_baja_ops.py`, `pedidos_crear_modales.py`, `historial_cards.py`, `quiebre_banner.py`, `dlg_ubicaciones_lotes.py`, `dlg_ola_picking.py`, `heatmap_fefo_render.py`, `mercadolibre_api_cards.py` y `cierre/cierre_mercado_cards.py`.
* **Reportes SQLite-First y Cierre en 3 Canales (`src/stock/reports_movements_*.py`):** `reports_movements_common.py` comparte exportadores PDF/XLS, `reports_movements_canales.py` discrimina salidas del operario en Mayoristas / Mercado Libre / Full (+ Ingresos) solo para artículos con movimiento, y `reports_movements.py` emite el consolidado por producto para Administración.
* **`Debouncer` (`src/ui/components/debounce.py`):** Temporizador reactivo para campos de búsqueda (ej. 200 ms en visor de stock e historial de pedidos), evitando re-renderizados innecesarios y garantizando fluidez a 60 FPS.
* **Validación Inline (`error_text`):** Mensajes de error en tiempo real debajo de los campos de texto en `dlg_clientes.py` y `dlg_productos.py` (nombre, SKU, stock), sin necesidad de modales intrusivos.
* **Acción Interactiva "Deshacer" en SnackBar:** Ventana de 6 segundos tras un ajuste de stock rápido en `dlg_movimientos_rapidos.py` para revertir la operación con un solo clic y registrar la reversión en la auditoría.
* **Barra de Progreso Reactiva con Porcentaje:** Integrada en el dashboard (`self.progreso_barra`) para tareas pesadas de importación, sincronización y generación de reportes.

---

## 🔒 7. Seguridad y Resiliencia

* **Cierre Determinístico SQLite y Arquitectura Acíclica (`src/core/sqlite_utils.py`):** Todas las conexiones SQLite usan el gestor de contexto `sqlite_connection` (`contextlib.closing()` + WAL + `PRAGMA foreign_keys=ON`), verificado automáticamente por `tests/test_sqlite_closing.py`, eliminando fugas de descriptores y ciclos entre `src/core` y `src/products`.
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

Toda la arquitectura modular ha sido verificada contra la suite completa de pruebas automatizadas (`.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider`):
* **Total de pruebas aprobadas:** `545 passed, 23 subtests passed, 0 failed` en `86` módulos `tests/test_*.py` (incluyendo las suites integrales `test_fase1_security_ui_fixes.py`, `test_fase2_backend_hardening.py`, `test_fase3_design_system_ux.py`, `test_fase4_mobile_security_ux.py`, `test_fase4_reservations_multiloc_fefo.py`, `test_etapa_a_ui_fefo_multiloc.py`, `test_etapa_b_order_reservations.py`, `test_etapa_c_despacho_api_and_mobile_contract.py`, `test_modular_refactoring.py` y `test_rol_despachador.py`).
* **Tasa de éxito:** 100% pasando sobre toda la batería de pruebas unitarias y de integración.
* **Retrocompatibilidad:** Cero rupturas de contratos; todas las fachadas y descriptores `DelegadoAtributo` preservan las firmas públicas e inyección de mocks.
