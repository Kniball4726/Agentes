"""Esquema DDL, migraciones idempotentes, índices, triggers y vistas SQLite para productos."""

from __future__ import annotations

import sqlite3


def inicializar_esquema_productos(connection: sqlite3.Connection) -> None:
    """Crea y migra de forma idempotente todas las tablas e índices del dominio de productos."""
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
    columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(products)")
    }
    if "active" not in columns:
        connection.execute(
            "ALTER TABLE products ADD COLUMN active INTEGER NOT NULL DEFAULT 1"
        )
    if "stock_minimo" not in columns:
        connection.execute(
            "ALTER TABLE products ADD COLUMN stock_minimo INTEGER NOT NULL DEFAULT 5"
        )
    if "stock_maximo" not in columns:
        connection.execute(
            "ALTER TABLE products ADD COLUMN stock_maximo INTEGER NOT NULL DEFAULT 100"
        )
    if "stock_fisico" not in columns:
        connection.execute(
            "ALTER TABLE products ADD COLUMN stock_fisico INTEGER DEFAULT NULL"
        )
    if "cod_barras" not in columns:
        connection.execute(
            "ALTER TABLE products ADD COLUMN cod_barras TEXT DEFAULT ''"
        )
    if "ubicacion" not in columns:
        connection.execute(
            "ALTER TABLE products ADD COLUMN ubicacion TEXT NOT NULL DEFAULT ''"
        )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_products_cod_barras
        ON products(cod_barras)
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_products_ubicacion
        ON products(ubicacion)
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
    cols_mov = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(stock_movements)")
    }
    if "usuario" not in cols_mov:
        connection.execute(
            "ALTER TABLE stock_movements ADD COLUMN usuario TEXT NOT NULL DEFAULT 'sistema'"
        )
    if "detalle" not in cols_mov:
        connection.execute(
            "ALTER TABLE stock_movements ADD COLUMN detalle TEXT NOT NULL DEFAULT ''"
        )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_stock_movements_code
        ON stock_movements(product_code)
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_stock_movements_date
        ON stock_movements(registered_at)
        """
    )

    # 1. Trigger para auditar todo cambio de stock automáticamente en SQLite
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

    # 3. Vista de análisis de reposición y quiebre de stock
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

    # 4. Tablas para trazabilidad de despachos y sus detalles
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
        """
        CREATE INDEX IF NOT EXISTS idx_despacho_detalles_despacho
        ON despacho_detalles(despacho_id)
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_despacho_detalles_product
        ON despacho_detalles(product_code)
        """
    )

    # Columna de usuario para trazabilidad en despachos
    columns_despachos = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(despachos)")
    }
    if "usuario" not in columns_despachos:
        connection.execute(
            "ALTER TABLE despachos ADD COLUMN usuario TEXT NOT NULL DEFAULT 'sistema'"
        )

    # Tabla de notificaciones para administradores
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
        """
        CREATE INDEX IF NOT EXISTS idx_admin_notifications_read
        ON admin_notifications(is_read)
        """
    )

    # Tablas para relevamiento de inventario físico y su comparativa
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
        """
        CREATE INDEX IF NOT EXISTS idx_inv_fisico_det_inv
        ON inventario_fisico_detalles(inventario_id)
        """
    )
