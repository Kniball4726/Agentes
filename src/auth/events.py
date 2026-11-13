"""Hooks de eventos internos para sincronizar revocaciones de sesiones API."""

from __future__ import annotations

from typing import Callable

_session_revocation_listeners: list[Callable[[str, int | None, str | None], None]] = []


def register_session_revocation_listener(
    callback: Callable[[str, int | None, str | None], None],
) -> None:
    """Registra un hook para invalidar cachés en memoria al revocar sesiones o desactivar usuarios."""
    if callback not in _session_revocation_listeners:
        _session_revocation_listeners.append(callback)


def notify_session_revocation(
    event: str, *, user_id: int | None = None, token_hash: str | None = None
) -> None:
    """Notifica a los listeners registrados sobre revocaciones de tokens o usuarios."""
    for listener in list(_session_revocation_listeners):
        try:
            listener(event, user_id, token_hash)
        except Exception:
            pass
