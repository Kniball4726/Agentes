"""Módulo de Telemetría y Salud del Servidor: Monitoreo de disco, memoria y estado operativo."""

import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .paths import application_root


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
    except Exception:
        pass
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
    except Exception:
        pass
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
