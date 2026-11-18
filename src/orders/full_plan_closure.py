"""Lógica transaccional para cierres parciales (multidía) y finales de planes Mercado Full."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Any


def recalcular_progreso_plan_full(
    connection: sqlite3.Connection,
    plan_id: int,
) -> tuple[int, int, int, float]:
    """Recalcula totales, pickeados, descontados y porcentaje de un envío Mercado Full."""
    stats = connection.execute(
        """
        SELECT
            COALESCE(SUM(cantidad_solicitada), 0) AS tot,
            COALESCE(SUM(cantidad_pickeada), 0) AS pick,
            COALESCE(SUM(cantidad_descontada), 0) AS desc_tot
        FROM plan_mercado_full_items
        WHERE plan_id = ?
        """,
        (plan_id,),
    ).fetchone()
    tot = int(stats["tot"]) if stats else 0
    pick = int(stats["pick"]) if stats else 0
    desc_tot = int(stats["desc_tot"]) if stats else 0
    porcentaje = round((pick / tot * 100.0), 1) if tot > 0 else 0.0
    connection.execute(
        """
        UPDATE planes_mercado_full
        SET articulos_totales = ?,
            articulos_pickeados = ?,
            articulos_descontados = ?,
            porcentaje = ?
        WHERE id = ?
        """,
        (tot, pick, desc_tot, porcentaje, plan_id),
    )
    return tot, pick, desc_tot, porcentaje


def _recolectar_deltas_full(
    connection: sqlite3.Connection,
    plan_id: int,
) -> tuple[list[tuple[int, int]], dict[str, int], list[tuple[str, str, int]], int]:
    """Obtiene por SKU las unidades pickeadas aún no descontadas del stock."""
    rows = connection.execute(
        """
        SELECT id, codigo, descripcion, cantidad_pickeada, cantidad_descontada
        FROM plan_mercado_full_items
        WHERE plan_id = ?
        ORDER BY id ASC
        """,
        (plan_id,),
    ).fetchall()
    items_actualizar: list[tuple[int, int]] = []
    delta_items: dict[str, int] = {}
    items_detalle: list[tuple[str, str, int]] = []
    total_delta = 0

    for row in rows:
        pick = int(row["cantidad_pickeada"] or 0)
        desc = int(row["cantidad_descontada"] or 0)
        delta = max(0, pick - desc)
        if delta <= 0:
            continue
        cod = str(row["codigo"])
        items_actualizar.append((pick, int(row["id"])))
        delta_items[cod] = delta_items.get(cod, 0) + delta
        items_detalle.append((cod, str(row["descripcion"] or ""), delta))
        total_delta += delta

    return items_actualizar, delta_items, items_detalle, total_delta


def _ejecutar_cierre_plan_full(
    connection: sqlite3.Connection,
    plan_id: int,
    picker: str,
    es_final: bool,
) -> dict[str, Any]:
    """Ejecuta un cierre parcial o final de un plan Mercado Full dentro de una conexión."""
    plan = connection.execute(
        "SELECT * FROM planes_mercado_full WHERE id = ?",
        (plan_id,),
    ).fetchone()
    if not plan:
        return {"exito": False, "mensaje": "Plan de Mercado Full no encontrado."}

    estado_actual = str(plan["estado"] or "")
    if estado_actual == "cancelado":
        return {"exito": False, "mensaje": "El envío Full está cancelado."}
    if estado_actual == "completado":
        return {"exito": False, "mensaje": "El envío Full ya tuvo su cierre final."}

    items_actualizar, delta_items, items_detalle, total_delta = _recolectar_deltas_full(
        connection,
        plan_id,
    )
    if not es_final and total_delta <= 0:
        return {
            "exito": False,
            "mensaje": "No hay unidades pickeadas nuevas pendientes de descontar.",
            "delta_items": {},
            "items_detalle": [],
            "total_descontado": 0,
        }

    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    picker_limpio = picker.strip() or str(plan["picker_asignado"] or "")

    if items_actualizar:
        connection.executemany(
            "UPDATE plan_mercado_full_items SET cantidad_descontada = ? WHERE id = ?",
            items_actualizar,
        )

    tot, pick, desc_tot, porcentaje = recalcular_progreso_plan_full(connection, plan_id)
    nuevo_estado = "completado" if es_final else "en_proceso"
    tipo_cierre = "final" if es_final else "parcial"

    connection.execute(
        """
        UPDATE planes_mercado_full
        SET estado = ?,
            picker_asignado = COALESCE(NULLIF(?, ''), picker_asignado),
            updated_at = ?
        WHERE id = ?
        """,
        (nuevo_estado, picker_limpio, ahora, plan_id),
    )
    connection.execute(
        """
        INSERT INTO cierres_parciales_full (
            plan_id, tipo, picker, articulos_descontados, detalle_items, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            plan_id,
            tipo_cierre,
            picker_limpio,
            total_delta,
            json.dumps(delta_items, ensure_ascii=False),
            ahora,
        ),
    )

    accion = "CIERRE_FINAL_FULL" if es_final else "CIERRE_PARCIAL_FULL"
    detalle_log = (
        f"Envío Full #{plan_id} ({plan['nombre_envio']}) - cierre {tipo_cierre}: "
        f"{total_delta} un. descontadas en este lote ({porcentaje:.1f}% pickeado, "
        f"{desc_tot}/{tot} un. descontadas acumuladas)."
    )
    connection.execute(
        """
        INSERT INTO logs_auditoria (usuario, accion, detalle, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (picker_limpio or "Picker", accion, detalle_log, ahora),
    )

    return {
        "exito": True,
        "plan_id": plan_id,
        "nombre_envio": str(plan["nombre_envio"] or ""),
        "archivo_excel": str(plan["archivo_excel"] or "MercadoFull.xlsx"),
        "tipo": tipo_cierre,
        "estado": nuevo_estado,
        "total_descontado": total_delta,
        "delta_items": delta_items,
        "items_detalle": items_detalle,
        "acumulado_descontado": desc_tot,
        "articulos_pickeados": pick,
        "articulos_totales": tot,
        "porcentaje": porcentaje,
    }


def ejecutar_cierre_parcial_full(
    connection: sqlite3.Connection,
    plan_id: int,
    picker: str = "",
) -> dict[str, Any]:
    """Descuenta el delta pickeado del envío Full manteniendo el plan en proceso."""
    return _ejecutar_cierre_plan_full(connection, plan_id, picker=picker, es_final=False)


def ejecutar_cierre_final_full(
    connection: sqlite3.Connection,
    plan_id: int,
    picker: str = "",
) -> dict[str, Any]:
    """Descuenta cualquier delta pendiente y cierra definitivamente el envío Full."""
    return _ejecutar_cierre_plan_full(connection, plan_id, picker=picker, es_final=True)
