"""Repositorio desacoplado para el registro y consulta de movimientos de stock y despachos."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from typing import Callable, Iterable


class MovementsRepository:
    """Encapsula el historial de movimientos de inventario y trazabilidad de despachos."""

    def __init__(self, connect_fn: Callable[[], sqlite3.Connection]) -> None:
        self._connect = connect_fn

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
        """Registra o enriquece movimientos de stock en el historial sin duplicar filas del trigger.

        Cada elemento de `movements` es (product_code, product_name, quantity, movement_type).
        movement_type: 'descuento' | 'ingreso_fabrica' | 'ingreso_rapido' | 'salida_rapida' | 'ajuste_manual'
        quantity: positivo para ingresos, negativo para descuentos.
        """
        if not movements:
            return
        usuario_limpio = (usuario or "sistema").strip() or "sistema"
        detalle_limpio = (detalle or "").strip()
        with closing(self._connect()) as connection, connection:
            por_insertar: list[tuple[str, str, int, str, str, str]] = []
            for cod, nom, qty, mtype in movements:
                qty_int = int(qty)
                # Si trg_auditoria_stock acaba de insertar esta misma variación sin enriquecer,
                # actualizamos esa fila en lugar de duplicar el conteo en stock_movements.
                row_trig = connection.execute(
                    """
                    SELECT id
                    FROM stock_movements
                    WHERE product_code = ?
                      AND quantity = ?
                      AND usuario = 'sistema'
                      AND detalle = ''
                      AND registered_at >= strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime', '-15 seconds')
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (cod, qty_int),
                ).fetchone()
                if row_trig is not None:
                    connection.execute(
                        """
                        UPDATE stock_movements
                        SET usuario = ?, detalle = ?, movement_type = ?,
                            product_name = COALESCE(NULLIF(?, ''), product_name)
                        WHERE id = ?
                        """,
                        (usuario_limpio, detalle_limpio, mtype, nom, int(row_trig["id"])),
                    )
                else:
                    por_insertar.append((cod, nom, qty_int, mtype, usuario_limpio, detalle_limpio))

            if por_insertar:
                connection.executemany(
                    """
                    INSERT INTO stock_movements (product_code, product_name, quantity, movement_type, usuario, detalle)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    por_insertar,
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
        params: list = [date_from, date_to]
        if movement_type:
            m_clean = str(movement_type).strip().lower()
            if m_clean in ("descuento", "salida", "salidas"):
                tipo_filtro = "AND (m.movement_type IN ('descuento', 'salida_rapida') OR m.quantity < 0)"
            elif m_clean in ("ingreso_fabrica", "ingreso", "ingresos"):
                tipo_filtro = "AND (m.movement_type IN ('ingreso_fabrica', 'ingreso_rapido') OR m.quantity > 0)"
            else:
                tipo_filtro = "AND m.movement_type = ?"
                params.append(movement_type)
        else:
            tipo_filtro = ""

        if top_n:
            limit = f"LIMIT {int(top_n)}"
        else:
            limit = ""
        with closing(self._connect()) as connection:
            return connection.execute(
                f"""
                SELECT
                    m.product_code AS product_code,
                    COALESCE(NULLIF(m.product_name, ''), p.name, m.product_code) AS product_name,
                    SUM(ABS(m.quantity)) AS total_quantity
                FROM stock_movements m
                LEFT JOIN products p ON p.code = m.product_code
                WHERE m.registered_at >= ?
                  AND m.registered_at <= ?
                  {tipo_filtro}
                GROUP BY m.product_code
                ORDER BY total_quantity DESC
                {limit}
                """,
                params,
            ).fetchall()
