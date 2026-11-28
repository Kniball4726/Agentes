"""Repositorio desacoplado para estadísticas y flujo de stock en tiempo real (entradas vs salidas)."""

from __future__ import annotations

from datetime import datetime
import json
import logging
from typing import Any

from .protocols import OrderConnectFn

logger = logging.getLogger("stockagent.orders.flow")


class StockFlowRepository:
    """Repositorio para calcular analítica operativa de entradas y salidas en tiempo real."""

    def __init__(self, connect_fn: OrderConnectFn) -> None:
        self._connect = connect_fn

    def obtener_flujo_stock_diario(self, fecha: str = "") -> dict[str, Any]:
        """
        Calcula el balance y flujo de stock en tiempo real para una fecha (por defecto hoy 'YYYY-MM-DD').

        Retorna:
        - fecha: str
        - entradas_totales: int
        - salidas_totales: int
        - balance_neto: int (entradas - salidas)
        - bultos_totales: int
        - salidas_canales: dict[str, dict] (unidades, pedidos, ratio, porcentaje)
        - entradas_origen: dict[str, dict] (unidades, ratio, porcentaje)
        - top_salidas: list[dict] (codigo, descripcion, cantidad, porcentaje)
        - top_entradas: list[dict] (codigo, descripcion, cantidad, porcentaje)
        """
        dia = fecha.strip() or datetime.now().strftime("%Y-%m-%d")

        with self._connect() as connection:
            # -------------------------------------------------------------
            # 1. SALIDAS POR PEDIDOS (Mayoristas, ML, Canjes)
            # -------------------------------------------------------------
            rows_pedidos = connection.execute(
                """
                SELECT id, logistica, tipo_archivo, articulos_descontados, bultos, cierre_mercado_id
                FROM pedidos
                WHERE DATE(created_at, 'localtime') = ? AND estado != 'anulado'
                """,
                (dia,),
            ).fetchall()

            cant_ml = 0
            cant_canje = 0
            cant_mayorista = 0
            bultos_pedidos = 0

            p_ml = 0
            p_canje = 0
            p_mayorista = 0

            for p in rows_pedidos:
                cant = int(p["articulos_descontados"] or 0)
                b = int(p["bultos"] or 0)
                bultos_pedidos += b
                log = str(p["logistica"] or "").lower()
                tipo = str(p["tipo_archivo"] or "").lower()

                if "mercado libre" in log or tipo == "docx":
                    cant_ml += cant
                    p_ml += 1
                elif "canje" in log or tipo == "excel":
                    cant_canje += cant
                    p_canje += 1
                else:
                    cant_mayorista += cant
                    p_mayorista += 1

            # -------------------------------------------------------------
            # 2. SALIDAS POR MERCADO FULL
            # -------------------------------------------------------------
            row_full = connection.execute(
                """
                SELECT COALESCE(SUM(articulos_pickeados), 0) as cant_full, COUNT(*) as planes_count
                FROM planes_mercado_full
                WHERE (DATE(created_at) = ? OR DATE(updated_at) = ?) AND articulos_pickeados > 0
                """,
                (dia, dia),
            ).fetchone()
            cant_full = int(row_full["cant_full"] or 0)
            p_full = int(row_full["planes_count"] or 0)

            total_salidas = cant_ml + cant_canje + cant_mayorista + cant_full

            # -------------------------------------------------------------
            # 3. ENTRADAS: REMITOS DE FÁBRICA Y CIERRES
            # -------------------------------------------------------------
            rows_cierres_fab = connection.execute(
                """
                SELECT articulos_ingresados, detalle_items
                FROM cierres_parciales_fabrica
                WHERE DATE(created_at) = ?
                """,
                (dia,),
            ).fetchall()

            items_entradas_dict: dict[str, int] = {}
            unidades_fabrica = 0

            if rows_cierres_fab:
                for r in rows_cierres_fab:
                    unidades_fabrica += int(r["articulos_ingresados"] or 0)
                    try:
                        det = json.loads(r["detalle_items"] or "{}")
                        if isinstance(det, dict):
                            for cod, cant in det.items():
                                items_entradas_dict[str(cod)] = items_entradas_dict.get(str(cod), 0) + int(cant)
                    except (json.JSONDecodeError, TypeError, ValueError) as exc:
                        logger.warning("Detalle JSON inválido en cierres_parciales_fabrica (%s): %s", dia, exc)
            else:
                rows_planes_fab = connection.execute(
                    """
                    SELECT id, articulos_ingresados, articulos_controlados
                    FROM planes_ingreso_fabrica
                    WHERE (DATE(created_at) = ? OR DATE(updated_at) = ?) AND articulos_ingresados > 0
                    """,
                    (dia, dia),
                ).fetchall()
                for pf in rows_planes_fab:
                    unidades_fabrica += int(pf["articulos_ingresados"] or 0)
                    rows_it_fab = connection.execute(
                        "SELECT codigo, cantidad_ingresada FROM plan_ingreso_fabrica_items WHERE plan_id = ? AND cantidad_ingresada > 0",
                        (pf["id"],),
                    ).fetchall()
                    for itf in rows_it_fab:
                        c_it = str(itf["codigo"])
                        items_entradas_dict[c_it] = items_entradas_dict.get(c_it, 0) + int(itf["cantidad_ingresada"] or 0)

            total_entradas = unidades_fabrica
            balance_neto = total_entradas - total_salidas

            # -------------------------------------------------------------
            # 4. TOP SALIDAS (PRODUCTOS)
            # -------------------------------------------------------------
            rows_top_salidas = connection.execute(
                """
                SELECT pi.codigo, pi.descripcion, SUM(pi.cantidad) as cant
                FROM pedido_items pi
                JOIN pedidos p ON p.id = pi.pedido_id
                WHERE DATE(p.created_at, 'localtime') = ? AND p.estado != 'anulado'
                GROUP BY pi.codigo
                ORDER BY cant DESC
                LIMIT 5
                """,
                (dia,),
            ).fetchall()

            items_full_salidas = connection.execute(
                """
                SELECT pfi.codigo, pfi.descripcion, SUM(pfi.cantidad_pickeada) as cant
                FROM plan_mercado_full_items pfi
                JOIN planes_mercado_full pmf ON pmf.id = pfi.plan_id
                WHERE (DATE(pmf.created_at) = ? OR DATE(pmf.updated_at) = ?) AND pfi.cantidad_pickeada > 0
                GROUP BY pfi.codigo
                """,
                (dia, dia),
            ).fetchall()

            salidas_unificadas: dict[str, dict[str, Any]] = {}
            for r in rows_top_salidas:
                c = str(r["codigo"])
                salidas_unificadas[c] = {
                    "codigo": c,
                    "descripcion": str(r["descripcion"] or "Producto"),
                    "cantidad": int(r["cant"] or 0),
                }
            for rf in items_full_salidas:
                cf = str(rf["codigo"])
                if cf in salidas_unificadas:
                    salidas_unificadas[cf]["cantidad"] += int(rf["cant"] or 0)
                else:
                    salidas_unificadas[cf] = {
                        "codigo": cf,
                        "descripcion": str(rf["descripcion"] or "Producto Full"),
                        "cantidad": int(rf["cant"] or 0),
                    }

            top_salidas_sorted = sorted(salidas_unificadas.values(), key=lambda x: x["cantidad"], reverse=True)[:5]
            for it in top_salidas_sorted:
                it["porcentaje"] = round((it["cantidad"] / total_salidas * 100.0), 1) if total_salidas > 0 else 0.0

            # -------------------------------------------------------------
            # 5. TOP ENTRADAS (PRODUCTOS)
            # -------------------------------------------------------------
            top_entradas_sorted = []
            if items_entradas_dict:
                items_ordenados = sorted(items_entradas_dict.items(), key=lambda x: x[1], reverse=True)[:5]
                for cod, cant in items_ordenados:
                    row_desc = connection.execute(
                        "SELECT descripcion FROM plan_ingreso_fabrica_items WHERE codigo = ? LIMIT 1",
                        (cod,),
                    ).fetchone()
                    desc = str(row_desc["descripcion"]) if row_desc and row_desc["descripcion"] else "Producto Fábrica"
                    top_entradas_sorted.append({
                        "codigo": cod,
                        "descripcion": desc,
                        "cantidad": cant,
                        "porcentaje": round((cant / total_entradas * 100.0), 1) if total_entradas > 0 else 0.0,
                    })

            # -------------------------------------------------------------
            # 6. DISTRIBUCIÓN POR CANAL (RATIOS)
            # -------------------------------------------------------------
            def _calc_ratio(parcial: int, total: int) -> float:
                return round(parcial / total, 3) if total > 0 else 0.0

            def _calc_porc(parcial: int, total: int) -> float:
                return round((parcial / total * 100.0), 1) if total > 0 else 0.0

            salidas_canales = {
                "mercado_libre": {
                    "etiqueta": "Mercado Libre",
                    "unidades": cant_ml,
                    "pedidos": p_ml,
                    "ratio": _calc_ratio(cant_ml, total_salidas),
                    "porcentaje": _calc_porc(cant_ml, total_salidas),
                },
                "mercado_full": {
                    "etiqueta": "Mercado Full",
                    "unidades": cant_full,
                    "pedidos": p_full,
                    "ratio": _calc_ratio(cant_full, total_salidas),
                    "porcentaje": _calc_porc(cant_full, total_salidas),
                },
                "mayoristas": {
                    "etiqueta": "Mayoristas / Transporte",
                    "unidades": cant_mayorista,
                    "pedidos": p_mayorista,
                    "ratio": _calc_ratio(cant_mayorista, total_salidas),
                    "porcentaje": _calc_porc(cant_mayorista, total_salidas),
                },
                "canjes": {
                    "etiqueta": "Canjes y Retiros",
                    "unidades": cant_canje,
                    "pedidos": p_canje,
                    "ratio": _calc_ratio(cant_canje, total_salidas),
                    "porcentaje": _calc_porc(cant_canje, total_salidas),
                },
            }

            entradas_origen = {
                "fabrica": {
                    "etiqueta": "Ingresos de Fábrica",
                    "unidades": unidades_fabrica,
                    "ratio": 1.0 if total_entradas > 0 else 0.0,
                    "porcentaje": 100.0 if total_entradas > 0 else 0.0,
                },
            }

        return {
            "fecha": dia,
            "entradas_totales": total_entradas,
            "salidas_totales": total_salidas,
            "balance_neto": balance_neto,
            "bultos_totales": bultos_pedidos,
            "salidas_canales": salidas_canales,
            "entradas_origen": entradas_origen,
            "top_salidas": top_salidas_sorted,
            "top_entradas": top_entradas_sorted,
        }
