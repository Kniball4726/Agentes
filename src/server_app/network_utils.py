"""Utilidades de red, detección de IP, puertos, consola y rutas estáticas de arranque."""

from __future__ import annotations

import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import webbrowser

PUERTO_WEB_DEFAULT = 8550


def obtener_directorio_assets() -> str:
    """Devuelve la ruta absoluta al directorio de assets estáticos (favicons, logos)."""
    from ..paths import application_root

    if getattr(sys, "_MEIPASS", None):
        candidato = Path(sys._MEIPASS) / "assets"
        if candidato.is_dir():
            return str(candidato.resolve())
    candidato = application_root() / "assets"
    if candidato.is_dir():
        return str(candidato.resolve())
    candidato = Path(__file__).resolve().parent.parent.parent / "assets"
    if candidato.is_dir():
        return str(candidato.resolve())
    return str((Path(__file__).resolve().parent.parent / "img").resolve())


def obtener_ip_local() -> str:
    """Devuelve la dirección IP de la máquina en la red local (LAN)."""
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


def obtener_ip_tailscale() -> str | None:
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


def _puerto_local_activo(port: int) -> bool:
    """Verifica si el puerto local TCP ya se encuentra en escucha."""
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.4):
            return True
    except OSError:
        return False


def ocultar_consola_windows() -> None:
    """Oculta la ventana de consola en Windows cuando se ejecuta en modo silencioso."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)
    except Exception:
        pass


def asegurar_flujos_estandar() -> None:
    """Garantiza streams válidos en ejecutables sin consola asociada (PyInstaller)."""
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")


def resolver_instancia_unica(
    port: int, esquema: str, abrir_navegador: bool, ft_module
) -> bool:
    """Verifica si existe una instancia previa en el puerto y la reutiliza o reinicia.

    Retorna True si el servidor actual debe abortar porque delegó en la instancia activa.
    """
    forzar_reinicio = any(
        f in sys.argv for f in ("--force", "--forzar", "--reiniciar", "--restart")
    )
    if hasattr(ft_module.run, "_mock_name") or not _puerto_local_activo(port):
        return False

    if forzar_reinicio:
        try:
            salida = subprocess.check_output("netstat -ano", shell=True, text=True)
            for line in salida.splitlines():
                if f":{port}" in line and "LISTENING" in line:
                    pid_str = line.strip().split()[-1]
                    subprocess.run(
                        f"taskkill /F /PID {pid_str}", shell=True, capture_output=True
                    )
            time.sleep(0.6)
        except Exception:
            pass

    if not forzar_reinicio or _puerto_local_activo(port):
        url_activa = f"{esquema}://localhost:{port}"
        if abrir_navegador:
            print(
                f"[INFO] Servidor activo detectado en {url_activa}. Abriendo navegador..."
            )
            webbrowser.open(url_activa)
        else:
            print(f"[INFO] Servidor activo detectado en {url_activa}.")
        return True
    return False
