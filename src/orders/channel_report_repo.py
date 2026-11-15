"""Repositorio mixin para consolidación de descuentos por canal y ventanas de cierre."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from .models import clasificar_canal_pedido


class ChannelReportMixin:
    """Agrega consultas de salidas por canal (Mayoristas, Mercado Libre, Full) y ventanas de jornada."""

    _connect: Callable[[], Any]

    def obtener_descuentos_operario_por_canal(
        self,
        pedidos_ids: list[int] | None = None,
        solo_pendientes: bool = True,
        fecha_desde: str = "",
        fecha_hasta: str = "",
        cierre_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """Agrupa descuentos de pedidos por producto discriminando Mayoristas, Mercado Libre y Full.

        Retorna únicamente artículos con total descontado > 0.
        """
        condiciones = ["p.estado != 'anulado'", "pi.cantidad > 0"]
        params: list[Any] = []

        if cierre_id is not None:
            condiciones.append("p.cierre_id = ?")
            params.append(int(cierre_id))
        elif pedidos_ids is not None:
            if not pedidos_ids:
                return []
            placeholders = ",".join("?" * len(pedidos_ids))
            condiciones.append(f"p.id IN ({placeholders})")
            params.extend(int(pid) for pid in pedidos_ids)
        elif fecha_desde or fecha_hasta:
            if fecha_desde:
                desde_iso = fecha_desde if "T" in fecha_desde else f"{fecha_desde}T00:00:00"
                condiciones.append("strftime('%Y-%m-%dT%H:%M:%S', p.created_at, 'localtime') >= ?")
                params.append(desde_iso)
            if fecha_hasta:
                hasta_iso = fecha_hasta if "T" in fecha_hasta else f"{fecha_hasta}T23:59:59"
                condiciones.append("strftime('%Y-%m-%dT%H:%M:%S', p.created_at, 'localtime') <= ?")
                params.append(hasta_iso)
        elif solo_pendientes:
            condiciones.append("p.cierre_id IS NULL")

        where_sql = " AND ".join(condiciones)
        query = f"""
            SELECT
                pi.codigo,
                pi.descripcion,
                pi.cantidad,
                p.canal,
                p.tipo_archivo,
                p.cliente,
                p.nombre_archivo,
                p.nota_pedido,
                p.logistica
            FROM pedido_items pi
            JOIN pedidos p ON p.id = pi.pedido_id
            WHERE {where_sql}
            ORDER BY pi.codigo ASC, p.id ASC
        """
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()

        agrupado: dict[str, dict[str, Any]] = {}
        for r in rows:
            cod = str(r["codigo"] or "").strip().upper()
            if not cod:
                continue
            cant = int(r["cantidad"] or 0)
            if cant <= 0:
                continue

            canal = clasificar_canal_pedido(
                tipo_archivo=str(r["tipo_archivo"] or ""),
                cliente=str(r["cliente"] or ""),
                nombre_archivo=str(r["nombre_archivo"] or ""),
                nota_pedido=str(r["nota_pedido"] or ""),
                logistica=str(r["logistica"] or ""),
                canal_explicito=str(r["canal"] or ""),
            )
            entry = agrupado.get(cod)
            if entry is None:
                entry = {
                    "codigo": cod,
                    "descripcion": str(r["descripcion"] or "").strip(),
                    "mayoristas": 0,
                    "mercado_libre": 0,
                    "full": 0,
                    "canjes": 0,
                    "total": 0,
                    "remitos": [],
                }
                agrupado[cod] = entry
            elif not entry["descripcion"] and r["descripcion"]:
                entry["descripcion"] = str(r["descripcion"]).strip()

            if canal == "mercado_libre":
                entry["mercado_libre"] += cant
            elif canal == "full":
                entry["full"] += cant
            elif canal == "canje":
                entry["canjes"] += cant
            else:
                entry["mayoristas"] += cant

            entry["total"] += cant
            remito = str(r["nota_pedido"] or "").strip()
            if remito and remito not in entry["remitos"]:
                entry["remitos"].append(remito)

        return [item for item in agrupado.values() if item["total"] > 0]

    def obtener_ventana_ultimo_cierre(
        self,
        cierre_id: int | None = None,
    ) -> tuple[str, str, int | None]:
        """Devuelve `(desde_iso_local, hasta_iso_local, cierre_anterior_id)` para consolidar la jornada."""
        with self._connect() as connection:
            if cierre_id is not None:
                row_actual = connection.execute(
                    "SELECT id, strftime('%Y-%m-%dT%H:%M:%S', created_at, 'localtime') AS ts FROM cierres_jornada WHERE id = ?",
                    (int(cierre_id),),
                ).fetchone()
                hasta_iso = (
                    str(row_actual["ts"])
                    if row_actual and row_actual["ts"]
                    else datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
                )
                row_prev = connection.execute(
                    "SELECT id, strftime('%Y-%m-%dT%H:%M:%S', created_at, 'localtime') AS ts FROM cierres_jornada WHERE id < ? ORDER BY id DESC LIMIT 1",
                    (int(cierre_id),),
                ).fetchone()
            else:
                hasta_iso = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
                row_prev = connection.execute(
                    "SELECT id, strftime('%Y-%m-%dT%H:%M:%S', created_at, 'localtime') AS ts FROM cierres_jornada ORDER BY id DESC LIMIT 1"
                ).fetchone()

        if row_prev and row_prev["ts"]:
            return str(row_prev["ts"]), hasta_iso, int(row_prev["id"])
        return f"{hasta_iso[:10]}T00:00:00", hasta_iso, None
