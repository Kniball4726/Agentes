# StockAgent Móvil (Android & Apple iOS)

Aplicación cliente nativa en **Flutter** con arquitectura desacoplada, diseñada para conectarse a través de la red local Wi-Fi a la API REST del servidor principal **StockAgent** que se ejecuta en tu PC.

---

## 🏗️ Nueva Arquitectura Desacoplada (Frontend Nativo + Backend REST API)

A diferencia de versiones anteriores basadas en WebViews, la aplicación móvil ahora es **100% nativa en Flutter**:

* **Consumo de API REST (/api/v1):** Se comunica con el backend mediante peticiones JSON estándar y sin estado (`Bearer Token`), liberando la memoria del servidor de la PC.
* **Sesión Segura y Roles:** Login nativo con verificación de credenciales y roles (`operador`, `administrador`, `master`).
* **Resiliencia Offline:** Los conteos de inventario se guardan continuamente en almacenamiento local del teléfono. Si el operario entra a un sector sin Wi-Fi, no pierde ni un solo escaneo.
* **Feedback Háptico y Sonoro:** Confirmación inmediata por vibración y pitido auditivo tras cada lectura válida de código de barras o rótulo QR.

---

## 📱 Módulos y Pantallas Operativas

### 1. Inventario en Vivo (Conteo de Existencias)
* **Escaneo rápido:** Compatible con lectores láser Bluetooth/USB (Barcode Wedge) y teclado del teléfono.
* **Multiplicadores de cantidad rápida:** Botones `+1`, `+5`, `+10`, `+50` para agilizar conteos de bultos cerrados.
* **Balance preliminar en vivo:** Permite contrastar los productos contados contra el stock del sistema antes de cerrar el lote, identificando faltantes y sobrantes.
* **Cierre y sincronización:** Envía el conteo a la PC, actualiza el stock físico en la base de datos y genera el informe Excel oficial para administración.

### 2. Despacho y Logística (Rótulos QR y Remitos)
* **Escaneo de rótulos QR:** Lee etiquetas impresas (`REMITO:...|CLIENTE:...|BULTOS:...`) o números de remito directos.
* **Avance automático de estados:** Transición inmediata de `Armado` → `Despachado` → `Entregado`.
* **Modo forzado:** Permite fijar un estado específico si se requiere reabrir o retroceder un pedido.
* **Historial auditado:** Registro en pantalla de cada bulto despachado con la hora exacta y operario responsable.

### 3. Catálogo y Slotting de Depósito
* **Búsqueda inmediata:** Por nombre, SKU interno o código de barras EAN-13/Code-128.
* **Gestión de ubicación física:** Permite al operario modificar en el momento la estantería o posición asignada (ej: `A-02-3`).
* **Vinculación de códigos:** Asocia un nuevo código de barras leído por el escáner a un producto del catálogo.

---

## 🚀 1. En la PC del Servidor

Para permitir la conexión por red local:

1. Haz doble clic en:
   ```bat
   iniciar_servidor_movil.bat
   ```
2. La consola liberará automáticamente el puerto `8550`, verificará el Firewall de Windows y mostrará los datos de conexión LAN:
   ```text
   ==================================================================
     >>> DATOS PARA CONECTAR TU CELULAR (APP O NAVEGADOR) <<<
     * Host / IP:   192.168.100.19
     * Puerto:      8550
     * Protocolo:   HTTP

     * URL Directa: http://192.168.100.19:8550
   ==================================================================
   ```

---

## 📱 2. Compilar e Instalar el APK en Android

1. En tu PC, haz doble clic en:
   ```bat
   compilar_apk.bat
   ```
2. El instalador quedará generado en `stockagent_mobile\dist_movil\StockAgent.apk`.
3. Pásalo a tu celular (WhatsApp, cable USB o Telegram) e instálalo.
4. Al abrir la app:
   * Ingresa la IP de la PC (ej: `192.168.100.19`).
   * Toca **"Probar Conexión"** y luego **"Conectar a StockAgent"**.
   * Inicia sesión con tus credenciales de usuario (ej: `Otto`, `Gregory`, `Admin`).
