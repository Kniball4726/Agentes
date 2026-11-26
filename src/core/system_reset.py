"""Módulo para el reseteo seguro a cero (Zapping) de la base de datos de producción."""

from __future__ import annotations

from contextlib import closing
from datetime import datetime
import sqlite3
from typing import Any
import openpyxl

from ..auth.events import notify_session_revocation
from ..paths import application_root
from .environment import is_qa_environment


def ejecutar_zapping_produccion(
    conservar_clientes: bool = True,
    crear_backup: bool = True,
) -> dict[str, Any]:
    """
    Ejecuta una puesta a cero segura (Zapping) del entorno de producción:
    - Crea respaldo .zip preventivo con fecha y hora.
    - Conserva todos los productos, códigos, SKUs, descripciones y ubicaciones.
    - Lleva el stock a cero para todos los productos en SQLite y en Productos.xlsx.
    - Conserva los clientes si conservar_clientes=True.
    - Conserva las cuentas de usuarios (Master, Admin, Picker, Operador).
    - Vacía pedidos, remitos, cierres de jornada, cierres de mercado, planes Full,
      movimientos de stock y logs de auditoría.
    - Resetea los contadores autoincrementales para reiniciar desde #1.
    """
    if is_qa_environment():
        raise RuntimeError(
            "No se puede ejecutar el zapping de producción mientras el entorno QA está activo."
        )

    from ..backup_manager import crear_backup_sistema
    from ..inventory.excel_sync import detectar_esquema

    raiz = application_root()
    data_dir = raiz / "data"
    desc_dir = raiz / "Descuentos"
    ruta_excel = desc_dir / "Productos.xlsx"

    # 1. Crear Backup Preventivo Automático
    ruta_backup = None
    if crear_backup:
        ruta_backup = crear_backup_sistema(
            carpeta_destino=data_dir / "backups",
            ruta_excel_base=ruta_excel if ruta_excel.exists() else None,
            usuario="Master_Zapping",
        )

    # 2. Resetear productos.sqlite3
    db_productos = data_dir / "productos.sqlite3"
    total_productos = 0
    if db_productos.exists():
        with closing(sqlite3.connect(db_productos)) as conn:
            conn.execute("PRAGMA foreign_keys = OFF")
            conn.execute("BEGIN IMMEDIATE")

            # Llevar stock a cero conservando todos los artículos
            conn.execute("UPDATE products SET stock = 0, stock_fisico = NULL")
            total_productos = conn.execute("SELECT count(*) FROM products").fetchone()[0]

            # Vaciar tablas transaccionales de movimientos y alertas
            for tabla in (
                "stock_movements",
                "despachos",
                "despacho_detalles",
                "admin_notifications",
                "inventario_fisico",
                "inventario_fisico_detalles",
            ):
                try:
                    conn.execute(f"DELETE FROM {tabla}")
                except sqlite3.OperationalError:
                    pass

            # Resetear contadores de secuencias
            try:
                conn.execute(
                    """
                    DELETE FROM sqlite_sequence
                    WHERE name IN (
                        'stock_movements', 'despachos', 'despacho_detalles',
                        'admin_notifications', 'inventario_fisico', 'inventario_fisico_detalles'
                    )
                    """
                )
            except sqlite3.OperationalError:
                pass

            conn.commit()
            conn.execute("VACUUM")

    # 3. Resetear pedidos.sqlite3
    db_pedidos = data_dir / "pedidos.sqlite3"
    total_clientes = 0
    if db_pedidos.exists():
        with closing(sqlite3.connect(db_pedidos)) as conn:
            conn.execute("PRAGMA foreign_keys = OFF")
            conn.execute("BEGIN IMMEDIATE")

            # Conteo de clientes conservados
            total_clientes = conn.execute("SELECT count(*) FROM clientes").fetchone()[0]

            if not conservar_clientes:
                conn.execute("DELETE FROM clientes")
                total_clientes = 0

            # Vaciar pedidos, items, cierres, planes full, auditoría y chat
            for tabla in (
                "pedidos",
                "pedido_items",
                "cierres_jornada",
                "cierres_mercado",
                "planes_mercado_full",
                "plan_mercado_full_items",
                "logs_auditoria",
                "mensajes_chat_leidos",
                "mensajes_chat",
                "pedidos_bloqueos",
                "transacciones_procesadas",
            ):
                try:
                    conn.execute(f"DELETE FROM {tabla}")
                except sqlite3.OperationalError:
                    pass

            # Resetear secuencias autoincrementales
            if conservar_clientes:
                conn.execute("DELETE FROM sqlite_sequence WHERE name != 'clientes'")
            else:
                conn.execute("DELETE FROM sqlite_sequence")

            conn.commit()
            conn.execute("VACUUM")

    # 4. Limpiar archivos adjuntos de pedidos
    carpeta_archivos = data_dir / "pedidos_archivos"
    if carpeta_archivos.exists():
        for f in carpeta_archivos.glob("*"):
            if f.is_file():
                try:
                    f.unlink()
                except Exception:
                    pass

    # 5. Usuarios: limpiar sesiones e intentos fallidos, conservando las cuentas
    db_usuarios = data_dir / "usuarios.sqlite3"
    total_usuarios = 0
    if db_usuarios.exists():
        with closing(sqlite3.connect(db_usuarios)) as conn:
            conn.execute("PRAGMA foreign_keys = OFF")
            conn.execute("BEGIN IMMEDIATE")
            total_usuarios = conn.execute("SELECT count(*) FROM users").fetchone()[0]
            for tabla in ("login_attempts", "api_sessions"):
                try:
                    conn.execute(f"DELETE FROM {tabla}")
                except sqlite3.OperationalError:
                    pass
            conn.commit()
            conn.execute("VACUUM")
        notify_session_revocation("all")

    # 6. Resetear stock a 0 en Productos.xlsx
    if ruta_excel.exists():
        try:
            with closing(openpyxl.load_workbook(str(ruta_excel))) as wb:
                ws = wb.active
                info = detectar_esquema(ws)
                col_stock = info.get("col_stock", 3)
                col_stock_final = info.get("col_stock_final")
                col_descuento = info.get("col_descuento")
                fila_inicio = info.get("fila_inicio_datos", 4)

                for fila in range(fila_inicio, ws.max_row + 1):
                    val_cod = ws.cell(fila, info.get("col_codigo", 1)).value
                    val_nom = ws.cell(fila, info.get("col_nombre", 2)).value
                    if val_cod is not None or (val_nom and str(val_nom).strip()):
                        ws.cell(fila, col_stock, 0)
                        if col_stock_final is not None:
                            ws.cell(fila, col_stock_final, 0)
                        if col_descuento is not None:
                            ws.cell(fila, col_descuento, None)

                wb.save(ruta_excel)
        except Exception as exc_excel:
            print(f"[WARN] No se pudo resetear Productos.xlsx: {exc_excel}")

    # 7. Limpiar comprobantes procesados en Descuentos/
    for sub in ("descuentos", "descontados"):
        c = desc_dir / sub
        if c.exists():
            for f in c.glob("*"):
                if f.is_file():
                    try:
                        f.unlink()
                    except Exception:
                        pass

    return {
        "status": "ok",
        "backup_path": str(ruta_backup) if ruta_backup else None,
        "productos_conservados": total_productos,
        "clientes_conservados": total_clientes,
        "usuarios_conservados": total_usuarios,
        "stock_nuevo": 0,
        "pedidos_restantes": 0,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
