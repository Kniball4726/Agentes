"""Repositorio transaccional de reservas de stock frente al saldo disponible."""

from __future__ import annotations

from contextlib import closing
import json
import sqlite3
from typing import Any, Callable

from ..core.exceptions import InsufficientStockError, ProductNotFoundError
from .locations_lots_repo import (
    consumir_lotes_fefo_en_tx,
    descontar_ubicaciones_en_tx,
    normalizar_ubicacion,
    planificar_lotes_fefo_en_tx,
)

VALID_RESERVATION_STATES: tuple[str, ...] = ("activa", "consolidada", "liberada")


def _deserializar_lotes(raw: object) -> list[dict[str, Any]]:
    texto = str(raw or "").strip()
    if not texto:
        return []
    try:
        parsed = json.loads(texto)
        return parsed if isinstance(parsed, list) else []
    except Exception:
        return []


class StockReservationsRepository:
    """Administra reservas previas al picking para evitar sobre-asignación concurrente."""

    def __init__(
        self,
        connect_fn: Callable[[], sqlite3.Connection],
        invalidate_cache_cb: Callable[[], None] | None = None,
    ) -> None:
        self._connect = connect_fn
        self._invalidar_cache = invalidate_cache_cb

    def _notificar_cambio_catalogo(self) -> None:
        if self._invalidar_cache is not None:
            self._invalidar_cache()

    @staticmethod
    def _map_reservation_row(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": int(row["id"]),
            "referencia_tipo": str(row["referencia_tipo"]),
            "referencia_id": str(row["referencia_id"]),
            "product_code": str(row["product_code"]),
            "cantidad": int(row["cantidad"]),
            "estado": str(row["estado"]),
            "lot_id": int(row["lot_id"]) if row["lot_id"] is not None else None,
            "ubicacion": str(row["ubicacion"] or ""),
            "lotes_asignados": _deserializar_lotes(row["lotes_asignados"]),
            "usuario": str(row["usuario"] or "sistema"),
            "nota": str(row["nota"] or ""),
            "created_at": str(row["created_at"] or ""),
            "updated_at": str(row["updated_at"] or ""),
            "expires_at": str(row["expires_at"] or ""),
        }

    def obtener_mapa_reservas_activas(
        self,
        codigos: list[str] | None = None,
    ) -> dict[str, int]:
        """Retorna `{product_code: cantidad_reservada}` sumando reservas en estado `'activa'`."""
        with closing(self._connect()) as connection:
            if codigos:
                codigos_norm = [str(c).strip() for c in codigos if str(c).strip()]
                if not codigos_norm:
                    return {}
                placeholders = ",".join("?" for _ in codigos_norm)
                rows = connection.execute(
                    f"""
                    SELECT product_code, COALESCE(SUM(cantidad), 0) AS reservado
                    FROM stock_reservations
                    WHERE estado = 'activa' AND product_code IN ({placeholders})
                    GROUP BY product_code
                    """,
                    tuple(codigos_norm),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT product_code, COALESCE(SUM(cantidad), 0) AS reservado
                    FROM stock_reservations
                    WHERE estado = 'activa'
                    GROUP BY product_code
                    """
                ).fetchall()
        return {str(r["product_code"]): int(r["reservado"]) for r in rows}

    def obtener_resumen_stock_disponible(self, code: str) -> dict[str, Any]:
        """Retorna stock físico actual, stock reservado activo y stock disponible neto de un SKU."""
        cod = str(code or "").strip()
        if not cod:
            raise ValueError("El código de producto no puede estar vacío.")
        with closing(self._connect()) as connection:
            prod = connection.execute(
                "SELECT code, name, stock, ubicacion, active FROM products WHERE code = ?",
                (cod,),
            ).fetchone()
            if prod is None:
                raise ProductNotFoundError(cod)
            res_row = connection.execute(
                """
                SELECT COALESCE(SUM(cantidad), 0) AS reservado
                FROM stock_reservations
                WHERE product_code = ? AND estado = 'activa'
                """,
                (cod,),
            ).fetchone()
        stock_actual = int(prod["stock"])
        reservado = int(res_row["reservado"]) if res_row is not None else 0
        disponible = max(0, stock_actual - reservado)
        return {
            "product_code": str(prod["code"]),
            "product_name": str(prod["name"] or ""),
            "stock_fisico": stock_actual,
            "stock_actual": stock_actual,
            "stock_reservado": reservado,
            "stock_disponible": disponible,
            "ubicacion": str(prod["ubicacion"] or ""),
            "active": bool(prod["active"]),
        }

    def listar_reservas(
        self,
        estado: str | None = "activa",
        referencia_tipo: str | None = None,
        referencia_id: str | None = None,
        product_code: str | None = None,
    ) -> list[dict[str, Any]]:
        """Lista reservas filtrando opcionalmente por estado, referencia o producto."""
        filtros: list[str] = []
        params: list[Any] = []
        if estado:
            estado_norm = str(estado).strip().lower()
            if estado_norm not in VALID_RESERVATION_STATES:
                raise ValueError(f"Estado de reserva inválido '{estado}'.")
            filtros.append("sr.estado = ?")
            params.append(estado_norm)
        if referencia_tipo:
            filtros.append("sr.referencia_tipo = ?")
            params.append(str(referencia_tipo).strip())
        if referencia_id:
            filtros.append("sr.referencia_id = ?")
            params.append(str(referencia_id).strip())
        if product_code:
            filtros.append("sr.product_code = ?")
            params.append(str(product_code).strip())

        where_sql = f"WHERE {' AND '.join(filtros)}" if filtros else ""
        with closing(self._connect()) as connection:
            rows = connection.execute(
                f"""
                SELECT sr.*, p.name AS product_name, p.stock AS stock_actual
                FROM stock_reservations sr
                INNER JOIN products p ON p.code = sr.product_code
                {where_sql}
                ORDER BY sr.created_at DESC, sr.id DESC
                """,
                tuple(params),
            ).fetchall()

        resultado: list[dict[str, Any]] = []
        for row in rows:
            item = self._map_reservation_row(row)
            item["product_name"] = str(row["product_name"] or "")
            item["stock_fisico"] = int(row["stock_actual"])
            resultado.append(item)
        return resultado

    def reservar_stock(
        self,
        items: list[tuple[str, int]] | dict[str, int],
        referencia_id: str,
        referencia_tipo: str = "ola_picking",
        usuario: str = "sistema",
        nota: str = "",
        asignar_fefo: bool = True,
        permitir_parcial: bool = False,
        expires_at: str = "",
    ) -> dict[str, Any]:
        """Reserva cantidades contra `stock_disponible` de manera atómica e idempotente.

        Si `permitir_parcial=False`, ante cualquier faltante revierte toda la transacción
        y lanza `InsufficientStockError`.
        """
        ref_id = str(referencia_id or "").strip()
        ref_tipo = str(referencia_tipo or "ola_picking").strip() or "ola_picking"
        if not ref_id:
            raise ValueError("El identificador de referencia para la reserva es obligatorio.")

        pares = list(items.items()) if isinstance(items, dict) else list(items)
        consolidados: dict[str, int] = {}
        for cod_raw, qty_raw in pares:
            cod = str(cod_raw or "").strip()
            qty = int(qty_raw)
            if not cod or qty <= 0:
                continue
            consolidados[cod] = consolidados.get(cod, 0) + qty

        if not consolidados:
            return {
                "referencia_tipo": ref_tipo,
                "referencia_id": ref_id,
                "reservas": [],
                "sin_stock": [],
                "total_unidades_reservadas": 0,
            }

        usuario_limpio = (usuario or "sistema").strip() or "sistema"
        nota_limpia = (nota or "").strip()
        reservas_guardadas: list[dict[str, Any]] = []
        sin_stock: list[dict[str, Any]] = []

        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            for cod, qty_solicitada in consolidados.items():
                prod = connection.execute(
                    "SELECT code, stock, ubicacion FROM products WHERE code = ?",
                    (cod,),
                ).fetchone()
                if prod is None:
                    raise ProductNotFoundError(cod)

                # Excluir la propia referencia si se re-reserva idempotentemente
                reservado_otros_row = connection.execute(
                    """
                    SELECT COALESCE(SUM(cantidad), 0) AS reservado
                    FROM stock_reservations
                    WHERE product_code = ?
                      AND estado = 'activa'
                      AND NOT (referencia_tipo = ? AND referencia_id = ?)
                    """,
                    (cod, ref_tipo, ref_id),
                ).fetchone()
                reservado_otros = int(reservado_otros_row["reservado"]) if reservado_otros_row else 0
                disponible = max(0, int(prod["stock"]) - reservado_otros)

                if disponible < qty_solicitada and not permitir_parcial:
                    raise InsufficientStockError(cod, qty_solicitada, disponible)

                qty_a_reservar = min(qty_solicitada, disponible)
                if qty_a_reservar <= 0:
                    sin_stock.append(
                        {
                            "product_code": cod,
                            "solicitado": qty_solicitada,
                            "disponible": disponible,
                        }
                    )
                    continue

                if qty_a_reservar < qty_solicitada:
                    sin_stock.append(
                        {
                            "product_code": cod,
                            "solicitado": qty_solicitada,
                            "reservado_parcial": qty_a_reservar,
                            "faltante": qty_solicitada - qty_a_reservar,
                        }
                    )

                lotes_asignados: list[dict[str, Any]] = []
                lot_id_principal: int | None = None
                ubic_reserva = normalizar_ubicacion(prod["ubicacion"])
                if asignar_fefo:
                    lotes_asignados, _ = planificar_lotes_fefo_en_tx(
                        connection, cod, qty_a_reservar
                    )
                    if lotes_asignados:
                        lot_id_principal = int(lotes_asignados[0]["lot_id"])
                        if lotes_asignados[0].get("ubicacion"):
                            ubic_reserva = normalizar_ubicacion(lotes_asignados[0]["ubicacion"])

                lotes_json = json.dumps(lotes_asignados, ensure_ascii=False)
                connection.execute(
                    """
                    INSERT INTO stock_reservations (
                        referencia_tipo, referencia_id, product_code, cantidad,
                        estado, lot_id, ubicacion, lotes_asignados, usuario, nota, expires_at
                    )
                    VALUES (?, ?, ?, ?, 'activa', ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(referencia_tipo, referencia_id, product_code) DO UPDATE SET
                        cantidad = excluded.cantidad,
                        estado = 'activa',
                        lot_id = excluded.lot_id,
                        ubicacion = excluded.ubicacion,
                        lotes_asignados = excluded.lotes_asignados,
                        usuario = excluded.usuario,
                        nota = excluded.nota,
                        expires_at = excluded.expires_at,
                        updated_at = strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime')
                    """,
                    (
                        ref_tipo,
                        ref_id,
                        cod,
                        qty_a_reservar,
                        lot_id_principal,
                        ubic_reserva,
                        lotes_json,
                        usuario_limpio,
                        nota_limpia,
                        str(expires_at or "").strip(),
                    ),
                )
                row_res = connection.execute(
                    """
                    SELECT *
                    FROM stock_reservations
                    WHERE referencia_tipo = ? AND referencia_id = ? AND product_code = ?
                    """,
                    (ref_tipo, ref_id, cod),
                ).fetchone()
                reservas_guardadas.append(self._map_reservation_row(row_res))

        return {
            "referencia_tipo": ref_tipo,
            "referencia_id": ref_id,
            "reservas": reservas_guardadas,
            "sin_stock": sin_stock,
            "total_unidades_reservadas": sum(r["cantidad"] for r in reservas_guardadas),
        }

    def consolidar_reserva(
        self,
        referencia_id: str,
        referencia_tipo: str = "ola_picking",
        product_code: str | None = None,
        descontar_stock: bool = True,
        usuario: str = "sistema",
        detalle: str = "",
    ) -> dict[str, Any]:
        """Consolida reservas activas pasando a `'consolidada'` y descontando stock físico/FEFO opcionalmente."""
        ref_id = str(referencia_id or "").strip()
        ref_tipo = str(referencia_tipo or "ola_picking").strip() or "ola_picking"
        if not ref_id:
            raise ValueError("El identificador de referencia es obligatorio.")

        usuario_limpio = (usuario or "sistema").strip() or "sistema"
        detalle_limpio = (detalle or f"Consolidación {ref_tipo}: {ref_id}").strip()[:120]

        filtros = ["referencia_tipo = ?", "referencia_id = ?", "estado = 'activa'"]
        params: list[Any] = [ref_tipo, ref_id]
        if product_code:
            filtros.append("product_code = ?")
            params.append(str(product_code).strip())

        items_consolidados: list[dict[str, Any]] = []
        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            rows = connection.execute(
                f"SELECT * FROM stock_reservations WHERE {' AND '.join(filtros)} ORDER BY id ASC",
                tuple(params),
            ).fetchall()

            for row in rows:
                cod = str(row["product_code"])
                qty = int(row["cantidad"])
                lotes_pref = _deserializar_lotes(row["lotes_asignados"])
                consumos_fefo: list[dict[str, Any]] = []
                ubic_desc: list[dict[str, Any]] = []

                if descontar_stock:
                    prod = connection.execute(
                        "SELECT stock FROM products WHERE code = ?",
                        (cod,),
                    ).fetchone()
                    stock_actual = int(prod["stock"]) if prod is not None else 0
                    if stock_actual < qty:
                        raise InsufficientStockError(cod, qty, stock_actual)

                    connection.execute(
                        "UPDATE products SET stock = stock - ? WHERE code = ?",
                        (qty, cod),
                    )
                    connection.execute(
                        """
                        UPDATE stock_movements
                        SET usuario = ?,
                            detalle = ?
                        WHERE id = (
                            SELECT id FROM stock_movements
                            WHERE product_code = ?
                            ORDER BY id DESC LIMIT 1
                        ) AND (usuario = 'sistema' OR detalle = '')
                        """,
                        (usuario_limpio, detalle_limpio, cod),
                    )
                    consumos_fefo, _ = consumir_lotes_fefo_en_tx(
                        connection,
                        cod,
                        qty,
                        permitir_parcial=True,
                        lotes_preferidos=lotes_pref,
                    )
                    ubic_desc = descontar_ubicaciones_en_tx(
                        connection,
                        cod,
                        qty,
                        ubicacion_preferida=str(row["ubicacion"] or ""),
                    )

                connection.execute(
                    """
                    UPDATE stock_reservations
                    SET estado = 'consolidada',
                        updated_at = strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime')
                    WHERE id = ?
                    """,
                    (row["id"],),
                )
                items_consolidados.append(
                    {
                        "id": int(row["id"]),
                        "product_code": cod,
                        "cantidad": qty,
                        "lotes_consumidos": consumos_fefo,
                        "ubicaciones_afectadas": ubic_desc,
                    }
                )

        if descontar_stock and items_consolidados:
            self._notificar_cambio_catalogo()

        return {
            "referencia_tipo": ref_tipo,
            "referencia_id": ref_id,
            "consolidadas": len(items_consolidados),
            "unidades_consolidadas": sum(i["cantidad"] for i in items_consolidados),
            "stock_descontado": descontar_stock,
            "items": items_consolidados,
        }

    def liberar_reserva(
        self,
        referencia_id: str,
        referencia_tipo: str = "ola_picking",
        product_code: str | None = None,
        motivo: str = "",
    ) -> dict[str, Any]:
        """Libera reservas activas devolviendo inmediatamente las unidades a `stock_disponible`."""
        ref_id = str(referencia_id or "").strip()
        ref_tipo = str(referencia_tipo or "ola_picking").strip() or "ola_picking"
        if not ref_id:
            raise ValueError("El identificador de referencia es obligatorio.")

        filtros = ["referencia_tipo = ?", "referencia_id = ?", "estado = 'activa'"]
        params: list[Any] = [ref_tipo, ref_id]
        if product_code:
            filtros.append("product_code = ?")
            params.append(str(product_code).strip())

        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            rows = connection.execute(
                f"SELECT id, product_code, cantidad FROM stock_reservations WHERE {' AND '.join(filtros)}",
                tuple(params),
            ).fetchall()
            if rows:
                ids = [int(r["id"]) for r in rows]
                placeholders = ",".join("?" for _ in ids)
                nota_update = ", nota = CASE WHEN TRIM(?) != '' THEN ? ELSE nota END"
                motivo_limpio = str(motivo or "").strip()
                connection.execute(
                    f"""
                    UPDATE stock_reservations
                    SET estado = 'liberada',
                        updated_at = strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime')
                        {nota_update}
                    WHERE id IN ({placeholders})
                    """,
                    (motivo_limpio, motivo_limpio, *ids),
                )

        return {
            "referencia_tipo": ref_tipo,
            "referencia_id": ref_id,
            "liberadas": len(rows),
            "unidades_liberadas": sum(int(r["cantidad"]) for r in rows),
            "codigos": [str(r["product_code"]) for r in rows],
        }
