"""Módulo del icono en la bandeja del sistema (System Tray / Área de Notificaciones).

Muestra el estado en tiempo real del servidor web de StockAgent:
- 🟢 En línea (servidor respondiendo en el puerto configurado)
- 🟡 Iniciando / Verificando
- 🔴 Caído o Inaccesible
- ⚪ Detenido

Permite:
- Hacer doble clic para abrir la aplicación web en el navegador.
- Menú contextual con clic derecho:
    * Estado actual detallado y puerto.
    * Abrir en el navegador local.
    * Copiar enlace de acceso en red local (LAN) al portapapeles.
    * Abrir carpeta del programa.
    * Ver el archivo de logs en vivo.
    * Detener el servidor y salir limpiamente.
"""

from __future__ import annotations

import logging
import os
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import Callable, Optional

from .logger_config import configurar_logging, obtener_ruta_log
from .paths import application_root

logger = configurar_logging()

# Estados posibles del servidor
ESTADO_INICIANDO = "iniciando"
ESTADO_ONLINE = "online"
ESTADO_ERROR = "error"
ESTADO_DETENIDO = "detenido"

TEXTOS_ESTADO = {
    ESTADO_INICIANDO: "🟡 Iniciando...",
    ESTADO_ONLINE: "🟢 En línea",
    ESTADO_ERROR: "🔴 Desconectado / Error",
    ESTADO_DETENIDO: "⚪ Detenido",
}

COLORES_BADGE = {
    ESTADO_INICIANDO: (234, 179, 8, 255),    # Amarillo (#eab308)
    ESTADO_ONLINE: (34, 197, 94, 255),       # Verde (#22c55e)
    ESTADO_ERROR: (239, 68, 68, 255),        # Rojo (#ef4444)
    ESTADO_DETENIDO: (156, 163, 175, 255),   # Gris (#9ca3af)
}


def _obtener_ip_local() -> str:
    """Devuelve la dirección IP del equipo en la red local (LAN)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(0.2)
            s.connect(("8.8.8.8", 80))
            return str(s.getsockname()[0])
    except Exception:
        try:
            return str(socket.gethostbyname(socket.gethostname()))
        except Exception:
            return "127.0.0.1"


def _obtener_ip_tailscale() -> Optional[str]:
    """Busca una dirección IPv4 de Tailscale asignada a la máquina (rango 100.64.0.0/10)."""
    try:
        host = socket.gethostname()
        for item in socket.getaddrinfo(host, None, socket.AF_INET):
            ip = item[4][0]
            if ip.startswith("100."):
                partes = [int(p) for p in ip.split(".") if p.isdigit()]
                if len(partes) == 4 and 64 <= partes[1] <= 127:
                    return ip
    except Exception:
        pass
    return None


def _copiar_al_portapapeles(texto: str) -> bool:
    """Copia una cadena de texto al portapapeles nativo de Windows."""
    try:
        subprocess.run(
            "clip",
            input=texto.encode("utf-16"),
            shell=True,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except Exception as exc:
        logger.warning("No se pudo copiar al portapapeles: %s", exc)
        return False


def _buscar_icono_base() -> Optional[Path]:
    """Busca la imagen base del logotipo para el icono de la bandeja."""
    candidatos = []
    # 1. En ejecutable empaquetado PyInstaller (_MEIPASS)
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        p = Path(meipass)
        candidatos.extend([
            p / "src" / "img" / "ultratech.png",
            p / "assets" / "favicon.png",
            p / "assets" / "icons" / "icon-192.png",
        ])

    # 2. En la raíz de la aplicación o código fuente
    app_root = application_root()
    candidatos.extend([
        app_root / "src" / "img" / "ultratech.png",
        app_root / "assets" / "favicon.png",
        app_root / "assets" / "icons" / "icon-192.png",
        Path(__file__).resolve().parent / "img" / "ultratech.png",
    ])

    for ruta in candidatos:
        if ruta.is_file():
            return ruta
    return None


class TrayIconServidor:
    """Controlador del icono en el área de notificaciones de Windows (System Tray)."""

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
        self.url_local = f"{self.esquema}://127.0.0.1:{self.port}"
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

    def _generar_imagen(self, estado: str):
        """Genera una imagen con el badge de estado para el icono de la bandeja."""
        if estado in self._imagenes_cache:
            return self._imagenes_cache[estado]

        try:
            from PIL import Image, ImageDraw

            ruta_base = _buscar_icono_base()
            if ruta_base and ruta_base.exists():
                base = Image.open(ruta_base).convert("RGBA").resize((64, 64), Image.Resampling.LANCZOS)
            else:
                # Icono sintético si no hay imagen en disco
                base = Image.new("RGBA", (64, 64), color=(0, 0, 0, 0))
                draw_bg = ImageDraw.Draw(base)
                draw_bg.rounded_rectangle(
                    (4, 4, 60, 60),
                    radius=12,
                    fill=(30, 41, 59, 255),
                    outline=(71, 85, 105, 255),
                    width=2,
                )

            # Dibujar el badge circular de estado en la esquina inferior derecha
            draw = ImageDraw.Draw(base)
            box_badge = (38, 38, 62, 62)
            color_badge = COLORES_BADGE.get(estado, COLORES_BADGE[ESTADO_INICIANDO])

            # Anillo exterior blanco para contraste sobre barras de tareas oscuras y claras
            draw.ellipse((36, 36, 64, 64), fill=(255, 255, 255, 255))
            # Círculo interior del color de estado
            draw.ellipse(box_badge, fill=color_badge)

            self._imagenes_cache[estado] = base
            return base
        except Exception as exc:
            logger.error("Error al generar imagen para System Tray: %s", exc)
            try:
                from PIL import Image
                fallback = Image.new("RGBA", (16, 16), color=(34, 197, 94, 255))
                return fallback
            except Exception:
                return None

    def _crear_menu(self):
        """Construye el menú contextual para el icono."""
        import pystray

        texto_estado_actual = f"Servidor: {TEXTOS_ESTADO.get(self.estado, self.estado)} (Puerto {self.port})"

        items = [
            pystray.MenuItem(
                texto_estado_actual,
                None,
                enabled=False,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "🌐 Abrir en el navegador",
                self._accion_abrir_navegador,
                default=True,
            ),
            pystray.MenuItem(
                "📋 Copiar enlace de red local",
                self._accion_copiar_enlace_red,
            ),
        ]
        if self.url_remoto:
            items.append(
                pystray.MenuItem(
                    "🔒 Copiar enlace remoto (Tailscale)",
                    self._accion_copiar_enlace_remoto,
                )
            )
        items.extend([
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "📂 Abrir carpeta del programa",
                self._accion_abrir_carpeta,
            ),
            pystray.MenuItem(
                "📄 Ver registro de actividad (Logs)",
                self._accion_ver_logs,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "⏹️ Detener servidor y salir",
                self._accion_detener,
            ),
        ])
        return pystray.Menu(*items)

    def _accion_abrir_navegador(self, _icon=None, _item=None):
        """Abre la URL local en el navegador predeterminado."""
        try:
            webbrowser.open(self.url_local)
        except Exception as exc:
            logger.warning("No se pudo abrir navegador desde System Tray: %s", exc)

    def _accion_copiar_enlace_red(self, _icon=None, _item=None):
        """Copia el enlace de la red LAN al portapapeles y notifica."""
        copiado = _copiar_al_portapapeles(self.url_red)
        if copiado:
            self.mostrar_notificacion(
                "Enlace de Red Copiado",
                f"Dirección copiada al portapapeles:\n{self.url_red}",
            )

    def _accion_copiar_enlace_remoto(self, _icon=None, _item=None):
        """Copia el enlace remoto de Tailscale al portapapeles y notifica."""
        if self.url_remoto:
            copiado = _copiar_al_portapapeles(self.url_remoto)
            if copiado:
                self.mostrar_notificacion(
                    "Enlace Remoto Copiado",
                    f"Dirección remota copiada al portapapeles:\n{self.url_remoto}",
                )

    def _accion_abrir_carpeta(self, _icon=None, _item=None):
        """Abre la carpeta raíz de la aplicación en el explorador de archivos."""
        try:
            ruta = application_root()
            if sys.platform == "win32":
                os.startfile(ruta)
            else:
                subprocess.run(["xdg-open", str(ruta)], check=False)
        except Exception as exc:
            logger.warning("No se pudo abrir carpeta del programa: %s", exc)

    def _accion_ver_logs(self, _icon=None, _item=None):
        """Abre el archivo principal de registro (logs)."""
        try:
            ruta_log = obtener_ruta_log()
            if sys.platform == "win32":
                os.startfile(ruta_log)
            else:
                subprocess.run(["xdg-open", str(ruta_log)], check=False)
        except Exception as exc:
            logger.warning("No se pudo abrir archivo de log: %s", exc)

    def _accion_detener(self, _icon=None, _item=None):
        """Detiene el servidor y finaliza la aplicación."""
        logger.info("Cierre del servidor solicitado desde el System Tray.")
        self.mostrar_notificacion(
            "StockAgent",
            "Deteniendo el servidor y cerrando la aplicación...",
        )
        self.detener()
        time.sleep(0.4)
        if callable(self.on_exit):
            try:
                self.on_exit()
            except Exception as exc:
                logger.error("Error en callback de salida: %s", exc)
        # Finalización segura e inmediata del proceso
        os._exit(0)

    def mostrar_notificacion(self, titulo: str, mensaje: str):
        """Envía una notificación emergente nativa de Windows (Toast/Balloon)."""
        try:
            if self._icon and hasattr(self._icon, "notify"):
                self._icon.notify(mensaje, titulo)
        except Exception as exc:
            logger.debug("No se pudo enviar notificación de bandeja: %s", exc)

    def actualizar_estado(self, nuevo_estado: str):
        """Actualiza el icono, tooltip y menú según el nuevo estado del servidor."""
        if not self._icon:
            return

        cambio = self.estado != nuevo_estado
        self.estado = nuevo_estado

        try:
            # 1. Actualizar icono gráfico
            img = self._generar_imagen(nuevo_estado)
            if img:
                self._icon.icon = img

            # 2. Actualizar texto de Tooltip al pasar el mouse
            if nuevo_estado == ESTADO_ONLINE:
                self._icon.title = f"StockAgent: En línea ({self.esquema.upper()} :{self.port})"
            elif nuevo_estado == ESTADO_INICIANDO:
                self._icon.title = f"StockAgent: Iniciando en puerto {self.port}..."
            elif nuevo_estado == ESTADO_ERROR:
                self._icon.title = f"StockAgent: Servidor caído o no responde (Puerto {self.port})"
            else:
                self._icon.title = "StockAgent: Detenido"

            # 3. Actualizar menú contextual
            self._icon.menu = self._crear_menu()

            # 4. Notificaciones por cambios de estado relevantes
            if cambio and nuevo_estado == ESTADO_ONLINE and not self._primera_conexion_notificada:
                self._primera_conexion_notificada = True
                self.mostrar_notificacion(
                    "StockAgent: Servidor Activo",
                    f"Servidor web en línea en {self.url_local}\nAcceso en red: {self.url_red}",
                )
            elif cambio and nuevo_estado == ESTADO_ERROR:
                self.mostrar_notificacion(
                    "StockAgent: Advertencia",
                    f"El servidor no responde en el puerto {self.port}.",
                )
        except Exception as exc:
            logger.debug("Error al actualizar estado en System Tray: %s", exc)

    def _verificar_servidor_activo(self) -> bool:
        """Comprueba si el servidor web responde en el puerto local."""
        try:
            with socket.create_connection(("127.0.0.1", self.port), timeout=0.6):
                return True
        except OSError:
            return False

    def _loop_monitor(self):
        """Hilo en segundo plano para verificar periódicamente la salud del servidor."""
        # Breve espera inicial para dar tiempo a que el servidor Flet / Uvicorn se vincule al puerto
        time.sleep(1.0)
        while self._activo:
            try:
                activo = self._verificar_servidor_activo()
                if activo:
                    self.actualizar_estado(ESTADO_ONLINE)
                else:
                    if self._primera_conexion_notificada:
                        self.actualizar_estado(ESTADO_ERROR)
                    else:
                        self.actualizar_estado(ESTADO_INICIANDO)
            except Exception as exc:
                logger.debug("Excepción en monitor de System Tray: %s", exc)
            time.sleep(2.5)

    def _run_icon_loop(self):
        """Bucle principal de eventos de Win32 para el System Tray."""
        try:
            import pystray

            img_inicial = self._generar_imagen(self.estado)
            self._icon = pystray.Icon(
                name="StockAgentTray",
                icon=img_inicial,
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
            logger.warning(
                "No se pudo inicializar el icono de bandeja: librería requerida ausente (%s)",
                e,
            )
            return False

        self._activo = True

        # Hilo para el icono pystray (Win32 message loop)
        self._tray_thread = threading.Thread(
            target=self._run_icon_loop,
            name="StockAgentTrayIconThread",
            daemon=True,
        )
        self._tray_thread.start()

        # Hilo para el monitor de salud del servidor
        self._monitor_thread = threading.Thread(
            target=self._loop_monitor,
            name="StockAgentTrayMonitorThread",
            daemon=True,
        )
        self._monitor_thread.start()

        return True

    def detener(self):
        """Detiene el monitor y quita el icono de la bandeja."""
        self._activo = False
        try:
            if self._icon:
                self._icon.stop()
        except Exception as exc:
            logger.debug("Error al detener icono de System Tray: %s", exc)
        self._icon = None


def iniciar_icono_bandeja(
    port: int = 8550,
    host: str = "0.0.0.0",
    https: bool = True,
    on_exit: Optional[Callable[[], None]] = None,
) -> Optional[TrayIconServidor]:
    """Crea e inicia el servicio de System Tray para el servidor StockAgent."""
    try:
        tray = TrayIconServidor(
            port=port,
            host=host,
            https=https,
            on_exit=on_exit,
        )
        if tray.iniciar():
            return tray
    except Exception as exc:
        logger.warning("No se pudo iniciar el servicio de icono de bandeja: %s", exc)
    return None
