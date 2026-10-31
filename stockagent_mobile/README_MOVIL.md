# StockAgent Móvil (Android & Apple iOS)

Aplicación cliente nativa en **Flutter** diseñada para conectarse a través de la red local Wi-Fi al servidor principal **StockAgent** que se ejecuta en tu PC.

---

## 🚀 1. En la PC del Servidor

Para permitir una conexión limpia y sin advertencias de certificados SSL en los teléfonos:

1. Haz doble clic en el archivo:
   ```bat
   iniciar_servidor_movil.bat
   ```
2. La consola te mostrará la dirección IP local de tu PC en la red LAN, por ejemplo:
   ```text
   -> Acceso Red LAN (misma red): http://192.168.1.50:8550
   ```
3. Anota esa dirección IP (en el ejemplo: `192.168.1.50`).

> 💡 **Nota de Firewall:** El script `iniciar_servidor_movil.bat` abre automáticamente el puerto TCP 8550 en el Firewall de Windows. Si alguna vez necesitas forzarlo manualmente, ejecuta `configurar_firewall_red.bat` como Administrador.

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
4. Toca el archivo en tu teléfono y selecciona **Instalar**.
5. Al abrirla por primera vez:
   * Escribe la IP de la PC (ej: `192.168.1.50`).
   * Toca **"Probar Conexión"** para verificar.
   * Toca **"Conectar a StockAgent"**.
   * ¡Listo! La IP quedará memorizada para siempre.

### Modificar la IP en cualquier momento:
En la esquina inferior derecha verás un icono flotante de engranaje (⚙️). Tocándolo puedes cambiar la IP del servidor si cambia tu router o conexión.

---

## 🍏 3. En Teléfonos Apple (iPhone / iPad)

### Método Directo y Recomendado (PWA Nativa - Sin necesidad de Mac):
1. Asegúrate de que el iPhone esté conectado a la **misma red Wi-Fi** que la PC.
2. Abre **Safari** en el iPhone y escribe la dirección de la PC:
   `http://192.168.1.50:8550` (reemplazando por tu IP real).
3. Toca el botón **Compartir** (icono de cuadrado con flecha hacia arriba en la parte inferior).
4. Selecciona **"Agregar a pantalla de inicio"** (Add to Home Screen).
5. Se creará el icono oficial de StockAgent en tu iPhone. Al abrirlo, funcionará a pantalla completa como una aplicación nativa, con soporte para el escáner de cámara.

### Método Compilado (.ipa con Flutter):
Si dispones de una Mac:
1. Abre la carpeta `stockagent_mobile` en la Mac.
2. Ejecuta `flutter build ipa`.
3. Instálala mediante Xcode o súbela a TestFlight para distribuirla a tus operadores.

---

## 🔧 Solución de Problemas Frecuentes

1. **"No se pudo conectar con el servidor":**
   * Verifica que la PC y el teléfono estén conectados a la **misma red Wi-Fi** (ojo con tener la PC en la red 5 GHz y el móvil en 2.4 GHz de un router que aísle clientes).
   * Asegúrate de que la consola de `iniciar_servidor_movil.bat` siga abierta en la PC.
   * Desactiva temporalmente el antivirus de terceros si bloquea el puerto 8550.
2. **"La cámara del escáner no abre":**
   * Acepta el permiso de cámara cuando la app te lo solicite en el primer escaneo.
   * La app ya tiene pre-configurado el permiso nativo `android.permission.CAMERA` y `NSCameraUsageDescription`.
