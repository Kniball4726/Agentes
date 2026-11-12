"""Motor de persistencia SQLite y lógica de negocio para pedidos, clientes y cierres."""

from __future__ import annotations

import json
import re
import sqlite3
from contextlib import closing, contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Generator

from ..core.exceptions import OrderStoreError
from .audit_repo import AuditRepositoryMixin
from .chat_repo import ChatRepositoryMixin
from .client_repo import ClientRepositoryMixin
from .closure_repo import ClosureRepositoryMixin
from .concurrency_repo import ConcurrencyRepositoryMixin
from .models import (
    ESTADOS_DESPACHO,
    LOGISTICA_OPCIONES,
    _COLUMNAS_DESPACHO,
    Pedido,
)


class OrderStore(
    ClientRepositoryMixin,
    ChatRepositoryMixin,
    ConcurrencyRepositoryMixin,
    AuditRepositoryMixin,
    ClosureRepositoryMixin,
):
    """Gestor unificado de almacenamiento y operaciones de pedidos, clientes y despachos."""

    _initialized_dbs: set[tuple[str, int, int]] = set()

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def _connect(self) -> Generator[sqlite3.Connection, None, None]:
        with closing(sqlite3.connect(self.database_path, timeout=10)) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("PRAGMA synchronous = NORMAL")
            connection.execute("PRAGMA temp_store = MEMORY")
            connection.execute("PRAGMA busy_timeout = 10000")
            yield connection

    def _db_signature(self) -> tuple[str, int, int] | None:
        try:
            if not self.database_path.exists():
                return None
            st = self.database_path.stat()
            if st.st_size <= 0:
                return None
            return (str(self.database_path.resolve()), st.st_ctime_ns, st.st_ino)
        except OSError:
            return None

    def _initialize(self) -> None:
        sig_before = self._db_signature()
        if sig_before is not None and sig_before in self._initialized_dbs:
            return
        with self._connect() as connection, connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS clientes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nombre TEXT NOT NULL COLLATE NOCASE UNIQUE,
                    activo INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1)),
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    codigo TEXT NOT NULL DEFAULT '',
                    direccion TEXT NOT NULL DEFAULT ''
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS pedidos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nota_pedido TEXT NOT NULL COLLATE NOCASE UNIQUE,
                    numero_pedido TEXT NOT NULL DEFAULT '',
                    cliente TEXT NOT NULL,
                    bultos INTEGER NOT NULL DEFAULT 1 CHECK (bultos >= 1),
                    logistica TEXT NOT NULL CHECK (
                        logistica IN (
                            'Domicilio',
                            'Centro de distribución',
                            'Transporte',
                            'Comisionista',
                            'Mabel',
                            'Canje'
                        )
                    ),
                    armador TEXT NOT NULL,
                    tipo_archivo TEXT NOT NULL CHECK (tipo_archivo IN ('pdf', 'excel', 'docx')),
                    nombre_archivo TEXT NOT NULL,
                    agregado INTEGER NOT NULL DEFAULT 0 CHECK (agregado IN (0, 1)),
                    articulos_descontados INTEGER NOT NULL DEFAULT 0,
                    resumen_items TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    estado TEXT NOT NULL DEFAULT 'descontado' CHECK (estado IN ('descontado', 'anulado')),
                    fecha_retiro TEXT NOT NULL DEFAULT '',
                    archivo_descuento TEXT NOT NULL DEFAULT '',
                    cierre_id INTEGER DEFAULT NULL,
                    archivo_hash TEXT NOT NULL DEFAULT '',
                    numero_guia TEXT NOT NULL DEFAULT '',
                    items_sin_coincidencia TEXT NOT NULL DEFAULT '[]'
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS cierres_jornada (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    usuario TEXT NOT NULL,
                    cantidad_pedidos INTEGER NOT NULL,
                    articulos_totales INTEGER NOT NULL,
                    resumen_pedidos TEXT NOT NULL,
                    archivo_pdf TEXT NOT NULL DEFAULT '',
                    archivo_excel TEXT NOT NULL DEFAULT '',
                    archivo_hoja_ruta TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS pedido_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pedido_id INTEGER NOT NULL REFERENCES pedidos(id) ON DELETE CASCADE,
                    codigo TEXT NOT NULL,
                    descripcion TEXT NOT NULL,
                    cantidad INTEGER NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS logs_auditoria (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    usuario TEXT NOT NULL,
                    accion TEXT NOT NULL,
                    detalle TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS mensajes_chat (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    emisor TEXT NOT NULL,
                    destinatario TEXT NOT NULL DEFAULT 'Todos',
                    mensaje TEXT NOT NULL,
                    leido INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_mensajes_destinatario ON mensajes_chat(destinatario, leido)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_pedidos_estado ON pedidos(estado)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_pedidos_cierre ON pedidos(cierre_id)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_pedidos_cliente ON pedidos(cliente)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_pedidos_fecha ON pedidos(created_at)"
            )
            cols_clientes = {r["name"] for r in connection.execute("PRAGMA table_info(clientes)").fetchall()}
            if "codigo" not in cols_clientes:
                connection.execute("ALTER TABLE clientes ADD COLUMN codigo TEXT NOT NULL DEFAULT ''")
            if "direccion" not in cols_clientes:
                connection.execute("ALTER TABLE clientes ADD COLUMN direccion TEXT NOT NULL DEFAULT ''")
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_clientes_codigo ON clientes(codigo)"
            )
            cols_cierres = {r["name"] for r in connection.execute("PRAGMA table_info(cierres_jornada)").fetchall()}
            if "archivo_hoja_ruta" not in cols_cierres:
                connection.execute("ALTER TABLE cierres_jornada ADD COLUMN archivo_hoja_ruta TEXT NOT NULL DEFAULT ''")

            row_pedidos = connection.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='pedidos'"
            ).fetchone()
            if row_pedidos and row_pedidos[0] and "'docx'" not in row_pedidos[0]:
                connection.execute("PRAGMA foreign_keys = OFF")
                connection.execute(
                    """
                    CREATE TABLE pedidos_temp (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        nota_pedido TEXT NOT NULL COLLATE NOCASE UNIQUE,
                        numero_pedido TEXT NOT NULL DEFAULT '',
                        cliente TEXT NOT NULL,
                        bultos INTEGER NOT NULL DEFAULT 1 CHECK (bultos >= 1),
                        logistica TEXT NOT NULL CHECK (
                            logistica IN (
                                'Domicilio',
                                'Centro de distribución',
                                'Transporte',
                                'Comisionista',
                                'Mabel',
                                'Canje'
                            )
                        ),
                        armador TEXT NOT NULL,
                        tipo_archivo TEXT NOT NULL CHECK (tipo_archivo IN ('pdf', 'excel', 'docx')),
                        nombre_archivo TEXT NOT NULL,
                        agregado INTEGER NOT NULL DEFAULT 0 CHECK (agregado IN (0, 1)),
                        articulos_descontados INTEGER NOT NULL DEFAULT 0,
                        resumen_items TEXT,
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        estado TEXT NOT NULL DEFAULT 'descontado' CHECK (estado IN ('descontado', 'anulado')),
                        fecha_retiro TEXT NOT NULL DEFAULT '',
                        archivo_descuento TEXT NOT NULL DEFAULT '',
                        cierre_id INTEGER DEFAULT NULL,
                        items_sin_coincidencia TEXT NOT NULL DEFAULT '',
                        numero_guia TEXT NOT NULL DEFAULT '',
                        estado_despacho TEXT NOT NULL DEFAULT 'armado',
                        despachado_at TEXT NOT NULL DEFAULT '',
                        despachado_por TEXT NOT NULL DEFAULT '',
                        entregado_at TEXT NOT NULL DEFAULT '',
                        entregado_por TEXT NOT NULL DEFAULT ''
                    )
                    """
                )
                cols_viejas = {r["name"] for r in connection.execute("PRAGMA table_info(pedidos)").fetchall()}
                cols_comunes = [
                    c for c in [
                        "id", "nota_pedido", "numero_pedido", "cliente", "bultos", "logistica",
                        "armador", "tipo_archivo", "nombre_archivo", "agregado", "articulos_descontados",
                        "resumen_items", "created_at", "estado", "fecha_retiro", "archivo_descuento", "cierre_id"
                    ] if c in cols_viejas
                ]
                cols_str = ", ".join(cols_comunes)
                connection.execute(f"INSERT INTO pedidos_temp ({cols_str}) SELECT {cols_str} FROM pedidos")
                connection.execute("DROP TABLE pedidos")
                connection.execute("ALTER TABLE pedidos_temp RENAME TO pedidos")
                connection.execute("PRAGMA foreign_keys = ON")

            columnas_actuales = {
                r["name"] for r in connection.execute("PRAGMA table_info(pedidos)").fetchall()
            }
            if "archivo_hash" not in columnas_actuales:
                connection.execute("ALTER TABLE pedidos ADD COLUMN archivo_hash TEXT NOT NULL DEFAULT ''")
            if "items_sin_coincidencia" not in columnas_actuales:
                connection.execute("ALTER TABLE pedidos ADD COLUMN items_sin_coincidencia TEXT NOT NULL DEFAULT '[]'")
            for columna, definicion in (
                ("numero_guia", "TEXT NOT NULL DEFAULT ''"),
                ("estado_despacho", "TEXT NOT NULL DEFAULT 'armado'"),
                ("despachado_at", "TEXT NOT NULL DEFAULT ''"),
                ("despachado_por", "TEXT NOT NULL DEFAULT ''"),
                ("entregado_at", "TEXT NOT NULL DEFAULT ''"),
                ("entregado_por", "TEXT NOT NULL DEFAULT ''"),
            ):
                if columna not in columnas_actuales:
                    connection.execute(f"ALTER TABLE pedidos ADD COLUMN {columna} {definicion}")
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_pedidos_estado_despacho ON pedidos(estado_despacho)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_pedidos_turno ON pedidos(estado, cierre_id, id DESC)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_pedido_items_pedido_id ON pedido_items(pedido_id)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_pedidos_archivo_hash ON pedidos(archivo_hash)"
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS pedidos_bloqueos (
                    pedido_id INTEGER PRIMARY KEY,
                    usuario TEXT NOT NULL,
                    bloqueado_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS transacciones_procesadas (
                    tx_id TEXT PRIMARY KEY,
                    accion TEXT NOT NULL,
                    detalle TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        sig_after = self._db_signature()
        if sig_after is not None:
            self._initialized_dbs.add(sig_after)

    @staticmethod
    def _map_pedido(row: sqlite3.Row) -> Pedido:
        claves = row.keys()
        c_id = row["cierre_id"] if "cierre_id" in claves else None
        hash_val = row["archivo_hash"] if "archivo_hash" in row.keys() and row["archivo_hash"] else ""
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
            archivo_hash=hash_val,
            numero_guia=guia_val,
            estado_despacho=(row["estado_despacho"] if "estado_despacho" in claves else "armado") or "armado",
            despachado_at=(row["despachado_at"] if "despachado_at" in claves else "") or "",
            despachado_por=(row["despachado_por"] if "despachado_por" in claves else "") or "",
            entregado_at=(row["entregado_at"] if "entregado_at" in claves else "") or "",
            entregado_por=(row["entregado_por"] if "entregado_por" in claves else "") or "",
        )

    def existe_nota_pedido(self, nota_pedido: str) -> bool:
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
    ) -> Pedido:
        nota_pedido = nota_pedido.strip()
        numero_pedido = numero_pedido.strip()
        cliente = cliente.strip()
        armador = armador.strip()
        nombre_archivo = nombre_archivo.strip()
        tipo_archivo = tipo_archivo.lower().strip()
        fecha_retiro = fecha_retiro.strip()
        archivo_descuento = archivo_descuento.strip()
        archivo_hash = archivo_hash.strip()

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
        if not armador:
            armador = "Operario"

        try:
            with self._connect() as connection, connection:
                cursor = connection.execute(
                    """
                    INSERT INTO pedidos (
                        nota_pedido, numero_pedido, cliente, bultos, logistica, armador,
                        tipo_archivo, nombre_archivo, agregado, articulos_descontados, resumen_items,
                        fecha_retiro, archivo_descuento, archivo_hash, numero_guia, items_sin_coincidencia
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    ),
                )
                nuevo_id = cursor.lastrowid
                if items:
                    for cod, desc, cant in items:
                        connection.execute(
                            """
                            INSERT INTO pedido_items (pedido_id, codigo, descripcion, cantidad)
                            VALUES (?, ?, ?, ?)
                            """,
                            (nuevo_id, str(cod).strip(), str(desc).strip(), int(cant)),
                        )

                row = connection.execute(
                    """
                    SELECT id, nota_pedido, numero_pedido, cliente, bultos, logistica, armador,
                           tipo_archivo, nombre_archivo, agregado, articulos_descontados,
                           resumen_items, created_at, estado, fecha_retiro, archivo_descuento, cierre_id, archivo_hash, numero_guia,
                           estado_despacho, despachado_at, despachado_por, entregado_at, entregado_por
                    FROM pedidos WHERE id = ?
                    """,
                    (nuevo_id,),
                ).fetchone()
        except sqlite3.IntegrityError as error:
            raise ValueError(f"La nota de pedido '{nota_pedido}' ya fue registrada previamente.") from error

        ped_res = self._map_pedido(row)
        self.registrar_auditoria(
            usuario=armador,
            accion="CARGAR_PEDIDO",
            detalle=f"Remito {ped_res.nota_pedido} cargado para '{ped_res.cliente}' ({ped_res.bultos} bulto(s), {ped_res.logistica})",
        )
        return ped_res

    def buscar_pedido_por_hash(self, archivo_hash: str) -> Pedido | None:
        if not archivo_hash:
            return None
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT id, nota_pedido, numero_pedido, cliente, bultos, logistica, armador,
                       tipo_archivo, nombre_archivo, agregado, articulos_descontados,
                       resumen_items, created_at, estado, fecha_retiro, archivo_descuento,
                       cierre_id, archivo_hash, numero_guia,
                           estado_despacho, despachado_at, despachado_por, entregado_at, entregado_por
                FROM pedidos
                WHERE archivo_hash = ? AND estado != 'anulado'
                LIMIT 1
                """,
                (archivo_hash.strip(),),
            ).fetchone()
            if row is None:
                return None
            return self._map_pedido(row)

    def listar_pedidos(self, limit: int = 50) -> list[Pedido]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, nota_pedido, numero_pedido, cliente, bultos, logistica, armador,
                       tipo_archivo, nombre_archivo, agregado, articulos_descontados,
                       resumen_items, created_at, estado, fecha_retiro, archivo_descuento, cierre_id, archivo_hash, numero_guia,
                           estado_despacho, despachado_at, despachado_por, entregado_at, entregado_por
                FROM pedidos
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._map_pedido(r) for r in rows]

    def anular_pedido(self, pedido_id: int, motivo: str = "", usuario: str = "Sistema") -> None:
        with self._connect() as connection, connection:
            row = connection.execute("SELECT nota_pedido FROM pedidos WHERE id = ?", (pedido_id,)).fetchone()
            remito = row["nota_pedido"] if row else f"ID {pedido_id}"
            connection.execute(
                "UPDATE pedidos SET estado = 'anulado' WHERE id = ?",
                (pedido_id,),
            )
        self.registrar_auditoria(
            usuario=usuario,
            accion="ANULAR_PEDIDO",
            detalle=f"Remito {remito} anulado. Motivo: {motivo.strip() or 'Sin especificar'}",
        )

    def obtener_items_sin_coincidencia(self, pedido_id: int) -> list[tuple[str, str]]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT items_sin_coincidencia FROM pedidos WHERE id = ?", (pedido_id,)
            ).fetchone()
        if not row or not row["items_sin_coincidencia"]:
            return []
        try:
            items = json.loads(row["items_sin_coincidencia"])
            return [(str(desc), str(mot)) for desc, mot in items]
        except Exception:
            return []

    def guardar_items_sin_coincidencia(self, pedido_id: int, items: list[tuple[str, str]]) -> None:
        with self._connect() as connection, connection:
            connection.execute(
                "UPDATE pedidos SET items_sin_coincidencia = ? WHERE id = ?",
                (json.dumps(items or [], ensure_ascii=False), pedido_id),
            )

    def obtener_items_pedido(self, pedido_id: int) -> list[tuple[str, str, int]]:
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
        with self._connect() as connection:
            row = connection.execute(
                f"""
                SELECT id, nota_pedido, numero_pedido, cliente, bultos, logistica, armador,
                       tipo_archivo, nombre_archivo, agregado, articulos_descontados,
                       resumen_items, created_at, estado, fecha_retiro, archivo_descuento, cierre_id,
                       archivo_hash, {_COLUMNAS_DESPACHO}
                FROM pedidos WHERE id = ?
                """,
                (pedido_id,),
            ).fetchone()
            if row is None:
                raise OrderStoreError(f"No se encontró el pedido con ID {pedido_id}.")
            pedido_actual = self._map_pedido(row)

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

        if nuevo_cliente:
            try:
                self.registrar_cliente(nuevo_cliente)
            except Exception:
                pass

        detalle_cambios = f"Pedido #{pedido_actual.nota_pedido} modificado: " + "; ".join(cambios)
        self.registrar_auditoria(
            usuario=usuario,
            accion="MODIFICAR_PEDIDO",
            detalle=detalle_cambios,
        )

        with self._connect() as connection:
            row_act = connection.execute(
                f"""
                SELECT id, nota_pedido, numero_pedido, cliente, bultos, logistica, armador,
                       tipo_archivo, nombre_archivo, agregado, articulos_descontados,
                       resumen_items, created_at, estado, fecha_retiro, archivo_descuento, cierre_id,
                       archivo_hash, {_COLUMNAS_DESPACHO}
                FROM pedidos WHERE id = ?
                """,
                (pedido_id,),
            ).fetchone()
        return self._map_pedido(row_act)

    @staticmethod
    def extraer_remito_de_codigo(texto: str) -> str:
        limpio = (texto or "").strip()
        coincidencia = re.search(r"REMITO:\s*([^|]+)", limpio, re.IGNORECASE)
        return coincidencia.group(1).strip() if coincidencia else limpio

    def buscar_pedido_por_nota(self, nota_pedido: str) -> Pedido | None:
        nota = (nota_pedido or "").strip()
        if not nota:
            return None
        with self._connect() as connection:
            row = connection.execute(
                f"""
                SELECT id, nota_pedido, numero_pedido, cliente, bultos, logistica, armador,
                       tipo_archivo, nombre_archivo, agregado, articulos_descontados,
                       resumen_items, created_at, estado, fecha_retiro, archivo_descuento,
                       cierre_id, archivo_hash, {_COLUMNAS_DESPACHO}
                FROM pedidos WHERE nota_pedido = ? COLLATE NOCASE LIMIT 1
                """,
                (nota,),
            ).fetchone()
        return self._map_pedido(row) if row is not None else None

    def actualizar_estado_despacho(
        self,
        pedido_id: int,
        nuevo_estado: str,
        usuario: str = "Sistema",
        permitir_retroceso: bool = False,
    ) -> Pedido:
        if nuevo_estado not in ESTADOS_DESPACHO:
            raise ValueError(f"Estado de despacho inválido: {nuevo_estado}")
        with self._connect() as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT nota_pedido, estado, estado_despacho FROM pedidos WHERE id = ?",
                (pedido_id,),
            ).fetchone()
            if row is None:
                raise OrderStoreError("No se encontró el pedido.")
            if row["estado"] == "anulado":
                raise OrderStoreError("El pedido está anulado y no admite cambios de estado.")
            actual = row["estado_despacho"] or "armado"
            idx_actual = ESTADOS_DESPACHO.index(actual)
            idx_nuevo = ESTADOS_DESPACHO.index(nuevo_estado)
            if idx_nuevo == idx_actual:
                raise OrderStoreError(f"El pedido ya figura como '{actual}'.")
            if idx_nuevo < idx_actual and not permitir_retroceso:
                raise OrderStoreError("Solo un administrador puede retroceder el estado de un pedido.")
            if idx_nuevo > idx_actual + 1:
                raise OrderStoreError(
                    f"Primero debe marcarse como '{ESTADOS_DESPACHO[idx_actual + 1]}'."
                )
            ahora = "strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime')"
            if nuevo_estado == "despachado":
                connection.execute(
                    f"UPDATE pedidos SET estado_despacho = ?, despachado_at = {ahora}, despachado_por = ?, "
                    "entregado_at = '', entregado_por = '' WHERE id = ?",
                    (nuevo_estado, usuario, pedido_id),
                )
            elif nuevo_estado == "entregado":
                connection.execute(
                    f"UPDATE pedidos SET estado_despacho = ?, entregado_at = {ahora}, entregado_por = ? WHERE id = ?",
                    (nuevo_estado, usuario, pedido_id),
                )
            else:
                connection.execute(
                    "UPDATE pedidos SET estado_despacho = ?, despachado_at = '', despachado_por = '', "
                    "entregado_at = '', entregado_por = '' WHERE id = ?",
                    (nuevo_estado, pedido_id),
                )
            remito = row["nota_pedido"]
        self.registrar_auditoria(
            usuario=usuario,
            accion="ESTADO_DESPACHO",
            detalle=f"Remito {remito}: {actual} → {nuevo_estado}",
        )
        with self._connect() as connection:
            fila = connection.execute(
                f"""
                SELECT id, nota_pedido, numero_pedido, cliente, bultos, logistica, armador,
                       tipo_archivo, nombre_archivo, agregado, articulos_descontados,
                       resumen_items, created_at, estado, fecha_retiro, archivo_descuento,
                       cierre_id, archivo_hash, {_COLUMNAS_DESPACHO}
                FROM pedidos WHERE id = ?
                """,
                (pedido_id,),
            ).fetchone()
        return self._map_pedido(fila)

    def avanzar_estado_lote(
        self,
        pedido_ids: list[int],
        nuevo_estado: str,
        usuario: str = "Operador",
    ) -> int:
        if not pedido_ids:
            return 0
        nuevo = nuevo_estado.strip().lower()
        if nuevo not in ESTADOS_DESPACHO:
            raise OrderStoreError(f"Estado de despacho inválido: '{nuevo_estado}'")
        actualizados = 0
        for pid in pedido_ids:
            try:
                self.actualizar_estado_despacho(pid, nuevo, usuario=usuario, permitir_retroceso=True)
                actualizados += 1
            except Exception:
                continue
        return actualizados

    def avanzar_estado_por_codigo(
        self,
        codigo: str = "",
        usuario: str = "Sistema",
        *,
        codigo_qr_o_remito: str = "",
        nuevo_estado: str | None = None,
    ) -> tuple[bool, str, Pedido | None]:
        raw = codigo or codigo_qr_o_remito
        remito = self.extraer_remito_de_codigo(raw)
        pedido = self.buscar_pedido_por_nota(remito)
        if pedido is None:
            return False, f"No se encontró ningún pedido con el remito '{remito}'.", None
        if pedido.estado == "anulado":
            return False, f"El pedido {pedido.nota_pedido} se encuentra ANULADO.", pedido
        if nuevo_estado:
            destino = nuevo_estado.strip().lower()
        else:
            idx = ESTADOS_DESPACHO.index(pedido.estado_despacho)
            if idx >= len(ESTADOS_DESPACHO) - 1:
                return False, f"El pedido {pedido.nota_pedido} ya figura como ENTREGADO.", pedido
            destino = ESTADOS_DESPACHO[idx + 1]
        try:
            actualizado = self.actualizar_estado_despacho(
                pedido.id, destino, usuario=usuario, permitir_retroceso=True
            )
            return (
                True,
                f"Remito #{actualizado.nota_pedido} ({actualizado.cliente}) → {actualizado.estado_despacho.upper()}",
                actualizado,
            )
        except Exception as e:
            return False, str(e), pedido
