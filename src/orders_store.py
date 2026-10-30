"""Persistencia SQLite para clientes y pedidos en tiempo real."""

from __future__ import annotations

import hashlib
import re
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
    "Canje",
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


ESTADOS_DESPACHO: tuple[str, ...] = ("armado", "despachado", "entregado")
_COLUMNAS_DESPACHO = "numero_guia, estado_despacho, despachado_at, despachado_por, entregado_at, entregado_por"


class OrderStoreError(Exception):
    """Error al operar sobre la base de pedidos o clientes."""


@dataclass(frozen=True)
class Cliente:
    id: int
    nombre: str
    activo: bool
    created_at: str
    codigo: str = ""
    direccion: str = ""


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
    numero_guia: str = ""
    estado_despacho: str = "armado"
    despachado_at: str = ""
    despachado_por: str = ""
    entregado_at: str = ""
    entregado_por: str = ""


@dataclass(frozen=True)
class MensajeChat:
    id: int
    emisor: str
    destinatario: str
    mensaje: str
    leido: bool
    created_at: str

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> MensajeChat:
        return cls(
            id=int(row["id"]),
            emisor=str(row["emisor"]),
            destinatario=str(row["destinatario"]),
            mensaje=str(row["mensaje"]),
            leido=bool(row["leido"]),
            created_at=str(row["created_at"]),
        )


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
                    numero_guia TEXT NOT NULL DEFAULT ''
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

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS mensajes_chat (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    emisor TEXT NOT NULL,
                    destinatario TEXT NOT NULL DEFAULT 'Todos',
                    mensaje TEXT NOT NULL,
                    leido INTEGER NOT NULL DEFAULT 0 CHECK (leido IN (0, 1)),
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_chat_created_at ON mensajes_chat(created_at DESC)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_chat_destinatario ON mensajes_chat(destinatario, leido)")
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
            if "numero_guia" not in columnas_existentes:
                connection.execute("ALTER TABLE pedidos ADD COLUMN numero_guia TEXT NOT NULL DEFAULT ''")
                connection.execute("CREATE INDEX IF NOT EXISTS idx_pedidos_numero_guia ON pedidos(numero_guia)")

            columnas_cierres = {
                r["name"] for r in connection.execute("PRAGMA table_info(cierres_jornada)").fetchall()
            }
            if "archivo_hoja_ruta" not in columnas_cierres:
                connection.execute("ALTER TABLE cierres_jornada ADD COLUMN archivo_hoja_ruta TEXT NOT NULL DEFAULT ''")

            columnas_clientes = {
                r["name"] for r in connection.execute("PRAGMA table_info(clientes)").fetchall()
            }
            if "codigo" not in columnas_clientes:
                connection.execute("ALTER TABLE clientes ADD COLUMN codigo TEXT NOT NULL DEFAULT ''")
            if "direccion" not in columnas_clientes:
                connection.execute("ALTER TABLE clientes ADD COLUMN direccion TEXT NOT NULL DEFAULT ''")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_clientes_codigo ON clientes(codigo)")

            # Migración de check constraints para admitir 'docx' y logística 'Canje'
            try:
                connection.execute("SAVEPOINT test_check_constraints")
                connection.execute(
                    "INSERT INTO pedidos (nota_pedido, cliente, logistica, armador, tipo_archivo, nombre_archivo) "
                    "VALUES ('__test_ml_canje__', '__test__', 'Canje', 'Operario', 'docx', '__test__')"
                )
                connection.execute("ROLLBACK TO test_check_constraints")
            except sqlite3.IntegrityError:
                connection.execute("ROLLBACK TO test_check_constraints")
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
                        cierre_id INTEGER DEFAULT NULL
                    )
                """)
                columnas_ped = [
                    r["name"] for r in connection.execute("PRAGMA table_info(pedidos)").fetchall()
                ]
                temp_ped = [
                    r["name"] for r in connection.execute("PRAGMA table_info(pedidos_temp)").fetchall()
                ]
                comunes = [c for c in columnas_ped if c in temp_ped]
                comunes_str = ", ".join(comunes)
                connection.execute(
                    f"INSERT INTO pedidos_temp ({comunes_str}) SELECT {comunes_str} FROM pedidos"
                )
                connection.execute("DROP TABLE pedidos")
                connection.execute("ALTER TABLE pedidos_temp RENAME TO pedidos")
                connection.execute("PRAGMA foreign_keys = ON")

            # Estados de despacho (armado -> despachado -> entregado)
            columnas_actuales = {
                r["name"] for r in connection.execute("PRAGMA table_info(pedidos)").fetchall()
            }
            if "archivo_hash" not in columnas_actuales:
                connection.execute("ALTER TABLE pedidos ADD COLUMN archivo_hash TEXT NOT NULL DEFAULT ''")
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

    # ==========================
    # GESTIÓN DE CLIENTES
    # ==========================

    def listar_clientes(self) -> list[Cliente]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id, nombre, activo, created_at, codigo, direccion FROM clientes WHERE activo = 1 ORDER BY nombre COLLATE NOCASE"
            ).fetchall()
        return [
            Cliente(
                id=r["id"],
                nombre=r["nombre"],
                activo=bool(r["activo"]),
                created_at=r["created_at"],
                codigo=r["codigo"] or "",
                direccion=r["direccion"] or "",
            )
            for r in rows
        ]

    def listar_nombres_clientes(self) -> list[str]:
        return [c.nombre for c in self.listar_clientes()]

    def buscar_clientes(self, query: str = "") -> list[Cliente]:
        """Busca clientes activos filtrando por nombre, código o dirección."""
        q = (query or "").strip()
        if not q:
            return self.listar_clientes()
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, nombre, activo, created_at, codigo, direccion
                FROM clientes
                WHERE activo = 1 AND (
                    nombre LIKE ? COLLATE NOCASE
                    OR codigo LIKE ?
                    OR direccion LIKE ? COLLATE NOCASE
                )
                ORDER BY nombre COLLATE NOCASE
                """,
                (f"%{q}%", f"%{q}%", f"%{q}%"),
            ).fetchall()
        return [
            Cliente(
                id=r["id"],
                nombre=r["nombre"],
                activo=bool(r["activo"]),
                created_at=r["created_at"],
                codigo=r["codigo"] or "",
                direccion=r["direccion"] or "",
            )
            for r in rows
        ]

    def crear_cliente(
        self,
        nombre: str,
        usuario: str = "Sistema",
        codigo: str = "",
        direccion: str = "",
    ) -> Cliente:
        nombre = nombre.strip()
        codigo = codigo.strip()
        direccion = direccion.strip()
        if not nombre:
            raise ValueError("El nombre del cliente no puede estar vacío.")
        if len(nombre) > 120:
            raise ValueError("El nombre del cliente no puede superar los 120 caracteres.")

        with self._connect() as connection:
            existente = connection.execute(
                "SELECT id, nombre, activo, created_at, codigo, direccion FROM clientes WHERE nombre = ? COLLATE NOCASE",
                (nombre,),
            ).fetchone()

        if existente:
            if existente["activo"] == 1:
                raise ValueError(f"El cliente '{nombre}' ya existe.")
            with self._connect() as connection, connection:
                connection.execute(
                    "UPDATE clientes SET activo = 1, nombre = ?, codigo = COALESCE(NULLIF(?, ''), codigo), direccion = COALESCE(NULLIF(?, ''), direccion) WHERE id = ?",
                    (nombre, codigo, direccion, existente["id"]),
                )
            self.registrar_auditoria(usuario, "REACTIVAR_CLIENTE", f"Reactivación de cliente '{nombre}'")
            return Cliente(
                id=existente["id"],
                nombre=nombre,
                activo=True,
                created_at=existente["created_at"],
                codigo=codigo or (existente["codigo"] or ""),
                direccion=direccion or (existente["direccion"] or ""),
            )

        try:
            with self._connect() as connection, connection:
                cursor = connection.execute(
                    "INSERT INTO clientes (nombre, activo, codigo, direccion) VALUES (?, 1, ?, ?)",
                    (nombre, codigo, direccion),
                )
                row = connection.execute(
                    "SELECT id, nombre, activo, created_at, codigo, direccion FROM clientes WHERE id = ?",
                    (cursor.lastrowid,),
                ).fetchone()
        except sqlite3.IntegrityError as error:
            raise ValueError(f"El cliente '{nombre}' ya existe.") from error
        cliente_nuevo = Cliente(
            id=row["id"],
            nombre=row["nombre"],
            activo=bool(row["activo"]),
            created_at=row["created_at"],
            codigo=row["codigo"] or "",
            direccion=row["direccion"] or "",
        )
        self.registrar_auditoria(usuario, "CREAR_CLIENTE", f"Alta de cliente '{nombre}' (código: '{codigo}')")
        return cliente_nuevo

    def registrar_cliente(
        self,
        nombre: str,
        usuario: str = "Sistema",
        codigo: str = "",
        direccion: str = "",
    ) -> Cliente:
        """Alias compatible para crear o asegurar la existencia de un cliente."""
        return self.crear_cliente(nombre, usuario=usuario, codigo=codigo, direccion=direccion)

    def obtener_o_crear_cliente(
        self,
        nombre: str,
        codigo: str = "",
        direccion: str = "",
        usuario: str = "Sistema",
    ) -> Cliente:
        """Busca un cliente por nombre; si no existe, lo crea. Si existe y se proporcionan código o dirección vacíos previamente, los actualiza."""
        nombre = nombre.strip()
        codigo = codigo.strip()
        direccion = direccion.strip()
        if not nombre:
            raise ValueError("El nombre del cliente no puede estar vacío.")

        with self._connect() as connection:
            existente = connection.execute(
                "SELECT id, nombre, activo, created_at, codigo, direccion FROM clientes WHERE nombre = ? COLLATE NOCASE",
                (nombre,),
            ).fetchone()
            if not existente and codigo:
                existente = connection.execute(
                    "SELECT id, nombre, activo, created_at, codigo, direccion FROM clientes WHERE codigo = ? AND codigo != ''",
                    (codigo,),
                ).fetchone()

        if existente:
            c_id = existente["id"]
            c_nom = existente["nombre"]
            c_activo = bool(existente["activo"])
            c_cod = existente["codigo"] or ""
            c_dir = existente["direccion"] or ""
            update_needed = False
            if not c_activo:
                c_activo = True
                update_needed = True
            if codigo and not c_cod:
                c_cod = codigo
                update_needed = True
            if direccion and not c_dir:
                c_dir = direccion
                update_needed = True

            if update_needed:
                with self._connect() as connection, connection:
                    connection.execute(
                        "UPDATE clientes SET activo = 1, codigo = ?, direccion = ? WHERE id = ?",
                        (c_cod, c_dir, c_id),
                    )
            return Cliente(
                id=c_id,
                nombre=c_nom,
                activo=c_activo,
                created_at=existente["created_at"],
                codigo=c_cod,
                direccion=c_dir,
            )

        return self.crear_cliente(nombre, usuario=usuario, codigo=codigo, direccion=direccion)

    def actualizar_cliente(
        self,
        cliente_id: int,
        nuevo_nombre: str,
        actualizar_pedidos: bool = True,
        usuario: str = "Sistema",
        codigo: str | None = None,
        direccion: str | None = None,
    ) -> Cliente:
        """Actualiza el nombre, código y dirección de un cliente existente y opcionalmente sus pedidos vinculados."""
        nuevo_nombre = nuevo_nombre.strip()
        if not nuevo_nombre:
            raise ValueError("El nombre del cliente no puede estar vacío.")
        if len(nuevo_nombre) > 120:
            raise ValueError("El nombre del cliente no puede superar los 120 caracteres.")

        with self._connect() as connection:
            actual = connection.execute(
                "SELECT id, nombre, activo, created_at, codigo, direccion FROM clientes WHERE id = ?",
                (cliente_id,),
            ).fetchone()
            if not actual:
                raise ValueError(f"No se encontró el cliente con ID {cliente_id}.")

            nombre_anterior = actual["nombre"]
            if nombre_anterior.strip().lower() != nuevo_nombre.lower():
                existente = connection.execute(
                    "SELECT id FROM clientes WHERE nombre = ? COLLATE NOCASE AND id != ?",
                    (nuevo_nombre, cliente_id),
                ).fetchone()
                if existente:
                    raise ValueError(f"Ya existe otro cliente con el nombre '{nuevo_nombre}'.")

            nuevo_codigo = actual["codigo"] if codigo is None else codigo.strip()
            nueva_direccion = actual["direccion"] if direccion is None else direccion.strip()

            with connection:
                connection.execute(
                    "UPDATE clientes SET nombre = ?, codigo = ?, direccion = ? WHERE id = ?",
                    (nuevo_nombre, nuevo_codigo, nueva_direccion, cliente_id),
                )
                if actualizar_pedidos and nombre_anterior != nuevo_nombre:
                    connection.execute(
                        "UPDATE pedidos SET cliente = ? WHERE cliente = ? COLLATE NOCASE",
                        (nuevo_nombre, nombre_anterior),
                    )

        self.registrar_auditoria(
            usuario,
            "ACTUALIZAR_CLIENTE",
            f"Cliente ID {cliente_id} actualizado ('{nombre_anterior}' -> '{nuevo_nombre}', cod: '{nuevo_codigo}')",
        )
        return Cliente(
            id=cliente_id,
            nombre=nuevo_nombre,
            activo=bool(actual["activo"]),
            created_at=actual["created_at"],
            codigo=nuevo_codigo,
            direccion=nueva_direccion,
        )

    def eliminar_cliente(self, cliente_id: int, usuario: str = "Sistema") -> None:
        """Da de baja lógica a un cliente desactivándolo."""
        with self._connect() as connection:
            actual = connection.execute(
                "SELECT id, nombre FROM clientes WHERE id = ?",
                (cliente_id,),
            ).fetchone()
            if not actual:
                raise ValueError(f"No se encontró el cliente con ID {cliente_id}.")

            with connection:
                connection.execute(
                    "UPDATE clientes SET activo = 0 WHERE id = ?",
                    (cliente_id,),
                )

        self.registrar_auditoria(
            usuario,
            "ELIMINAR_CLIENTE",
            f"Cliente ID {cliente_id} ('{actual['nombre']}') desactivado",
        )

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
        numero_guia: str = "",
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
                        fecha_retiro, archivo_descuento, archivo_hash, numero_guia
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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

    def listar_pedidos_pendientes_cierre(self) -> list[Pedido]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, nota_pedido, numero_pedido, cliente, bultos, logistica, armador,
                       tipo_archivo, nombre_archivo, agregado, articulos_descontados,
                       resumen_items, created_at, estado, fecha_retiro, archivo_descuento, cierre_id, archivo_hash, numero_guia,
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
        """Devuelve productos consolidados pendientes de cierre: (codigo, descripcion, total_cantidad, [notas_pedido]).
        
        Agrupa estrictamente por código de producto (normalizado) deduplicando notas de pedido
        para evitar líneas separadas si una misma referencia tuviera descripciones levemente distintas.
        """
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
            # Deduplicar preservando orden
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
        # La auditoría usa otra conexión: debe ejecutarse una vez liberada la transacción.
        self.registrar_auditoria(
            usuario=usuario,
            accion="ANULAR_PEDIDO",
            detalle=f"Remito {remito} anulado. Motivo: {motivo.strip() or 'Sin especificar'}",
        )

    def obtener_items_pedido(self, pedido_id: int) -> list[tuple[str, str, int]]:
        """Devuelve los ítems asociados a un pedido: [(codigo, descripcion, cantidad), ...]."""
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
        """Actualiza la información de cabecera de un pedido y registra auditoría."""
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

    # ==========================
    # ESTADOS DE DESPACHO
    # ==========================

    @staticmethod
    def extraer_remito_de_codigo(texto: str) -> str:
        """Obtiene el número de remito desde el QR del rótulo ('REMITO:123|CLIENTE:...') o texto plano."""
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
        """Avanza (o retrocede, si se permite) el estado logístico de un pedido."""
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
        """Avanza en lote el estado de despacho de múltiples pedidos. Retorna la cantidad actualizada."""
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
        """Avanza al siguiente estado (o fija nuevo_estado) el pedido identificado por QR o remito."""
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
        filtro: str = "",
    ) -> list[RegistroAuditoria]:
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

    def obtener_pedido_resumen_chat(self, nota_pedido: str) -> str:
        """Resumen de una línea de un pedido, para enlazarlo desde el chat de equipo."""
        pedido = self.buscar_pedido_por_nota(nota_pedido)
        if pedido is None:
            return ""
        return (
            f"Pedido #{pedido.nota_pedido} · {pedido.cliente} · {pedido.bultos} bulto(s) · "
            f"{pedido.logistica} · {pedido.estado_despacho.upper()}"
            + (" · ANULADO" if pedido.estado == "anulado" else "")
        )

    def enviar_mensaje_chat(
        self,
        emisor: str,
        mensaje: str,
        destinatario: str = "Todos",
    ) -> MensajeChat:
        msg_limpio = mensaje.strip()
        if not msg_limpio:
            raise ValueError("El mensaje no puede estar vacío.")
        dest_limpio = (destinatario or "Todos").strip()
        with self._connect() as connection, connection:
            cursor = connection.execute(
                """
                INSERT INTO mensajes_chat (emisor, destinatario, mensaje, leido)
                VALUES (?, ?, ?, 0)
                """,
                (emisor.strip(), dest_limpio, msg_limpio),
            )
            nuevo_id = int(cursor.lastrowid)
            row = connection.execute(
                "SELECT id, emisor, destinatario, mensaje, leido, created_at FROM mensajes_chat WHERE id = ?",
                (nuevo_id,),
            ).fetchone()
            return MensajeChat.from_row(row)

    def listar_mensajes_chat(
        self,
        usuario: str,
        limite: int = 60,
    ) -> list[MensajeChat]:
        usr_limpio = usuario.strip()
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, emisor, destinatario, mensaje, leido, created_at
                FROM mensajes_chat
                WHERE destinatario = 'Todos' OR destinatario = ? OR emisor = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (usr_limpio, usr_limpio, limite),
            ).fetchall()
            mensajes = [MensajeChat.from_row(r) for r in rows]
            mensajes.reverse()
            return mensajes

    def contar_mensajes_no_leidos(self, usuario: str) -> int:
        usr_limpio = usuario.strip()
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT COUNT(*) as total
                FROM mensajes_chat
                WHERE (destinatario = 'Todos' OR destinatario = ?)
                  AND leido = 0
                  AND emisor != ?
                """,
                (usr_limpio, usr_limpio),
            ).fetchone()
            return int(row["total"]) if row else 0

    def marcar_mensajes_leidos(self, usuario: str) -> None:
        usr_limpio = usuario.strip()
        with self._connect() as connection, connection:
            connection.execute(
                """
                UPDATE mensajes_chat
                SET leido = 1
                WHERE (destinatario = 'Todos' OR destinatario = ?)
                  AND leido = 0
                  AND emisor != ?
                """,
                (usr_limpio, usr_limpio),
            )
