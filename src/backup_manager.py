"""Administrador de Copias de Seguridad (Backup y Restauración) del Sistema de Depósito.

Genera un archivo comprimido .zip con las tres bases de datos SQLite (incluyendo WAL activo:
pedidos.sqlite3, productos.sqlite3, usuarios.sqlite3), las configuraciones y el archivo Excel
maestro de stock. Soporta copia automática a carpeta externa/secundaria y restauración
verificada con PRAGMA integrity_check.
"""

from __future__ import annotations

import json
import logging
import shutil
import sqlite3
import tempfile
import zipfile
from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import Any

from .paths import application_root

logger = logging.getLogger("stockagent")

BASES_SQLITE = ("pedidos.sqlite3", "productos.sqlite3", "usuarios.sqlite3")
ARCHIVOS_CONFIG = ("usuarios.json", "config_notificaciones.json", "email_config.json", "backup_config.json")


def _ruta_config_backup() -> Path:
    return application_root() / "data" / "backup_config.json"


def obtener_config_backup() -> dict[str, Any]:
    ruta = _ruta_config_backup()
    cfg = {"carpeta_externa": "", "max_backups": 30}
    if ruta.exists():
        try:
            datos = json.loads(ruta.read_text(encoding="utf-8"))
            if isinstance(datos, dict):
                cfg.update(datos)
        except Exception:
            pass
    return cfg


def guardar_config_backup(carpeta_externa: str | dict[str, Any], max_backups: int = 30) -> None:
    ruta = _ruta_config_backup()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(carpeta_externa, dict):
        ext = str(
            carpeta_externa.get("carpeta_externa")
            or carpeta_externa.get("carpeta_secundaria")
            or ""
        ).strip()
        max_b = int(carpeta_externa.get("max_backups", max_backups) or 30)
    else:
        ext = (carpeta_externa or "").strip()
        max_b = int(max_backups or 30)
    datos = {
        "carpeta_externa": ext,
        "max_backups": max(5, max_b),
    }
    ruta.write_text(json.dumps(datos, indent=2, ensure_ascii=False), encoding="utf-8")


def _respaldar_sqlite_seguro(origen: Path, destino: Path) -> bool:
    if not origen.exists():
        return False
    try:
        with closing(sqlite3.connect(origen, timeout=10)) as src_conn, closing(
            sqlite3.connect(destino)
        ) as dst_conn:
            src_conn.backup(dst_conn)
        return True
    except Exception:
        try:
            shutil.copy2(origen, destino)
            return True
        except Exception:
            return False


def verificar_integridad_sqlite(ruta_db: Path) -> tuple[bool, str]:
    """Ejecuta PRAGMA integrity_check sobre un archivo SQLite."""
    if not ruta_db.exists():
        return False, f"Archivo no encontrado: {ruta_db.name}"
    try:
        with closing(sqlite3.connect(ruta_db, timeout=10)) as conn:
            fila = conn.execute("PRAGMA integrity_check").fetchone()
            resultado = str(fila[0]) if fila else "error"
            if resultado.lower() == "ok":
                return True, "OK"
            return False, f"Fallo de integridad en {ruta_db.name}: {resultado}"
    except Exception as exc:
        return False, f"Archivo SQLite inválido ({ruta_db.name}): {exc}"


def crear_backup_sistema(
    carpeta_destino: Path | None = None,
    ruta_excel_base: Path | None = None,
    usuario: str = "Sistema",
) -> Path:
    """Genera un archivo .zip con el respaldo completo de las bases SQLite, configs y Excel."""
    raiz = application_root()
    data_dir = raiz / "data"
    carpeta_backups = carpeta_destino or (data_dir / "backups")
    carpeta_backups.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nombre_zip = f"Backup_Deposito_{timestamp}.zip"
    ruta_zip = carpeta_backups / nombre_zip

    temporales: list[Path] = []
    try:
        with zipfile.ZipFile(ruta_zip, mode="w", compression=zipfile.ZIP_DEFLATED) as zip_file:
            # 1. Respaldar las 3 bases de datos SQLite de forma segura
            for nombre_db in BASES_SQLITE:
                db_path = data_dir / nombre_db
                if db_path.exists():
                    temp_db = carpeta_backups / f"_temp_{timestamp}_{nombre_db}"
                    if _respaldar_sqlite_seguro(db_path, temp_db) and temp_db.exists():
                        temporales.append(temp_db)
                        zip_file.write(temp_db, arcname=nombre_db)

            # 2. Archivos de configuración
            for nombre_cfg in ARCHIVOS_CONFIG:
                cfg_path = data_dir / nombre_cfg
                if cfg_path.exists():
                    zip_file.write(cfg_path, arcname=nombre_cfg)

            # 3. Archivo Excel maestro de stock si existe
            excel_path = ruta_excel_base
            if excel_path is None:
                posible = raiz / "Productos.xlsx"
                if posible.exists():
                    excel_path = posible
            if excel_path and excel_path.exists():
                zip_file.write(excel_path, arcname=f"excel_base/{excel_path.name}")

            # 4. Manifiesto de metadatos del backup
            manifiesto = {
                "fecha": datetime.now().isoformat(timespec="seconds"),
                "usuario": usuario,
                "bases_incluidas": [db for db in BASES_SQLITE if (data_dir / db).exists()],
            }
            zip_file.writestr("backup_manifest.json", json.dumps(manifiesto, indent=2, ensure_ascii=False))
    finally:
        for temp in temporales:
            try:
                temp.unlink(missing_ok=True)
            except OSError:
                pass

    # Copia opcional a carpeta externa/secundaria si está configurada
    cfg_backup = obtener_config_backup()
    carpeta_ext_str = str(cfg_backup.get("carpeta_externa", "")).strip()
    if carpeta_ext_str:
        try:
            carpeta_ext = Path(carpeta_ext_str)
            carpeta_ext.mkdir(parents=True, exist_ok=True)
            if carpeta_ext.resolve() != carpeta_backups.resolve():
                shutil.copy2(ruta_zip, carpeta_ext / nombre_zip)
                logger.info("Copia secundaria de backup guardada en %s", carpeta_ext / nombre_zip)
        except Exception as exc:
            logger.warning("No se pudo copiar el backup a la carpeta externa '%s': %s", carpeta_ext_str, exc)

    # Rotación: mantener un máximo de respaldos
    max_keep = int(cfg_backup.get("max_backups", 30) or 30)
    try:
        backups_existentes = sorted(
            carpeta_backups.glob("Backup_Deposito_*.zip"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for viejo in backups_existentes[max_keep:]:
            viejo.unlink(missing_ok=True)
    except Exception:
        pass

    logger.info("Backup generado exitosamente en %s por %s", ruta_zip, usuario)
    return ruta_zip


def listar_backups_disponibles(carpeta_destino: Path | None = None) -> list[Path]:
    """Lista los archivos .zip de backup disponibles ordenados del más reciente al más antiguo."""
    raiz = application_root()
    carpeta_backups = carpeta_destino or (raiz / "data" / "backups")
    if not carpeta_backups.exists():
        return []
    return sorted(
        carpeta_backups.glob("Backup_*.zip"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )


def restaurar_backup_sistema(
    ruta_zip: str | Path,
    ruta_excel_base: Path | None = None,
    usuario: str = "Admin",
) -> tuple[bool, str, list[str]]:
    """Restaura un archivo .zip de backup tras verificar la integridad de todas sus bases SQLite.

    Retorna `(exito, mensaje, archivos_restaurados)`.
    """
    ruta_zip = Path(ruta_zip)
    if not ruta_zip.exists():
        return False, f"No existe el archivo de backup: {ruta_zip}", []

    if not zipfile.is_zipfile(ruta_zip):
        return False, f"El archivo '{ruta_zip.name}' no es un archivo .zip válido.", []

    raiz = application_root()
    data_dir = raiz / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="restore_stockagent_") as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)
        try:
            with zipfile.ZipFile(ruta_zip, mode="r") as zf:
                zf.extractall(tmp_dir)
        except Exception as exc:
            return False, f"Error al extraer el archivo .zip: {exc}", []

        # Verificar que contenga al menos una base SQLite o config conocida y validar integridad SQLite
        dbs_encontradas = [
            tmp_dir / nombre_db for nombre_db in BASES_SQLITE if (tmp_dir / nombre_db).exists()
        ]
        if not dbs_encontradas:
            return (
                False,
                "El archivo .zip no contiene bases de datos del sistema (pedidos/productos/usuarios).",
                [],
            )

        for db_temp in dbs_encontradas:
            ok, msg = verificar_integridad_sqlite(db_temp)
            if not ok:
                return False, f"Restauración cancelada por seguridad: {msg}", []

        # Crear un backup de seguridad previo a la restauración
        try:
            crear_backup_sistema(ruta_excel_base=ruta_excel_base, usuario=f"PreRestore_{usuario}")
        except Exception:
            pass

        restaurados: list[str] = []

        # Restaurar SQLite usando la API de backup de SQLite para sobreescribir limpiamente incluso con WAL
        for db_temp in dbs_encontradas:
            destino_db = data_dir / db_temp.name
            try:
                with closing(sqlite3.connect(db_temp)) as src_conn, closing(
                    sqlite3.connect(destino_db, timeout=15)
                ) as dst_conn:
                    src_conn.backup(dst_conn)
                restaurados.append(db_temp.name)
            except Exception:
                shutil.copy2(db_temp, destino_db)
                restaurados.append(db_temp.name)

        # Restaurar archivos de configuración
        for nombre_cfg in ARCHIVOS_CONFIG:
            cfg_temp = tmp_dir / nombre_cfg
            if cfg_temp.exists():
                shutil.copy2(cfg_temp, data_dir / nombre_cfg)
                restaurados.append(nombre_cfg)

        # Restaurar Excel maestro si está en el backup
        carpeta_excel_tmp = tmp_dir / "excel_base"
        if carpeta_excel_tmp.exists():
            for archivo_xlsx in carpeta_excel_tmp.glob("*.xls*"):
                destino_excel = ruta_excel_base or (raiz / archivo_xlsx.name)
                try:
                    shutil.copy2(archivo_xlsx, destino_excel)
                    restaurados.append(destino_excel.name)
                except Exception as exc:
                    logger.warning("No se pudo restaurar Excel base %s: %s", destino_excel, exc)

    logger.info(
        "Backup '%s' restaurado por '%s'. Archivos: %s",
        ruta_zip.name,
        usuario,
        ", ".join(restaurados),
    )
    return (
        True,
        f"Backup '{ruta_zip.name}' verificado (PRAGMA integrity_check = OK) y restaurado ({len(restaurados)} archivos).",
        restaurados,
    )
