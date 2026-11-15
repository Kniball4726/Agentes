"""Repositorio y lógica de negocio para planes guiados de recepción y control de ingreso de fábrica."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from ..parsers.remito_parser import normalizar_codigo
from ..products.barcode_utils import coincide_codigo_o_barras


class FactoryPlanRepositoryMixin:
    """Mixin que gestiona la creación, control guiado y seguimiento en tiempo real de ingresos de fábrica."""

    def crear_plan_ingreso_fabrica(
        self,
        nombre_remito: str,
        archivo_remito: str,
        creado_por: str,
        items: list[tuple[str, str, int]],
    ) -> int:
        """Crea un nuevo plan de recepción y control de fábrica a partir de un remito o planilla."""
        if not items:
            raise ValueError("No se puede crear un plan de ingreso de fábrica sin artículos.")

        articulos_esperados = sum(max(0, int(cant)) for _, _, cant in items)
        ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO planes_ingreso_fabrica (
                    nombre_remito, archivo_remito, creado_por, estado,
                    articulos_esperados, articulos_controlados, articulos_ingresados, porcentaje,
                    picker_asignado, created_at, updated_at
                ) VALUES (?, ?, ?, 'pendiente', ?, 0, 0, 0.0, '', ?, ?)
                """,
                (nombre_remito.strip() or "Remito Fábrica", archivo_remito, creado_por, articulos_esperados, ahora, ahora),
            )
            plan_id = cursor.lastrowid

            for cod, desc, cant in items:
                cant_val = max(0, int(cant))
                if cant_val <= 0:
                    continue
                connection.execute(
                    """
                    INSERT INTO plan_ingreso_fabrica_items (
                        plan_id, codigo, descripcion, cantidad_esperada, cantidad_controlada, cantidad_ingresada, completado
                    ) VALUES (?, ?, ?, ?, 0, 0, 0)
                    """,
                    (plan_id, normalizar_codigo(cod), desc.strip(), cant_val),
                )
            connection.commit()

        return plan_id

    def obtener_plan_ingreso_fabrica(self, plan_id: int) -> dict[str, Any] | None:
        """Obtiene la cabecera de un plan de ingreso de fábrica por ID."""
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT id, nombre_remito, archivo_remito, creado_por, estado,
                       articulos_esperados, articulos_controlados, articulos_ingresados, porcentaje,
                       picker_asignado, created_at, updated_at
                FROM planes_ingreso_fabrica
                WHERE id = ?
                """,
                (plan_id,),
            ).fetchone()
        if not row:
            return None
        return dict(row)

    def obtener_plan_activo_ingreso_fabrica(self) -> dict[str, Any] | None:
        """Obtiene el plan de ingreso de fábrica más reciente en proceso o pendiente."""
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT id, nombre_remito, archivo_remito, creado_por, estado,
                       articulos_esperados, articulos_controlados, articulos_ingresados, porcentaje,
                       picker_asignado, created_at, updated_at
                FROM planes_ingreso_fabrica
                WHERE estado IN ('en_proceso', 'pendiente')
                ORDER BY id DESC
                LIMIT 1
                """
            ).fetchone()
        if not row:
            return None
        return dict(row)

    def listar_planes_ingreso_fabrica(self, estado: str | None = None) -> list[dict[str, Any]]:
        """Lista planes de ingreso de fábrica ordenados por fecha descendente."""
        with self._connect() as connection:
            if estado:
                rows = connection.execute(
                    """
                    SELECT id, nombre_remito, archivo_remito, creado_por, estado,
                           articulos_esperados, articulos_controlados, articulos_ingresados, porcentaje,
                           picker_asignado, created_at, updated_at
                    FROM planes_ingreso_fabrica
                    WHERE estado = ?
                    ORDER BY id DESC
                    """,
                    (estado,),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT id, nombre_remito, archivo_remito, creado_por, estado,
                           articulos_esperados, articulos_controlados, articulos_ingresados, porcentaje,
                           picker_asignado, created_at, updated_at
                    FROM planes_ingreso_fabrica
                    ORDER BY id DESC
                    """
                ).fetchall()
        return [dict(r) for r in rows]

    def obtener_items_plan_ingreso_fabrica(self, plan_id: int) -> list[dict[str, Any]]:
        """Devuelve todos los artículos asociados a un plan de ingreso de fábrica."""
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, plan_id, codigo, descripcion, cantidad_esperada, cantidad_controlada, cantidad_ingresada, completado
                FROM plan_ingreso_fabrica_items
                WHERE plan_id = ?
                ORDER BY completado ASC, id ASC
                """,
                (plan_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def registrar_escaneo_item_ingreso_fabrica(
        self,
        plan_id: int,
        codigo_escaneado: str,
        cantidad: int = 1,
        picker: str = "",
    ) -> dict[str, Any]:
        """
        Registra el escaneo y verificación física de un artículo en el remito de fábrica.
        Valida que el artículo pertenezca al remito y no exceda la cuota declarada.
        """
        codigo_limpio = normalizar_codigo(codigo_escaneado)
        if not codigo_limpio:
            return {"exito": False, "motivo": "codigo_vacio", "mensaje": "Código vacío o inválido."}

        with self._connect() as connection:
            plan_row = connection.execute(
                "SELECT id, estado, articulos_esperados, articulos_controlados, picker_asignado FROM planes_ingreso_fabrica WHERE id = ?",
                (plan_id,),
            ).fetchone()
            if not plan_row:
                return {"exito": False, "motivo": "plan_no_encontrado", "mensaje": f"Remito #{plan_id} no existe."}

            if plan_row["estado"] in ("completado", "cancelado"):
                return {"exito": False, "motivo": "plan_cerrado", "mensaje": f"El remito está en estado '{plan_row['estado']}'."}

            items_rows = connection.execute(
                "SELECT id, codigo, descripcion, cantidad_esperada, cantidad_controlada, completado FROM plan_ingreso_fabrica_items WHERE plan_id = ?",
                (plan_id,),
            ).fetchall()

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
                    "mensaje": f"El código '{codigo_escaneado}' no figura en este remito de fábrica.",
                }

            item_id = matched_item["id"]
            cod_final = matched_item["codigo"]
            desc_final = matched_item["descripcion"]
            esperada = int(matched_item["cantidad_esperada"])
            actual = int(matched_item["cantidad_controlada"])

            if actual >= esperada:
                return {
                    "exito": False,
                    "motivo": "excedido",
                    "codigo": cod_final,
                    "descripcion": desc_final,
                    "cantidad_actual": actual,
                    "cantidad_esperada": esperada,
                    "mensaje": f"El producto [{cod_final}] ya completó su cantidad esperada ({esperada} un.).",
                }

            nueva_cant = min(esperada, actual + cantidad)
            completado = 1 if nueva_cant >= esperada else 0

            connection.execute(
                "UPDATE plan_ingreso_fabrica_items SET cantidad_controlada = ?, completado = ? WHERE id = ?",
                (nueva_cant, completado, item_id),
            )

            total_controlados = connection.execute(
                "SELECT SUM(cantidad_controlada) as total FROM plan_ingreso_fabrica_items WHERE plan_id = ?",
                (plan_id,),
            ).fetchone()["total"] or 0

            art_esperados = int(plan_row["articulos_esperados"] or 0)
            nuevo_porcentaje = round((total_controlados / art_esperados * 100.0), 1) if art_esperados > 0 else 100.0
            ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            picker_final = picker.strip() or plan_row["picker_asignado"] or "Picker"
            connection.execute(
                """
                UPDATE planes_ingreso_fabrica
                SET articulos_controlados = ?,
                    porcentaje = ?,
                    picker_asignado = ?,
                    estado = 'en_proceso',
                    updated_at = ?
                WHERE id = ?
                """,
                (total_controlados, nuevo_porcentaje, picker_final, ahora, plan_id),
            )
            connection.commit()

        return {
            "exito": True,
            "codigo": cod_final,
            "descripcion": desc_final,
            "cantidad_anterior": actual,
            "cantidad_actual": nueva_cant,
            "cantidad_esperada": esperada,
            "completado_item": bool(completado),
            "articulos_controlados": total_controlados,
            "articulos_esperados": art_esperados,
            "porcentaje": nuevo_porcentaje,
            "plan_completo": total_controlados >= art_esperados,
        }

    def ajustar_cantidad_item_ingreso_fabrica(
        self,
        plan_id: int,
        codigo: str,
        nueva_cantidad: int,
        picker: str = "",
    ) -> dict[str, Any]:
        """Ajusta manualmente la cantidad controlada de un producto en el remito de fábrica."""
        codigo_limpio = normalizar_codigo(codigo)
        with self._connect() as connection:
            row = connection.execute(
                "SELECT id, codigo, descripcion, cantidad_esperada FROM plan_ingreso_fabrica_items WHERE plan_id = ? AND codigo = ?",
                (plan_id, codigo_limpio),
            ).fetchone()
            if not row:
                return {"exito": False, "motivo": "no_encontrado"}

            esperada = int(row["cantidad_esperada"])
            cant_ajustada = max(0, min(esperada, int(nueva_cantidad)))
            completado = 1 if cant_ajustada >= esperada else 0

            connection.execute(
                "UPDATE plan_ingreso_fabrica_items SET cantidad_controlada = ?, completado = ? WHERE id = ?",
                (cant_ajustada, completado, row["id"]),
            )

            total_controlados = connection.execute(
                "SELECT SUM(cantidad_controlada) as total FROM plan_ingreso_fabrica_items WHERE plan_id = ?",
                (plan_id,),
            ).fetchone()["total"] or 0

            art_esperados = connection.execute(
                "SELECT articulos_esperados FROM planes_ingreso_fabrica WHERE id = ?",
                (plan_id,),
            ).fetchone()["articulos_esperados"] or 0

            porcentaje = round((total_controlados / art_esperados * 100.0), 1) if art_esperados > 0 else 100.0
            ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            connection.execute(
                """
                UPDATE planes_ingreso_fabrica
                SET articulos_controlados = ?,
                    porcentaje = ?,
                    picker_asignado = COALESCE(NULLIF(?, ''), picker_asignado),
                    updated_at = ?
                WHERE id = ?
                """,
                (total_controlados, porcentaje, picker.strip(), ahora, plan_id),
            )
            connection.commit()

        return {
            "exito": True,
            "codigo": row["codigo"],
            "cantidad_actual": cant_ajustada,
            "cantidad_esperada": esperada,
            "articulos_controlados": total_controlados,
            "articulos_esperados": art_esperados,
            "porcentaje": porcentaje,
        }

    def registrar_cierre_parcial_ingreso_fabrica(
        self,
        plan_id: int,
        picker: str = "",
    ) -> dict[str, Any]:
        """
        Registra un cierre parcial diario para un plan de ingreso de fábrica en proceso.
        Calcula las unidades verificadas que aún no fueron ingresadas a stock
        (cantidad_controlada - cantidad_ingresada), actualiza cantidad_ingresada en DB,
        registra el evento en cierres_parciales_fabrica y logs_auditoria,
        y devuelve el diccionario {codigo: cantidad_a_sumar} para acreditar al inventario.
        El plan se mantiene en estado 'en_proceso' para continuar los días siguientes.
        """
        import json
        ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._connect() as connection:
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
                """
                SELECT id, codigo, descripcion, cantidad_esperada, cantidad_controlada, cantidad_ingresada
                FROM plan_ingreso_fabrica_items
                WHERE plan_id = ?
                """,
                (plan_id,),
            ).fetchall()

            items_a_ingresar: dict[str, int] = {}
            for it in items_rows:
                ctrl = int(it["cantidad_controlada"] or 0)
                ingr = int(it["cantidad_ingresada"] or 0)
                dif = ctrl - ingr
                if dif > 0:
                    items_a_ingresar[it["codigo"]] = dif
                    connection.execute(
                        "UPDATE plan_ingreso_fabrica_items SET cantidad_ingresada = ? WHERE id = ?",
                        (ctrl, it["id"]),
                    )

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

            connection.execute(
                """
                INSERT INTO cierres_parciales_fabrica (plan_id, tipo, picker, articulos_ingresados, detalle_items, created_at)
                VALUES (?, 'parcial', ?, ?, ?, ?)
                """,
                (plan_id, picker_final, total_parcial, json.dumps(items_a_ingresar), ahora),
            )

            connection.execute(
                """
                INSERT INTO logs_auditoria (usuario, accion, detalle, created_at)
                VALUES (?, 'CIERRE_PARCIAL_FABRICA', ?, ?)
                """,
                (
                    picker_final,
                    f"Cierre parcial remito #{plan_id}: +{total_parcial} un. ingresadas ({len(items_a_ingresar)} ítems). Total acumulado: {nuevo_total_ingresados} un.",
                    ahora,
                ),
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

    def finalizar_plan_ingreso_fabrica(self, plan_id: int, picker: str = "") -> dict[str, Any]:
        """
        Marca un plan de ingreso de fábrica como completado y devuelve el detalle
        de los artículos controlados físicamente pendientes de acreditar en el inventario.
        Si se hicieron cierres parciales previos, solo acredita el remanente no ingresado.
        """
        import json
        ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._connect() as connection:
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
                """
                SELECT id, codigo, descripcion, cantidad_esperada, cantidad_controlada, cantidad_ingresada
                FROM plan_ingreso_fabrica_items
                WHERE plan_id = ?
                """,
                (plan_id,),
            ).fetchall()

            # Determinar unidades pendientes que no fueron ingresadas en cierres parciales
            items_a_ingresar: dict[str, int] = {}
            for it in items_rows:
                ctrl = int(it["cantidad_controlada"] or 0)
                ingr = int(it["cantidad_ingresada"] or 0)
                dif = ctrl - ingr
                if dif > 0:
                    items_a_ingresar[it["codigo"]] = dif
                connection.execute(
                    "UPDATE plan_ingreso_fabrica_items SET cantidad_ingresada = ? WHERE id = ?",
                    (ctrl, it["id"]),
                )

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

            connection.execute(
                """
                INSERT INTO cierres_parciales_fabrica (plan_id, tipo, picker, articulos_ingresados, detalle_items, created_at)
                VALUES (?, 'final', ?, ?, ?, ?)
                """,
                (plan_id, picker_final, total_final_a_ingresar, json.dumps(items_a_ingresar), ahora),
            )

            connection.execute(
                """
                INSERT INTO logs_auditoria (usuario, accion, detalle, created_at)
                VALUES (?, 'CIERRE_FINAL_FABRICA', ?, ?)
                """,
                (
                    picker_final,
                    f"Cierre final remito #{plan_id}: +{total_final_a_ingresar} un. restantes ingresadas. Total verificado ingresado: {nuevo_total_ingresados} un.",
                    ahora,
                ),
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

    def listar_cierres_parciales_fabrica(self, plan_id: int) -> list[dict[str, Any]]:
        """Devuelve el historial de cierres (parciales y final) de un remito de fábrica."""
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, plan_id, tipo, picker, articulos_ingresados, detalle_items, created_at
                FROM cierres_parciales_fabrica
                WHERE plan_id = ?
                ORDER BY id ASC
                """,
                (plan_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def cancelar_plan_ingreso_fabrica(self, plan_id: int) -> bool:
        """Cancela un plan de ingreso de fábrica."""
        ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE planes_ingreso_fabrica SET estado = 'cancelado', updated_at = ? WHERE id = ?",
                (ahora, plan_id),
            )
            connection.commit()
            return cursor.rowcount > 0
