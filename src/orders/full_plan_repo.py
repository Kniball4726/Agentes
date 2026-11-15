"""Repositorio y lógica de negocio para planes guiados de Mercado Envíos Full."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from ..parsers.remito_parser import normalizar_codigo
from ..products.barcode_utils import coincide_codigo_o_barras


from .protocols import OrderConnectFn


class FullPlanRepository:
    """Repositorio que gestiona la creación, escaneo guiado y seguimiento en tiempo real de planes Mercado Full."""

    def __init__(self, connect_fn: OrderConnectFn) -> None:
        self._connect = connect_fn

    def crear_plan_mercado_full(
        self,
        nombre_envio: str,
        archivo_excel: str,
        creado_por: str,
        items: list[tuple[str, str, int]],
    ) -> int:
        """Crea un nuevo plan de preparación de Mercado Full a partir de una planilla."""
        if not items:
            raise ValueError("No se puede crear un plan Mercado Full sin artículos.")

        articulos_totales = sum(max(0, int(cant)) for _, _, cant in items)
        ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO planes_mercado_full (
                    nombre_envio, archivo_excel, creado_por, estado,
                    articulos_totales, articulos_pickeados, porcentaje,
                    picker_asignado, created_at, updated_at
                ) VALUES (?, ?, ?, 'pendiente', ?, 0, 0.0, '', ?, ?)
                """,
                (nombre_envio.strip() or "Envío Mercado Full", archivo_excel, creado_por, articulos_totales, ahora, ahora),
            )
            plan_id = cursor.lastrowid

            for cod, desc, cant in items:
                cant_val = max(0, int(cant))
                if cant_val <= 0:
                    continue
                connection.execute(
                    """
                    INSERT INTO plan_mercado_full_items (
                        plan_id, codigo, descripcion, cantidad_solicitada, cantidad_pickeada, completado
                    ) VALUES (?, ?, ?, ?, 0, 0)
                    """,
                    (plan_id, normalizar_codigo(cod), desc.strip(), cant_val),
                )
            connection.commit()

        return plan_id

    def obtener_plan_mercado_full(self, plan_id: int) -> dict[str, Any] | None:
        """Obtiene la información cabecera de un plan de Mercado Full por ID."""
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT id, nombre_envio, archivo_excel, creado_por, estado,
                       articulos_totales, articulos_pickeados, porcentaje,
                       picker_asignado, created_at, updated_at
                FROM planes_mercado_full
                WHERE id = ?
                """,
                (plan_id,),
            ).fetchone()
        if not row:
            return None
        return dict(row)

    def obtener_plan_activo_mercado_full(self) -> dict[str, Any] | None:
        """Obtiene el plan de Mercado Full más reciente que esté en proceso o pendiente."""
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT id, nombre_envio, archivo_excel, creado_por, estado,
                       articulos_totales, articulos_pickeados, porcentaje,
                       picker_asignado, created_at, updated_at
                FROM planes_mercado_full
                WHERE estado IN ('en_proceso', 'pendiente')
                ORDER BY id DESC
                LIMIT 1
                """
            ).fetchone()
        if not row:
            return None
        return dict(row)

    def listar_planes_mercado_full(self, estado: str | None = None) -> list[dict[str, Any]]:
        """Lista planes de Mercado Full ordenados por fecha descendente, opcionalmente filtrados por estado."""
        with self._connect() as connection:
            if estado:
                rows = connection.execute(
                    """
                    SELECT id, nombre_envio, archivo_excel, creado_por, estado,
                           articulos_totales, articulos_pickeados, porcentaje,
                           picker_asignado, created_at, updated_at
                    FROM planes_mercado_full
                    WHERE estado = ?
                    ORDER BY id DESC
                    """,
                    (estado,),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT id, nombre_envio, archivo_excel, creado_por, estado,
                           articulos_totales, articulos_pickeados, porcentaje,
                           picker_asignado, created_at, updated_at
                    FROM planes_mercado_full
                    ORDER BY id DESC
                    """
                ).fetchall()
        return [dict(r) for r in rows]

    def obtener_items_plan_full(self, plan_id: int) -> list[dict[str, Any]]:
        """Devuelve todos los artículos asociados a un plan de Mercado Full."""
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, plan_id, codigo, descripcion, cantidad_solicitada, cantidad_pickeada, completado
                FROM plan_mercado_full_items
                WHERE plan_id = ?
                ORDER BY completado ASC, id ASC
                """,
                (plan_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def registrar_escaneo_item_plan(
        self,
        plan_id: int,
        codigo_escaneado: str,
        cantidad: int = 1,
        picker: str = "",
    ) -> dict[str, Any]:
        """
        Registra el escaneo de un artículo en el plan de Mercado Full.
        Valida concordancia de código/SKU/código de barras y límites de cantidad.
        """
        codigo_limpio = normalizar_codigo(codigo_escaneado)
        if not codigo_limpio:
            return {"exito": False, "motivo": "codigo_vacio", "mensaje": "Código vacío o inválido."}

        with self._connect() as connection:
            # Obtener el plan
            plan_row = connection.execute(
                "SELECT id, estado, articulos_totales, articulos_pickeados, picker_asignado FROM planes_mercado_full WHERE id = ?",
                (plan_id,),
            ).fetchone()
            if not plan_row:
                return {"exito": False, "motivo": "plan_no_encontrado", "mensaje": f"Plan #{plan_id} no existe."}

            if plan_row["estado"] in ("completado", "cancelado"):
                return {"exito": False, "motivo": "plan_cerrado", "mensaje": f"El plan está en estado '{plan_row['estado']}'."}

            # Obtener items del plan
            items_rows = connection.execute(
                "SELECT id, codigo, descripcion, cantidad_solicitada, cantidad_pickeada, completado FROM plan_mercado_full_items WHERE plan_id = ?",
                (plan_id,),
            ).fetchall()

            # Buscar item coincidente
            matched_item = None
            for it in items_rows:
                it_cod = it["codigo"]
                if it_cod == codigo_limpio or coincide_codigo_o_barras(codigo_limpio, it_cod):
                    matched_item = it
                    break

            if not matched_item:
                return {
                    "exito": False,
                    "motivo": "no_encontrado",
                    "mensaje": f"El código '{codigo_escaneado}' no pertenece a este plan Full.",
                }

            item_id = matched_item["id"]
            cod_final = matched_item["codigo"]
            desc_final = matched_item["descripcion"]
            solicitada = int(matched_item["cantidad_solicitada"])
            actual = int(matched_item["cantidad_pickeada"])

            if actual >= solicitada:
                return {
                    "exito": False,
                    "motivo": "excedido",
                    "codigo": cod_final,
                    "descripcion": desc_final,
                    "cantidad_actual": actual,
                    "cantidad_solicitada": solicitada,
                    "mensaje": f"El producto [{cod_final}] ya completó su cuota ({solicitada} un.).",
                }

            nueva_cant = min(solicitada, actual + cantidad)
            completado = 1 if nueva_cant >= solicitada else 0

            connection.execute(
                "UPDATE plan_mercado_full_items SET cantidad_pickeada = ?, completado = ? WHERE id = ?",
                (nueva_cant, completado, item_id),
            )

            # Recalcular totales del plan
            total_pickeados = connection.execute(
                "SELECT SUM(cantidad_pickeada) as total FROM plan_mercado_full_items WHERE plan_id = ?",
                (plan_id,),
            ).fetchone()["total"] or 0

            art_totales = int(plan_row["articulos_totales"] or 0)
            nuevo_porcentaje = round((total_pickeados / art_totales * 100.0), 1) if art_totales > 0 else 100.0
            ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            picker_final = picker.strip() or plan_row["picker_asignado"] or "Picker"
            connection.execute(
                """
                UPDATE planes_mercado_full
                SET articulos_pickeados = ?,
                    porcentaje = ?,
                    picker_asignado = ?,
                    estado = 'en_proceso',
                    updated_at = ?
                WHERE id = ?
                """,
                (total_pickeados, nuevo_porcentaje, picker_final, ahora, plan_id),
            )
            connection.commit()

        return {
            "exito": True,
            "codigo": cod_final,
            "descripcion": desc_final,
            "cantidad_anterior": actual,
            "cantidad_actual": nueva_cant,
            "cantidad_solicitada": solicitada,
            "completado_item": bool(completado),
            "articulos_pickeados": total_pickeados,
            "articulos_totales": art_totales,
            "porcentaje": nuevo_porcentaje,
            "plan_completo": total_pickeados >= art_totales,
        }

    def ajustar_cantidad_item_plan(
        self,
        plan_id: int,
        codigo: str,
        nueva_cantidad: int,
        picker: str = "",
    ) -> dict[str, Any]:
        """Ajusta manualmente la cantidad pickeada de un producto en el plan."""
        codigo_limpio = normalizar_codigo(codigo)
        with self._connect() as connection:
            row = connection.execute(
                "SELECT id, codigo, descripcion, cantidad_solicitada FROM plan_mercado_full_items WHERE plan_id = ? AND codigo = ?",
                (plan_id, codigo_limpio),
            ).fetchone()
            if not row:
                return {"exito": False, "motivo": "no_encontrado"}

            solicitada = int(row["cantidad_solicitada"])
            cant_ajustada = max(0, min(solicitada, int(nueva_cantidad)))
            completado = 1 if cant_ajustada >= solicitada else 0

            connection.execute(
                "UPDATE plan_mercado_full_items SET cantidad_pickeada = ?, completado = ? WHERE id = ?",
                (cant_ajustada, completado, row["id"]),
            )

            total_pickeados = connection.execute(
                "SELECT SUM(cantidad_pickeada) as total FROM plan_mercado_full_items WHERE plan_id = ?",
                (plan_id,),
            ).fetchone()["total"] or 0

            art_totales = connection.execute(
                "SELECT articulos_totales FROM planes_mercado_full WHERE id = ?",
                (plan_id,),
            ).fetchone()["articulos_totales"] or 0

            porcentaje = round((total_pickeados / art_totales * 100.0), 1) if art_totales > 0 else 100.0
            ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            connection.execute(
                """
                UPDATE planes_mercado_full
                SET articulos_pickeados = ?,
                    porcentaje = ?,
                    picker_asignado = COALESCE(NULLIF(?, ''), picker_asignado),
                    updated_at = ?
                WHERE id = ?
                """,
                (total_pickeados, porcentaje, picker.strip(), ahora, plan_id),
            )
            connection.commit()

        return {
            "exito": True,
            "codigo": row["codigo"],
            "cantidad_actual": cant_ajustada,
            "cantidad_solicitada": solicitada,
            "articulos_pickeados": total_pickeados,
            "articulos_totales": art_totales,
            "porcentaje": porcentaje,
        }

    def finalizar_plan_mercado_full(self, plan_id: int, picker: str = "") -> bool:
        """Marca un plan de Mercado Full como completado."""
        ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE planes_mercado_full
                SET estado = 'completado',
                    picker_asignado = COALESCE(NULLIF(?, ''), picker_asignado),
                    updated_at = ?
                WHERE id = ? AND estado != 'cancelado'
                """,
                (picker.strip(), ahora, plan_id),
            )
            connection.commit()
            return cursor.rowcount > 0

    def cancelar_plan_mercado_full(self, plan_id: int) -> bool:
        """Cancela un plan de Mercado Full."""
        ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE planes_mercado_full SET estado = 'cancelado', updated_at = ? WHERE id = ?",
                (ahora, plan_id),
            )
            connection.commit()
            return cursor.rowcount > 0
