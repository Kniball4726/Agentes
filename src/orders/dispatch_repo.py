"""Repositorio desacoplado para máquina de estados de despacho y seguimiento por código/remito."""

from __future__ import annotations

import re
import sqlite3
from typing import Any

from ..core.exceptions import OrderStoreError
from .models import ESTADOS_DESPACHO, _COLUMNAS_DESPACHO, Pedido
from .protocols import AuditLogFn, MapPedidoFn, OrderConnectFn

_COLUMNAS_SELECT_PEDIDO = (
    "id, nota_pedido, numero_pedido, cliente, bultos, logistica, armador, "
    "tipo_archivo, nombre_archivo, agregado, articulos_descontados, "
    "resumen_items, created_at, estado, fecha_retiro, archivo_descuento, "
    f"cierre_id, cierre_mercado_id, archivo_hash, canal, {_COLUMNAS_DESPACHO}"
)


class DispatchRepository:
    """Repositorio que gestiona transiciones de estado de despacho (`armado` -> `despachado` -> `entregado`)."""

    def __init__(
        self,
        connect_fn: OrderConnectFn,
        map_pedido_fn: MapPedidoFn,
        audit_fn: AuditLogFn,
    ) -> None:
        self._connect = connect_fn
        self._map_pedido = map_pedido_fn
        self._audit = audit_fn

    @staticmethod
    def extraer_remito_de_codigo(texto: str) -> str:
        """Extrae el número de remito de un payload QR o texto escaneado."""
        limpio = (texto or "").strip()
        coincidencia = re.search(r"REMITO:\s*([^|]+)", limpio, re.IGNORECASE)
        return coincidencia.group(1).strip() if coincidencia else limpio

    def buscar_pedido_por_nota(self, nota_pedido: str) -> Pedido | None:
        """Busca un pedido por su nota/remito sin distinguir mayúsculas."""
        nota = (nota_pedido or "").strip()
        if not nota:
            return None
        with self._connect() as connection:
            row = connection.execute(
                f"SELECT {_COLUMNAS_SELECT_PEDIDO} FROM pedidos WHERE nota_pedido = ? COLLATE NOCASE LIMIT 1",
                (nota,),
            ).fetchone()
        return self._map_pedido(row) if row is not None else None

    def actualizar_estado_despacho(
        self,
        pedido_id: int,
        nuevo_estado: str,
        usuario: str = "Sistema",
        permitir_retroceso: bool = False,
    ) -> Pedido:
        """Valida y actualiza el estado de despacho de un pedido con registro de auditoría."""
        if nuevo_estado not in ESTADOS_DESPACHO:
            raise ValueError(f"Estado de despacho inválido: {nuevo_estado}")

        with self._connect() as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT nota_pedido, estado, estado_despacho FROM pedidos WHERE id = ?",
                (pedido_id,),
            ).fetchone()
            if row is None:
                raise OrderStoreError("No se encontró el pedido.")
            if row["estado"] == "anulado":
                raise OrderStoreError("El pedido está anulado y no admite cambios de estado.")

            actual = row["estado_despacho"] or "armado"
            idx_actual = ESTADOS_DESPACHO.index(actual)
            idx_nuevo = ESTADOS_DESPACHO.index(nuevo_estado)
            if idx_nuevo == idx_actual:
                raise OrderStoreError(f"El pedido ya figura como '{actual}'.")
            if idx_nuevo < idx_actual and not permitir_retroceso:
                raise OrderStoreError("Solo un administrador puede retroceder el estado de un pedido.")
            if idx_nuevo > idx_actual + 1:
                raise OrderStoreError(
                    f"Primero debe marcarse como '{ESTADOS_DESPACHO[idx_actual + 1]}'."
                )

            ahora = "strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime')"
            if nuevo_estado == "despachado":
                connection.execute(
                    f"UPDATE pedidos SET estado_despacho = ?, despachado_at = {ahora}, despachado_por = ?, "
                    "entregado_at = '', entregado_por = '' WHERE id = ?",
                    (nuevo_estado, usuario, pedido_id),
                )
            elif nuevo_estado == "entregado":
                connection.execute(
                    f"UPDATE pedidos SET estado_despacho = ?, entregado_at = {ahora}, entregado_por = ? WHERE id = ?",
                    (nuevo_estado, usuario, pedido_id),
                )
            else:
                connection.execute(
                    "UPDATE pedidos SET estado_despacho = ?, despachado_at = '', despachado_por = '', "
                    "entregado_at = '', entregado_por = '' WHERE id = ?",
                    (nuevo_estado, pedido_id),
                )
            remito = row["nota_pedido"]

        self._audit(
            usuario=usuario,
            accion="ESTADO_DESPACHO",
            detalle=f"Remito {remito}: {actual} → {nuevo_estado}",
        )
        with self._connect() as connection:
            fila = connection.execute(
                f"SELECT {_COLUMNAS_SELECT_PEDIDO} FROM pedidos WHERE id = ?",
                (pedido_id,),
            ).fetchone()
        return self._map_pedido(fila)

    def avanzar_estado_lote(
        self,
        pedido_ids: list[int],
        nuevo_estado: str,
        usuario: str = "Operador",
    ) -> int:
        """Actualiza por lote el estado de despacho de múltiples pedidos válidos."""
        if not pedido_ids:
            return 0
        nuevo = nuevo_estado.strip().lower()
        if nuevo not in ESTADOS_DESPACHO:
            raise OrderStoreError(f"Estado de despacho inválido: '{nuevo_estado}'")
        actualizados = 0
        for pid in pedido_ids:
            try:
                self.actualizar_estado_despacho(pid, nuevo, usuario=usuario, permitir_retroceso=True)
                actualizados += 1
            except Exception:
                continue
        return actualizados

    def avanzar_estado_por_codigo(
        self,
        codigo: str = "",
        usuario: str = "Sistema",
        *,
        codigo_qr_o_remito: str = "",
        nuevo_estado: str | None = None,
    ) -> tuple[bool, str, Pedido | None]:
        """Avanza el estado de un pedido buscado por texto QR o número de remito."""
        raw = codigo or codigo_qr_o_remito
        remito = self.extraer_remito_de_codigo(raw)
        pedido = self.buscar_pedido_por_nota(remito)
        if pedido is None:
            return False, f"No se encontró ningún pedido con el remito '{remito}'.", None
        if pedido.estado == "anulado":
            return False, f"El pedido {pedido.nota_pedido} se encuentra ANULADO.", pedido
        if nuevo_estado:
            destino = nuevo_estado.strip().lower()
        else:
            idx = ESTADOS_DESPACHO.index(pedido.estado_despacho)
            if idx >= len(ESTADOS_DESPACHO) - 1:
                return False, f"El pedido {pedido.nota_pedido} ya figura como ENTREGADO.", pedido
            destino = ESTADOS_DESPACHO[idx + 1]
        try:
            actualizado = self.actualizar_estado_despacho(
                pedido.id, destino, usuario=usuario, permitir_retroceso=True
            )
            return (
                True,
                f"Remito #{actualizado.nota_pedido} ({actualizado.cliente}) → {actualizado.estado_despacho.upper()}",
                actualizado,
            )
        except Exception as e:
            return False, str(e), pedido
