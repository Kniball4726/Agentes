"""Repositorio y consolidación de cierres diarios de jornada y hojas de ruta."""

from __future__ import annotations

from typing import Any

from .models import CierreJornada, CierreMercado, Pedido


class ClosureRepositoryMixin:
    """Mixin que gestiona los cierres diarios de jornada y las hojas de ruta de despacho."""

    def listar_pedidos_pendientes_cierre(self) -> list[Pedido]:
        """Devuelve todos los pedidos descontados que aún no fueron incluidos en un cierre."""
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, nota_pedido, numero_pedido, cliente, bultos, logistica, armador,
                       tipo_archivo, nombre_archivo, agregado, articulos_descontados,
                       resumen_items, created_at, estado, fecha_retiro, archivo_descuento, cierre_id, cierre_mercado_id, archivo_hash, numero_guia,
                           estado_despacho, despachado_at, despachado_por, entregado_at, entregado_por
                FROM pedidos
                WHERE cierre_id IS NULL AND estado = 'descontado'
                ORDER BY id ASC
                """
            ).fetchall()
        return [self._map_pedido(r) for r in rows]

    def contar_pedidos_pendientes_cierre_por_tipo(self) -> dict[str, int]:
        """Devuelve el conteo de pedidos descontados de la jornada actual agrupados por tipo."""
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT tipo_archivo, COUNT(*) as cantidad
                FROM pedidos
                WHERE cierre_id IS NULL AND estado = 'descontado'
                GROUP BY tipo_archivo
                """
            ).fetchall()
        conteo = {"pdf": 0, "excel": 0, "docx": 0, "total": 0}
        for r in rows:
            tipo = str(r["tipo_archivo"] or "").lower()
            cant = int(r["cantidad"] or 0)
            conteo[tipo] = conteo.get(tipo, 0) + cant
            conteo["total"] += cant
        return conteo

    def obtener_items_pendientes_cierre(self) -> list[tuple[str, str, int, list[str]]]:
        """Devuelve productos consolidados pendientes de cierre: (codigo, descripcion, total_cantidad, [notas_pedido])."""
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT pi.codigo,
                       MAX(pi.descripcion) as descripcion,
                       SUM(pi.cantidad) as total_cant,
                       GROUP_CONCAT(p.nota_pedido, ', ') as remitos_origen
                FROM pedido_items pi
                JOIN pedidos p ON p.id = pi.pedido_id
                WHERE p.cierre_id IS NULL AND p.estado = 'descontado'
                GROUP BY pi.codigo
                ORDER BY pi.codigo ASC
                """
            ).fetchall()
        resultado = []
        for r in rows:
            remitos_crudos = [n.strip() for n in (r["remitos_origen"] or "").split(",") if n.strip()]
            remitos_unicos: list[str] = []
            for rem in remitos_crudos:
                if rem not in remitos_unicos:
                    remitos_unicos.append(rem)
            resultado.append(
                (
                    r["codigo"],
                    r["descripcion"],
                    int(r["total_cant"]),
                    remitos_unicos,
                )
            )
        return resultado

    def registrar_cierre(
        self,
        usuario: str,
        pedidos_ids: list[int],
        articulos_totales: int,
        resumen_pedidos: str,
        archivo_pdf: str = "",
        archivo_excel: str = "",
        archivo_hoja_ruta: str = "",
    ) -> int:
        """Consolida los pedidos seleccionados en un nuevo registro de CierreJornada."""
        if not pedidos_ids:
            raise ValueError("No hay pedidos para incluir en el cierre.")
        with self._connect() as connection, connection:
            cursor = connection.execute(
                """
                INSERT INTO cierres_jornada (
                    usuario, cantidad_pedidos, articulos_totales, resumen_pedidos,
                    archivo_pdf, archivo_excel, archivo_hoja_ruta
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    usuario,
                    len(pedidos_ids),
                    articulos_totales,
                    resumen_pedidos,
                    archivo_pdf,
                    archivo_excel,
                    archivo_hoja_ruta,
                ),
            )
            cierre_id = cursor.lastrowid
            placeholders = ",".join("?" * len(pedidos_ids))
            connection.execute(
                f"UPDATE pedidos SET cierre_id = ? WHERE id IN ({placeholders})",
                (cierre_id, *pedidos_ids),
            )
        self.registrar_auditoria(
            usuario=usuario,
            accion="CIERRE_JORNADA",
            detalle=f"Cierre #{cierre_id} registrado con éxito ({resumen_pedidos})",
        )
        return cierre_id

    def listar_cierres(self, limit: int = 50) -> list[CierreJornada]:
        """Lista cierres de jornada ordenados de forma descendente."""
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, usuario, cantidad_pedidos, articulos_totales, resumen_pedidos,
                       archivo_pdf, archivo_excel, archivo_hoja_ruta, created_at
                FROM cierres_jornada
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            CierreJornada(
                id=r["id"],
                usuario=r["usuario"],
                cantidad_pedidos=r["cantidad_pedidos"],
                articulos_totales=r["articulos_totales"],
                resumen_pedidos=r["resumen_pedidos"],
                archivo_pdf=r["archivo_pdf"] or "",
                archivo_excel=r["archivo_excel"] or "",
                archivo_hoja_ruta=r["archivo_hoja_ruta"] if "archivo_hoja_ruta" in r.keys() and r["archivo_hoja_ruta"] else "",
                created_at=r["created_at"],
            )
            for r in rows
        ]

    def obtener_pedidos_por_cierre(self, cierre_id: int) -> list[Pedido]:
        """Obtiene los pedidos asociados a un cierre específico agrupados por logística."""
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, nota_pedido, numero_pedido, cliente, bultos, logistica,
                       armador, tipo_archivo, nombre_archivo, agregado, articulos_descontados,
                       resumen_items, created_at, estado, fecha_retiro, archivo_descuento,
                       cierre_id, archivo_hash, numero_guia,
                           estado_despacho, despachado_at, despachado_por, entregado_at, entregado_por
                FROM pedidos
                WHERE cierre_id = ?
                ORDER BY logistica ASC, id ASC
                """,
                (cierre_id,),
            ).fetchall()
        return [self._map_pedido(r) for r in rows]

    def actualizar_hoja_ruta_cierre(self, cierre_id: int, archivo_hoja_ruta: str) -> None:
        """Asocia la hoja de ruta generada al cierre de jornada."""
        with self._connect() as connection, connection:
            connection.execute(
                "UPDATE cierres_jornada SET archivo_hoja_ruta = ? WHERE id = ?",
                (archivo_hoja_ruta, cierre_id),
            )
        self.registrar_auditoria(
            usuario="Sistema",
            accion="HOJA_RUTA_GENERADA",
            detalle=f"Hoja de ruta para cierre #{cierre_id}: {archivo_hoja_ruta}",
        )

    def listar_pedidos_mercado_pendientes_cierre(
        self,
        tipo: str = "TODOS",
        armador: str | None = None,
    ) -> list[Pedido]:
        """Devuelve los pedidos de Mercado Libre y Mercado Full descontados pendientes de cerrar tanda."""
        query = """
            SELECT id, nota_pedido, numero_pedido, cliente, bultos, logistica, armador,
                   tipo_archivo, nombre_archivo, agregado, articulos_descontados,
                   resumen_items, created_at, estado, fecha_retiro, archivo_descuento,
                   cierre_id, cierre_mercado_id, archivo_hash, numero_guia,
                   estado_despacho, despachado_at, despachado_por, entregado_at, entregado_por
            FROM pedidos
            WHERE cierre_mercado_id IS NULL AND estado = 'descontado'
        """
        params: list[Any] = []
        tipo_upper = (tipo or "TODOS").upper()
        if tipo_upper == "MERCADO_LIBRE":
            query += " AND (cliente LIKE '%Mercado Libre%' OR nombre_archivo LIKE 'ML_%' OR nota_pedido LIKE 'ML%')"
        elif tipo_upper == "MERCADO_FULL":
            query += " AND (cliente LIKE '%Full%' OR nombre_archivo LIKE '%Full%' OR nota_pedido LIKE '%FULL%')"
        else:
            query += " AND (cliente LIKE '%Mercado%' OR nombre_archivo LIKE 'ML_%' OR nombre_archivo LIKE '%Full%' OR nota_pedido LIKE 'ML%' OR nota_pedido LIKE '%FULL%')"

        if armador and armador.strip():
            query += " AND armador = ?"
            params.append(armador.strip())

        query += " ORDER BY id ASC"

        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [self._map_pedido(r) for r in rows]

    def obtener_items_mercado_pendientes(
        self,
        pedidos_ids: list[int],
    ) -> list[tuple[str, str, int, list[str]]]:
        """Devuelve los productos consolidados para una lista específica de pedidos de mercado."""
        if not pedidos_ids:
            return []
        placeholders = ",".join("?" * len(pedidos_ids))
        query = f"""
            SELECT pi.codigo,
                   MAX(pi.descripcion) as descripcion,
                   SUM(pi.cantidad) as total_cant,
                   GROUP_CONCAT(p.nota_pedido, ', ') as remitos_origen
            FROM pedido_items pi
            JOIN pedidos p ON p.id = pi.pedido_id
            WHERE p.id IN ({placeholders})
            GROUP BY pi.codigo
            ORDER BY pi.codigo ASC
        """
        with self._connect() as connection:
            rows = connection.execute(query, pedidos_ids).fetchall()
        resultado = []
        for r in rows:
            remitos_crudos = [n.strip() for n in (r["remitos_origen"] or "").split(",") if n.strip()]
            remitos_unicos: list[str] = []
            for rem in remitos_crudos:
                if rem not in remitos_unicos:
                    remitos_unicos.append(rem)
            resultado.append(
                (
                    r["codigo"],
                    r["descripcion"],
                    int(r["total_cant"]),
                    remitos_unicos,
                )
            )
        return resultado

    def registrar_cierre_mercado(
        self,
        usuario: str,
        tipo_mercado: str,
        pedidos_ids: list[int],
        articulos_totales: int,
        resumen_pedidos: str,
        archivo_pdf: str = "",
        archivo_excel: str = "",
    ) -> int:
        """Registra un nuevo cierre de tanda de Mercado Libre / Full y sella los pedidos."""
        if not pedidos_ids:
            raise ValueError("No hay pedidos de mercado para incluir en el cierre.")
        with self._connect() as connection, connection:
            cursor = connection.execute(
                """
                INSERT INTO cierres_mercado (
                    usuario, tipo_mercado, cantidad_pedidos, articulos_totales,
                    resumen_pedidos, archivo_pdf, archivo_excel
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    usuario,
                    tipo_mercado,
                    len(pedidos_ids),
                    articulos_totales,
                    resumen_pedidos,
                    archivo_pdf,
                    archivo_excel,
                ),
            )
            cierre_m_id = cursor.lastrowid
            placeholders = ",".join("?" * len(pedidos_ids))
            connection.execute(
                f"UPDATE pedidos SET cierre_mercado_id = ? WHERE id IN ({placeholders})",
                (cierre_m_id, *pedidos_ids),
            )
        self.registrar_auditoria(
            usuario=usuario,
            accion="CIERRE_MERCADO",
            detalle=f"Cierre Mercado #{cierre_m_id} ({tipo_mercado}) registrado con éxito ({resumen_pedidos})",
        )
        return cierre_m_id

    def listar_cierres_mercado(self, limit: int = 50) -> list[CierreMercado]:
        """Lista cierres de mercado ordenados cronológicamente descendente."""
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, usuario, tipo_mercado, cantidad_pedidos, articulos_totales,
                       resumen_pedidos, archivo_pdf, archivo_excel, created_at
                FROM cierres_mercado
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            CierreMercado(
                id=r["id"],
                usuario=r["usuario"],
                tipo_mercado=r["tipo_mercado"],
                cantidad_pedidos=r["cantidad_pedidos"],
                articulos_totales=r["articulos_totales"],
                resumen_pedidos=r["resumen_pedidos"],
                archivo_pdf=r["archivo_pdf"] or "",
                archivo_excel=r["archivo_excel"] or "",
                created_at=r["created_at"],
            )
            for r in rows
        ]
