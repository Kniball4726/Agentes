"""Repositorio de trazabilidad de lotes y vencimientos FEFO."""

from __future__ import annotations

from contextlib import closing
from datetime import date, datetime, timedelta
import sqlite3
from typing import Any, Callable

from ..core.exceptions import InsufficientStockError
from .locations_repo import (
    _asegurar_producto_en_tx,
    descontar_ubicaciones_en_tx,
    normalizar_ubicacion,
)

VALID_LOT_STATES: tuple[str, ...] = ("disponible", "bloqueado", "vencido", "agotado")

_FEFO_ORDER_SQL = """
ORDER BY
    CASE WHEN TRIM(COALESCE(fecha_vencimiento, '')) = '' THEN 1 ELSE 0 END ASC,
    fecha_vencimiento ASC,
    created_at ASC,
    id ASC
"""


def normalizar_fecha_vencimiento(fecha: object) -> str:
    """Valida y normaliza una fecha de vencimiento a ISO ``YYYY-MM-DD`` (o ``''`` si está vacía)."""
    texto = str(fecha or "").strip()
    if not texto:
        return ""
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(texto, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    raise ValueError(
        f"Formato de fecha de vencimiento inválido '{texto}'. Use YYYY-MM-DD o DD/MM/YYYY."
    )


def map_lot_row(row: sqlite3.Row, hoy: date) -> dict[str, Any]:
    """Convierte una fila SQLite de ``stock_lots`` en diccionario con días restantes FEFO."""
    fv = str(row["fecha_vencimiento"] or "").strip()
    dias_para_vencer: int | None = None
    vencido = False
    if fv:
        try:
            fecha_dt = date.fromisoformat(fv)
            dias_para_vencer = (fecha_dt - hoy).days
            vencido = dias_para_vencer < 0
        except ValueError:
            dias_para_vencer = None
    return {
        "id": int(row["id"]),
        "product_code": str(row["product_code"]),
        "lote": str(row["lote"]),
        "ubicacion": str(row["ubicacion"] or ""),
        "fecha_vencimiento": fv,
        "stock": int(row["stock"]),
        "estado": str(row["estado"]),
        "notas": str(row["notas"] or ""),
        "created_at": str(row["created_at"] or ""),
        "updated_at": str(row["updated_at"] or ""),
        "dias_para_vencer": dias_para_vencer,
        "vencido": vencido,
    }


def _descontar_lote_en_tx(
    connection: sqlite3.Connection,
    lot_id: int,
    stock_actual: int,
    tomar: int,
) -> tuple[int, str]:
    """Aplica el descuento de ``tomar`` unidades sobre un lote y actualiza su estado."""
    nuevo_stock = int(stock_actual) - int(tomar)
    nuevo_estado = "agotado" if nuevo_stock == 0 else "disponible"
    connection.execute(
        """
        UPDATE stock_lots
        SET stock = ?,
            estado = ?,
            updated_at = strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime')
        WHERE id = ?
        """,
        (nuevo_stock, nuevo_estado, int(lot_id)),
    )
    return nuevo_stock, nuevo_estado


def _registro_consumo_lote(
    lot_id: int,
    lote: str,
    ubicacion: str,
    fecha_vencimiento: str,
    tomar: int,
    nuevo_stock: int,
) -> dict[str, Any]:
    return {
        "lot_id": int(lot_id),
        "lote": str(lote),
        "ubicacion": str(ubicacion or ""),
        "fecha_vencimiento": str(fecha_vencimiento or ""),
        "cantidad": int(tomar),
        "stock_restante_lote": int(nuevo_stock),
    }


def planificar_lotes_fefo_en_tx(
    connection: sqlite3.Connection,
    code: str,
    cantidad: int,
    ubicacion: str | None = None,
    incluir_vencidos: bool = False,
    hoy_iso: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """Calcula la asignación FEFO para ``cantidad`` sin mutar saldos.

    Retorna ``(asignaciones, total_disponible_lotes)``.
    """
    hoy = hoy_iso or date.today().isoformat()
    filtros = ["product_code = ?", "estado = 'disponible'", "stock > 0"]
    params: list[Any] = [str(code or "").strip()]
    if ubicacion:
        filtros.append("ubicacion = ?")
        params.append(normalizar_ubicacion(ubicacion))
    if not incluir_vencidos:
        filtros.append("(TRIM(COALESCE(fecha_vencimiento, '')) = '' OR fecha_vencimiento >= ?)")
        params.append(hoy)

    rows = connection.execute(
        f"""
        SELECT id, lote, ubicacion, fecha_vencimiento, stock, estado
        FROM stock_lots
        WHERE {' AND '.join(filtros)}
        {_FEFO_ORDER_SQL}
        """,
        tuple(params),
    ).fetchall()

    total_disp = sum(max(0, int(r["stock"])) for r in rows)
    restante = max(0, int(cantidad))
    asignaciones: list[dict[str, Any]] = []
    for row in rows:
        if restante <= 0:
            break
        disponible_lote = max(0, int(row["stock"]))
        tomar = min(disponible_lote, restante)
        if tomar <= 0:
            continue
        asignaciones.append(
            {
                "lot_id": int(row["id"]),
                "lote": str(row["lote"]),
                "ubicacion": str(row["ubicacion"] or ""),
                "fecha_vencimiento": str(row["fecha_vencimiento"] or ""),
                "cantidad": tomar,
            }
        )
        restante -= tomar
    return asignaciones, total_disp


def consumir_lotes_fefo_en_tx(
    connection: sqlite3.Connection,
    code: str,
    cantidad: int,
    ubicacion: str | None = None,
    permitir_parcial: bool = False,
    incluir_vencidos: bool = False,
    lotes_preferidos: list[dict[str, Any]] | None = None,
    hoy_iso: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """Descuenta ``cantidad`` de lotes ``stock_lots`` respetando orden FEFO dentro de una tx.

    Retorna ``(consumos, faltante_sin_lote)``.
    """
    cod = str(code or "").strip()
    objetivo = max(0, int(cantidad))
    if objetivo <= 0:
        return [], 0

    consumos: list[dict[str, Any]] = []
    restante = objetivo
    hoy = hoy_iso or date.today().isoformat()

    # 1. Intentar primero sobre lotes explícitamente asignados (p.ej., desde reserva)
    for pref in lotes_preferidos or []:
        if restante <= 0:
            break
        lot_id = pref.get("lot_id")
        qty_pref = min(restante, max(0, int(pref.get("cantidad", 0))))
        if not lot_id or qty_pref <= 0:
            continue
        row = connection.execute(
            """
            SELECT id, lote, ubicacion, fecha_vencimiento, stock, estado
            FROM stock_lots
            WHERE id = ? AND product_code = ? AND estado = 'disponible' AND stock > 0
            """,
            (int(lot_id), cod),
        ).fetchone()
        if row is None:
            continue
        tomar = min(max(0, int(row["stock"])), qty_pref)
        if tomar <= 0:
            continue
        nuevo_stock, _ = _descontar_lote_en_tx(connection, int(row["id"]), int(row["stock"]), tomar)
        consumos.append(
            _registro_consumo_lote(
                int(row["id"]),
                str(row["lote"]),
                str(row["ubicacion"] or ""),
                str(row["fecha_vencimiento"] or ""),
                tomar,
                nuevo_stock,
            )
        )
        restante -= tomar

    # 2. Completar restante siguiendo estrictamente FEFO
    if restante > 0:
        plan, total_disp = planificar_lotes_fefo_en_tx(
            connection,
            cod,
            restante,
            ubicacion=ubicacion,
            incluir_vencidos=incluir_vencidos,
            hoy_iso=hoy,
        )
        if total_disp < restante and not permitir_parcial and not lotes_preferidos:
            raise InsufficientStockError(cod, restante, total_disp)
        for item in plan:
            if restante <= 0:
                break
            tomar = min(restante, int(item["cantidad"]))
            row = connection.execute(
                "SELECT stock FROM stock_lots WHERE id = ?",
                (item["lot_id"],),
            ).fetchone()
            stock_actual = int(row["stock"]) if row is not None else 0
            tomar = min(tomar, stock_actual)
            if tomar <= 0:
                continue
            nuevo_stock, _ = _descontar_lote_en_tx(
                connection, int(item["lot_id"]), stock_actual, tomar
            )
            consumos.append(
                _registro_consumo_lote(
                    int(item["lot_id"]),
                    str(item["lote"]),
                    str(item["ubicacion"]),
                    str(item["fecha_vencimiento"]),
                    tomar,
                    nuevo_stock,
                )
            )
            restante -= tomar

    return consumos, restante


def trasladar_lotes_en_tx(
    connection: sqlite3.Connection,
    code: str,
    origen: str,
    destino: str,
    cantidad: int,
) -> list[dict[str, Any]]:
    """Acompaña el traslado físico de bins moviendo lotes en origen siguiendo orden FEFO."""
    restante = int(cantidad)
    lotes = connection.execute(
        f"""
        SELECT *
        FROM stock_lots
        WHERE product_code = ? AND ubicacion = ? AND estado = 'disponible' AND stock > 0
        {_FEFO_ORDER_SQL}
        """,
        (code, origen),
    ).fetchall()
    movidos: list[dict[str, Any]] = []
    for lot in lotes:
        if restante <= 0:
            break
        tomar = min(int(lot["stock"]), restante)
        if tomar <= 0:
            continue
        _descontar_lote_en_tx(connection, int(lot["id"]), int(lot["stock"]), tomar)
        connection.execute(
            """
            INSERT INTO stock_lots (
                product_code, lote, ubicacion, fecha_vencimiento, stock, estado, notas
            )
            VALUES (?, ?, ?, ?, ?, 'disponible', ?)
            ON CONFLICT(product_code, lote, ubicacion) DO UPDATE SET
                stock = stock_lots.stock + excluded.stock,
                estado = 'disponible',
                fecha_vencimiento = CASE
                    WHEN TRIM(excluded.fecha_vencimiento) != '' THEN excluded.fecha_vencimiento
                    ELSE stock_lots.fecha_vencimiento
                END,
                updated_at = strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime')
            """,
            (
                code,
                lot["lote"],
                destino,
                lot["fecha_vencimiento"],
                tomar,
                lot["notas"],
            ),
        )
        movidos.append(
            {
                "lote": str(lot["lote"]),
                "fecha_vencimiento": str(lot["fecha_vencimiento"] or ""),
                "cantidad": tomar,
            }
        )
        restante -= tomar
    return movidos


class FefoLotsRepository:
    """Gestiona registro, consulta, alertas y consumo FEFO de lotes."""

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

    _map_lot_row = staticmethod(map_lot_row)

    def registrar_lote(
        self,
        code: str,
        lote: str,
        cantidad: int,
        fecha_vencimiento: str = "",
        ubicacion: str = "",
        estado: str = "disponible",
        notas: str = "",
        sumar_si_existe: bool = False,
    ) -> dict[str, Any]:
        """Registra o actualiza un lote de stock con vencimiento y ubicación opcional."""
        cod = str(code or "").strip()
        lote_norm = str(lote or "").strip().upper()
        if not lote_norm:
            raise ValueError("El código de lote no puede estar vacío.")
        qty = int(cantidad)
        if qty < 0:
            raise ValueError("La cantidad del lote no puede ser negativa.")
        estado_norm = str(estado or "disponible").strip().lower()
        if estado_norm not in VALID_LOT_STATES:
            raise ValueError(f"Estado de lote inválido '{estado}'.")
        fecha_iso = normalizar_fecha_vencimiento(fecha_vencimiento)

        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            prod = _asegurar_producto_en_tx(connection, cod)
            ubic_norm = normalizar_ubicacion(ubicacion) or normalizar_ubicacion(prod["ubicacion"])

            existente = connection.execute(
                "SELECT id, stock FROM stock_lots WHERE product_code = ? AND lote = ? AND ubicacion = ?",
                (cod, lote_norm, ubic_norm),
            ).fetchone()
            stock_final = (
                (int(existente["stock"]) + qty)
                if (sumar_si_existe and existente is not None)
                else qty
            )
            if stock_final == 0 and estado_norm == "disponible":
                estado_norm = "agotado"
            elif stock_final > 0 and estado_norm == "agotado":
                estado_norm = "disponible"

            if existente is not None:
                connection.execute(
                    """
                    UPDATE stock_lots
                    SET fecha_vencimiento = ?,
                        stock = ?,
                        estado = ?,
                        notas = ?,
                        updated_at = strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime')
                    WHERE id = ?
                    """,
                    (
                        fecha_iso,
                        stock_final,
                        estado_norm,
                        str(notas or "").strip(),
                        existente["id"],
                    ),
                )
                lot_id = int(existente["id"])
            else:
                cur = connection.execute(
                    """
                    INSERT INTO stock_lots (
                        product_code, lote, ubicacion, fecha_vencimiento, stock, estado, notas
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        cod,
                        lote_norm,
                        ubic_norm,
                        fecha_iso,
                        stock_final,
                        estado_norm,
                        str(notas or "").strip(),
                    ),
                )
                lot_id = int(cur.lastrowid or 0)

            row = connection.execute("SELECT * FROM stock_lots WHERE id = ?", (lot_id,)).fetchone()
        return map_lot_row(row, date.today())

    def listar_lotes_fefo(
        self,
        code: str,
        solo_disponibles: bool = False,
        ubicacion: str | None = None,
    ) -> list[dict[str, Any]]:
        """Lista lotes de un SKU ordenados por FEFO (vencimiento más próximo primero)."""
        cod = str(code or "").strip()
        if not cod:
            return []
        filtros = ["product_code = ?"]
        params: list[Any] = [cod]
        if solo_disponibles:
            filtros.extend(["estado = 'disponible'", "stock > 0"])
        if ubicacion:
            filtros.append("ubicacion = ?")
            params.append(normalizar_ubicacion(ubicacion))
        with closing(self._connect()) as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM stock_lots
                WHERE {' AND '.join(filtros)}
                {_FEFO_ORDER_SQL}
                """,
                tuple(params),
            ).fetchall()
        hoy = date.today()
        return [map_lot_row(r, hoy) for r in rows]

    def consumir_lotes_fefo(
        self,
        code: str,
        cantidad: int,
        ubicacion: str | None = None,
        permitir_parcial: bool = False,
        incluir_vencidos: bool = False,
        descontar_stock_producto: bool = False,
        usuario: str = "sistema",
        detalle: str = "",
    ) -> dict[str, Any]:
        """Consume unidades de un SKU aplicando regla FEFO sobre ``stock_lots``."""
        cod = str(code or "").strip()
        qty = int(cantidad)
        if qty <= 0:
            raise ValueError("La cantidad a consumir debe ser mayor a 0.")

        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            prod = _asegurar_producto_en_tx(connection, cod)
            consumos, restante = consumir_lotes_fefo_en_tx(
                connection,
                cod,
                qty,
                ubicacion=ubicacion,
                permitir_parcial=permitir_parcial,
                incluir_vencidos=incluir_vencidos,
            )
            consumido_total = qty - restante
            for item in consumos:
                if item["ubicacion"]:
                    descontar_ubicaciones_en_tx(
                        connection,
                        cod,
                        int(item["cantidad"]),
                        ubicacion_preferida=item["ubicacion"],
                    )

            if descontar_stock_producto and consumido_total > 0:
                stock_actual = int(prod["stock"])
                if stock_actual < consumido_total:
                    raise InsufficientStockError(cod, consumido_total, stock_actual)
                connection.execute(
                    "UPDATE products SET stock = stock - ? WHERE code = ?",
                    (consumido_total, cod),
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
                    (
                        (usuario or "sistema").strip() or "sistema",
                        (detalle or "Consumo FEFO por lote").strip()[:120],
                        cod,
                    ),
                )

        if descontar_stock_producto and consumido_total > 0:
            self._notificar_cambio_catalogo()

        return {
            "product_code": cod,
            "solicitado": qty,
            "consumido": consumido_total,
            "restante": restante,
            "consumos": consumos,
        }

    def listar_lotes_proximos_vencer(
        self,
        dias: int = 30,
        incluir_vencidos: bool = True,
        solo_con_stock: bool = True,
    ) -> list[dict[str, Any]]:
        """Retorna lotes con fecha de vencimiento dentro de la ventana de alerta."""
        ventana = max(0, int(dias))
        hoy = date.today()
        limite_iso = (hoy + timedelta(days=ventana)).isoformat()
        hoy_iso = hoy.isoformat()

        filtros = [
            "TRIM(COALESCE(sl.fecha_vencimiento, '')) != ''",
            "sl.fecha_vencimiento <= ?",
            "sl.estado != 'bloqueado'",
        ]
        params: list[Any] = [limite_iso]
        if not incluir_vencidos:
            filtros.append("sl.fecha_vencimiento >= ?")
            params.append(hoy_iso)
        if solo_con_stock:
            filtros.append("sl.stock > 0")

        with closing(self._connect()) as connection:
            rows = connection.execute(
                f"""
                SELECT sl.*, p.name AS product_name
                FROM stock_lots sl
                INNER JOIN products p ON p.code = sl.product_code
                WHERE p.active = 1 AND {' AND '.join(filtros)}
                ORDER BY sl.fecha_vencimiento ASC, sl.product_code ASC, sl.id ASC
                """,
                tuple(params),
            ).fetchall()

        alertas: list[dict[str, Any]] = []
        for row in rows:
            item = map_lot_row(row, hoy)
            item["product_name"] = str(row["product_name"] or "")
            dias_rest = item["dias_para_vencer"]
            if dias_rest is not None and dias_rest < 0:
                item["nivel_alerta"] = "VENCIDO"
            elif dias_rest is not None and dias_rest <= 7:
                item["nivel_alerta"] = "CRITICO"
            else:
                item["nivel_alerta"] = "PROXIMO"
            alertas.append(item)
        return alertas
