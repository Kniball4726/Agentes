# Desacoplamiento y Compilación del Cliente Móvil (StockAgent Mobile)

Este documento detalla la arquitectura desacoplada y los controles de seguridad del cliente móvil Flutter respecto al servidor Python/FastAPI/Flet de **StockAgent**.

---

## 🏗️ 1. Filosofía de Arquitectura Desacoplada y Segura

El cliente móvil está diseñado para operar de forma 100% independiente:
* **Protocolo:** Comunicación exclusivamente vía REST API (`/api/v1/`) sobre **HTTPS por defecto** con **Certificate Pinning (TOFU)** (`lib/services/tls_pinning_service.dart`) y prevención de downgrade silencioso a HTTP.
* **Almacenamiento Cifrado y Aislado:** El token Bearer se cifra en hardware mediante `AndroidKeyStore` (`AES/GCM/NoPadding` en `MainActivity.kt`), mientras que los borradores de inventario, caché de nombres y colas offline de despacho se aíslan por usuario (`username`).
* **Endurecimiento Nativo Android/iOS:**
  * `android:allowBackup="false"` y `networkSecurityConfig` (`cleartextTrafficPermitted="false"` por defecto).
  * `FileProvider` restringido exclusivamente a subdirectorios `cacheDir/updates/` y `cacheDir/picker_uploads/`.
  * Verificación de integridad `SHA-256` y `packageName` antes de instalar actualizaciones OTA.
  * `NSAllowsArbitraryLoads = false` y `NSAllowsLocalNetworking = true` en iOS (`Info.plist`).

---

## 🚀 2. Exportación Automática

Para extraer la aplicación a una carpeta independiente, ejecuta el script ubicado en la raíz del servidor:

```cmd
exportar_stockagent_mobile.bat
```

Por defecto, esto copiará todo el código a `..\StockAgent_Mobile`, excluyendo carpetas pesadas de compilación (`build/`, `.dart_tool/`, `.gradle/`).

---

## 📦 3. Compilación de la Aplicación Android (APK)

1. **Instalar dependencias:**
   ```bash
   flutter pub get
   ```
2. **Compilar APK de producción (con R8 / ProGuard y soporte de `key.properties`):**
   ```bash
   flutter build apk --release
   ```
   O ejecuta directamente `stockagent_mobile\compilar_apk.bat`, que además genera `dist_movil\version.json` incluyendo el hash `sha256` del binario compilado.

---

## ⚡ 4. Capacidades Offline, Colas FIFO y Ergonomía en Depósito

* **Thumb Zone y Objetivos Táctiles `>= 48dp`:**
  Barra de navegación inferior con transferencia explícita de `FocusNode` entre pestañas (`Inventario`, `Despacho`, `Catálogo`) para evitar que lectores láser Bluetooth HID escriban en pestañas ocultas.
* **Colas FIFO y Persistencia Offline con Auto-Sync:**
  * Las ráfagas de lectura con pistola láser se encolan en orden FIFO sin descartar lecturas mientras una petición está en curso.
  * Ante pérdidas de señal Wi-Fi, tanto el conteo de inventario como el despacho guardan las lecturas en disco y sincronizan automáticamente la cola pendiente al reconectar con el servidor central.
* **Modo Claro Alto Contraste y Modo Lector Láser:**
  Alternables desde el menú superior para operar bajo luz solar directa o con colectores físicos sin teclado virtual en pantalla.
