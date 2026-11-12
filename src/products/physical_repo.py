"""Repositorio mixin para el inventario físico y reconciliación de stock."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from typing import Callable


class PhysicalRepositoryMixin:
    """Mixin que encapsula el registro de conteos físicos, comparativas y discrepancias."""

    _connect: Callable[[], sqlite3.Connection]

    def record_physical_inventory(
        self,
        usuario: str,
        nombre_archivo: str,
        reporte_unificado: str,
        detalles: list[tuple[str, str, int, int, int, str]],
    ) -> int:
        """Registra un relevamiento de stock físico, actualiza products.stock_fisico
        y guarda la comparativa detallada.

        Cada tupla de `detalles` es:
            (product_code, product_name, stock_digital, stock_fisico, diferencia, estado)
        Retorna el id del inventario insertado.
        """
        total_relevados = len(detalles)
        total_diferencias = sum(1 for _, _, _, _, dif, _ in detalles if dif != 0)
        with closing(self._connect()) as connection, connection:
            cursor = connection.execute(
                """
                INSERT INTO inventario_fisico (
                    usuario, nombre_archivo, reporte_unificado, total_relevados, total_diferencias
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (usuario, nombre_archivo, reporte_unificado, total_relevados, total_diferencias),
            )
            inventario_id = int(cursor.lastrowid or 0)
            if detalles:
                connection.executemany(
                    "UPDATE products SET stock_fisico = ? WHERE code = ?",
                    [(stk_fis, cod) for cod, _, _, stk_fis, _, _ in detalles],
                )
                connection.executemany(
                    """
                    INSERT INTO inventario_fisico_detalles (
                        inventario_id, product_code, product_name,
                        stock_digital, stock_fisico, diferencia, estado
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (inventario_id, cod, nom, stk_dig, stk_fis, dif, estado)
                        for cod, nom, stk_dig, stk_fis, dif, estado in detalles
                    ],
                )
            return inventario_id

    def list_physical_inventories(self, limit: int = 20) -> list[sqlite3.Row]:
        with closing(self._connect()) as connection:
            return connection.execute(
                """
                SELECT id, fecha, usuario, nombre_archivo, reporte_unificado,
                       total_relevados, total_diferencias
                FROM inventario_fisico
                ORDER BY id DESC
                LIMIT ?
                """,
                (int(limit),),
            ).fetchall()

    def get_physical_inventory_details(self, inventario_id: int) -> list[sqlite3.Row]:
        with closing(self._connect()) as connection:
            return connection.execute(
                """
                SELECT id, inventario_id, product_code, product_name,
                       stock_digital, stock_fisico, diferencia, estado
                FROM inventario_fisico_detalles
                WHERE inventario_id = ?
                ORDER BY ABS(diferencia) DESC, product_code ASC
                """,
                (int(inventario_id),),
            ).fetchall()

    def get_latest_physical_inventory(
        self,
    ) -> tuple[sqlite3.Row | None, list[sqlite3.Row]]:
        with closing(self._connect()) as connection:
            cabecera = connection.execute(
                """
                SELECT id, fecha, usuario, nombre_archivo, reporte_unificado,
                       total_relevados, total_diferencias
                FROM inventario_fisico
                ORDER BY id DESC
                LIMIT 1
                """
            ).fetchone()
            if cabecera is None:
                return None, []
            detalles = connection.execute(
                """
                SELECT id, inventario_id, product_code, product_name,
                       stock_digital, stock_fisico, diferencia, estado
                FROM inventario_fisico_detalles
                WHERE inventario_id = ?
                ORDER BY ABS(diferencia) DESC, product_code ASC
                """,
                (int(cabecera["id"]),),
            ).fetchall()
            return cabecera, detalles
