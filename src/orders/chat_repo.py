"""Repositorio de mensajes y notificaciones del chat interno de equipo."""

from __future__ import annotations

from typing import Any

from .models import MensajeChat
from .protocols import LookupOrderFn, OrderConnectFn


class ChatRepository:
    """Repositorio que proporciona operaciones para el chat colaborativo en tiempo real."""

    def __init__(
        self,
        connect_fn: OrderConnectFn,
        lookup_order_fn: LookupOrderFn,
    ) -> None:
        self._connect = connect_fn
        self._lookup_order = lookup_order_fn

    def obtener_pedido_resumen_chat(self, nota_pedido: str) -> str:
        """Resumen de una línea de un pedido, para enlazarlo desde el chat de equipo."""
        pedido = self._lookup_order(nota_pedido)
        if pedido is None:
            return ""
        return (
            f"Pedido #{pedido.nota_pedido} · {pedido.cliente} · {pedido.bultos} bulto(s) · "
            f"{pedido.logistica} · {pedido.estado_despacho.upper()}"
            + (" · ANULADO" if pedido.estado == "anulado" else "")
        )

    def enviar_mensaje_chat(
        self,
        emisor: str,
        mensaje: str,
        destinatario: str = "Todos",
    ) -> MensajeChat:
        """Persiste y despacha un nuevo mensaje de chat entre terminales."""
        msg_limpio = mensaje.strip()
        if not msg_limpio:
            raise ValueError("El mensaje no puede estar vacío.")
        dest_limpio = (destinatario or "Todos").strip()
        with self._connect() as connection, connection:
            cursor = connection.execute(
                """
                INSERT INTO mensajes_chat (emisor, destinatario, mensaje, leido)
                VALUES (?, ?, ?, 0)
                """,
                (emisor.strip(), dest_limpio, msg_limpio),
            )
            nuevo_id = int(cursor.lastrowid)
            row = connection.execute(
                "SELECT id, emisor, destinatario, mensaje, leido, created_at FROM mensajes_chat WHERE id = ?",
                (nuevo_id,),
            ).fetchone()
            return MensajeChat.from_row(row)

    def listar_mensajes_chat(
        self,
        usuario: str,
        limite: int = 60,
    ) -> list[MensajeChat]:
        """Obtiene los últimos mensajes públicos o dirigidos a un usuario específico."""
        usr_limpio = usuario.strip()
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, emisor, destinatario, mensaje, leido, created_at
                FROM mensajes_chat
                WHERE destinatario = 'Todos' OR destinatario = ? OR emisor = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (usr_limpio, usr_limpio, limite),
            ).fetchall()
            mensajes = [MensajeChat.from_row(r) for r in rows]
            mensajes.reverse()
            return mensajes

    def contar_mensajes_no_leidos(self, usuario: str) -> int:
        """Cuenta la cantidad de mensajes no leídos para un usuario."""
        usr_limpio = usuario.strip()
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT COUNT(*) as total
                FROM mensajes_chat
                WHERE (destinatario = 'Todos' OR destinatario = ?)
                  AND leido = 0
                  AND emisor != ?
                """,
                (usr_limpio, usr_limpio),
            ).fetchone()
            return int(row["total"]) if row else 0

    def marcar_mensajes_leidos(self, usuario: str) -> None:
        """Marca como leídos todos los mensajes dirigidos a un usuario o a Todos."""
        usr_limpio = usuario.strip()
        with self._connect() as connection, connection:
            connection.execute(
                """
                UPDATE mensajes_chat
                SET leido = 1
                WHERE (destinatario = 'Todos' OR destinatario = ?)
                  AND leido = 0
                  AND emisor != ?
                """,
                (usr_limpio, usr_limpio),
            )
