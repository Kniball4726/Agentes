"""Repositorio de multi-ubicación logística por zona de depósito."""

from __future__ import annotations

from contextlib import closing
import sqlite3
from typing import Any, Callable

from ..core.exceptions import InsufficientStockError, ProductNotFoundError

VALID_ZONE_TYPES: tuple[str, ...] = ("picking", "pulmon", "pallet", "recepcion", "cuarentena")

_ZONE_ORDER_SQL = """
CASE tipo_zona
    WHEN 'picking' THEN 1
    WHEN 'pulmon' THEN 2
    WHEN 'pallet' THEN 3
    WHEN 'recepcion' THEN 4
    ELSE 5
END
"""

TransferLotsCallback = Callable[[sqlite3.Connection, str, str, str, int], list[dict[str, Any]]]


def normalizar_ubicacion(ubicacion: object) -> str:
    """Normaliza un código de ubicación física a mayúsculas sin espacios laterales."""
    return str(ubicacion or "").strip().upper()


def normalizar_zona(tipo_zona: object) -> str:
    """Valida y normaliza una zona logística contra ``VALID_ZONE_TYPES``."""
    zona = str(tipo_zona or "picking").strip().lower()
    if zona not in VALID_ZONE_TYPES:
        validas = ", ".join(VALID_ZONE_TYPES)
        raise ValueError(f"Tipo de zona inválido '{tipo_zona}'. Valores válidos: {validas}.")
    return zona


def _asegurar_producto_en_tx(connection: sqlite3.Connection, code: str) -> sqlite3.Row:
    """Verifica existencia del SKU en ``products`` dentro de la transacción activa."""
    cod = str(code or "").strip()
    if not cod:
        raise ValueError("El código de producto es obligatorio.")
    row = connection.execute(
        "SELECT code, name, stock, ubicacion, active FROM products WHERE code = ?",
        (cod,),
    ).fetchone()
    if row is None:
        raise ProductNotFoundError(cod)
    return row


def map_location_row(row: sqlite3.Row) -> dict[str, Any]:
    """Convierte una fila SQLite de ``product_locations`` en diccionario de dominio."""
    return {
        "id": int(row["id"]),
        "product_code": str(row["product_code"]),
        "ubicacion": str(row["ubicacion"]),
        "tipo_zona": str(row["tipo_zona"]),
        "stock": int(row["stock"]),
        "capacidad_max": int(row["capacidad_max"]),
        "es_principal": bool(row["es_principal"]),
        "updated_at": str(row["updated_at"] or ""),
    }


def sincronizar_ubicacion_principal_en_tx(
    connection: sqlite3.Connection,
    code: str,
    ubicacion: str,
) -> None:
    """Mantiene sincronizada ``products.ubicacion`` con la tabla ``product_locations``."""
    ubic = normalizar_ubicacion(ubicacion)
    cod = str(code or "").strip()
    if not cod or not ubic:
        return

    existente = connection.execute(
        "SELECT id FROM product_locations WHERE product_code = ? AND ubicacion = ?",
        (cod, ubic),
    ).fetchone()
    if existente is not None:
        connection.execute(
            "UPDATE product_locations SET es_principal = 0 WHERE product_code = ? AND ubicacion != ?",
            (cod, ubic),
        )
        connection.execute(
            """
            UPDATE product_locations
            SET es_principal = 1,
                updated_at = strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime')
            WHERE id = ?
            """,
            (existente["id"],),
        )
        return

    principal_actual = connection.execute(
        """
        SELECT id, ubicacion
        FROM product_locations
        WHERE product_code = ?
        ORDER BY es_principal DESC, id ASC
        LIMIT 1
        """,
        (cod,),
    ).fetchone()
    if principal_actual is not None:
        ubic_anterior = str(principal_actual["ubicacion"] or "").strip()
        connection.execute(
            """
            UPDATE product_locations
            SET ubicacion = ?,
                es_principal = 1,
                updated_at = strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime')
            WHERE id = ?
            """,
            (ubic, principal_actual["id"]),
        )
        if ubic_anterior:
            connection.execute(
                """
                UPDATE stock_lots
                SET ubicacion = ?,
                    updated_at = strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime')
                WHERE product_code = ? AND ubicacion = ?
                """,
                (ubic, cod, ubic_anterior),
            )
        return

    prod = connection.execute("SELECT stock FROM products WHERE code = ?", (cod,)).fetchone()
    stock_inicial = max(0, int(prod["stock"])) if prod is not None else 0
    connection.execute(
        """
        INSERT INTO product_locations (
            product_code, ubicacion, tipo_zona, stock, capacidad_max, es_principal
        )
        VALUES (?, ?, 'picking', ?, 0, 1)
        """,
        (cod, ubic, stock_inicial),
    )


def descontar_ubicaciones_en_tx(
    connection: sqlite3.Connection,
    code: str,
    cantidad: int,
    ubicacion_preferida: str = "",
) -> list[dict[str, Any]]:
    """Descuenta hasta ``cantidad`` unidades desde ``product_locations`` (picking primero)."""
    restante = max(0, int(cantidad))
    if restante <= 0:
        return []
    pref = normalizar_ubicacion(ubicacion_preferida)
    rows = connection.execute(
        f"""
        SELECT id, ubicacion, tipo_zona, stock
        FROM product_locations
        WHERE product_code = ? AND stock > 0
        ORDER BY
            CASE WHEN ? != '' AND ubicacion = ? THEN 0 ELSE 1 END ASC,
            {_ZONE_ORDER_SQL} ASC,
            es_principal DESC,
            id ASC
        """,
        (code, pref, pref),
    ).fetchall()
    movimientos: list[dict[str, Any]] = []
    for row in rows:
        if restante <= 0:
            break
        disponible = max(0, int(row["stock"]))
        tomar = min(disponible, restante)
        if tomar <= 0:
            continue
        connection.execute(
            """
            UPDATE product_locations
            SET stock = stock - ?,
                updated_at = strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime')
            WHERE id = ?
            """,
            (tomar, row["id"]),
        )
        movimientos.append(
            {
                "ubicacion": str(row["ubicacion"]),
                "tipo_zona": str(row["tipo_zona"]),
                "cantidad": tomar,
            }
        )
        restante -= tomar
    return movimientos


class WarehouseLocationsRepository:
    """Gestiona ubicaciones múltiples por zona logística y transferencias entre bins."""

    def __init__(
        self,
        connect_fn: Callable[[], sqlite3.Connection],
        invalidate_cache_cb: Callable[[], None] | None = None,
        transfer_lots_tx: TransferLotsCallback | None = None,
    ) -> None:
        self._connect = connect_fn
        self._invalidar_cache = invalidate_cache_cb
        self._transfer_lots_tx = transfer_lots_tx

    def _notificar_cambio_catalogo(self) -> None:
        if self._invalidar_cache is not None:
            self._invalidar_cache()

    _map_location_row = staticmethod(map_location_row)

    @staticmethod
    def _obtener_o_crear_destino_tx(
        connection: sqlite3.Connection,
        code: str,
        destino: str,
        zona_dest: str,
        crear_destino: bool,
    ) -> sqlite3.Row:
        row_dest = connection.execute(
            "SELECT * FROM product_locations WHERE product_code = ? AND ubicacion = ?",
            (code, destino),
        ).fetchone()
        if row_dest is not None:
            return row_dest
        if not crear_destino:
            raise ValueError(
                f"La ubicación destino '{destino}' no existe para el producto '{code}'."
            )
        connection.execute(
            """
            INSERT INTO product_locations (
                product_code, ubicacion, tipo_zona, stock, capacidad_max, es_principal
            )
            VALUES (?, ?, ?, 0, 0, 0)
            """,
            (code, destino, zona_dest),
        )
        return connection.execute(
            "SELECT * FROM product_locations WHERE product_code = ? AND ubicacion = ?",
            (code, destino),
        ).fetchone()

    def asignar_ubicacion_producto(
        self,
        code: str,
        ubicacion: str,
        tipo_zona: str = "picking",
        stock: int | None = None,
        capacidad_max: int = 0,
        es_principal: bool = False,
    ) -> dict[str, Any]:
        """Crea o actualiza una ubicación específica (``picking``, ``pulmon``, ``pallet``, etc.) para un SKU."""
        cod = str(code or "").strip()
        ubic = normalizar_ubicacion(ubicacion)
        if not ubic:
            raise ValueError("La ubicación física no puede estar vacía.")
        zona = normalizar_zona(tipo_zona)
        cap = int(capacidad_max)
        if cap < 0:
            raise ValueError("La capacidad máxima de la ubicación no puede ser negativa.")
        if stock is not None and int(stock) < 0:
            raise ValueError("El stock asignado a la ubicación no puede ser negativo.")

        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            _asegurar_producto_en_tx(connection, cod)

            total_prev = int(
                connection.execute(
                    "SELECT COUNT(*) AS cnt FROM product_locations WHERE product_code = ?",
                    (cod,),
                ).fetchone()["cnt"]
            )
            marcar_principal = bool(es_principal) or total_prev == 0

            existente = connection.execute(
                "SELECT id, stock FROM product_locations WHERE product_code = ? AND ubicacion = ?",
                (cod, ubic),
            ).fetchone()

            if marcar_principal:
                connection.execute(
                    "UPDATE product_locations SET es_principal = 0 WHERE product_code = ?",
                    (cod,),
                )
                connection.execute(
                    "UPDATE products SET ubicacion = ? WHERE code = ?",
                    (ubic, cod),
                )

            stock_final = (
                int(stock)
                if stock is not None
                else (int(existente["stock"]) if existente is not None else 0)
            )

            if existente is not None:
                connection.execute(
                    """
                    UPDATE product_locations
                    SET tipo_zona = ?,
                        stock = ?,
                        capacidad_max = ?,
                        es_principal = ?,
                        updated_at = strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime')
                    WHERE id = ?
                    """,
                    (zona, stock_final, cap, 1 if marcar_principal else 0, existente["id"]),
                )
                row_id = int(existente["id"])
            else:
                cur = connection.execute(
                    """
                    INSERT INTO product_locations (
                        product_code, ubicacion, tipo_zona, stock, capacidad_max, es_principal
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (cod, ubic, zona, stock_final, cap, 1 if marcar_principal else 0),
                )
                row_id = int(cur.lastrowid or 0)

            row = connection.execute(
                "SELECT * FROM product_locations WHERE id = ?",
                (row_id,),
            ).fetchone()

        self._notificar_cambio_catalogo()
        return map_location_row(row)

    def listar_ubicaciones_producto(self, code: str) -> list[dict[str, Any]]:
        """Lista todas las ubicaciones asignadas a un SKU ordenadas por principal y prioridad de zona."""
        cod = str(code or "").strip()
        if not cod:
            return []
        with closing(self._connect()) as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM product_locations
                WHERE product_code = ?
                ORDER BY es_principal DESC, {_ZONE_ORDER_SQL} ASC, ubicacion ASC
                """,
                (cod,),
            ).fetchall()
            return [map_location_row(r) for r in rows]

    def listar_ubicaciones_mapa(self, solo_activos: bool = True) -> dict[str, list[dict[str, Any]]]:
        """Retorna un diccionario ``{product_code: [ubicaciones...]}`` en una única consulta."""
        filtro = "WHERE p.active = 1" if solo_activos else ""
        with closing(self._connect()) as connection:
            rows = connection.execute(
                f"""
                SELECT pl.*
                FROM product_locations pl
                INNER JOIN products p ON p.code = pl.product_code
                {filtro}
                ORDER BY pl.product_code ASC, pl.es_principal DESC, {_ZONE_ORDER_SQL} ASC, pl.ubicacion ASC
                """
            ).fetchall()
        mapa: dict[str, list[dict[str, Any]]] = {}
        for r in rows:
            item = map_location_row(r)
            mapa.setdefault(item["product_code"], []).append(item)
        return mapa

    def transferir_entre_ubicaciones(
        self,
        code: str,
        origen: str,
        destino: str,
        cantidad: int,
        destino_zona: str = "picking",
        crear_destino: bool = True,
    ) -> dict[str, Any]:
        """Transfiere stock entre dos ubicaciones del mismo SKU (ej. ``pulmon`` -> ``picking``)."""
        cod = str(code or "").strip()
        orig = normalizar_ubicacion(origen)
        dest = normalizar_ubicacion(destino)
        qty = int(cantidad)
        if not orig or not dest:
            raise ValueError("Debe especificar ubicación de origen y destino.")
        if orig == dest:
            raise ValueError("La ubicación de origen y destino deben ser distintas.")
        if qty <= 0:
            raise ValueError("La cantidad a transferir debe ser mayor a 0.")
        zona_dest = normalizar_zona(destino_zona)

        transfer_lots = self._transfer_lots_tx
        if transfer_lots is None:
            from .lots_fefo_repo import trasladar_lotes_en_tx

            transfer_lots = trasladar_lotes_en_tx

        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            _asegurar_producto_en_tx(connection, cod)

            row_orig = connection.execute(
                "SELECT * FROM product_locations WHERE product_code = ? AND ubicacion = ?",
                (cod, orig),
            ).fetchone()
            if row_orig is None:
                raise ValueError(f"La ubicación origen '{orig}' no existe para el producto '{cod}'.")
            stock_orig = int(row_orig["stock"])
            if stock_orig < qty:
                raise InsufficientStockError(f"{cod}@{orig}", qty, stock_orig)

            row_dest = self._obtener_o_crear_destino_tx(
                connection, cod, dest, zona_dest, crear_destino
            )

            connection.execute(
                """
                UPDATE product_locations
                SET stock = stock - ?,
                    updated_at = strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime')
                WHERE id = ?
                """,
                (qty, row_orig["id"]),
            )
            connection.execute(
                """
                UPDATE product_locations
                SET stock = stock + ?,
                    updated_at = strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime')
                WHERE id = ?
                """,
                (qty, row_dest["id"]),
            )
            lotes_movidos = transfer_lots(connection, cod, orig, dest, qty)

            orig_actualizado = connection.execute(
                "SELECT * FROM product_locations WHERE id = ?",
                (row_orig["id"],),
            ).fetchone()
            dest_actualizado = connection.execute(
                "SELECT * FROM product_locations WHERE id = ?",
                (row_dest["id"],),
            ).fetchone()

        self._notificar_cambio_catalogo()
        return {
            "product_code": cod,
            "cantidad": qty,
            "origen": map_location_row(orig_actualizado),
            "destino": map_location_row(dest_actualizado),
            "lotes_trasladados": lotes_movidos,
        }
