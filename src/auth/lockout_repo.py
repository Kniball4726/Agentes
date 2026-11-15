"""Repositorio desacoplado para control de intentos fallidos y bloqueo temporal anti fuerza bruta."""

from __future__ import annotations

import sqlite3
import time
from contextlib import AbstractContextManager
from typing import Callable

from .models import (
    FAILED_WINDOW_SECONDS,
    LOCKOUT_SECONDS,
    MAX_FAILED_ATTEMPTS,
    AuthResult,
)


class LockoutRepository:
    """Gestiona bloqueos temporales por intentos fallidos en `login_attempts`."""

    def __init__(self, connect_fn: Callable[[], AbstractContextManager[sqlite3.Connection]]) -> None:
        self._connect = connect_fn

    def segundos_bloqueo_restantes(
        self, username: str, ahora: float | None = None
    ) -> int:
        ahora = time.time() if ahora is None else ahora
        with self._connect() as connection:
            row = connection.execute(
                "SELECT locked_until FROM login_attempts WHERE username = ?",
                (username.strip(),),
            ).fetchone()
        if row is None or row["locked_until"] <= ahora:
            return 0
        return int(row["locked_until"] - ahora) + 1

    def registrar_fallo(self, username: str, ahora: float) -> AuthResult:
        if not username:
            return AuthResult(None, "invalid")
        with self._connect() as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT failed_count, first_failed_at FROM login_attempts WHERE username = ?",
                (username,),
            ).fetchone()
            if row is None or ahora - row["first_failed_at"] > FAILED_WINDOW_SECONDS:
                cantidad, primero = 1, ahora
            else:
                cantidad, primero = row["failed_count"] + 1, row["first_failed_at"]
            if cantidad >= MAX_FAILED_ATTEMPTS:
                connection.execute(
                    """
                    INSERT INTO login_attempts (username, failed_count, first_failed_at, locked_until)
                    VALUES (?, 0, 0, ?)
                    ON CONFLICT(username) DO UPDATE SET
                        failed_count = 0, first_failed_at = 0, locked_until = excluded.locked_until
                    """,
                    (username, ahora + LOCKOUT_SECONDS),
                )
                try:
                    from ..integrations.telegram_notifier import notificar_seguridad_bloqueo_telegram

                    notificar_seguridad_bloqueo_telegram(username, retry_after_minutos=15)
                except Exception:
                    pass
                return AuthResult(None, "locked", retry_after=LOCKOUT_SECONDS)
            connection.execute(
                """
                INSERT INTO login_attempts (username, failed_count, first_failed_at, locked_until)
                VALUES (?, ?, ?, 0)
                ON CONFLICT(username) DO UPDATE SET
                    failed_count = excluded.failed_count,
                    first_failed_at = excluded.first_failed_at
                """,
                (username, cantidad, primero),
            )
        return AuthResult(None, "invalid", attempts_left=MAX_FAILED_ATTEMPTS - cantidad)

    def limpiar_intentos(self, username: str) -> None:
        with self._connect() as connection, connection:
            connection.execute(
                "DELETE FROM login_attempts WHERE username = ?", (username,)
            )

    def unlock_user(self, username: str) -> None:
        """Desbloquea manualmente una cuenta (acción de administración)."""
        self.limpiar_intentos(username.strip())

    def list_locked_usernames(self) -> list[str]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT username FROM login_attempts WHERE locked_until > ?",
                (time.time(),),
            ).fetchall()
        return [r["username"] for r in rows]
