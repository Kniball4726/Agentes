"""Administrador de Copias de Seguridad (Backup) del Sistema de Depósito.

Genera un archivo comprimido .zip con la base de datos SQLite (incluyendo WAL activo),
los usuarios y credenciales, las configuraciones de notificación y el archivo Excel
maestro de stock. Mantiene automáticamente un historial rotativo de respaldos.
"""

from __future__ import annotations

import sqlite3
import zipfile
from datetime import datetime
from pathlib import Path

from .paths import application_root


def crear_backup_sistema(
    carpeta_destino: Path | None = None,
    ruta_excel_base: Path | None = None,
    usuario: str = "Sistema",
) -> Path:
    """Genera un archivo .zip con el respaldo completo de la base de datos y configuraciones."""
    raiz = application_root()
    data_dir = raiz / "data"
    carpeta_backups = carpeta_destino or (data_dir / "backups")
    carpeta_backups.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nombre_zip = f"Backup_Deposito_{timestamp}.zip"
    ruta_zip = carpeta_backups / nombre_zip

    # Respaldar SQLite de forma segura con la API nativa de backup de SQLite
    db_path = data_dir / "pedidos.sqlite3"
    temp_db_backup = carpeta_backups / f"_temp_pedidos_{timestamp}.sqlite3"

    if db_path.exists():
        try:
            with sqlite3.connect(db_path) as src_conn, sqlite3.connect(temp_db_backup) as dst_conn:
                src_conn.backup(dst_conn)
        except Exception:
            # Fallback a copia directa si sqlite connection falla
            temp_db_backup = db_path

    with zipfile.ZipFile(ruta_zip, mode="w", compression=zipfile.ZIP_DEFLATED) as zip_file:
        # 1. Base de datos SQLite
        if temp_db_backup.exists():
            zip_file.write(temp_db_backup, arcname="pedidos.sqlite3")

        # 2. Archivo de usuarios
        usuarios_path = data_dir / "usuarios.json"
        if usuarios_path.exists():
            zip_file.write(usuarios_path, arcname="usuarios.json")

        # 3. Configuración de notificaciones
        config_notif = data_dir / "config_notificaciones.json"
        if config_notif.exists():
            zip_file.write(config_notif, arcname="config_notificaciones.json")

        # 4. Archivo Excel maestro de stock si existe
        if ruta_excel_base and ruta_excel_base.exists():
            zip_file.write(ruta_excel_base, arcname=f"excel_base/{ruta_excel_base.name}")

    # Eliminar temporal de SQLite si fue creado
    if temp_db_backup != db_path and temp_db_backup.exists():
        try:
            temp_db_backup.unlink()
        except OSError:
            pass

    # Rotación: mantener un máximo de 30 respaldos
    try:
        backups_existentes = sorted(
            carpeta_backups.glob("Backup_Deposito_*.zip"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for viejo in backups_existentes[30:]:
            viejo.unlink(missing_ok=True)
    except Exception:
        pass

    return ruta_zip
