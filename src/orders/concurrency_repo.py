"""Control de concurrencia optimista, soft-locking de pedidos e idempotencia."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
import sqlite3


class ConcurrencyRepositoryMixin:
    """Mixin para gestión de bloqueos temporales de edición y transacciones idempotentes."""

    def adquirir_bloqueo_pedido(
        self, pedido_id: int, usuario: str, expiracion_minutos: int = 5
    ) -> tuple[bool, str, str]:
        """Intenta adquirir el bloqueo de edición de un pedido.
        
        Devuelve (éxito, usuario_bloqueo, fecha_bloqueo).
        Si el bloqueo expiró (más de expiracion_minutos), se sobreescribe automáticamente.
        """
        limite = (datetime.now() - timedelta(minutes=expiracion_minutos)).isoformat()
        with self._connect() as connection, connection:
            # Limpiar bloqueos expirados
            connection.execute(
                "DELETE FROM pedidos_bloqueos WHERE bloqueado_at < ?", (limite,)
            )
            # Consultar bloqueo existente
            row = connection.execute(
                "SELECT usuario, bloqueado_at FROM pedidos_bloqueos WHERE pedido_id = ?",
                (pedido_id,),
            ).fetchone()
            if row is not None:
                usr_act = str(row["usuario"] or "")
                if usr_act.lower() != usuario.lower():
                    return False, usr_act, str(row["bloqueado_at"] or "")

            # Adquirir o renovar bloqueo
            ahora = datetime.now().isoformat()
            connection.execute(
                """
                INSERT INTO pedidos_bloqueos (pedido_id, usuario, bloqueado_at)
                VALUES (?, ?, ?)
                ON CONFLICT(pedido_id) DO UPDATE SET
                    usuario = excluded.usuario,
                    bloqueado_at = excluded.bloqueado_at
                """,
                (pedido_id, usuario, ahora),
            )
            return True, usuario, ahora

    def liberar_bloqueo_pedido(self, pedido_id: int, usuario: str | None = None) -> None:
        """Libera el bloqueo de un pedido. Si se especifica usuario, solo libera si coincide."""
        with self._connect() as connection, connection:
            if usuario:
                connection.execute(
                    "DELETE FROM pedidos_bloqueos WHERE pedido_id = ? AND LOWER(usuario) = LOWER(?)",
                    (pedido_id, usuario.strip()),
                )
            else:
                connection.execute(
                    "DELETE FROM pedidos_bloqueos WHERE pedido_id = ?",
                    (pedido_id,),
                )

    def consultar_bloqueo_pedido(
        self, pedido_id: int, expiracion_minutos: int = 5
    ) -> tuple[str, str] | None:
        """Verifica si un pedido está bloqueado actualmente por otro usuario."""
        limite = (datetime.now() - timedelta(minutes=expiracion_minutos)).isoformat()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT usuario, bloqueado_at FROM pedidos_bloqueos WHERE pedido_id = ? AND bloqueado_at >= ?",
                (pedido_id, limite),
            ).fetchone()
            if row is not None:
                return str(row["usuario"] or ""), str(row["bloqueado_at"] or "")
            return None

    def registrar_transaccion_idempotente(self, tx_id: str, accion: str, detalle: str = "") -> bool:
        """Registra una transacción por UUID. Devuelve True si es nueva, o False si ya fue procesada."""
        if not tx_id:
            return True
        with self._connect() as connection, connection:
            limite = (datetime.now() - timedelta(hours=1)).isoformat()
            connection.execute(
                "DELETE FROM transacciones_procesadas WHERE created_at < ?", (limite,)
            )
            try:
                connection.execute(
                    "INSERT INTO transacciones_procesadas (tx_id, accion, detalle) VALUES (?, ?, ?)",
                    (tx_id, accion, detalle),
                )
                return True
            except sqlite3.IntegrityError:
                return False
