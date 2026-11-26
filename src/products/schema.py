"""Esquema DDL, migraciones idempotentes, índices, triggers y vistas SQLite para productos."""

from __future__ import annotations

from pathlib import Path
import sqlite3

from ..core.sqlite_migrations import MigrationStep, aplicar_migraciones_sqlite

PRODUCTS_SCHEMA_VERSION = 4


def _crear_tablas_base_productos(connection: sqlite3.Connection) -> None:
    """Crea tablas base de catálogo y movimientos de inventario."""
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS products (
            code TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            stock INTEGER NOT NULL DEFAULT 0,
            stock_minimo INTEGER NOT NULL DEFAULT 5,
            stock_maximo INTEGER NOT NULL DEFAULT 100,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS product_catalog_rows (
            id INTEGER PRIMARY KEY,
            product_code TEXT NOT NULL REFERENCES products(code),
            display_name TEXT NOT NULL,
            display_order INTEGER NOT NULL,
            template_row INTEGER
        )
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_product_catalog_rows_order
        ON product_catalog_rows(display_order)
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS product_catalog_metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS stock_movements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_code TEXT NOT NULL,
            product_name TEXT NOT NULL DEFAULT '',
            quantity INTEGER NOT NULL,
            movement_type TEXT NOT NULL,
            usuario TEXT NOT NULL DEFAULT 'sistema',
            detalle TEXT NOT NULL DEFAULT '',
            registered_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime'))
        )
        """
    )


def _migrar_columnas_indices_trigger_productos(connection: sqlite3.Connection) -> None:
    """Aplica columnas incrementales, índices, trigger de auditoría y vista de reposición."""
    columns = {row["name"] for row in connection.execute("PRAGMA table_info(products)")}
    if "active" not in columns:
        connection.execute("ALTER TABLE products ADD COLUMN active INTEGER NOT NULL DEFAULT 1")
    if "stock_minimo" not in columns:
        connection.execute("ALTER TABLE products ADD COLUMN stock_minimo INTEGER NOT NULL DEFAULT 5")
    if "stock_maximo" not in columns:
        connection.execute("ALTER TABLE products ADD COLUMN stock_maximo INTEGER NOT NULL DEFAULT 100")
    if "stock_fisico" not in columns:
        connection.execute("ALTER TABLE products ADD COLUMN stock_fisico INTEGER DEFAULT NULL")
    if "cod_barras" not in columns:
        connection.execute("ALTER TABLE products ADD COLUMN cod_barras TEXT DEFAULT ''")
    if "ubicacion" not in columns:
        connection.execute("ALTER TABLE products ADD COLUMN ubicacion TEXT NOT NULL DEFAULT ''")

    connection.execute("CREATE INDEX IF NOT EXISTS idx_products_cod_barras ON products(cod_barras)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_products_ubicacion ON products(ubicacion)")

    cols_mov = {row["name"] for row in connection.execute("PRAGMA table_info(stock_movements)")}
    if "usuario" not in cols_mov:
        connection.execute(
            "ALTER TABLE stock_movements ADD COLUMN usuario TEXT NOT NULL DEFAULT 'sistema'"
        )
    if "detalle" not in cols_mov:
        connection.execute(
            "ALTER TABLE stock_movements ADD COLUMN detalle TEXT NOT NULL DEFAULT ''"
        )
    connection.execute("CREATE INDEX IF NOT EXISTS idx_stock_movements_code ON stock_movements(product_code)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_stock_movements_date ON stock_movements(registered_at)")

    connection.execute(
        """
        CREATE TRIGGER IF NOT EXISTS trg_auditoria_stock
        AFTER UPDATE OF stock ON products
        WHEN NEW.stock != OLD.stock
        BEGIN
            INSERT INTO stock_movements (
                product_code,
                product_name,
                quantity,
                movement_type,
                registered_at
            )
            VALUES (
                NEW.code,
                NEW.name,
                NEW.stock - OLD.stock,
                CASE
                    WHEN NEW.stock < OLD.stock THEN 'descuento'
                    ELSE 'ingreso_fabrica'
                END,
                strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime')
            );
        END;
        """
    )
    connection.execute(
        """
        CREATE VIEW IF NOT EXISTS v_analisis_reposicion AS
        SELECT
            p.code AS code,
            p.name AS name,
            p.stock AS stock,
            p.stock_minimo AS stock_minimo,
            p.stock_maximo AS stock_maximo,
            CASE
                WHEN p.stock <= 0 THEN 'AGOTADO'
                WHEN p.stock <= p.stock_minimo THEN 'QUIEBRE_INMINENTE'
                WHEN p.stock > p.stock_maximo THEN 'SOBRESTOCK'
                ELSE 'OPTIMO'
            END AS estado_inventario,
            CASE
                WHEN p.stock <= p.stock_minimo THEN MAX(0, p.stock_maximo - p.stock)
                ELSE 0
            END AS cantidad_sugerida_pedir
        FROM products p
        WHERE p.active = 1;
        """
    )


def _crear_tablas_despacho_notificaciones_e_inventario(connection: sqlite3.Connection) -> None:
    """Crea tablas de trazabilidad de despachos, notificaciones admin e inventario físico."""
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS despachos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime')),
            tipo_origen TEXT NOT NULL,
            nombre_archivo TEXT NOT NULL,
            total_articulos INTEGER NOT NULL DEFAULT 0,
            reporte_archivo TEXT
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS despacho_detalles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            despacho_id INTEGER NOT NULL REFERENCES despachos(id) ON DELETE CASCADE,
            product_code TEXT NOT NULL REFERENCES products(code),
            cantidad_descontada INTEGER NOT NULL,
            stock_anterior INTEGER NOT NULL,
            stock_nuevo INTEGER NOT NULL
        )
        """
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_despacho_detalles_despacho ON despacho_detalles(despacho_id)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_despacho_detalles_product ON despacho_detalles(product_code)"
    )

    columns_despachos = {row["name"] for row in connection.execute("PRAGMA table_info(despachos)")}
    if "usuario" not in columns_despachos:
        connection.execute(
            "ALTER TABLE despachos ADD COLUMN usuario TEXT NOT NULL DEFAULT 'sistema'"
        )

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS admin_notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            operator_username TEXT NOT NULL,
            notification_type TEXT NOT NULL DEFAULT 'descuento',
            details TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime')),
            is_read INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_admin_notifications_read ON admin_notifications(is_read)"
    )

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS inventario_fisico (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime')),
            usuario TEXT NOT NULL DEFAULT 'operador',
            nombre_archivo TEXT NOT NULL,
            reporte_unificado TEXT NOT NULL DEFAULT '',
            total_relevados INTEGER NOT NULL DEFAULT 0,
            total_diferencias INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS inventario_fisico_detalles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            inventario_id INTEGER NOT NULL REFERENCES inventario_fisico(id) ON DELETE CASCADE,
            product_code TEXT NOT NULL,
            product_name TEXT NOT NULL DEFAULT '',
            stock_digital INTEGER NOT NULL,
            stock_fisico INTEGER NOT NULL,
            diferencia INTEGER NOT NULL,
            estado TEXT NOT NULL
        )
        """
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_inv_fisico_det_inv ON inventario_fisico_detalles(inventario_id)"
    )


def _migrar_fase4_reservas_ubicaciones_lotes(connection: sqlite3.Connection) -> None:
    """Crea tablas de multi-ubicación, lotes FEFO, reservas de stock y backfill inicial."""
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS product_locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_code TEXT NOT NULL REFERENCES products(code) ON UPDATE CASCADE ON DELETE CASCADE,
            ubicacion TEXT NOT NULL,
            tipo_zona TEXT NOT NULL DEFAULT 'picking'
                CHECK (tipo_zona IN ('picking', 'pulmon', 'pallet', 'recepcion', 'cuarentena')),
            stock INTEGER NOT NULL DEFAULT 0 CHECK (stock >= 0),
            capacidad_max INTEGER NOT NULL DEFAULT 0 CHECK (capacidad_max >= 0),
            es_principal INTEGER NOT NULL DEFAULT 0 CHECK (es_principal IN (0, 1)),
            updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime')),
            UNIQUE(product_code, ubicacion)
        )
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_product_locations_sku
        ON product_locations(product_code, es_principal DESC)
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_product_locations_ubic
        ON product_locations(ubicacion)
        """
    )
    connection.execute(
        """
        INSERT OR IGNORE INTO product_locations (
            product_code, ubicacion, tipo_zona, stock, capacidad_max, es_principal
        )
        SELECT
            code,
            UPPER(TRIM(ubicacion)),
            'picking',
            CASE WHEN stock > 0 THEN stock ELSE 0 END,
            0,
            1
        FROM products
        WHERE TRIM(COALESCE(ubicacion, '')) != ''
        """
    )

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS stock_lots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_code TEXT NOT NULL REFERENCES products(code) ON UPDATE CASCADE ON DELETE CASCADE,
            lote TEXT NOT NULL,
            ubicacion TEXT NOT NULL DEFAULT '',
            fecha_vencimiento TEXT NOT NULL DEFAULT '',
            stock INTEGER NOT NULL DEFAULT 0 CHECK (stock >= 0),
            estado TEXT NOT NULL DEFAULT 'disponible'
                CHECK (estado IN ('disponible', 'bloqueado', 'vencido', 'agotado')),
            notas TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime')),
            updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime')),
            UNIQUE(product_code, lote, ubicacion)
        )
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_stock_lots_fefo
        ON stock_lots(product_code, estado, fecha_vencimiento, id)
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_stock_lots_vencimiento
        ON stock_lots(fecha_vencimiento, estado)
        """
    )

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS stock_reservations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            referencia_tipo TEXT NOT NULL DEFAULT 'ola_picking',
            referencia_id TEXT NOT NULL,
            product_code TEXT NOT NULL REFERENCES products(code) ON UPDATE CASCADE ON DELETE CASCADE,
            cantidad INTEGER NOT NULL CHECK (cantidad > 0),
            estado TEXT NOT NULL DEFAULT 'activa'
                CHECK (estado IN ('activa', 'consolidada', 'liberada')),
            lot_id INTEGER REFERENCES stock_lots(id) ON DELETE SET NULL,
            ubicacion TEXT NOT NULL DEFAULT '',
            lotes_asignados TEXT NOT NULL DEFAULT '[]',
            usuario TEXT NOT NULL DEFAULT 'sistema',
            nota TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime')),
            updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime')),
            expires_at TEXT NOT NULL DEFAULT '',
            UNIQUE(referencia_tipo, referencia_id, product_code)
        )
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_stock_reservations_sku_estado
        ON stock_reservations(product_code, estado)
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_stock_reservations_ref
        ON stock_reservations(referencia_tipo, referencia_id, estado)
        """
    )
    connection.execute("DROP VIEW IF EXISTS v_stock_disponible")
    connection.execute(
        """
        CREATE VIEW v_stock_disponible AS
        SELECT
            p.code AS product_code,
            p.name AS product_name,
            p.stock AS stock_fisico,
            COALESCE(r.reservado, 0) AS stock_reservado,
            MAX(0, p.stock - COALESCE(r.reservado, 0)) AS stock_disponible,
            p.ubicacion AS ubicacion_principal,
            p.active AS active
        FROM products p
        LEFT JOIN (
            SELECT product_code, SUM(cantidad) AS reservado
            FROM stock_reservations
            WHERE estado = 'activa'
            GROUP BY product_code
        ) r ON r.product_code = p.code
        """
    )


_PRODUCTS_MIGRATION_STEPS: tuple[MigrationStep, ...] = (
    MigrationStep(1, "Tablas base de productos, catálogo y movimientos", _crear_tablas_base_productos),
    MigrationStep(2, "Columnas de slotting/barcodes, trigger auditoría y vista reposición", _migrar_columnas_indices_trigger_productos),
    MigrationStep(3, "Tablas de despachos, notificaciones admin e inventario físico", _crear_tablas_despacho_notificaciones_e_inventario),
    MigrationStep(4, "Reservas de stock, multi-ubicación product_locations y lotes FEFO", _migrar_fase4_reservas_ubicaciones_lotes),
)


def inicializar_esquema_productos(
    connection: sqlite3.Connection,
    database_path: Path | str | None = None,
) -> None:
    """Crea y migra mediante `PRAGMA user_version` el esquema SQLite de productos."""
    aplicar_migraciones_sqlite(connection, database_path, _PRODUCTS_MIGRATION_STEPS, domain="products")
