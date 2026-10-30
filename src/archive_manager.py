"""Módulo de Gestión y Archivado Histórico de Comprobantes.

Organiza comprobantes y archivos de pedidos antiguos en carpetas cronológicas
`data/historico/YYYY/MM/`, manteniendo las carpetas operativas ligeras y rápidas.
"""

from datetime import datetime, timedelta
from pathlib import Path
import shutil
from typing import Any

from .paths import application_root


def obtener_estadisticas_almacenamiento(root_path: Path | None = None) -> dict[str, Any]:
    """Calcula la cantidad de archivos y volumen ocupado en las carpetas de comprobantes."""
    root = root_path or application_root()
    dir_pedidos = root / "data" / "pedidos_archivos"
    dir_descontados = root / "data" / "descontados"
    dir_historico = root / "data" / "historico"

    def _medir_dir(d: Path) -> tuple[int, int]:
        if not d.exists():
            return 0, 0
        archivos = [f for f in d.rglob("*") if f.is_file()]
        total_b = sum(f.stat().st_size for f in archivos)
        return len(archivos), total_b

    cant_ped, bytes_ped = _medir_dir(dir_pedidos)
    cant_desc, bytes_desc = _medir_dir(dir_descontados)
    cant_hist, bytes_hist = _medir_dir(dir_historico)

    total_bytes = bytes_ped + bytes_desc + bytes_hist
    return {
        "pedidos_archivos_cant": cant_ped,
        "pedidos_archivos_mb": round(bytes_ped / (1024**2), 2),
        "descontados_cant": cant_desc,
        "descontados_mb": round(bytes_desc / (1024**2), 2),
        "historico_cant": cant_hist,
        "historico_mb": round(bytes_hist / (1024**2), 2),
        "total_archivos": cant_ped + cant_desc + cant_hist,
        "total_mb": round(total_bytes / (1024**2), 2),
    }


def archivar_comprobantes_antiguos(
    dias_antiguedad: int = 30, root_path: Path | None = None
) -> dict[str, Any]:
    """Organiza comprobantes que superen los días de antigüedad en `data/historico/YYYY/MM/`."""
    root = root_path or application_root()
    dir_historico = root / "data" / "historico"
    dir_historico.mkdir(parents=True, exist_ok=True)

    limite_dt = datetime.now() - timedelta(days=dias_antiguedad)

    origenes = [
        root / "data" / "pedidos_archivos",
        root / "data" / "descontados",
    ]

    movidos = 0
    bytes_movidos = 0
    carpetas_creadas: set[str] = set()

    for carpeta in origenes:
        if not carpeta.exists():
            continue

        # Iterar sobre archivos directos (no recursivo en historico)
        for f in list(carpeta.glob("*")):
            if not f.is_file():
                continue

            try:
                mtime_dt = datetime.fromtimestamp(f.stat().st_mtime)
                # Si el archivo es más antiguo que el límite fijado
                if mtime_dt <= limite_dt:
                    yyyy = mtime_dt.strftime("%Y")
                    mm = mtime_dt.strftime("%m")
                    sub_dest = dir_historico / yyyy / mm
                    sub_dest.mkdir(parents=True, exist_ok=True)
                    carpetas_creadas.add(f"{yyyy}/{mm}")

                    dest_file = sub_dest / f.name
                    # Si ya existe en destino, agregar un sufijo único
                    if dest_file.exists():
                        timestamp_sufijo = int(datetime.now().timestamp())
                        dest_file = sub_dest / f"{f.stem}_{timestamp_sufijo}{f.suffix}"

                    f_size = f.stat().st_size
                    shutil.move(str(f), str(dest_file))
                    movidos += 1
                    bytes_movidos += f_size
            except Exception:
                continue

    return {
        "archivos_movidos": movidos,
        "mb_organizados": round(bytes_movidos / (1024**2), 2),
        "carpetas_organizadas": sorted(list(carpetas_creadas)),
    }
