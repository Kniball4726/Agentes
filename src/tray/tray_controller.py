"""Controlador del icono System Tray de StockAgent y monitor de salud del servidor."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from typing import Callable, Optional

from ..logger_config import configurar_logging, obtener_ruta_log
from ..paths import application_root
from .net_and_images import (
    ESTADO_CLIENTE,
    ESTADO_ERROR,
    ESTADO_INICIANDO,
    ESTADO_ONLINE,
    TEXTOS_ESTADO,
    _copiar_al_portapapeles,
    _obtener_ip_local,
    _obtener_ip_tailscale,
    describir_dispositivo,
    generar_imagen_estado,
)

logger = configurar_logging()


class TrayIconServidor:
    """Controlador del icono en el área de notificaciones de Windows (System Tray)."""

    _VENTANA_CLIENTE_HTTP_S = 25.0
    _INTERVALO_NOTIF_CLIENTE_S = 120.0

    def __init__(
        self,
        port: int = 8550,
        host: str = "0.0.0.0",
        https: bool = True,
        on_exit: Optional[Callable[[], None]] = None,
    ):
        self.port = port
        self.host = host
        self.https = https
        self.esquema = "https" if https else "http"
        self.on_exit = on_exit

        self.ip_local = _obtener_ip_local()
        self.url_local = f"{self.esquema}://localhost:{self.port}"
        self.ip_tailscale = _obtener_ip_tailscale()
        self.url_red = f"{self.esquema}://{self.ip_local}:{self.port}"
        self.url_remoto = f"{self.esquema}://{self.ip_tailscale}:{self.port}" if self.ip_tailscale else None

        self.estado = ESTADO_INICIANDO
        self._icon = None
        self._tray_thread: Optional[threading.Thread] = None
        self._monitor_thread: Optional[threading.Thread] = None
        self._activo = False
        self._primera_conexion_notificada = False
        self._imagenes_cache: dict[str, object] = {}
        self._lock_clientes = threading.Lock()
        self._clientes_ws: dict[str, int] = {}
        self._clientes_http: dict[str, float] = {}

    @staticmethod
    def _es_ip_local(ip: str) -> bool:
        return not ip or ip in ("127.0.0.1", "::1", "localhost", "desconocido")

    def registrar_actividad_cliente(self, ip: str) -> None:
        """Marca actividad HTTP reciente de un dispositivo remoto."""
        if self._es_ip_local(ip):
            return
        with self._lock_clientes:
            self._clientes_http[ip] = time.monotonic()

    def cliente_ws_abierto(self, ip: str) -> None:
        """Registra una sesión WebSocket abierta (app en un dispositivo)."""
        if self._es_ip_local(ip):
            return
        with self._lock_clientes:
            self._clientes_ws[ip] = self._clientes_ws.get(ip, 0) + 1

    def cliente_ws_cerrado(self, ip: str) -> None:
        """Registra el cierre de una sesión WebSocket."""
        if self._es_ip_local(ip):
            return
        with self._lock_clientes:
            restantes = self._clientes_ws.get(ip, 0) - 1
            if restantes > 0:
                self._clientes_ws[ip] = restantes
            else:
                self._clientes_ws.pop(ip, None)
            self._clientes_http[ip] = time.monotonic()

    def clientes_conectados(self) -> list[str]:
        """Devuelve las IPs remotas actualmente conectadas (ordenadas)."""
        ahora = time.monotonic()
        with self._lock_clientes:
            ips = set(self._clientes_ws)
            for ip, visto in list(self._clientes_http.items()):
                if ahora - visto <= self._VENTANA_CLIENTE_HTTP_S:
                    ips.add(ip)
                else:
                    del self._clientes_http[ip]
            return sorted(ips)

    def _generar_imagen(self, estado: str):
        if estado in self._imagenes_cache:
            return self._imagenes_cache[estado]
        base = generar_imagen_estado(estado)
        if base is not None:
            self._imagenes_cache[estado] = base
        return base

    def _crear_menu(self):
        import pystray

        texto_estado_actual = f"Servidor: {TEXTOS_ESTADO.get(self.estado, self.estado)} (Puerto {self.port})"
        clientes = self.clientes_conectados()
        texto_clientes = (
            f"📱 Dispositivos conectados: {len(clientes)} ({', '.join(clientes[:3])})"
            if clientes
            else "📱 Sin dispositivos conectados"
        )

        items = [
            pystray.MenuItem(texto_estado_actual, None, enabled=False),
            pystray.MenuItem(texto_clientes, None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("🌐 Abrir en el navegador", self._accion_abrir_navegador, default=True),
            pystray.MenuItem("📋 Copiar enlace de red local", self._accion_copiar_enlace_red),
        ]
        if self.url_remoto:
            items.append(pystray.MenuItem("🔒 Copiar enlace remoto (Tailscale)", self._accion_copiar_enlace_remoto))
        items.extend([
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("📂 Abrir carpeta del programa", self._accion_abrir_carpeta),
            pystray.MenuItem("📄 Ver registro de actividad (Logs)", self._accion_ver_logs),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("⏹️ Detener servidor y salir", self._accion_detener),
        ])
        return pystray.Menu(*items)

    def _accion_abrir_navegador(self, _icon=None, _item=None):
        try:
            webbrowser.open(self.url_local)
        except Exception as exc:
            logger.warning("No se pudo abrir navegador desde System Tray: %s", exc)

    def _accion_copiar_enlace_red(self, _icon=None, _item=None):
        if _copiar_al_portapapeles(self.url_red):
            self.mostrar_notificacion("Enlace de Red Copiado", f"Dirección copiada al portapapeles:\n{self.url_red}")

    def _accion_copiar_enlace_remoto(self, _icon=None, _item=None):
        if self.url_remoto and _copiar_al_portapapeles(self.url_remoto):
            self.mostrar_notificacion("Enlace Remoto Copiado", f"Dirección remota copiada al portapapeles:\n{self.url_remoto}")

    def _accion_abrir_carpeta(self, _icon=None, _item=None):
        try:
            ruta = application_root()
            if sys.platform == "win32":
                os.startfile(ruta)
            else:
                subprocess.run(["xdg-open", str(ruta)], check=False)
        except Exception as exc:
            logger.warning("No se pudo abrir carpeta del programa: %s", exc)

    def _accion_ver_logs(self, _icon=None, _item=None):
        try:
            ruta_log = obtener_ruta_log()
            if sys.platform == "win32":
                os.startfile(ruta_log)
            else:
                subprocess.run(["xdg-open", str(ruta_log)], check=False)
        except Exception as exc:
            logger.warning("No se pudo abrir archivo de log: %s", exc)

    def _accion_detener(self, _icon=None, _item=None):
        logger.info("Cierre del servidor solicitado desde el System Tray.")
        self.mostrar_notificacion("StockAgent", "Deteniendo el servidor y cerrando la aplicación...")
        self.detener()
        time.sleep(0.4)
        if callable(self.on_exit):
            try:
                self.on_exit()
            except Exception as exc:
                logger.error("Error en callback de salida: %s", exc)
        os._exit(0)

    def mostrar_notificacion(self, titulo: str, mensaje: str) -> None:
        """Envía una notificación emergente nativa de Windows (Toast/Balloon)."""
        try:
            if self._icon and hasattr(self._icon, "notify"):
                self._icon.notify(mensaje, titulo)
        except Exception as exc:
            logger.debug("No se pudo enviar notificación de bandeja: %s", exc)

    @staticmethod
    def _describir_dispositivo(agente: str) -> str:
        return describir_dispositivo(agente)

    def notificar_conexion_cliente(self, ip: str, agente: str = "") -> bool:
        """Muestra una notificación limitada en frecuencia cuando un dispositivo remoto se conecta."""
        if not ip or ip in ("127.0.0.1", "::1", "localhost"):
            return False
        ahora = time.monotonic()
        ultimos = self.__dict__.setdefault("_ultimas_notif_cliente", {})
        if ahora - ultimos.get(ip, -1e9) < self._INTERVALO_NOTIF_CLIENTE_S:
            return False
        ultimos[ip] = ahora
        dispositivo = self._describir_dispositivo(agente)
        self.mostrar_notificacion("StockAgent: Nueva conexión", f"{dispositivo} conectado desde {ip}")
        return True

    def actualizar_estado(self, nuevo_estado: str) -> None:
        """Actualiza icono, tooltip y menú contextual según el nuevo estado del servidor."""
        if not self._icon:
            return
        cambio = self.estado != nuevo_estado
        self.estado = nuevo_estado
        try:
            img = self._generar_imagen(nuevo_estado)
            if img:
                self._icon.icon = img
            if nuevo_estado == ESTADO_CLIENTE:
                clientes = self.clientes_conectados()
                self._icon.title = f"StockAgent: {len(clientes)} dispositivo(s) conectado(s) ({self.esquema.upper()} :{self.port})"
            elif nuevo_estado == ESTADO_ONLINE:
                self._icon.title = f"StockAgent: En línea ({self.esquema.upper()} :{self.port})"
            elif nuevo_estado == ESTADO_INICIANDO:
                self._icon.title = f"StockAgent: Iniciando en puerto {self.port}..."
            elif nuevo_estado == ESTADO_ERROR:
                self._icon.title = f"StockAgent: Servidor caído o no responde (Puerto {self.port})"
            else:
                self._icon.title = "StockAgent: Detenido"

            self._icon.menu = self._crear_menu()

            if cambio and nuevo_estado in (ESTADO_ONLINE, ESTADO_CLIENTE) and not self._primera_conexion_notificada:
                self._primera_conexion_notificada = True
                self.mostrar_notificacion(
                    "StockAgent: Servidor Activo",
                    f"Servidor web en línea en {self.url_local}\nAcceso en red: {self.url_red}",
                )
            elif cambio and nuevo_estado == ESTADO_ERROR:
                self.mostrar_notificacion("StockAgent: Advertencia", f"El servidor no responde en el puerto {self.port}.")
        except Exception as exc:
            logger.debug("Error al actualizar estado en System Tray: %s", exc)

    def _verificar_servidor_activo(self) -> bool:
        try:
            with socket.create_connection(("127.0.0.1", self.port), timeout=0.6):
                return True
        except OSError:
            return False

    def _loop_monitor(self) -> None:
        time.sleep(1.0)
        while self._activo:
            try:
                if self._verificar_servidor_activo():
                    hay_clientes = bool(self.clientes_conectados())
                    self.actualizar_estado(ESTADO_CLIENTE if hay_clientes else ESTADO_ONLINE)
                else:
                    self.actualizar_estado(ESTADO_ERROR if self._primera_conexion_notificada else ESTADO_INICIANDO)
            except Exception as exc:
                logger.debug("Excepción en monitor de System Tray: %s", exc)
            time.sleep(2.5)

    def _run_icon_loop(self) -> None:
        try:
            import pystray

            self._icon = pystray.Icon(
                name="StockAgentTray",
                icon=self._generar_imagen(self.estado),
                title=f"StockAgent: Iniciando en puerto {self.port}...",
                menu=self._crear_menu(),
            )
            logger.info("System Tray de StockAgent iniciado correctamente.")
            self._icon.run()
        except Exception as exc:
            logger.warning("Fallo al ejecutar el icono del System Tray: %s", exc)
        finally:
            self._icon = None

    def iniciar(self) -> bool:
        """Inicia el icono en la bandeja y el monitor en hilos secundarios."""
        if self._activo:
            return True
        try:
            import pystray  # noqa: F401
            from PIL import Image  # noqa: F401
        except ImportError as e:
            logger.warning("No se pudo inicializar el icono de bandeja: librería requerida ausente (%s)", e)
            return False

        self._activo = True
        self._tray_thread = threading.Thread(target=self._run_icon_loop, name="StockAgentTrayIconThread", daemon=True)
        self._tray_thread.start()
        self._monitor_thread = threading.Thread(target=self._loop_monitor, name="StockAgentTrayMonitorThread", daemon=True)
        self._monitor_thread.start()
        return True

    def detener(self) -> None:
        """Detiene el monitor y quita el icono de la bandeja."""
        self._activo = False
        try:
            if self._icon:
                self._icon.stop()
        except Exception as exc:
            logger.debug("Error al detener icono de System Tray: %s", exc)
        self._icon = None
