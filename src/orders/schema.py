"""Esquema SQLite y migraciones idempotentes para el subsistema de pedidos y clientes."""

from __future__ import annotations

import sqlite3

_COLUMNAS_PEDIDO_COMPLETO = (
    "id, nota_pedido, numero_pedido, cliente, bultos, logistica, armador, "
    "tipo_archivo, nombre_archivo, agregado, articulos_descontados, "
    "resumen_items, created_at, estado, fecha_retiro, archivo_descuento, cierre_id"
)

_COLUMNAS_MIGRACION_DESPACHO = (
    ("numero_guia", "TEXT NOT NULL DEFAULT ''"),
    ("estado_despacho", "TEXT NOT NULL DEFAULT 'armado'"),
    ("despachado_at", "TEXT NOT NULL DEFAULT ''"),
    ("despachado_por", "TEXT NOT NULL DEFAULT ''"),
    ("entregado_at", "TEXT NOT NULL DEFAULT ''"),
    ("entregado_por", "TEXT NOT NULL DEFAULT ''"),
)


def inicializar_esquema_pedidos(connection: sqlite3.Connection) -> None:
    """Crea tablas, ejecuta migraciones pendientes y asegura índices del store de pedidos."""
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
        CREATE TABLE IF NOT EXISTS cierres_mercado (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT NOT NULL,
            tipo_mercado TEXT NOT NULL DEFAULT 'TODOS',
            cantidad_pedidos INTEGER NOT NULL,
            articulos_totales INTEGER NOT NULL,
            resumen_pedidos TEXT NOT NULL,
            archivo_pdf TEXT NOT NULL DEFAULT '',
            archivo_excel TEXT NOT NULL DEFAULT '',
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
    for ddl in (
        "CREATE INDEX IF NOT EXISTS idx_mensajes_destinatario ON mensajes_chat(destinatario, leido)",
        "CREATE INDEX IF NOT EXISTS idx_pedidos_estado ON pedidos(estado)",
        "CREATE INDEX IF NOT EXISTS idx_pedidos_cierre ON pedidos(cierre_id)",
        "CREATE INDEX IF NOT EXISTS idx_pedidos_cliente ON pedidos(cliente)",
        "CREATE INDEX IF NOT EXISTS idx_pedidos_fecha ON pedidos(created_at)",
    ):
        connection.execute(ddl)

    cols_clientes = {r["name"] for r in connection.execute("PRAGMA table_info(clientes)").fetchall()}
    if "codigo" not in cols_clientes:
        connection.execute("ALTER TABLE clientes ADD COLUMN codigo TEXT NOT NULL DEFAULT ''")
    if "direccion" not in cols_clientes:
        connection.execute("ALTER TABLE clientes ADD COLUMN direccion TEXT NOT NULL DEFAULT ''")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_clientes_codigo ON clientes(codigo)")

    cols_cierres = {r["name"] for r in connection.execute("PRAGMA table_info(cierres_jornada)").fetchall()}
    if "archivo_hoja_ruta" not in cols_cierres:
        connection.execute("ALTER TABLE cierres_jornada ADD COLUMN archivo_hoja_ruta TEXT NOT NULL DEFAULT ''")

    _migrar_constraint_docx(connection)
    _migrar_columnas_pedidos(connection)

    for ddl in (
        "CREATE INDEX IF NOT EXISTS idx_pedidos_estado_despacho ON pedidos(estado_despacho)",
        "CREATE INDEX IF NOT EXISTS idx_pedidos_turno ON pedidos(estado, cierre_id, id DESC)",
        "CREATE INDEX IF NOT EXISTS idx_pedidos_cierre_mercado ON pedidos(cierre_mercado_id)",
        "CREATE INDEX IF NOT EXISTS idx_pedido_items_pedido_id ON pedido_items(pedido_id)",
        "CREATE INDEX IF NOT EXISTS idx_pedidos_archivo_hash ON pedidos(archivo_hash)",
    ):
        connection.execute(ddl)

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


def _migrar_constraint_docx(connection: sqlite3.Connection) -> None:
    """Migra tablas `pedidos` heredadas sin tipo `'docx'` en su CHECK constraint."""
    row_pedidos = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='pedidos'"
    ).fetchone()
    if not (row_pedidos and row_pedidos[0] and "'docx'" not in row_pedidos[0]):
        return

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
    cols_comunes = [c for c in _COLUMNAS_PEDIDO_COMPLETO.replace(",", " ").split() if c in cols_viejas]
    cols_str = ", ".join(cols_comunes)
    connection.execute(f"INSERT INTO pedidos_temp ({cols_str}) SELECT {cols_str} FROM pedidos")
    connection.execute("DROP TABLE pedidos")
    connection.execute("ALTER TABLE pedidos_temp RENAME TO pedidos")
    connection.execute("PRAGMA foreign_keys = ON")


def _migrar_columnas_pedidos(connection: sqlite3.Connection) -> None:
    """Agrega columnas de trazabilidad de despacho, hash y faltantes si faltan."""
    columnas_actuales = {
        r["name"] for r in connection.execute("PRAGMA table_info(pedidos)").fetchall()
    }
    if "archivo_hash" not in columnas_actuales:
        connection.execute("ALTER TABLE pedidos ADD COLUMN archivo_hash TEXT NOT NULL DEFAULT ''")
    if "items_sin_coincidencia" not in columnas_actuales:
        connection.execute("ALTER TABLE pedidos ADD COLUMN items_sin_coincidencia TEXT NOT NULL DEFAULT '[]'")
    if "cierre_mercado_id" not in columnas_actuales:
        connection.execute("ALTER TABLE pedidos ADD COLUMN cierre_mercado_id INTEGER DEFAULT NULL")
    for columna, definicion in _COLUMNAS_MIGRACION_DESPACHO:
        if columna not in columnas_actuales:
            connection.execute(f"ALTER TABLE pedidos ADD COLUMN {columna} {definicion}")
