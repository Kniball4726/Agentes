"""Repositorio mixin para el registro y consulta de movimientos de stock y despachos."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from typing import Callable, Iterable


class MovementsRepositoryMixin:
    """Mixin que encapsula el historial de movimientos de inventario y trazabilidad de despachos."""

    _connect: Callable[[], sqlite3.Connection]

    def record_dispatch(
        self,
        tipo_origen: str,
        nombre_archivo: str,
        total_articulos: int,
        detalles: list[tuple[str, int, int, int]],
        reporte_archivo: str = "",
        usuario: str = "sistema",
    ) -> int:
        """Registra un lote de descuento en despachos y despacho_detalles.

        detalles: lista de (product_code, cantidad_descontada, stock_anterior, stock_nuevo).
        Retorna el id del despacho insertado.
        """
        with closing(self._connect()) as connection, connection:
            cursor = connection.execute(
                """
                INSERT INTO despachos (tipo_origen, nombre_archivo, total_articulos, reporte_archivo, usuario)
                VALUES (?, ?, ?, ?, ?)
                """,
                (tipo_origen, nombre_archivo, total_articulos, reporte_archivo, usuario),
            )
            despacho_id = cursor.lastrowid
            if detalles and despacho_id is not None:
                connection.executemany(
                    """
                    INSERT INTO despacho_detalles (
                        despacho_id, product_code, cantidad_descontada, stock_anterior, stock_nuevo
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    [
                        (despacho_id, cod, cant, ant, nvo)
                        for cod, cant, ant, nvo in detalles
                    ],
                )
                detalle_txt = f"{tipo_origen}: {nombre_archivo}"[:120]
                for cod, _, _, _ in detalles:
                    connection.execute(
                        """
                        UPDATE stock_movements
                        SET usuario = ?, detalle = ?
                        WHERE id = (
                            SELECT id FROM stock_movements
                            WHERE product_code = ?
                            ORDER BY id DESC LIMIT 1
                        ) AND (usuario = 'sistema' OR detalle = '')
                        """,
                        (usuario or "sistema", detalle_txt, cod),
                    )
            return despacho_id or 0

    def register_movements(
        self,
        movements: list[tuple[str, str, int, str]],
        usuario: str = "sistema",
        detalle: str = "",
    ) -> None:
        """Registra movimientos de stock en el historial.

        Cada elemento de `movements` es (product_code, product_name, quantity, movement_type).
        movement_type: 'descuento' | 'ingreso_fabrica' | 'ajuste_manual'
        quantity: positivo para ingresos, negativo para descuentos.
        """
        if not movements:
            return
        with closing(self._connect()) as connection, connection:
            connection.executemany(
                """
                INSERT INTO stock_movements (product_code, product_name, quantity, movement_type, usuario, detalle)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [(cod, nom, qty, mtype, usuario, detalle) for cod, nom, qty, mtype in movements],
            )

    def enrich_latest_movements(
        self,
        product_codes: Iterable[str],
        usuario: str = "sistema",
        detalle: str = "",
        movement_type: str | None = None,
    ) -> None:
        """Asocia usuario y detalle al último movimiento registrado por el trigger para los códigos dados."""
        codigos = list(product_codes)
        if not codigos:
            return
        with closing(self._connect()) as connection, connection:
            for cod in codigos:
                if movement_type:
                    connection.execute(
                        """
                        UPDATE stock_movements
                        SET usuario = ?, detalle = ?, movement_type = ?
                        WHERE id = (
                            SELECT id FROM stock_movements
                            WHERE product_code = ?
                            ORDER BY id DESC LIMIT 1
                        ) AND (usuario = 'sistema' OR detalle = '')
                        """,
                        (usuario or "sistema", detalle, movement_type, cod),
                    )
                else:
                    connection.execute(
                        """
                        UPDATE stock_movements
                        SET usuario = ?, detalle = ?
                        WHERE id = (
                            SELECT id FROM stock_movements
                            WHERE product_code = ?
                            ORDER BY id DESC LIMIT 1
                        ) AND (usuario = 'sistema' OR detalle = '')
                        """,
                        (usuario or "sistema", detalle, cod),
                    )

    def list_recent_movements(
        self,
        product_code: str = "",
        movement_type: str = "",
        limit: int = 150,
    ) -> list[sqlite3.Row]:
        """Devuelve el historial detallado de movimientos de stock más recientes."""
        condiciones: list[str] = []
        params: list = []
        if product_code.strip():
            condiciones.append("(product_code LIKE ? OR product_name LIKE ?)")
            patron = f"%{product_code.strip()}%"
            params.extend([patron, patron])
        if movement_type.strip():
            condiciones.append("movement_type = ?")
            params.append(movement_type.strip())
        where_sql = f"WHERE {' AND '.join(condiciones)}" if condiciones else ""
        params.append(int(limit))
        with closing(self._connect()) as connection:
            return connection.execute(
                f"""
                SELECT
                    id,
                    product_code,
                    product_name,
                    quantity,
                    movement_type,
                    usuario,
                    detalle,
                    registered_at
                FROM stock_movements
                {where_sql}
                ORDER BY id DESC
                LIMIT ?
                """,
                params,
            ).fetchall()

    def query_movements(
        self,
        date_from: str,
        date_to: str,
        movement_type: str | None = None,
        top_n: int | None = None,
    ) -> list[sqlite3.Row]:
        """Consulta movimientos agrupados por producto en un rango de fechas.

        Retorna filas con (product_code, product_name, total_quantity) ordenadas
        por total_quantity descendente.
        movement_type: filtrar por tipo ('descuento', 'ingreso_fabrica', 'ajuste_manual').
        Si None, incluye todos.
        """
        tipo_filtro = "AND movement_type = ?" if movement_type else ""
        params: list = [date_from, date_to]
        if movement_type:
            params.append(movement_type)
        if top_n:
            limit = f"LIMIT {int(top_n)}"
        else:
            limit = ""
        with closing(self._connect()) as connection:
            return connection.execute(
                f"""
                SELECT
                    product_code,
                    product_name,
                    SUM(ABS(quantity)) AS total_quantity
                FROM stock_movements
                WHERE registered_at >= ?
                  AND registered_at <= ?
                  {tipo_filtro}
                GROUP BY product_code, product_name
                ORDER BY total_quantity DESC
                {limit}
                """,
                params,
            ).fetchall()
