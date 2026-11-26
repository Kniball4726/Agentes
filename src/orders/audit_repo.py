"""Auditoría forense y agregación de métricas analíticas de rendimiento."""

from __future__ import annotations

from .models import ESTADOS_DESPACHO, RegistroAuditoria
from .protocols import OrderConnectFn


class AuditRepository:
    """Repositorio para registro y consulta de eventos de auditoría y métricas de despacho."""

    def __init__(self, connect_fn: OrderConnectFn) -> None:
        self._connect = connect_fn

    def registrar_auditoria(self, usuario: str, accion: str, detalle: str) -> None:
        """Registra una acción de auditoría forense."""
        usr = (usuario or "Sistema").strip()
        act = (accion or "ACCION").strip()
        det = (detalle or "").strip()
        with self._connect() as connection, connection:
            connection.execute(
                "INSERT INTO logs_auditoria (usuario, accion, detalle) VALUES (?, ?, ?)",
                (usr, act, det),
            )

    def listar_auditoria(
        self,
        limit: int = 150,
        filtro_usuario: str = "",
        filtro_accion: str = "",
        filtro_texto: str = "",
        filtro: str = "",
    ) -> list[RegistroAuditoria]:
        """Obtiene el historial de eventos de auditoría con filtros opcionales."""
        texto_busqueda = filtro_texto or filtro
        query = "SELECT id, usuario, accion, detalle, created_at FROM logs_auditoria WHERE 1=1"
        params: list = []
        if filtro_usuario:
            query += " AND usuario LIKE ?"
            params.append(f"%{filtro_usuario}%")
        if filtro_accion:
            query += " AND accion = ?"
            params.append(filtro_accion)
        if texto_busqueda:
            query += " AND (detalle LIKE ? OR accion LIKE ? OR usuario LIKE ?)"
            params.append(f"%{texto_busqueda}%")
            params.append(f"%{texto_busqueda}%")
            params.append(f"%{texto_busqueda}%")
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        with self._connect() as connection:
            rows = connection.execute(query, tuple(params)).fetchall()
        return [
            RegistroAuditoria(
                id=r["id"],
                usuario=r["usuario"],
                accion=r["accion"],
                detalle=r["detalle"],
                created_at=r["created_at"],
            )
            for r in rows
        ]

    @staticmethod
    def _filtro_fechas(
        columna: str, fecha_desde: str | None, fecha_hasta: str | None
    ) -> tuple[str, list[str]]:
        """Construye el fragmento SQL para filtrar por rango de fechas (formato AAAA-MM-DD)."""
        condiciones: list[str] = []
        params: list[str] = []
        if fecha_desde:
            condiciones.append(f"date({columna}, 'localtime') >= date(?)")
            params.append(fecha_desde)
        if fecha_hasta:
            condiciones.append(f"date({columna}, 'localtime') <= date(?)")
            params.append(fecha_hasta)
        return ("".join(f" AND {c}" for c in condiciones), params)

    def obtener_metricas_dashboard(
        self,
        fecha_desde: str | None = None,
        fecha_hasta: str | None = None,
    ) -> dict:
        """Métricas del panel de rendimiento, opcionalmente acotadas a un rango (AAAA-MM-DD)."""
        extra_p, params_p = self._filtro_fechas("created_at", fecha_desde, fecha_hasta)
        extra_pp, params_pp = self._filtro_fechas("p.created_at", fecha_desde, fecha_hasta)
        with self._connect() as connection:
            res_totales = connection.execute(
                f"""
                SELECT COUNT(*) as total_pedidos,
                       COALESCE(SUM(bultos), 0) as total_bultos,
                       COUNT(CASE WHEN cierre_id IS NOT NULL THEN 1 END) as pedidos_cerrados,
                       COUNT(CASE WHEN cierre_id IS NULL AND estado = 'descontado' THEN 1 END) as pedidos_pendientes,
                       COUNT(CASE WHEN estado = 'anulado' THEN 1 END) as pedidos_anulados
                FROM pedidos WHERE 1=1 {extra_p}
                """,
                params_p,
            ).fetchone()

            rows_logistica = connection.execute(
                f"""
                SELECT logistica, COUNT(*) as cant, COALESCE(SUM(bultos), 0) as bultos
                FROM pedidos
                WHERE estado = 'descontado' {extra_p}
                GROUP BY logistica
                ORDER BY cant DESC
                """,
                params_p,
            ).fetchall()

            rows_armador = connection.execute(
                f"""
                SELECT armador, COUNT(*) as cant, COALESCE(SUM(bultos), 0) as bultos
                FROM pedidos
                WHERE estado = 'descontado' {extra_p}
                GROUP BY armador
                ORDER BY cant DESC
                """,
                params_p,
            ).fetchall()

            rows_top_items = connection.execute(
                f"""
                SELECT pi.codigo, pi.descripcion, SUM(pi.cantidad) as total_cant
                FROM pedido_items pi
                JOIN pedidos p ON p.id = pi.pedido_id
                WHERE p.estado = 'descontado' {extra_pp}
                GROUP BY pi.codigo, pi.descripcion
                ORDER BY total_cant DESC
                LIMIT 10
                """,
                params_pp,
            ).fetchall()

            rows_por_dia = connection.execute(
                f"""
                SELECT date(created_at) as dia, COUNT(*) as cant, COALESCE(SUM(bultos), 0) as bultos
                FROM pedidos
                WHERE estado = 'descontado' {extra_p}
                GROUP BY date(created_at)
                ORDER BY dia ASC
                """,
                params_p,
            ).fetchall()

            rows_despacho = connection.execute(
                f"""
                SELECT estado_despacho, COUNT(*) as cant
                FROM pedidos
                WHERE estado = 'descontado' {extra_p}
                GROUP BY estado_despacho
                """,
                params_p,
            ).fetchall()

            extra_c, params_c = self._filtro_fechas("created_at", fecha_desde, fecha_hasta)
            cant_cierres = connection.execute(
                f"SELECT COUNT(*) FROM cierres_jornada WHERE 1=1 {extra_c}", params_c
            ).fetchone()[0]

            estados_despacho = {e: 0 for e in ESTADOS_DESPACHO}
            for r in rows_despacho:
                estados_despacho[r["estado_despacho"] or "armado"] = int(r["cant"])

            return {
                "fecha_desde": fecha_desde or "",
                "fecha_hasta": fecha_hasta or "",
                "total_pedidos": int(res_totales["total_pedidos"] or 0),
                "total_bultos": int(res_totales["total_bultos"] or 0),
                "pedidos_cerrados": int(res_totales["pedidos_cerrados"] or 0),
                "pedidos_pendientes": int(res_totales["pedidos_pendientes"] or 0),
                "pedidos_anulados": int(res_totales["pedidos_anulados"] or 0),
                "total_cierres": int(cant_cierres or 0),
                "estados_despacho": estados_despacho,
                "pedidos_por_dia": [
                    (r["dia"], int(r["cant"]), int(r["bultos"])) for r in rows_por_dia
                ],
                "distribucion_logistica": [
                    (r["logistica"], int(r["cant"]), int(r["bultos"]))
                    for r in rows_logistica
                ],
                "rendimiento_armadores": [
                    (r["armador"], int(r["cant"]), int(r["bultos"]))
                    for r in rows_armador
                ],
                "top_articulos": [
                    (r["codigo"], r["descripcion"], int(r["total_cant"]))
                    for r in rows_top_items
                ],
            }
