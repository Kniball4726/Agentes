# Arquitectura Modular del Backend y Frontend (src/)

Este directorio contiene el código fuente principal de **StockAgent**, estructurado bajo principios de arquitectura limpia, separación de responsabilidades (SRP), alta mantenibilidad y resiliencia ante errores.

---

## 🏛️ Visión General de la Arquitectura

```
src/
├── core/                       # Núcleo de excepciones y contratos de dominio
│   ├── __init__.py             # Exportaciones públicas de excepciones
│   └── exceptions.py           # Jerarquía unificada de errores tipados
│
├── auth/                       # Dominio de autenticación, seguridad y usuarios
│   ├── __init__.py             # Exportaciones del paquete auth
│   ├── models.py               # Modelos inmutables (User, ApiKey, UserRole)
│   ├── password.py             # Hashing PBKDF2-HMAC-SHA256 y validación de políticas
│   └── store.py                # Repositorio SQLite UserStore (usuarios, API keys, sesiones)
│
├── orders/                     # Dominio de pedidos, clientes y trazabilidad
│   ├── __init__.py             # Exportaciones del paquete orders
│   ├── models.py               # Modelos de datos (Pedido, Cliente, MensajeChat, LogAuditoria)
│   ├── client_repo.py          # Mixin de gestión de clientes y códigos automáticos
│   ├── chat_repo.py            # Mixin de canal colaborativo y menciones inteligentes
│   ├── concurrency_repo.py     # Mixin de soft-locking temporal (TTL) e idempotencia SHA-256
│   ├── audit_repo.py           # Mixin de registro transaccional y auditoría forense
│   ├── closure_repo.py         # Mixin de cierres de turno y consolidación documental
│   └── store.py                # Repositorio SQLite OrderStore unificado
│
├── products/                   # Dominio modular de productos, catálogo y despachos
│   ├── __init__.py             # Exportación de ProductStore
│   ├── store.py                # Repositorio SQLite ProductStore unificado (ensambla mixins)
│   ├── catalog_repo.py         # Repositorio mixin para catálogo, códigos de barras y CRUD
│   ├── movements_repo.py       # Repositorio mixin para historial de movimientos y despachos
│   ├── physical_repo.py        # Repositorio mixin para relevamiento físico y discrepancias
│   └── notifications_repo.py   # Repositorio mixin para notificaciones de administración y quiebres
│
├── inventory/                  # Dominio modular de inventario y sincronización Excel
│   ├── __init__.py             # Exportación de StockManager
│   ├── manager.py              # StockManager central
│   └── excel_sync.py           # Sincronización atómica y formateo de plantilla visual Excel
│
├── stock/                      # Dominio de stock, reposición y reportes
│   ├── __init__.py             # Exportaciones de stock
│   ├── models.py               # Dataclasses de descuento (RegistroDescuento, ReporteStock)
│   ├── reports.py              # Exportadores binarios Excel (.xls) y vectoriales PDF
│   ├── replenishment.py        # Algoritmos de sugerencia y armado de pedidos a fábrica
│   └── physical_inventory.py   # Reconciliación de inventario físico vs. digital
│
├── ui/                         # Capa de presentación gráfica y vistas (Flet)
│   ├── __init__.py             # Exportaciones de UI
│   ├── theme.py                # Paleta de colores corporativos Ultratech y tokens visuales
│   ├── dashboard_presenter.py  # Presentador desacoplado del Dashboard reactivo
│   ├── mixins/                 # Mixins modulares para la orquestación de la GUI
│   │   ├── __init__.py         # Re-exportación de mixins
│   │   ├── responsive.py       # Detección y adaptación a pantallas móviles y tablets
│   │   ├── document_viewer.py  # Apertura de informes, manuales PDF y compartición
│   │   ├── session_sync.py     # Sincronización en tiempo real entre sesiones y chat
│   │   └── dialog_dispatcher.py# Despachador central de vistas modales e impresión
│   ├── components/             # Componentes visuales desacoplados
│   │   ├── debounce.py         # Utilidad Debouncer para búsquedas reactivas de alto rendimiento
│   │   ├── header.py           # Encabezado superior y selector de perfil / IP
│   │   ├── sidebar.py          # Barra lateral / drawer responsivo
│   │   ├── floating_chat.py    # Ventana flotante de chat (asistente + equipo)
│   │   ├── audio_manager.py    # Motor acústico Web Audio API / winsound
│   │   ├── network_heartbeat.py# Demonio de sondeo LAN, semáforo visual y limpieza de sesiones
│   │   ├── mobile_nav.py       # Barra ergonómica inferior para dispositivos móviles
│   │   └── print_labels.py     # Despacho de rótulos térmicos (100x150 mm) y A4
│   └── dialogs/                # Vistas modulares por caso de uso
│       ├── dlg_auth.py         # Autenticación, reseteo de claves y perfil
│       ├── dlg_clientes.py     # ABM de clientes con validación inline de campos
│       ├── dlg_productos.py    # Edición de catálogo con validación inline en tiempo real
│       ├── dlg_pedidos.py      # Carga, cancelación y desarme de pedidos
│       ├── dlg_historial_pedidos.py # Historial con paginación y búsqueda con debounce
│       ├── dlg_movimientos_rapidos.py # Movimientos rápidos de stock con acción 'Deshacer'
│       ├── dlg_ver_stock.py    # Visor de existencias con filtrado dinámico asistido
│       ├── dlg_cierre/         # Asistente de cierre de jornada y hoja de ruta
│       └── dlg_stock_ops.py    # Operaciones de fábrica, ML Full y stock físico
│
├── user_store.py               # Fachada retrocompatible hacia src.auth.UserStore
├── orders_store.py             # Fachada retrocompatible hacia src.orders.OrderStore
├── product_store.py            # Fachada retrocompatible hacia src.products.ProductStore
├── stock_manager.py            # Fachada retrocompatible hacia src.inventory.StockManager
├── flet_gui.py                 # Orquestador UI ensamblado con mixins, barra de progreso y cuotas
└── server.py                   # Servidor ASGI / FastAPI, middleware PWA y OTA
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
  * Algoritmo `PBKDF2-HMAC-SHA256` con sal aleatoria de 32 bytes y 100,000 iteraciones.
  * Verificación en tiempo constante `hmac.compare_digest` para mitigar ataques de temporización (*timing attacks*).
  * Validación estricta de políticas de longitud mínima y complejidad.
* **`store.py`:** Repositorio transaccional `UserStore`:
  * Gestión en SQLite con modo WAL (`usuarios.sqlite3`).
  * Conteo de intentos fallidos y bloqueo temporal tras 5 fallos consecutivos.
  * Registro de sesiones activas concurrentes y auditoría de accesos.
* **`src/user_store.py` (Fachada):** Proporciona retrocompatibilidad del 100% para todo el código y tests existentes.

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
* **`store.py` (`OrderStore`):** Repositorio central que compone todos los mixins y garantiza la inicialización de esquemas y migraciones automáticas.
* **`src/orders_store.py` (Fachada):** Mantiene retrocompatibilidad transparente.

---

## 🏷️ 4. Paquete de Productos y Catálogo (`src/products/`)

Reemplaza el antiguo archivo monolítico `product_store.py` (más de 1,410 líneas), distribuyendo el modelo de datos y consultas en mixins orientados a subdominios:

* **`catalog_repo.py` (`CatalogRepositoryMixin`):** Carga rápida en una sola consulta (`load_catalog_fast`), búsqueda difusa por SKU o código de barras, paginación, inserción y reordenamiento topológico en catálogo.
* **`movements_repo.py` (`MovementsRepositoryMixin`):** Historial paginado de movimientos de inventario (`stock_movements`), registro de despachos con trazabilidad a nivel de ítem (`despachos`, `despacho_detalles`) y cálculo de KPIs.
* **`physical_repo.py` (`PhysicalRepositoryMixin`):** Registro de conteos físicos de operarios, cálculo de diferencias vs. stock digital y almacenamiento de comparativas históricas.
* **`notifications_repo.py` (`NotificationsRepositoryMixin`):** Notificaciones operativas para administradores y consulta a la vista `v_analisis_reposicion` para alertas de quiebre o sobrestock.
* **`store.py` (`ProductStore`):** Ensambla los mixins, orquesta el caché de SKU en memoria protegido por `threading.Lock` y el trigger automático `trg_auditoria_stock`.
* **`src/product_store.py` (Fachada):** Mantiene retrocompatibilidad del 100%.

---

## 📊 5. Paquete de Inventario y Sincronización Excel (`src/inventory/`)

Reemplaza el antiguo archivo monolítico `stock_manager.py` (más de 1,500 líneas):

* **`excel_sync.py`:** Aísla la manipulación de bajo nivel con `openpyxl`: detección de esquemas dinámicos, normalización de encabezados, copiado exacto de estilos visuales y construcción de informes idénticos a la plantilla de producción.
* **`manager.py` (`StockManager`):** Orquestación del catálogo, sincronización atómica con debounce entre SQLite y `Productos.xlsx`, aplicación de remitos mayoristas, canjes y despachos de Mercado Envíos Full.
* **`src/stock_manager.py` (Fachada):** Re-exporta `StockManager`, `RegistroDescuento`, `ReporteStock` y utilidades para compatibilidad absoluta.

---

## 🎨 6. Mixins y Componentes de Interfaz de Usuario (`src/ui/`)

### Mixins de Orquestación GUI (`src/ui/mixins/`):
1. **`ResponsiveLayoutMixin`:** Detección precisa de viewports móviles (< 768px), redimensionamiento dinámico y drawer táctil.
2. **`DocumentViewerMixin`:** Previsualización inline de informes, manuales SOP en PDF según rol y compartición.
3. **`SessionSyncMixin`:** Sincronización de eventos en tiempo real entre múltiples terminales LAN y chat colaborativo.
4. **`DialogDispatcherMixin`:** Despacho centralizado de diálogos modales e impresión de rótulos térmicos/A4.

### Componentes y Mejoras UX/UI:
* **`Debouncer` (`src/ui/components/debounce.py`):** Temporizador reactivo para campos de búsqueda (ej. 200 ms en visor de stock e historial de pedidos), evitando re-renderizados innecesarios y garantizando fluidez a 60 FPS.
* **Validación Inline (`error_text`):** Mensajes de error en tiempo real debajo de los campos de texto en `dlg_clientes.py` y `dlg_productos.py` (nombre, SKU, stock), sin necesidad de modales intrusivos.
* **Acción Interactiva "Deshacer" en SnackBar:** Ventana de 6 segundos tras un ajuste de stock rápido en `dlg_movimientos_rapidos.py` para revertir la operación con un solo clic y registrar la reversión en la auditoría.
* **Barra de Progreso Reactiva con Porcentaje:** Integrada en el dashboard (`self.progreso_barra`) para tareas pesadas de importación, sincronización y generación de reportes.

---

## 🔒 7. Seguridad y Resiliencia

* **Límite Estricto de Carga de Archivos:** Validación de tamaño máximo de 25 MB (`MAX_SUBIDA_BYTES = 25 * 1024 * 1024`) en `flet_gui.py:subir_archivo`, con alertas amigables que impiden ataques de denegación de servicio (DoS) por agotamiento de memoria.
* **Limpieza Periódica de Sesiones Expiradas:** Integrada de forma autónoma en el demonio de latencia `network_heartbeat.py`, purgando tokens de API y sesiones inactivas cada 5 minutos sin impacto en el rendimiento.
* **Protección de Descargas y Rutas:** Resolución estricta de rutas mediante `application_root()` evitando vulnerabilidades de Directory Traversal (`../`).

---

## 🤖 8. Integración Continua (CI Workflow)

Ubicado en `.github/workflows/ci.yml`:
* **Matriz de Ejecución:** Windows Server ejecutando en paralelo bajo **Python 3.11, 3.12 y 3.13**.
* **Paso a Paso:** Clonado del repositorio, instalación de dependencias desde `requirements.txt` y ejecución de la suite completa de pruebas unitarias e integración con `pytest`.
* **Garantía de Calidad:** Bloquea regresiones y garantiza que cada commit o pull request cumpla con el 100% de tests aprobados.

---

## 🧪 9. Verificación y Cobertura de Pruebas

Toda la arquitectura modular ha sido verificada contra la suite completa de pruebas automatizadas:
* **Total de pruebas:** 302 pruebas unitarias y de integración.
* **Tasa de éxito:** 100% pasando (`302 passed`).
* **Retrocompatibilidad:** Cero rupturas de contratos, importaciones existentes preservadas sin cambios.
