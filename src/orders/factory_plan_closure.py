"""Helpers compartidos de cálculo de progreso y cierres parciales/finales para planes de ingreso de fábrica."""

from __future__ import annotations

from datetime import datetime
import json
import sqlite3
from typing import Any

from .protocols import OrderConnectFn

PLAN_HEADER_COLUMNS = (
    "id, nombre_remito, archivo_remito, creado_por, estado, "
    "articulos_esperados, articulos_controlados, articulos_ingresados, porcentaje, "
    "picker_asignado, created_at, updated_at"
)

_PLAN_ITEM_COLUMNS = (
    "id, codigo, descripcion, cantidad_esperada, cantidad_controlada, cantidad_ingresada"
)


def recalcular_progreso_plan_fabrica(
    connection: sqlite3.Connection,
    plan_id: int,
    art_esperados: int | None = None,
    picker: str = "",
    nuevo_estado: str | None = None,
) -> tuple[int, int, float]:
    """Recalcula el total controlado y porcentaje del plan de ingreso y actualiza la cabecera."""
    total_controlados = (
        connection.execute(
            "SELECT SUM(cantidad_controlada) as total FROM plan_ingreso_fabrica_items WHERE plan_id = ?",
            (plan_id,),
        ).fetchone()["total"]
        or 0
    )

    if art_esperados is None:
        row_esp = connection.execute(
            "SELECT articulos_esperados FROM planes_ingreso_fabrica WHERE id = ?",
            (plan_id,),
        ).fetchone()
        esperados = int((row_esp["articulos_esperados"] if row_esp else 0) or 0)
    else:
        esperados = int(art_esperados or 0)

    porcentaje = round((total_controlados / esperados * 100.0), 1) if esperados > 0 else 100.0
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    picker_limpio = picker.strip()

    if nuevo_estado is not None:
        connection.execute(
            """
            UPDATE planes_ingreso_fabrica
            SET articulos_controlados = ?,
                porcentaje = ?,
                picker_asignado = COALESCE(NULLIF(?, ''), picker_asignado),
                estado = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (total_controlados, porcentaje, picker_limpio, nuevo_estado, ahora, plan_id),
        )
    else:
        connection.execute(
            """
            UPDATE planes_ingreso_fabrica
            SET articulos_controlados = ?,
                porcentaje = ?,
                picker_asignado = COALESCE(NULLIF(?, ''), picker_asignado),
                updated_at = ?
            WHERE id = ?
            """,
            (total_controlados, porcentaje, picker_limpio, ahora, plan_id),
        )

    return total_controlados, esperados, porcentaje


def _acreditar_delta_items_fabrica(
    connection: sqlite3.Connection,
    items_rows: list[sqlite3.Row],
    actualizar_todos: bool,
) -> dict[str, int]:
    """Calcula unidades verificadas pendientes de acreditar y actualiza `cantidad_ingresada`."""
    items_a_ingresar: dict[str, int] = {}
    for it in items_rows:
        ctrl = int(it["cantidad_controlada"] or 0)
        ingr = int(it["cantidad_ingresada"] or 0)
        dif = ctrl - ingr
        if dif > 0:
            items_a_ingresar[it["codigo"]] = dif
            if not actualizar_todos:
                connection.execute(
                    "UPDATE plan_ingreso_fabrica_items SET cantidad_ingresada = ? WHERE id = ?",
                    (ctrl, it["id"]),
                )
        if actualizar_todos:
            connection.execute(
                "UPDATE plan_ingreso_fabrica_items SET cantidad_ingresada = ? WHERE id = ?",
                (ctrl, it["id"]),
            )
    return items_a_ingresar


def _registrar_evento_cierre_fabrica(
    connection: sqlite3.Connection,
    plan_id: int,
    tipo: str,
    picker_final: str,
    cantidad_acreditada: int,
    items_a_ingresar: dict[str, int],
    accion_auditoria: str,
    detalle_auditoria: str,
    ahora: str,
) -> None:
    """Inserta el registro del cierre parcial o final y su entrada en `logs_auditoria`."""
    connection.execute(
        """
        INSERT INTO cierres_parciales_fabrica (plan_id, tipo, picker, articulos_ingresados, detalle_items, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (plan_id, tipo, picker_final, cantidad_acreditada, json.dumps(items_a_ingresar), ahora),
    )
    connection.execute(
        """
        INSERT INTO logs_auditoria (usuario, accion, detalle, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (picker_final, accion_auditoria, detalle_auditoria, ahora),
    )


def ejecutar_cierre_parcial_fabrica(
    connect_fn: OrderConnectFn,
    plan_id: int,
    picker: str = "",
) -> dict[str, Any]:
    """Registra un cierre parcial diario y devuelve `{codigo: cantidad}` pendiente por ingresar."""
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with connect_fn() as connection:
        plan_row = connection.execute(
            """
            SELECT id, nombre_remito, archivo_remito, articulos_esperados,
                   articulos_controlados, articulos_ingresados, estado, picker_asignado
            FROM planes_ingreso_fabrica
            WHERE id = ?
            """,
            (plan_id,),
        ).fetchone()
        if not plan_row:
            return {"exito": False, "motivo": "no_encontrado", "mensaje": f"Remito #{plan_id} no existe."}

        if plan_row["estado"] in ("completado", "cancelado"):
            return {"exito": False, "motivo": "plan_cerrado", "mensaje": f"El remito ya está en estado '{plan_row['estado']}'."}

        items_rows = connection.execute(
            f"SELECT {_PLAN_ITEM_COLUMNS} FROM plan_ingreso_fabrica_items WHERE plan_id = ?",
            (plan_id,),
        ).fetchall()

        items_a_ingresar = _acreditar_delta_items_fabrica(connection, items_rows, actualizar_todos=False)
        if not items_a_ingresar:
            return {
                "exito": False,
                "motivo": "sin_pendientes",
                "mensaje": "No hay nuevas unidades verificadas pendientes de ingresar a stock.",
            }

        total_parcial = sum(items_a_ingresar.values())
        nuevo_total_ingresados = int(plan_row["articulos_ingresados"] or 0) + total_parcial
        picker_final = picker.strip() or plan_row["picker_asignado"] or "Picker"

        connection.execute(
            """
            UPDATE planes_ingreso_fabrica
            SET articulos_ingresados = ?,
                picker_asignado = ?,
                estado = 'en_proceso',
                updated_at = ?
            WHERE id = ?
            """,
            (nuevo_total_ingresados, picker_final, ahora, plan_id),
        )
        _registrar_evento_cierre_fabrica(
            connection=connection,
            plan_id=plan_id,
            tipo="parcial",
            picker_final=picker_final,
            cantidad_acreditada=total_parcial,
            items_a_ingresar=items_a_ingresar,
            accion_auditoria="CIERRE_PARCIAL_FABRICA",
            detalle_auditoria=(
                f"Cierre parcial remito #{plan_id}: +{total_parcial} un. ingresadas "
                f"({len(items_a_ingresar)} ítems). Total acumulado: {nuevo_total_ingresados} un."
            ),
            ahora=ahora,
        )
        connection.commit()

    return {
        "exito": True,
        "plan_id": plan_id,
        "nombre_remito": plan_row["nombre_remito"],
        "items_a_ingresar": items_a_ingresar,
        "items_controlados": items_a_ingresar,
        "articulos_ingresados_parcial": total_parcial,
        "articulos_ingresados_acumulado": nuevo_total_ingresados,
        "articulos_controlados": plan_row["articulos_controlados"],
        "articulos_esperados": plan_row["articulos_esperados"],
    }


def ejecutar_cierre_final_fabrica(
    connect_fn: OrderConnectFn,
    plan_id: int,
    picker: str = "",
) -> dict[str, Any]:
    """Finaliza un plan de ingreso de fábrica acreditando solo el remanente pendiente."""
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with connect_fn() as connection:
        plan_row = connection.execute(
            """
            SELECT id, nombre_remito, archivo_remito, articulos_esperados,
                   articulos_controlados, articulos_ingresados, picker_asignado
            FROM planes_ingreso_fabrica
            WHERE id = ?
            """,
            (plan_id,),
        ).fetchone()
        if not plan_row:
            return {"exito": False, "motivo": "no_encontrado"}

        items_rows = connection.execute(
            f"SELECT {_PLAN_ITEM_COLUMNS} FROM plan_ingreso_fabrica_items WHERE plan_id = ?",
            (plan_id,),
        ).fetchall()

        items_a_ingresar = _acreditar_delta_items_fabrica(connection, items_rows, actualizar_todos=True)
        total_final_a_ingresar = sum(items_a_ingresar.values())
        nuevo_total_ingresados = int(plan_row["articulos_controlados"] or 0)
        picker_final = picker.strip() or plan_row["picker_asignado"] or "Picker"

        connection.execute(
            """
            UPDATE planes_ingreso_fabrica
            SET estado = 'completado',
                articulos_ingresados = ?,
                picker_asignado = COALESCE(NULLIF(?, ''), picker_asignado),
                updated_at = ?
            WHERE id = ? AND estado != 'cancelado'
            """,
            (nuevo_total_ingresados, picker_final, ahora, plan_id),
        )
        _registrar_evento_cierre_fabrica(
            connection=connection,
            plan_id=plan_id,
            tipo="final",
            picker_final=picker_final,
            cantidad_acreditada=total_final_a_ingresar,
            items_a_ingresar=items_a_ingresar,
            accion_auditoria="CIERRE_FINAL_FABRICA",
            detalle_auditoria=(
                f"Cierre final remito #{plan_id}: +{total_final_a_ingresar} un. restantes ingresadas. "
                f"Total verificado ingresado: {nuevo_total_ingresados} un."
            ),
            ahora=ahora,
        )
        connection.commit()

    return {
        "exito": True,
        "plan_id": plan_id,
        "nombre_remito": plan_row["nombre_remito"],
        "archivo_remito": plan_row["archivo_remito"],
        "items_controlados": items_a_ingresar,
        "items_totales_controlados": {
            r["codigo"]: int(r["cantidad_controlada"])
            for r in items_rows
            if int(r["cantidad_controlada"]) > 0
        },
        "articulos_controlados": plan_row["articulos_controlados"],
        "articulos_esperados": plan_row["articulos_esperados"],
        "articulos_ingresados_final": total_final_a_ingresar,
        "articulos_ingresados_total": nuevo_total_ingresados,
        "detalle_items": [dict(r) for r in items_rows],
    }
