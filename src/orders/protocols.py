"""Contratos estructurales (Protocols) para composición de repositorios de pedidos."""

from __future__ import annotations

import sqlite3
from contextlib import AbstractContextManager
from typing import Any, Callable, Protocol, runtime_checkable

from .models import Pedido

OrderConnectFn = Callable[[], AbstractContextManager[sqlite3.Connection]]
MapPedidoFn = Callable[[sqlite3.Row], Pedido]
AuditLogFn = Callable[..., Any]
LookupOrderFn = Callable[[str], Pedido | None]


@runtime_checkable
class OrderAuditableProtocol(Protocol):
    """Contrato mínimo para registrar eventos de auditoría en pedidos."""

    def registrar_auditoria(self, usuario: str, accion: str, detalle: str) -> None: ...
