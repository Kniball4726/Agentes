# Desacoplamiento y Compilación del Cliente Móvil (StockAgent Mobile)

Este documento detalla la arquitectura desacoplada del cliente móvil Flutter respecto al servidor Python/FastAPI/Flet de **StockAgent**.

---

## 🏗️ 1. Filosofía de Arquitectura Desacoplada

El cliente móvil está diseñado para operar de forma 100% independiente:
* **Protocolo:** Comunicación exclusivamente vía REST API (`/api/v1/`) sobre HTTP/HTTPS y WebSockets.
* **Sin dependencias cruzadas:** La aplicación Flutter no comparte dependencias de Python ni requiere SQLite local del servidor; cuenta con su propio almacenamiento local (`shared_preferences`) y buffer de escaneo offline en memoria/disco.
* **Separación de repositorios:** Se recomienda mantener el código de Flutter en una carpeta hermana o repositorio independiente (`StockAgent_Mobile/`) para no mezclar los entornos de desarrollo (Flutter SDK vs Python 3.10+).

---

## 🚀 2. Exportación Automática

Para extraer la aplicación a una carpeta independiente, ejecuta el script ubicado en la raíz del servidor:

```cmd
exportar_stockagent_mobile.bat
```

Por defecto, esto copiará todo el código a `..\StockAgent_Mobile`, excluyendo carpetas pesadas de compilación (`build/`, `.dart_tool/`, `.gradle/`).

---

## 📦 3. Compilación de la Aplicación Android (APK)

Una vez en el directorio independiente de Flutter:

1. **Instalar dependencias:**
   ```bash
   flutter pub get
   ```

2. **Probar en emulador o dispositivo conectado:**
   ```bash
   flutter run
   ```

3. **Compilar APK de producción:**
   ```bash
   flutter build apk --release
   ```
   El archivo generado se ubicará en:
   `build/app/outputs/flutter-apk/app-release.apk`

---

## ⚡ 4. Capacidades Offline y Thumb Zone

* **Thumb Zone (Zona del Pulgar):**
  La interfaz está optimizada para sostener el teléfono o colector de datos (Zebra, Sunmi, Urovo) con una sola mano. La barra de navegación inferior da acceso con un solo toque a:
  * 📦 **Inventario:** Conteo físico y relevamiento.
  * 🚚 **Despacho:** Escaneo de rótulos QR y remitos.
  * 🔍 **Catálogo:** Búsqueda y asociación de códigos de barra.

* **Buffer de Escaneo Offline:**
  * Si el operario ingresa a una zona ciega de Wi-Fi en el depósito, los escaneos no se descartan ni generan error: se acumulan automáticamente en la **Cola Offline**.
  * Al recuperar la señal Wi-Fi, la app detecta la reconexión con el servidor central mediante el Heartbeat periódico y permite sincronizar todo el lote de escaneos acumulados con un solo toque o de manera automática vía `/api/v1/despacho/escanear-lote`.
