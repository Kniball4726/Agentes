"""Repositorio núcleo CRUD para pedidos, sus ítems y consulta de historial."""

from __future__ import annotations

import json
import sqlite3
from typing import Callable

from ..core.exceptions import OrderStoreError
from .dispatch_repo import _COLUMNAS_SELECT_PEDIDO
from .models import LOGISTICA_OPCIONES, Pedido, clasificar_canal_pedido
from .protocols import AuditLogFn, OrderConnectFn


class OrderCoreRepository:
    """Repositorio encargado de las operaciones CRUD núcleo sobre pedidos e ítems."""

    def __init__(
        self,
        connect_fn: OrderConnectFn,
        audit_fn: AuditLogFn,
        register_client_fn: Callable[[str], object] | None = None,
    ) -> None:
        self._connect = connect_fn
        self._audit = audit_fn
        self._register_client = register_client_fn

    @staticmethod
    def map_pedido(row: sqlite3.Row) -> Pedido:
        """Convierte una fila SQLite en una instancia inmutable/tipada de Pedido."""
        claves = row.keys()
        c_id = row["cierre_id"] if "cierre_id" in claves else None
        c_m_id = row["cierre_mercado_id"] if "cierre_mercado_id" in claves else None
        hash_val = row["archivo_hash"] if "archivo_hash" in claves and row["archivo_hash"] else ""
        guia_val = (row["numero_guia"] if "numero_guia" in claves else "") or ""
        return Pedido(
            id=row["id"],
            nota_pedido=row["nota_pedido"],
            numero_pedido=row["numero_pedido"],
            cliente=row["cliente"],
            bultos=row["bultos"],
            logistica=row["logistica"],
            armador=row["armador"],
            tipo_archivo=row["tipo_archivo"],
            nombre_archivo=row["nombre_archivo"],
            agregado=bool(row["agregado"]),
            articulos_descontados=row["articulos_descontados"],
            resumen_items=row["resumen_items"],
            created_at=row["created_at"],
            estado=row["estado"],
            fecha_retiro=row["fecha_retiro"] or "",
            archivo_descuento=row["archivo_descuento"] or "",
            cierre_id=c_id,
            cierre_mercado_id=c_m_id,
            archivo_hash=hash_val,
            numero_guia=guia_val,
            estado_despacho=(row["estado_despacho"] if "estado_despacho" in claves else "armado") or "armado",
            despachado_at=(row["despachado_at"] if "despachado_at" in claves else "") or "",
            despachado_por=(row["despachado_por"] if "despachado_por" in claves else "") or "",
            entregado_at=(row["entregado_at"] if "entregado_at" in claves else "") or "",
            entregado_por=(row["entregado_por"] if "entregado_por" in claves else "") or "",
            canal=(row["canal"] if "canal" in claves else "") or "",
        )

    def obtener_fila_pedido(
        self, connection: sqlite3.Connection, pedido_id: int
    ) -> sqlite3.Row | None:
        return connection.execute(
            f"SELECT {_COLUMNAS_SELECT_PEDIDO} FROM pedidos WHERE id = ?",
            (pedido_id,),
        ).fetchone()

    def existe_nota_pedido(self, nota_pedido: str) -> bool:
        """Indica si ya existe un pedido registrado con la nota especificada."""
        nota = nota_pedido.strip()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM pedidos WHERE nota_pedido = ? COLLATE NOCASE LIMIT 1",
                (nota,),
            ).fetchone()
            return row is not None

    def registrar_pedido(
        self,
        nota_pedido: str,
        numero_pedido: str,
        cliente: str,
        bultos: int,
        logistica: str,
        armador: str,
        tipo_archivo: str,
        nombre_archivo: str,
        agregado: bool = False,
        articulos_descontados: int = 0,
        resumen_items: str = "",
        fecha_retiro: str = "",
        archivo_descuento: str = "",
        items: list[tuple[str, str, int]] | None = None,
        archivo_hash: str = "",
        numero_guia: str = "",
        items_sin_coincidencia: list[tuple[str, str]] | None = None,
        canal: str = "",
    ) -> Pedido:
        """Valida e inserta un nuevo pedido junto a sus ítems y registro de auditoría."""
        nota_pedido = nota_pedido.strip()
        numero_pedido = numero_pedido.strip()
        cliente = cliente.strip()
        armador = armador.strip() or "Operario"
        nombre_archivo = nombre_archivo.strip()
        tipo_archivo = tipo_archivo.lower().strip()
        fecha_retiro = fecha_retiro.strip()
        archivo_descuento = archivo_descuento.strip()
        archivo_hash = archivo_hash.strip()
        canal_normalizado = clasificar_canal_pedido(
            tipo_archivo=tipo_archivo,
            cliente=cliente,
            nombre_archivo=nombre_archivo,
            nota_pedido=nota_pedido,
            logistica=logistica,
            canal_explicito=canal,
        )

        if not nota_pedido:
            raise ValueError("La nota de pedido no puede estar vacía.")
        if not cliente:
            raise ValueError("Debes especificar un cliente.")
        if bultos < 1:
            raise ValueError("La cantidad de bultos debe ser de al menos 1.")
        if logistica not in LOGISTICA_OPCIONES:
            raise ValueError(f"Logística inválida. Opciones permitidas: {', '.join(LOGISTICA_OPCIONES)}")
        if tipo_archivo not in ("pdf", "excel", "docx"):
            raise ValueError("Tipo de archivo inválido (debe ser pdf, excel o docx).")

        try:
            with self._connect() as connection, connection:
                cursor = connection.execute(
                    """
                    INSERT INTO pedidos (
                        nota_pedido, numero_pedido, cliente, bultos, logistica, armador,
                        tipo_archivo, nombre_archivo, agregado, articulos_descontados, resumen_items,
                        fecha_retiro, archivo_descuento, archivo_hash, numero_guia, items_sin_coincidencia, canal
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        nota_pedido,
                        numero_pedido,
                        cliente,
                        bultos,
                        logistica,
                        armador,
                        tipo_archivo,
                        nombre_archivo,
                        int(agregado),
                        articulos_descontados,
                        resumen_items,
                        fecha_retiro,
                        archivo_descuento,
                        archivo_hash,
                        (numero_guia or "").strip(),
                        json.dumps(items_sin_coincidencia or [], ensure_ascii=False),
                        canal_normalizado,
                    ),
                )
                nuevo_id = cursor.lastrowid
                if items:
                    connection.executemany(
                        """
                        INSERT INTO pedido_items (pedido_id, codigo, descripcion, cantidad)
                        VALUES (?, ?, ?, ?)
                        """,
                        [(nuevo_id, str(cod).strip(), str(desc).strip(), int(cant)) for cod, desc, cant in items],
                    )
                row = self.obtener_fila_pedido(connection, nuevo_id)
        except sqlite3.IntegrityError as error:
            raise ValueError(f"La nota de pedido '{nota_pedido}' ya fue registrada previamente.") from error

        ped_res = self.map_pedido(row)
        self._audit(
            usuario=armador,
            accion="CARGAR_PEDIDO",
            detalle=f"Remito {ped_res.nota_pedido} cargado para '{ped_res.cliente}' ({ped_res.bultos} bulto(s), {ped_res.logistica})",
        )
        return ped_res

    def buscar_pedido_por_hash(self, archivo_hash: str) -> Pedido | None:
        """Busca un pedido activo por el hash SHA-256 del archivo origen."""
        if not archivo_hash:
            return None
        with self._connect() as connection:
            row = connection.execute(
                f"""
                SELECT {_COLUMNAS_SELECT_PEDIDO}
                FROM pedidos
                WHERE archivo_hash = ? AND estado != 'anulado'
                LIMIT 1
                """,
                (archivo_hash.strip(),),
            ).fetchone()
            return self.map_pedido(row) if row is not None else None

    def listar_pedidos(self, limit: int = 50) -> list[Pedido]:
        """Lista los pedidos más recientes en orden descendente por ID."""
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT {_COLUMNAS_SELECT_PEDIDO} FROM pedidos ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self.map_pedido(r) for r in rows]

    def obtener_resumen_pedidos_por_fecha(self, limit: int = 30) -> list[dict[str, int | str]]:
        """Agrupa los pedidos armados (no anulados) por fecha en orden descendente."""
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT SUBSTR(created_at, 1, 10) AS fecha,
                       COUNT(*) AS cantidad_pedidos,
                       COALESCE(SUM(bultos), 0) AS total_bultos,
                       COALESCE(SUM(articulos_descontados), 0) AS total_articulos
                FROM pedidos
                WHERE estado != 'anulado'
                GROUP BY SUBSTR(created_at, 1, 10)
                ORDER BY fecha DESC, cantidad_pedidos DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            {
                "fecha": str(r["fecha"] or ""),
                "cantidad_pedidos": int(r["cantidad_pedidos"] or 0),
                "total_bultos": int(r["total_bultos"] or 0),
                "total_articulos": int(r["total_articulos"] or 0),
            }
            for r in rows
            if r["fecha"]
        ]

    def anular_pedido(self, pedido_id: int, motivo: str = "", usuario: str = "Sistema") -> None:
        """Marca un pedido como anulado y registra el motivo en auditoría."""
        with self._connect() as connection, connection:
            row = connection.execute("SELECT nota_pedido FROM pedidos WHERE id = ?", (pedido_id,)).fetchone()
            remito = row["nota_pedido"] if row else f"ID {pedido_id}"
            connection.execute(
                "UPDATE pedidos SET estado = 'anulado' WHERE id = ?",
                (pedido_id,),
            )
        self._audit(
            usuario=usuario,
            accion="ANULAR_PEDIDO",
            detalle=f"Remito {remito} anulado. Motivo: {motivo.strip() or 'Sin especificar'}",
        )

    def obtener_items_sin_coincidencia(self, pedido_id: int) -> list[tuple[str, str]]:
        """Devuelve la lista JSON de ítems sin coincidencia guardada para un pedido."""
        with self._connect() as connection:
            row = connection.execute(
                "SELECT items_sin_coincidencia FROM pedidos WHERE id = ?",
                (pedido_id,),
            ).fetchone()
        if not row or not row["items_sin_coincidencia"]:
            return []
        try:
            items = json.loads(row["items_sin_coincidencia"])
            return [(str(desc), str(mot)) for desc, mot in items]
        except Exception:
            return []

    def guardar_items_sin_coincidencia(self, pedido_id: int, items: list[tuple[str, str]]) -> None:
        """Guarda el detalle JSON de ítems sin coincidencia para un pedido."""
        with self._connect() as connection, connection:
            connection.execute(
                "UPDATE pedidos SET items_sin_coincidencia = ? WHERE id = ?",
                (json.dumps(items or [], ensure_ascii=False), pedido_id),
            )

    def obtener_items_pedido(self, pedido_id: int) -> list[tuple[str, str, int]]:
        """Retorna los ítems descontados asociados a un pedido."""
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT codigo, descripcion, cantidad
                FROM pedido_items
                WHERE pedido_id = ?
                ORDER BY id ASC
                """,
                (pedido_id,),
            ).fetchall()
        return [(r["codigo"], r["descripcion"], int(r["cantidad"])) for r in rows]

    def actualizar_datos_pedido(
        self,
        pedido_id: int,
        cliente: str | None = None,
        numero_pedido: str | None = None,
        bultos: int | None = None,
        logistica: str | None = None,
        fecha_retiro: str | None = None,
        usuario: str = "Sistema",
        numero_guia: str | None = None,
    ) -> Pedido:
        """Actualiza metadatos editables de un pedido con validación y trazabilidad."""
        with self._connect() as connection:
            row = self.obtener_fila_pedido(connection, pedido_id)
            if row is None:
                raise OrderStoreError(f"No se encontró el pedido con ID {pedido_id}.")
            pedido_actual = self.map_pedido(row)

        cambios: list[str] = []
        nuevo_cliente = pedido_actual.cliente if cliente is None else cliente.strip()
        if nuevo_cliente != pedido_actual.cliente:
            if not nuevo_cliente:
                raise OrderStoreError("El nombre del cliente no puede estar vacío.")
            cambios.append(f"Cliente: '{pedido_actual.cliente}' → '{nuevo_cliente}'")

        nuevo_num_pedido = pedido_actual.numero_pedido if numero_pedido is None else numero_pedido.strip()
        if nuevo_num_pedido != pedido_actual.numero_pedido:
            cambios.append(f"N° Pedido: '{pedido_actual.numero_pedido}' → '{nuevo_num_pedido}'")

        nuevo_bultos = pedido_actual.bultos if bultos is None else int(bultos)
        if nuevo_bultos < 1:
            raise OrderStoreError("La cantidad de bultos debe ser al menos 1.")
        if nuevo_bultos != pedido_actual.bultos:
            cambios.append(f"Bultos: {pedido_actual.bultos} → {nuevo_bultos}")

        nueva_logistica = pedido_actual.logistica if logistica is None else logistica.strip()
        if nueva_logistica not in LOGISTICA_OPCIONES:
            raise OrderStoreError(
                f"Logística inválida: '{nueva_logistica}'. Debe ser una de: {', '.join(LOGISTICA_OPCIONES)}"
            )
        if nueva_logistica != pedido_actual.logistica:
            cambios.append(f"Logística: '{pedido_actual.logistica}' → '{nueva_logistica}'")

        nueva_fecha_retiro = pedido_actual.fecha_retiro if fecha_retiro is None else fecha_retiro.strip()
        if nueva_fecha_retiro != pedido_actual.fecha_retiro:
            cambios.append(f"Fecha Retiro: '{pedido_actual.fecha_retiro}' → '{nueva_fecha_retiro}'")

        nuevo_numero_guia = pedido_actual.numero_guia if numero_guia is None else numero_guia.strip()
        if nuevo_numero_guia != pedido_actual.numero_guia:
            cambios.append(f"N° Guía: '{pedido_actual.numero_guia}' → '{nuevo_numero_guia}'")

        if not cambios:
            return pedido_actual

        with self._connect() as connection, connection:
            connection.execute(
                """
                UPDATE pedidos
                SET cliente = ?, numero_pedido = ?, bultos = ?, logistica = ?, fecha_retiro = ?, numero_guia = ?
                WHERE id = ?
                """,
                (nuevo_cliente, nuevo_num_pedido, nuevo_bultos, nueva_logistica, nueva_fecha_retiro, nuevo_numero_guia, pedido_id),
            )

        if nuevo_cliente and self._register_client is not None:
            try:
                self._register_client(nuevo_cliente)
            except Exception:
                pass

        self._audit(
            usuario=usuario,
            accion="MODIFICAR_PEDIDO",
            detalle=f"Pedido #{pedido_actual.nota_pedido} modificado: " + "; ".join(cambios),
        )

        with self._connect() as connection:
            row_act = self.obtener_fila_pedido(connection, pedido_id)
        return self.map_pedido(row_act)
