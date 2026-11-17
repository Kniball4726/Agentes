"""Repositorio de consultas analíticas y de reportes sobre movimientos e inventario en SQLite."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from typing import Any, Callable


def _estado_inventario_label(stock: int, stock_minimo: int, stock_maximo: int) -> str:
    if stock <= 0:
        return "AGOTADO"
    if stock <= stock_minimo:
        return "QUIEBRE_INMINENTE"
    if stock > stock_maximo:
        return "SOBRESTOCK"
    return "OPTIMO"


def _unir_textos_unicos(valores: list[str], limite: int = 3) -> str:
    unicos: list[str] = []
    for raw in valores:
        txt = (raw or "").strip()
        if txt and txt not in unicos:
            unicos.append(txt)
    if not unicos:
        return "-"
    if len(unicos) <= limite:
        return ", ".join(unicos)
    return ", ".join(unicos[:limite]) + f" (+{len(unicos) - limite})"


class MovementsReportRepository:
    """Provee consultas consolidadas de salidas, ingresos, kardex y rotación sin dependencia de Excel."""

    def __init__(self, connect_fn: Callable[[], sqlite3.Connection]) -> None:
        self._connect = connect_fn

    def get_period_movements_summary(
        self,
        date_from: str,
        date_to: str,
        order_by: str = "catalog",
        strict_after_from: bool = False,
    ) -> dict[str, Any]:
        """Consolida únicamente productos con salidas o ingresos en la ventana especificada."""
        desde_iso = date_from if "T" in date_from else f"{date_from}T00:00:00"
        hasta_iso = date_to if "T" in date_to else f"{date_to}T23:59:59"
        op_desde = ">" if strict_after_from else ">="

        with closing(self._connect()) as connection:
            movs = connection.execute(
                f"""
                SELECT
                    m.product_code,
                    m.product_name,
                    m.quantity,
                    m.movement_type,
                    m.usuario,
                    m.detalle,
                    m.registered_at
                FROM stock_movements m
                WHERE m.registered_at {op_desde} ?
                  AND m.registered_at <= ?
                ORDER BY m.registered_at ASC, m.id ASC
                """,
                (desde_iso, hasta_iso),
            ).fetchall()

            if not movs:
                return {
                    "salidas": [],
                    "ingresos": [],
                    "resumen_productos": [],
                    "kpis": {
                        "skus_salida": 0,
                        "unidades_salida": 0,
                        "skus_ingreso": 0,
                        "unidades_ingreso": 0,
                        "variacion_neta": 0,
                    },
                }

            codigos = sorted({str(r["product_code"]) for r in movs if r["product_code"]})
            placeholders = ",".join("?" * len(codigos))

            prod_rows = connection.execute(
                f"""
                SELECT
                    p.code,
                    p.name,
                    p.stock,
                    p.stock_minimo,
                    p.stock_maximo,
                    p.ubicacion,
                    COALESCE(cr.min_order, 999999) AS display_order
                FROM products p
                LEFT JOIN (
                    SELECT product_code, MIN(display_order) AS min_order
                    FROM product_catalog_rows
                    GROUP BY product_code
                ) cr ON cr.product_code = p.code
                WHERE p.code IN ({placeholders})
                """,
                codigos,
            ).fetchall()
            mapa_prod = {str(r["code"]): dict(r) for r in prod_rows}

            after_rows = connection.execute(
                f"""
                SELECT product_code, COALESCE(SUM(quantity), 0) AS delta_after
                FROM stock_movements
                WHERE product_code IN ({placeholders})
                  AND registered_at > ?
                GROUP BY product_code
                """,
                (*codigos, hasta_iso),
            ).fetchall()
            delta_after_map = {str(r["product_code"]): int(r["delta_after"] or 0) for r in after_rows}

        por_sku: dict[str, dict[str, Any]] = {}
        for r in movs:
            cod = str(r["product_code"] or "").strip()
            if not cod:
                continue
            qty = int(r["quantity"] or 0)
            if qty == 0:
                continue

            entry = por_sku.get(cod)
            if entry is None:
                p_info = mapa_prod.get(cod, {})
                stock_actual = int(p_info.get("stock", 0) or 0)
                stock_min = int(p_info.get("stock_minimo", 5) or 5)
                stock_max = int(p_info.get("stock_maximo", 100) or 100)
                stock_cierre = stock_actual - delta_after_map.get(cod, 0)
                entry = {
                    "code": cod,
                    "name": str(p_info.get("name") or r["product_name"] or cod),
                    "ubicacion": str(p_info.get("ubicacion") or ""),
                    "display_order": int(p_info.get("display_order", 999999) or 999999),
                    "stock_minimo": stock_min,
                    "stock_maximo": stock_max,
                    "stock_cierre": stock_cierre,
                    "stock_inicial": stock_cierre,
                    "cantidad_salida": 0,
                    "cantidad_ingreso": 0,
                    "variacion_neta": 0,
                    "detalles_salida": [],
                    "detalles_ingreso": [],
                    "usuarios": [],
                    "estado_inventario": _estado_inventario_label(stock_cierre, stock_min, stock_max),
                }
                por_sku[cod] = entry

            etiqueta_origen = str(r["detalle"] or "").strip() or str(r["movement_type"] or "").strip()
            usr = str(r["usuario"] or "").strip()
            if usr and usr != "sistema":
                entry["usuarios"].append(usr)

            if qty < 0:
                entry["cantidad_salida"] += abs(qty)
                if etiqueta_origen:
                    entry["detalles_salida"].append(etiqueta_origen)
            else:
                entry["cantidad_ingreso"] += qty
                if etiqueta_origen:
                    entry["detalles_ingreso"].append(etiqueta_origen)
            entry["variacion_neta"] += qty

        resumen_lista: list[dict[str, Any]] = []
        for entry in por_sku.values():
            entry["stock_inicial"] = entry["stock_cierre"] - entry["variacion_neta"]
            entry["origen_salida"] = _unir_textos_unicos(entry["detalles_salida"])
            entry["origen_ingreso"] = _unir_textos_unicos(entry["detalles_ingreso"])
            entry["responsables"] = _unir_textos_unicos(entry["usuarios"] or ["sistema"])
            resumen_lista.append(entry)

        clave_orden = (order_by or "catalog").strip().lower()
        if clave_orden == "ubicacion":
            resumen_lista.sort(key=lambda x: (x["ubicacion"] or "ZZZ", x["display_order"], x["code"]))
        elif clave_orden == "alpha":
            resumen_lista.sort(key=lambda x: (x["name"].lower(), x["code"]))
        elif clave_orden == "volume":
            resumen_lista.sort(key=lambda x: (-x["cantidad_salida"], -x["cantidad_ingreso"], x["code"]))
        else:
            resumen_lista.sort(key=lambda x: (x["display_order"], x["code"]))

        salidas = [dict(x) for x in resumen_lista if x["cantidad_salida"] > 0]
        ingresos = [dict(x) for x in resumen_lista if x["cantidad_ingreso"] > 0]
        if clave_orden == "volume":
            ingresos.sort(key=lambda x: (-x["cantidad_ingreso"], x["code"]))

        total_sal = sum(x["cantidad_salida"] for x in salidas)
        total_ing = sum(x["cantidad_ingreso"] for x in ingresos)
        return {
            "salidas": salidas,
            "ingresos": ingresos,
            "resumen_productos": resumen_lista,
            "kpis": {
                "skus_salida": len(salidas),
                "unidades_salida": total_sal,
                "skus_ingreso": len(ingresos),
                "unidades_ingreso": total_ing,
                "variacion_neta": total_ing - total_sal,
            },
        }

    def get_product_kardex(
        self,
        product_query: str,
        date_from: str = "",
        date_to: str = "",
        limit: int = 300,
    ) -> dict[str, Any]:
        """Obtiene la ficha de producto y su historial cronológico de movimientos con saldo."""
        q = (product_query or "").strip()
        if not q:
            return {"producto": None, "movimientos": []}

        with closing(self._connect()) as connection:
            prod = connection.execute(
                """
                SELECT code, name, stock, stock_minimo, stock_maximo, ubicacion, cod_barras, active
                FROM products
                WHERE UPPER(code) = UPPER(?) OR cod_barras = ?
                LIMIT 1
                """,
                (q, q),
            ).fetchone()
            if prod is None:
                patron = f"%{q}%"
                prod = connection.execute(
                    """
                    SELECT code, name, stock, stock_minimo, stock_maximo, ubicacion, cod_barras, active
                    FROM products
                    WHERE UPPER(code) LIKE UPPER(?) OR UPPER(name) LIKE UPPER(?)
                    ORDER BY active DESC, code ASC
                    LIMIT 1
                    """,
                    (patron, patron),
                ).fetchone()
            if prod is None:
                return {"producto": None, "movimientos": []}

            cod = str(prod["code"])
            conds = ["product_code = ?"]
            params: list[Any] = [cod]
            if date_from:
                desde_iso = date_from if "T" in date_from else f"{date_from}T00:00:00"
                conds.append("registered_at >= ?")
                params.append(desde_iso)
            if date_to:
                hasta_iso = date_to if "T" in date_to else f"{date_to}T23:59:59"
                conds.append("registered_at <= ?")
                params.append(hasta_iso)
            else:
                hasta_iso = ""

            rows = connection.execute(
                f"""
                SELECT id, quantity, movement_type, usuario, detalle, registered_at
                FROM stock_movements
                WHERE {' AND '.join(conds)}
                ORDER BY registered_at DESC, id DESC
                LIMIT ?
                """,
                (*params, int(limit)),
            ).fetchall()

            delta_posterior = 0
            if hasta_iso:
                row_after = connection.execute(
                    """
                    SELECT COALESCE(SUM(quantity), 0) AS d
                    FROM stock_movements
                    WHERE product_code = ? AND registered_at > ?
                    """,
                    (cod, hasta_iso),
                ).fetchone()
                delta_posterior = int(row_after["d"] or 0) if row_after else 0

        # Reconstruir saldo móvil hacia atrás desde el stock al final de la ventana
        saldo_corriente = int(prod["stock"] or 0) - delta_posterior
        movimientos_kardex: list[dict[str, Any]] = []
        for r in rows:
            delta = int(r["quantity"] or 0)
            stock_resultante = saldo_corriente
            stock_anterior = saldo_corriente - delta
            saldo_corriente = stock_anterior
            movimientos_kardex.append(
                {
                    "id": int(r["id"]),
                    "fecha": str(r["registered_at"] or ""),
                    "tipo": str(r["movement_type"] or ""),
                    "detalle": str(r["detalle"] or ""),
                    "usuario": str(r["usuario"] or "sistema"),
                    "delta": delta,
                    "entrada": delta if delta > 0 else 0,
                    "salida": abs(delta) if delta < 0 else 0,
                    "stock_anterior": stock_anterior,
                    "stock_resultante": stock_resultante,
                }
            )
        movimientos_kardex.reverse()
        return {"producto": dict(prod), "movimientos": movimientos_kardex}

    def get_rotation_ranking(
        self,
        date_from: str,
        date_to: str,
        dias_periodo: int = 30,
        top_n: int = 60,
    ) -> list[dict[str, Any]]:
        """Retorna el ranking de consumo/salidas y días estimados de cobertura por producto."""
        desde_iso = date_from if "T" in date_from else f"{date_from}T00:00:00"
        hasta_iso = date_to if "T" in date_to else f"{date_to}T23:59:59"
        dias = max(1, int(dias_periodo))
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT
                    m.product_code AS code,
                    COALESCE(p.name, MAX(m.product_name), m.product_code) AS name,
                    COALESCE(p.stock, 0) AS stock_actual,
                    COALESCE(p.stock_minimo, 5) AS stock_minimo,
                    COALESCE(p.ubicacion, '') AS ubicacion,
                    SUM(CASE WHEN m.quantity < 0 THEN ABS(m.quantity) ELSE 0 END) AS total_salidas,
                    SUM(CASE WHEN m.quantity > 0 THEN m.quantity ELSE 0 END) AS total_ingresos,
                    COUNT(m.id) AS cantidad_operaciones
                FROM stock_movements m
                LEFT JOIN products p ON p.code = m.product_code
                WHERE m.registered_at >= ?
                  AND m.registered_at <= ?
                GROUP BY m.product_code
                HAVING total_salidas > 0
                ORDER BY total_salidas DESC, m.product_code ASC
                LIMIT ?
                """,
                (desde_iso, hasta_iso, int(top_n)),
            ).fetchall()

        resultado: list[dict[str, Any]] = []
        for r in rows:
            sal = int(r["total_salidas"] or 0)
            stock_act = int(r["stock_actual"] or 0)
            prom_diario = round(sal / dias, 2)
            cobertura_dias = round(stock_act / prom_diario, 1) if prom_diario > 0 else 999.0
            resultado.append(
                {
                    "code": str(r["code"]),
                    "name": str(r["name"] or ""),
                    "ubicacion": str(r["ubicacion"] or ""),
                    "stock_actual": stock_act,
                    "stock_minimo": int(r["stock_minimo"] or 5),
                    "total_salidas": sal,
                    "total_ingresos": int(r["total_ingresos"] or 0),
                    "operaciones": int(r["cantidad_operaciones"] or 0),
                    "promedio_diario": prom_diario,
                    "cobertura_dias": cobertura_dias,
                }
            )
        return resultado

    def obtener_mapa_runway_inventario(self, dias_ventana: int = 14) -> dict[str, float]:
        """Calcula un mapa {codigo_producto: dias_runway} según el ritmo de salidas recientes."""
        dias = max(1, int(dias_ventana))
        with closing(self._connect()) as connection:
            rows = connection.execute(
                f"""
                SELECT
                    m.product_code AS code,
                    COALESCE(p.stock, 0) AS stock_actual,
                    SUM(CASE WHEN m.quantity < 0 THEN ABS(m.quantity) ELSE 0 END) AS total_salidas
                FROM stock_movements m
                LEFT JOIN products p ON p.code = m.product_code
                WHERE m.registered_at >= datetime('now', '-{dias} days', 'localtime')
                GROUP BY m.product_code
                HAVING total_salidas > 0
                """
            ).fetchall()

        mapa: dict[str, float] = {}
        for r in rows:
            stk = int(r["stock_actual"] or 0)
            sal = float(r["total_salidas"] or 0)
            prom_diario = sal / dias
            if prom_diario > 0:
                mapa[str(r["code"])] = round(stk / prom_diario, 1)
        return mapa
