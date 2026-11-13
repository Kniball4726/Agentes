import shutil
import sqlite3
import os
from pathlib import Path

# Create backup directory if not exists
backup_dir = Path("data/backups")
backup_dir.mkdir(parents=True, exist_ok=True)

# 1. Backup SQLite
db_path = Path("data/productos.sqlite3")
db_backup = backup_dir / "productos_backup_antes_import_pdf.sqlite3"
shutil.copy2(db_path, db_backup)
print(f"SQLite backup created at: {db_backup}")

# 2. Backup Excel
excel_path = Path("Descuentos/Productos.xlsx")
excel_backup = backup_dir / "Productos_backup_antes_import_pdf.xlsx"
shutil.copy2(excel_path, excel_backup)
print(f"Excel backup created at: {excel_backup}")
