"""Persistencia SQLite para clientes y pedidos en tiempo real."""

import hashlib
import sqlite3
from contextlib import closing, contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Generator, Literal


LOGISTICA_OPCIONES: tuple[str, ...] = (
    "Domicilio",
    "Centro de distribución",
    "Transporte",
    "Comisionista",
    "Mabel",
)


def calcular_hash_archivo(ruta_o_bytes: Path | bytes | str) -> str:
    """Calcula el hash SHA-256 de un archivo o flujo de bytes para detección de duplicados."""
    hasher = hashlib.sha256()
    if isinstance(ruta_o_bytes, (str, Path)):
        p = Path(ruta_o_bytes)
        if not p.exists() or not p.is_file():
            return ""
        try:
            with open(p, "rb") as f:
                while chunk := f.read(65536):
                    hasher.update(chunk)
        except Exception:
            return ""
    elif isinstance(ruta_o_bytes, (bytes, bytearray)):
        hasher.update(ruta_o_bytes)
    else:
        return ""
    return hasher.hexdigest()


class OrderStoreError(Exception):
    """Error al operar sobre la base de pedidos o clientes."""


@dataclass(frozen=True)
class Cliente:
    id: int
    nombre: str
    activo: bool
    created_at: str


@dataclass(frozen=True)
class CierreJornada:
    id: int
    usuario: str
    cantidad_pedidos: int
    articulos_totales: int
    resumen_pedidos: str
    archivo_pdf: str
    archivo_excel: str
    created_at: str
    archivo_hoja_ruta: str = ""


@dataclass(frozen=True)
class RegistroAuditoria:
    id: int
    usuario: str
    accion: str
    detalle: str
    created_at: str


@dataclass(frozen=True)
class Pedido:
    id: int
    nota_pedido: str
    numero_pedido: str
    cliente: str
    bultos: int
    logistica: str
    armador: str
    tipo_archivo: str
    nombre_archivo: str
    agregado: bool
    articulos_descontados: int
    resumen_items: str
    created_at: str
    estado: str
    fecha_retiro: str = ""
    archivo_descuento: str = ""
    cierre_id: int | None = None
    archivo_hash: str = ""


class OrderStore:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def _connect(self) -> Generator[sqlite3.Connection, None, None]:
        with closing(sqlite3.connect(self.database_path, timeout=10)) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("PRAGMA busy_timeout = 10000")
            yield connection

    def _initialize(self) -> None:
        with self._connect() as connection, connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS clientes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nombre TEXT NOT NULL COLLATE NOCASE UNIQUE,
                    activo INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1)),
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
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
                            'Mabel'
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
                    archivo_hash TEXT NOT NULL DEFAULT ''
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
            connection.execute("CREATE INDEX IF NOT EXISTS idx_logs_created_at ON logs_auditoria(created_at DESC)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_logs_usuario ON logs_auditoria(usuario)")
            # Migración de columnas por si la tabla ya existía
            columnas_existentes = {
                r["name"] for r in connection.execute("PRAGMA table_info(pedidos)").fetchall()
            }
            if "numero_pedido" not in columnas_existentes:
                connection.execute("ALTER TABLE pedidos ADD COLUMN numero_pedido TEXT NOT NULL DEFAULT ''")
            if "agregado" not in columnas_existentes:
                connection.execute("ALTER TABLE pedidos ADD COLUMN agregado INTEGER NOT NULL DEFAULT 0 CHECK (agregado IN (0, 1))")
            if "fecha_retiro" not in columnas_existentes:
                connection.execute("ALTER TABLE pedidos ADD COLUMN fecha_retiro TEXT NOT NULL DEFAULT ''")
            if "archivo_descuento" not in columnas_existentes:
                connection.execute("ALTER TABLE pedidos ADD COLUMN archivo_descuento TEXT NOT NULL DEFAULT ''")
            if "cierre_id" not in columnas_existentes:
                connection.execute("ALTER TABLE pedidos ADD COLUMN cierre_id INTEGER DEFAULT NULL")
            if "archivo_hash" not in columnas_existentes:
                connection.execute("ALTER TABLE pedidos ADD COLUMN archivo_hash TEXT NOT NULL DEFAULT ''")
                connection.execute("CREATE INDEX IF NOT EXISTS idx_pedidos_archivo_hash ON pedidos(archivo_hash)")

            columnas_cierres = {
                r["name"] for r in connection.execute("PRAGMA table_info(cierres_jornada)").fetchall()
            }
            if "archivo_hoja_ruta" not in columnas_cierres:
                connection.execute("ALTER TABLE cierres_jornada ADD COLUMN archivo_hoja_ruta TEXT NOT NULL DEFAULT ''")

            # Migración de check constraint de tipo_archivo para admitir 'docx'
            try:
                connection.execute("SAVEPOINT test_docx")
                connection.execute(
                    "INSERT INTO pedidos (nota_pedido, cliente, logistica, armador, tipo_archivo, nombre_archivo) "
                    "VALUES ('__test_ml__', '__test__', 'Transporte', 'Operario', 'docx', '__test__')"
                )
                connection.execute("ROLLBACK TO test_docx")
            except sqlite3.IntegrityError:
                connection.execute("ROLLBACK TO test_docx")
                connection.execute("PRAGMA foreign_keys = OFF")
                connection.execute("""
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
                                'Mabel'
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
                        cierre_id INTEGER DEFAULT NULL
                    )
                """)
                connection.execute(
                    "INSERT INTO pedidos_temp SELECT id, nota_pedido, numero_pedido, cliente, bultos, logistica, "
                    "armador, tipo_archivo, nombre_archivo, agregado, articulos_descontados, resumen_items, "
                    "created_at, estado, fecha_retiro, archivo_descuento, cierre_id FROM pedidos"
                )
                connection.execute("DROP TABLE pedidos")
                connection.execute("ALTER TABLE pedidos_temp RENAME TO pedidos")
                connection.execute("PRAGMA foreign_keys = ON")

    # ==========================
    # GESTIÓN DE CLIENTES
    # ==========================

    def listar_clientes(self) -> list[Cliente]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id, nombre, activo, created_at FROM clientes WHERE activo = 1 ORDER BY nombre COLLATE NOCASE"
            ).fetchall()
        return [
            Cliente(
                id=r["id"],
                nombre=r["nombre"],
                activo=bool(r["activo"]),
                created_at=r["created_at"],
            )
            for r in rows
        ]

    def listar_nombres_clientes(self) -> list[str]:
        return [c.nombre for c in self.listar_clientes()]

    def crear_cliente(self, nombre: str) -> Cliente:
        nombre = nombre.strip()
        if not nombre:
            raise ValueError("El nombre del cliente no puede estar vacío.")
        if len(nombre) > 120:
            raise ValueError("El nombre del cliente no puede superar los 120 caracteres.")
        try:
            with self._connect() as connection, connection:
                cursor = connection.execute(
                    "INSERT INTO clientes (nombre, activo) VALUES (?, 1)",
                    (nombre,),
                )
                row = connection.execute(
                    "SELECT id, nombre, activo, created_at FROM clientes WHERE id = ?",
                    (cursor.lastrowid,),
                ).fetchone()
        except sqlite3.IntegrityError as error:
            raise ValueError(f"El cliente '{nombre}' ya existe.") from error
        cliente_nuevo = Cliente(
            id=row["id"],
            nombre=row["nombre"],
            activo=bool(row["activo"]),
            created_at=row["created_at"],
        )
        self.registrar_auditoria("Sistema", "CREAR_CLIENTE", f"Alta de cliente '{nombre}'")
        return cliente_nuevo

    # ==========================
    # GESTIÓN DE PEDIDOS
    # ==========================

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
                        fecha_retiro, archivo_descuento, archivo_hash
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                           resumen_items, created_at, estado, fecha_retiro, archivo_descuento, cierre_id, archivo_hash
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

    @staticmethod
    def _map_pedido(row: sqlite3.Row) -> Pedido:
        c_id = row["cierre_id"] if "cierre_id" in row.keys() else None
        hash_val = row["archivo_hash"] if "archivo_hash" in row.keys() and row["archivo_hash"] else ""
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
        )

    def buscar_pedido_por_hash(self, archivo_hash: str) -> Pedido | None:
        """Busca si ya existe un comprobante no anulado con el mismo hash de archivo."""
        if not archivo_hash:
            return None
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT id, nota_pedido, numero_pedido, cliente, bultos, logistica, armador,
                       tipo_archivo, nombre_archivo, agregado, articulos_descontados,
                       resumen_items, created_at, estado, fecha_retiro, archivo_descuento,
                       cierre_id, archivo_hash
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
                       resumen_items, created_at, estado, fecha_retiro, archivo_descuento, cierre_id, archivo_hash
                FROM pedidos
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._map_pedido(r) for r in rows]

    def listar_pedidos_pendientes_cierre(self) -> list[Pedido]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, nota_pedido, numero_pedido, cliente, bultos, logistica, armador,
                       tipo_archivo, nombre_archivo, agregado, articulos_descontados,
                       resumen_items, created_at, estado, fecha_retiro, archivo_descuento, cierre_id, archivo_hash
                FROM pedidos
                WHERE cierre_id IS NULL AND estado = 'descontado'
                ORDER BY id ASC
                """
            ).fetchall()
        return [self._map_pedido(r) for r in rows]
        return [self._map_pedido(r) for r in rows]

    def obtener_items_pendientes_cierre(self) -> list[tuple[str, str, int, list[str]]]:
        """Devuelve productos consolidados pendientes de cierre: (codigo, descripcion, total_cantidad, [notas_pedido])."""
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT pi.codigo, pi.descripcion, SUM(pi.cantidad) as total_cant,
                       GROUP_CONCAT(p.nota_pedido, ', ') as remitos_origen
                FROM pedido_items pi
                JOIN pedidos p ON p.id = pi.pedido_id
                WHERE p.cierre_id IS NULL AND p.estado = 'descontado'
                GROUP BY pi.codigo, pi.descripcion
                ORDER BY pi.codigo ASC
                """
            ).fetchall()
        return [
            (
                r["codigo"],
                r["descripcion"],
                int(r["total_cant"]),
                [n.strip() for n in (r["remitos_origen"] or "").split(",") if n.strip()],
            )
            for r in rows
        ]

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
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, nota_pedido, numero_pedido, cliente, bultos, logistica,
                       armador, tipo_archivo, nombre_archivo, agregado, articulos_descontados,
                       resumen_items, created_at, estado, fecha_retiro, archivo_descuento,
                       cierre_id, archivo_hash
                FROM pedidos
                WHERE cierre_id = ?
                ORDER BY logistica ASC, id ASC
                """,
                (cierre_id,),
            ).fetchall()
        return [self._map_pedido(r) for r in rows]

    def actualizar_hoja_ruta_cierre(self, cierre_id: int, archivo_hoja_ruta: str) -> None:
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

    def registrar_auditoria(self, usuario: str, accion: str, detalle: str) -> None:
        with self._connect() as connection, connection:
            connection.execute(
                "INSERT INTO logs_auditoria (usuario, accion, detalle) VALUES (?, ?, ?)",
                (usuario or "Sistema", accion, detalle),
            )

    def listar_auditoria(
        self,
        limit: int = 150,
        filtro_usuario: str = "",
        filtro_accion: str = "",
        filtro_texto: str = "",
    ) -> list[RegistroAuditoria]:
        query = "SELECT id, usuario, accion, detalle, created_at FROM logs_auditoria WHERE 1=1"
        params: list = []
        if filtro_usuario:
            query += " AND usuario LIKE ?"
            params.append(f"%{filtro_usuario}%")
        if filtro_accion:
            query += " AND accion = ?"
            params.append(filtro_accion)
        if filtro_texto:
            query += " AND (detalle LIKE ? OR accion LIKE ? OR usuario LIKE ?)"
            params.append(f"%{filtro_texto}%")
            params.append(f"%{filtro_texto}%")
            params.append(f"%{filtro_texto}%")
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

    def obtener_metricas_dashboard(self) -> dict:
        with self._connect() as connection:
            res_totales = connection.execute(
                """
                SELECT COUNT(*) as total_pedidos,
                       COALESCE(SUM(bultos), 0) as total_bultos,
                       COUNT(CASE WHEN cierre_id IS NOT NULL THEN 1 END) as pedidos_cerrados,
                       COUNT(CASE WHEN cierre_id IS NULL AND estado = 'descontado' THEN 1 END) as pedidos_pendientes,
                       COUNT(CASE WHEN estado = 'anulado' THEN 1 END) as pedidos_anulados
                FROM pedidos
                """
            ).fetchone()

            rows_logistica = connection.execute(
                """
                SELECT logistica, COUNT(*) as cant, COALESCE(SUM(bultos), 0) as bultos
                FROM pedidos
                WHERE estado = 'descontado'
                GROUP BY logistica
                ORDER BY cant DESC
                """
            ).fetchall()

            rows_armador = connection.execute(
                """
                SELECT armador, COUNT(*) as cant, COALESCE(SUM(bultos), 0) as bultos
                FROM pedidos
                WHERE estado = 'descontado'
                GROUP BY armador
                ORDER BY cant DESC
                """
            ).fetchall()

            rows_top_items = connection.execute(
                """
                SELECT pi.codigo, pi.descripcion, SUM(pi.cantidad) as total_cant
                FROM pedido_items pi
                JOIN pedidos p ON p.id = pi.pedido_id
                WHERE p.estado = 'descontado'
                GROUP BY pi.codigo, pi.descripcion
                ORDER BY total_cant DESC
                LIMIT 10
                """
            ).fetchall()

            cant_cierres = connection.execute("SELECT COUNT(*) FROM cierres_jornada").fetchone()[0]

            return {
                "total_pedidos": int(res_totales["total_pedidos"] or 0),
                "total_bultos": int(res_totales["total_bultos"] or 0),
                "pedidos_cerrados": int(res_totales["pedidos_cerrados"] or 0),
                "pedidos_pendientes": int(res_totales["pedidos_pendientes"] or 0),
                "pedidos_anulados": int(res_totales["pedidos_anulados"] or 0),
                "total_cierres": int(cant_cierres or 0),
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
