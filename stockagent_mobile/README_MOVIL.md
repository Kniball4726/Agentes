# StockAgent Móvil (Android & Apple iOS)

Aplicación cliente nativa en **Flutter** diseñada para conectarse a través de la red local Wi-Fi al servidor principal **StockAgent** que se ejecuta en tu PC.

---

## 🚀 1. En la PC del Servidor

Para permitir una conexión limpia, rápida y sin advertencias de certificados SSL en los teléfonos:

1. Haz doble clic en el archivo:
   ```bat
   iniciar_servidor_movil.bat
   ```
2. La consola liberará automáticamente el puerto `8550`, verificará la regla en el Firewall de Windows (solicitando permisos de administrador solo si aún no está creada) y te mostrará la dirección IP local de tu PC en la red LAN:
   ```text
   ==================================================================
     >>> DATOS PARA CONECTAR TU CELULAR (APP O NAVEGADOR) <<<
     * Host / IP:   192.168.100.19
     * Puerto:      8550
     * Protocolo:   HTTP

     * URL Directa: http://192.168.100.19:8550
     * (El celular y la PC deben estar en la misma red Wi-Fi)
   ==================================================================
   ```
3. Anota esa dirección IP (en el ejemplo: `192.168.100.19`).

> 💡 **Nota de Firewall:** El script solicita automáticamente permisos de Administrador para abrir el puerto TCP 8550 en el Firewall de Windows si falta la regla. Si alguna vez necesitas forzarlo manualmente, ejecuta `configurar_firewall_red.bat` como Administrador.

---

## 📱 2. En Teléfonos Android

### Opción A: Compilar e Instalar el APK
1. En tu PC, haz doble clic en:
   ```bat
   compilar_apk.bat
   ```
2. El script compilará la aplicación y creará el instalador en:
   `dist_movil\StockAgent.apk`
3. Pasa ese archivo a tu teléfono (por WhatsApp, Telegram o cable USB).
4. Toca el archivo en tu teléfono y selecciona **Instalar** (habilita "Permitir desde esta fuente" si el sistema te lo solicita).
5. Al abrir la app por primera vez:
   * Se abrirá automáticamente la pantalla de configuración.
   * Escribe la IP de la PC (ej: `192.168.100.19`) o pega la URL completa (la app auto-detecta protocolo, host y puerto).
   * Toca **"Probar Conexión"** para verificar que la PC responda.
   * Toca **"Conectar a StockAgent"**.
   * ¡Listo! La configuración quedará guardada permanentemente.

### Modificar la IP o Recargar en cualquier momento:
En la esquina inferior derecha verás botones flotantes discretos:
* **🔄 Botón de Recargar:** Refresca la interfaz web al instante sin salir de la app.
* **⚙️ Botón de Ajustes:** Permite cambiar la IP del servidor si el router reinicia o cambia la conexión.

---

## 🍏 3. En Teléfonos Apple (iPhone / iPad)

### Método Directo y Recomendado (PWA Nativa - Sin necesidad de Mac):
1. Asegúrate de que el iPhone esté conectado a la **misma red Wi-Fi** que la PC.
2. Abre **Safari** en el iPhone y escribe la dirección de la PC:
   `http://192.168.100.19:8550` (reemplazando por tu IP real).
3. Toca el botón **Compartir** (icono de cuadrado con flecha hacia arriba en la parte inferior).
4. Selecciona **"Agregar a pantalla de inicio"** (Add to Home Screen).
5. Se creará el icono oficial de StockAgent en tu iPhone. Al abrirlo, funcionará a pantalla completa como una aplicación nativa, con soporte para el escáner de cámara.

### Método Compilado (.ipa con Flutter):
Si dispones de una computadora Mac con Xcode:
1. Abre la carpeta `stockagent_mobile` en la Mac.
2. Ejecuta `flutter build ipa`.
3. Instálala mediante Xcode o súbela a TestFlight para distribuirla a tus operadores.

---

## 📷 4. Escáner de Códigos de Barra y QR con Cámara

La app móvil incluye integración nativa con la cámara del dispositivo:
* Al ingresar a la sección de **Inventario en Vivo**, la app solicita acceso a la cámara.
* El controlador de Android WebView (`setOnPlatformPermissionRequest`) concede el permiso de video automáticamente sin bloqueos silenciosos.
* Permite leer códigos de barra de productos (EAN-13, Code 128) y códigos QR de remitos con sonido de confirmación auditivo.

---

## 🔧 Solución de Problemas Frecuentes

1. **"Sin conexión con el servidor" o "Tiempo de espera agotado":**
   * Verifica que la PC y el teléfono estén conectados a la **misma red Wi-Fi** (evita tener la PC en cable/5 GHz y el móvil en red de invitados con aislamiento de clientes habilitado).
   * Asegúrate de que la consola de `iniciar_servidor_movil.bat` siga abierta en la PC.
   * Ejecuta `configurar_firewall_red.bat` como Administrador para re-verificar que Windows Firewall no bloquee el puerto 8550.
2. **"Error de certificado SSL/TLS (HandshakeException)":**
   * Ocurre si la PC inició con `iniciar_servidor_web.bat` (que usa HTTPS).
   * Cierra esa ventana y ejecuta **`iniciar_servidor_movil.bat`** (que arranca en HTTP limpio sin advertencias de certificados).
   * En la pantalla de ajustes de la app móvil, asegúrate de tener seleccionado **HTTP** en el protocolo.
3. **Pegar URLs completas:**
   * Si copiaste la URL desde el chat o la consola (ej: `http://192.168.100.19:8550/`), pégala directamente en el campo de IP; la app separará automáticamente el host, el puerto y el protocolo.
