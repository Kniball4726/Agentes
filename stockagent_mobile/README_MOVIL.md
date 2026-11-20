# StockAgent Móvil (Android & Apple iOS)

Aplicación cliente nativa en **Flutter** con arquitectura desacoplada, diseñada para conectarse de forma segura a través de la red local Wi-Fi a la API REST (`/api/v1`) del servidor principal **StockAgent** que se ejecuta en tu PC.

---

## 🏗️ Arquitectura Desacoplada y Seguridad Criptográfica (Frontend Nativo + Backend REST API)

La aplicación móvil es **100% nativa en Flutter** e implementa controles de seguridad e integridad de grado industrial:

* **HTTPS por Defecto, TLS Certificate Pinning (TOFU) y Anti-Downgrade (`TlsPinningService`):**
  * Conecta por defecto sobre `HTTPS` y fija la huella digital del certificado X.509 del servidor local en el primer enlace validado (**Trust-On-First-Use**), verificando vigencia temporal (`startValidity` / `endValidity`) y coincidencia estricta de host.
  * Prohíbe la degradación silenciosa (`HTTPS → HTTP`) para impedir ataques *Man-in-the-Middle (MitM)* en redes Wi-Fi de depósito.
* **Almacén Cifrado por Hardware (`AndroidKeyStore`):**
  * El token de sesión (`Bearer Token`) se cifra con `AES/GCM/NoPadding` de 256 bits mediante el canal nativo `com.stockagent.mobile/secure_storage` respaldado por `AndroidKeyStore`, sin duplicarse en texto plano dentro del perfil JSON del usuario.
  * Los borradores de inventario, caché de nombres y colas offline quedan aislados por nombre de usuario (`username`), y se revocan automáticamente al cambiar de servidor o recibir `HTTP 401`.
* **Actualizaciones OTA con Verificación `SHA-256` (`UpdateService` + `MainActivity.kt`):**
  * Valida que la URL del APK pertenezca al mismo origen del servidor configurado, descarga el paquete en el directorio confinado `cacheDir/updates/`, verifica la firma criptográfica `SHA-256` publicada en `/actualizaciones/version.json` y comprueba con `PackageManager.getPackageArchiveInfo` que `packageName == com.stockagent.mobile` antes de invocar el instalador de Android.
* **Colas FIFO de Escaneo y Resiliencia Offline Persistente:**
  * Tanto Inventario como Despacho cuentan con **colas FIFO (`_colaEscaneos`)** para que ráfagas de lectura con pistolas láser nunca descarten códigos mientras una petición HTTP está en vuelo.
  * Ante microcortes de Wi-Fi en pasillos (`statusCode 0 / 408 / >= 502`), los conteos de inventario y los escaneos de despacho se persisten en disco y se **auto-sincronizan automáticamente** tan pronto como el heartbeat detecta la reconexión con el servidor.
* **Ergonomía para Depósito (`>= 48dp`, Modo Claro Alto Contraste y Modo Lector Láser):**
  * Botones y chips con área táctil mínima de `48dp` para operación con guantes de trabajo.
  * **Modo Claro de Alto Contraste** para lectura bajo luz solar directa en muelles exteriores y **Modo Lector Láser** para ocultar el teclado virtual en colectores de datos físicos (Zebra, Sunmi, Urovo).

---

## 📱 Módulos y Pantallas Operativas

### 1. Inventario en Vivo (Conteo de Existencias)
* **Escaneo rápido con cola FIFO:** Compatible con lectores láser Bluetooth/USB (Barcode Wedge) y teclado del teléfono sin pérdida de lecturas consecutivas.
* **Multiplicadores ergonómicos (`>= 48dp`):** Píldoras `+1`, `+5`, `+10`, `+50` apiladas sobre el campo de escaneo de ancho completo.
* **Deshacer eliminación (`DESHACER`):** Permite restaurar con un toque cualquier SKU eliminado accidentalmente de la lista de conteo.
* **Guardado offline en pasillos:** Si cae la señal Wi-Fi durante el conteo, el SKU y su cantidad se registran igualmente en el borrador local del operario.
* **Balance preliminar y cierre:** Contrasta productos contados contra el stock del sistema y genera el informe Excel oficial en la PC.

### 2. Despacho y Logística (Rótulos QR y Remitos)
* **Escaneo de rótulos QR y remitos:** Lee etiquetas impresas (`REMITO:...|CLIENTE:...|BULTOS:...`) o números de remito con cola FIFO.
* **Control de permisos por rol (RBAC):** Avance automático (`Armado → Despachado → Entregado`) o fijación de estado; la acción de revertir a `ARMADO` se restringe exclusivamente a perfiles con permiso administrativo (`canRevertDispatchState`).
* **Cola offline persistente con auto-sync:** Almacena en disco únicamente fallas reales de conectividad (sin contaminar la cola con errores `4xx` de negocio) y sincroniza el lote vía `/api/v1/despacho/escanear-lote` al recuperar conexión.

### 3. Catálogo y Slotting de Depósito
* **Búsqueda reactiva con debounce:** Filtrado automático por nombre, SKU o código de barras (`EAN-13`, `Code-128`, `Code-39` alfanumérico) con botón de limpieza reactivo (`ValueListenableBuilder`).
* **Gestión de ubicación y códigos (`canEditCatalog`):** Chips de `>= 48dp` en layout adaptable (`Wrap`) para actualizar estantería/posición (ej. `A-02-3`) o vincular códigos de barras numéricos y alfanuméricos.

---

## 🚀 1. En la PC del Servidor

1. Asegúrate de haber habilitado el puerto `8550` en perfil de red privada ejecutando `configurar_firewall_red.bat` como Administrador (una sola vez).
2. Haz doble clic en:
   ```bat
   stockagent_mobile\iniciar_servidor_movil.bat
   ```
3. Por defecto el servidor arranca sobre **HTTPS cifrado** en `0.0.0.0:8550` (`https://<IP_SERVIDOR>:8550`).

---

## 📱 2. Compilar e Instalar el APK en Android

1. En tu PC, haz doble clic en:
   ```bat
   stockagent_mobile\compilar_apk.bat
   ```
2. El script compila el APK en modo release, calcula su firma `sha256` y publica `StockAgent.apk` junto con `version.json` en `stockagent_mobile\dist_movil\`.
3. Instala el APK en el dispositivo, ingresa la IP de la PC, pulsa **"Probar Conexión"** (fija la huella TLS del servidor) y luego **"Conectar a StockAgent"**.
