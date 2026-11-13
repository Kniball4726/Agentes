# StockAgent Móvil (Android & Apple iOS)

Aplicación cliente nativa en **Flutter** con arquitectura desacoplada, diseñada para conectarse a través de la red local Wi-Fi a la API REST del servidor principal **StockAgent** que se ejecuta en tu PC.

---

## 🏗️ Nueva Arquitectura Desacoplada (Frontend Nativo + Backend REST API)

A diferencia de versiones anteriores basadas en WebViews, la aplicación móvil ahora es **100% nativa en Flutter**:

* **Consumo de API REST (/api/v1):** Se comunica con el backend modular mediante peticiones JSON estándar y sin estado (`Bearer Token` en encabezado `Authorization`), conectando directamente con los módulos de dominio desacoplados (`src.auth` para autenticación, `src.orders` para gestión de pedidos y despacho, `src.products` para consulta y actualización de catálogo/código de barras, `src.stock` para informes/etiquetas y `src.inventory` para reconciliación de stock).
* **Manejo Estructurado de Errores (`src.core.exceptions`):** Las respuestas de error del servidor retornan códigos tipificados y consistentes (ej. `AUTH_ACCOUNT_LOCKED`, `ORDER_NOT_FOUND`), permitiendo a la app móvil mostrar alertas precisas y descriptivas en pantalla.
* **Sesión Segura y Roles:** Login nativo con verificación de credenciales y control de permisos por rol (`operador`, `picker`, `administrador`, `master`, `consulta`).
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

1. Asegúrate de haber habilitado el puerto `8550` en perfil de red privada ejecutando `configurar_firewall_red.bat` como Administrador (una sola vez).
2. Haz doble clic en:
   ```bat
   stockagent_mobile\iniciar_servidor_movil.bat
   ```
   *(Sin argumentos inicia en segundo plano mediante `iniciar_servidor_movil_en_segundo_plano.vbs`. Para ver diagnóstico en consola ejecuta `iniciar_servidor_movil.bat --consola`.)*
3. Por defecto el servidor arranca sobre **HTTPS cifrado** en `0.0.0.0:8550` (`https://<IP_SERVIDOR>:8550`) usando el certificado en `data\certs\stockagent.crt`:
   * Si abres la app web/PWA desde otra PC Windows o navegador en LAN, instala `stockagent.crt` con `instalar_certificado.bat` o utiliza `crear_acceso_directo_cliente.bat`.
   * En dispositivos móviles o entornos de red local estrictamente aislados donde requieras HTTP plano temporalmente, pasa la bandera `--http`:
     ```bat
     stockagent_mobile\iniciar_servidor_movil.bat --consola --http
     ```
     *(Con `--http` el tráfico viaja sin cifrar; úsalo únicamente en una LAN privada de confianza.)*

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
