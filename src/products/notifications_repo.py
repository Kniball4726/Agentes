"""Repositorio desacoplado para notificaciones de administración y alertas de reposición."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from typing import Callable


class NotificationsRepository:
    """Encapsula el centro de notificaciones administrativas y análisis de reposición."""

    def __init__(self, connect_fn: Callable[[], sqlite3.Connection]) -> None:
        self._connect = connect_fn

    def get_replenishment_analysis(
        self, only_critical: bool = True
    ) -> list[sqlite3.Row]:
        """Consulta la vista v_analisis_reposicion.

        Si only_critical es True, devuelve solo productos en QUIEBRE_INMINENTE o AGOTADO.
        """
        filtro = (
            "WHERE estado_inventario IN ('AGOTADO', 'QUIEBRE_INMINENTE')"
            if only_critical
            else ""
        )
        with closing(self._connect()) as connection:
            return connection.execute(
                f"""
                SELECT
                    code,
                    name,
                    stock,
                    stock_minimo,
                    stock_maximo,
                    estado_inventario,
                    cantidad_sugerida_pedir
                FROM v_analisis_reposicion
                {filtro}
                ORDER BY
                    CASE estado_inventario
                        WHEN 'AGOTADO' THEN 1
                        WHEN 'QUIEBRE_INMINENTE' THEN 2
                        WHEN 'SOBRESTOCK' THEN 3
                        ELSE 4
                    END,
                    stock ASC
                """
            ).fetchall()

    def create_admin_notification(
        self,
        title: str,
        message: str,
        operator_username: str,
        notification_type: str = "descuento",
        details: str = "",
    ) -> int:
        with closing(self._connect()) as connection, connection:
            cursor = connection.execute(
                """
                INSERT INTO admin_notifications (title, message, operator_username, notification_type, details)
                VALUES (?, ?, ?, ?, ?)
                """,
                (title, message, operator_username, notification_type, details),
            )
            return int(cursor.lastrowid or 0)

    def list_admin_notifications(
        self, unread_only: bool = False, limit: int = 50
    ) -> list[sqlite3.Row]:
        query = """
            SELECT id, title, message, operator_username, notification_type, details, created_at, is_read
            FROM admin_notifications
        """
        params: list = []
        if unread_only:
            query += " WHERE is_read = 0"
        query += " ORDER BY id DESC LIMIT ?"
        params.append(int(limit))
        with closing(self._connect()) as connection:
            return connection.execute(query, params).fetchall()

    def get_unread_notifications_count(self) -> int:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT COUNT(*) as count FROM admin_notifications WHERE is_read = 0"
            ).fetchone()
            return int(row["count"]) if row else 0

    def mark_notification_as_read(self, notification_id: int) -> None:
        with closing(self._connect()) as connection, connection:
            connection.execute(
                "UPDATE admin_notifications SET is_read = 1 WHERE id = ?",
                (notification_id,),
            )

    def mark_all_notifications_as_read(self) -> int:
        with closing(self._connect()) as connection, connection:
            cursor = connection.execute(
                "UPDATE admin_notifications SET is_read = 1 WHERE is_read = 0"
            )
            return cursor.rowcount
