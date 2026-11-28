"""Módulo de Telemetría y Salud del Servidor: Monitoreo de disco, memoria y estado operativo."""

import logging
import os
import shutil
import sqlite3
import time
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

from .logger_config import obtener_ruta_log
from .paths import application_root

logger = logging.getLogger("stockagent.telemetry")


@dataclass
class TelemetriaSistema:
    """Métricas de estado y recursos del servidor."""
    disco_total_gb: float
    disco_libre_gb: float
    disco_usado_pct: float
    disco_alerta: bool
    ram_total_gb: float
    ram_disponible_gb: float
    ram_carga_pct: int
    ram_proceso_mb: float
    estado_salud: str  # "Óptimo", "Atención", "Crítico"
    detalle_salud: str


def _obtener_ram_proceso_mb() -> float:
    """Obtiene la memoria RAM en megabytes consumida por el proceso actual."""
    try:
        import ctypes
        from ctypes import wintypes

        class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        pid = os.getpid()
        handle = ctypes.windll.kernel32.OpenProcess(0x0400 | 0x0010, False, pid)
        if handle:
            counters = PROCESS_MEMORY_COUNTERS()
            counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
            exito = ctypes.windll.psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb)
            ctypes.windll.kernel32.CloseHandle(handle)
            if exito:
                return round(counters.WorkingSetSize / (1024**2), 1)
    except (OSError, AttributeError) as exc:
        logger.debug("No se pudo consultar RAM del proceso vía API Windows: %s", exc)
    return 0.0


def _obtener_ram_sistema() -> tuple[float, float, int]:
    """Obtiene total_gb, disponible_gb y porcentaje_carga de la memoria RAM global."""
    try:
        import ctypes

        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        stat = MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
            tot = round(stat.ullTotalPhys / (1024**3), 1)
            disp = round(stat.ullAvailPhys / (1024**3), 1)
            return tot, disp, int(stat.dwMemoryLoad)
    except (OSError, AttributeError) as exc:
        logger.debug("No se pudo consultar RAM global del sistema vía API Windows: %s", exc)
    return 8.0, 4.0, 50


def obtener_telemetria_sistema(ruta_base: Optional[Path] = None) -> TelemetriaSistema:
    """Calcula la telemetría completa de almacenamiento, memoria y diagnóstico de salud."""
    target_path = ruta_base or (application_root() / "data")
    if not target_path.exists():
        target_path = Path.cwd()

    try:
        total_b, used_b, free_b = shutil.disk_usage(str(target_path))
        d_total_gb = round(total_b / (1024**3), 1)
        d_libre_gb = round(free_b / (1024**3), 1)
        d_usado_pct = round((used_b / total_b) * 100, 1) if total_b > 0 else 0.0
    except Exception:
        d_total_gb = 100.0
        d_libre_gb = 50.0
        d_usado_pct = 50.0

    # Alerta si el disco libre es menor al 10% o menos de 3 GB
    disco_alerta = (d_libre_gb < 3.0) or (d_usado_pct >= 90.0)

    ram_total_gb, ram_disp_gb, ram_carga_pct = _obtener_ram_sistema()
    ram_proc_mb = _obtener_ram_proceso_mb()

    # Evaluación del estado de salud global
    if d_libre_gb < 2.0 or d_usado_pct >= 95.0 or ram_carga_pct >= 95:
        salud = "Crítico"
        detalle = f"Espacio libre crítico ({d_libre_gb} GB restantes). Peligro en generación de backups."
    elif disco_alerta or ram_carga_pct >= 85:
        salud = "Atención"
        detalle = f"Almacenamiento o memoria exigida ({d_usado_pct}% disco en uso, {ram_carga_pct}% RAM)."
    else:
        salud = "Óptimo"
        detalle = "Servidor operando con recursos estables y margen holgado de almacenamiento."

    return TelemetriaSistema(
        disco_total_gb=d_total_gb,
        disco_libre_gb=d_libre_gb,
        disco_usado_pct=d_usado_pct,
        disco_alerta=disco_alerta,
        ram_total_gb=ram_total_gb,
        ram_disponible_gb=ram_disp_gb,
        ram_carga_pct=ram_carga_pct,
        ram_proceso_mb=ram_proc_mb,
        estado_salud=salud,
        detalle_salud=detalle,
    )


def medir_latencia_sqlite(db_path: Path | str | None) -> Optional[float]:
    """Mide en milisegundos un sondeo `SELECT 1` sobre una base SQLite existente."""
    if not db_path:
        return None
    ruta = Path(db_path)
    try:
        if not ruta.exists() or not ruta.is_file():
            return None
        inicio = time.perf_counter()
        with closing(sqlite3.connect(str(ruta), timeout=2.0)) as conn:
            conn.execute("SELECT 1").fetchone()
        return round((time.perf_counter() - inicio) * 1000.0, 2)
    except Exception:
        return None


def obtener_metricas_logs(ruta_log: Optional[Path] = None) -> Dict[str, int]:
    """Retorna tamaño actual del log principal, tamaño total rotado y cantidad de archivos."""
    try:
        objetivo = ruta_log or obtener_ruta_log()
        principal_bytes = objetivo.stat().st_size if objetivo.exists() and objetivo.is_file() else 0
        carpeta = objetivo.parent
        archivos = list(carpeta.glob(f"{objetivo.name}*")) if carpeta.exists() else []
        total_bytes = sum(f.stat().st_size for f in archivos if f.is_file())
        return {
            "log_principal_bytes": int(principal_bytes),
            "log_total_bytes": int(total_bytes),
            "log_archivos": int(sum(1 for f in archivos if f.is_file())),
        }
    except Exception:
        return {
            "log_principal_bytes": 0,
            "log_total_bytes": 0,
            "log_archivos": 0,
        }
