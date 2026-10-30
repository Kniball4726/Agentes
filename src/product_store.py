"""SQLite persistence for catalog products and their report ordering."""

import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Callable, Iterable


class ProductStore:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA busy_timeout = 10000")
        return connection

    def _initialize(self) -> None:
        with closing(self._connect()) as connection, connection:
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

    def is_template_imported(self) -> bool:
        """Determina rápidamente si la plantilla inicial ya fue importada a SQLite."""
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT value FROM product_catalog_metadata
                WHERE key = 'template_imported'
                """
            ).fetchone()
            return row is not None

    def get_all_metadata(self) -> dict[str, str]:
        """Devuelve todos los metadatos almacenados para el catálogo."""
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT key, value FROM product_catalog_metadata"
            ).fetchall()
            return {row["key"]: row["value"] for row in rows}

    def get_metadata(self, key: str, default: str = "") -> str:
        """Devuelve un valor de metadatos o default si no existe."""
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT value FROM product_catalog_metadata WHERE key = ?",
                (key,),
            ).fetchone()
            return str(row["value"]) if row is not None else default

    def set_metadata(self, key: str, value: str) -> None:
        """Almacena o actualiza una clave de metadatos del catálogo."""
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """
                INSERT INTO product_catalog_metadata (key, value)
                VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, str(value)),
            )

    def import_template_once(
        self,
        products: Iterable[tuple[int, str, str, int]],
        metadata: dict[str, str] | None = None,
    ) -> None:
        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            imported = connection.execute(
                """
                SELECT value FROM product_catalog_metadata
                WHERE key = 'template_imported'
                """
            ).fetchone()
            if imported is not None:
                return

            existing = connection.execute(
                "SELECT COUNT(*) FROM products"
            ).fetchone()[0]
            if existing:
                raise RuntimeError(
                    "La base de productos contiene datos pero no tiene "
                    "registrada la importación inicial de la plantilla."
                )

            first_product_codes: set[str] = set()
            for orden, (fila, codigo, nombre, stock) in enumerate(products):
                if codigo not in first_product_codes:
                    first_product_codes.add(codigo)
                    connection.execute(
                        """
                        INSERT INTO products (code, name, stock)
                        VALUES (?, ?, ?)
                        """,
                        (codigo, nombre, stock),
                    )
                connection.execute(
                    """
                    INSERT INTO product_catalog_rows (
                        product_code, display_name, display_order, template_row
                    )
                    VALUES (?, ?, ?, ?)
                    """,
                    (codigo, nombre, orden, fila),
                )
            connection.execute(
                """
                INSERT INTO product_catalog_metadata (key, value)
                VALUES ('template_imported', '1')
                """
            )
            if metadata:
                for k, v in metadata.items():
                    connection.execute(
                        """
                        INSERT INTO product_catalog_metadata (key, value)
                        VALUES (?, ?)
                        ON CONFLICT(key) DO UPDATE SET value = excluded.value
                        """,
                        (k, str(v)),
                    )

    def list_catalog_rows(
        self, include_inactive: bool = False
    ) -> list[sqlite3.Row]:
        with closing(self._connect()) as connection:
            return connection.execute(
                f"""
                SELECT
                    catalog_row.product_code AS code,
                    product.name AS name,
                    product.stock AS stock,
                    catalog_row.display_name AS display_name,
                    catalog_row.display_order AS display_order,
                    catalog_row.template_row AS template_row
                FROM product_catalog_rows AS catalog_row
                JOIN products AS product
                    ON product.code = catalog_row.product_code
                {"WHERE product.active = 1" if not include_inactive else ""}
                ORDER BY catalog_row.display_order, catalog_row.id
                """
            ).fetchall()

    def list_products(self) -> list[sqlite3.Row]:
        with closing(self._connect()) as connection:
            return connection.execute(
                """
                SELECT
                    product.code AS code,
                    product.name AS name,
                    product.stock AS stock,
                    product.active AS active,
                    product.stock_minimo AS stock_minimo,
                    product.stock_maximo AS stock_maximo,
                    product.stock_fisico AS stock_fisico,
                    product.cod_barras AS cod_barras,
                    product.ubicacion AS ubicacion,
                    MIN(catalog_row.display_order) AS display_order
                FROM products AS product
                JOIN product_catalog_rows AS catalog_row
                    ON catalog_row.product_code = product.code
                GROUP BY product.code, product.name, product.stock, product.active, product.stock_minimo, product.stock_maximo, product.stock_fisico, product.cod_barras, product.ubicacion
                ORDER BY display_order, product.code
                """
            ).fetchall()

    def add_product_after(
        self,
        code: str,
        name: str,
        reference_code: str,
        stock: int,
        synchronize_template: Callable[[int], list[int]],
        restore_template: Callable[[], None],
        stock_minimo: int = 5,
        stock_maximo: int = 100,
        cod_barras: str = "",
    ) -> tuple[int, str]:
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                if connection.execute(
                    "SELECT 1 FROM products WHERE code = ?", (code,)
                ).fetchone():
                    raise ValueError(f"El código '{code}' ya existe en el catálogo.")

                referencia = connection.execute(
                    """
                    SELECT display_order, display_name
                    FROM product_catalog_rows
                    WHERE product_code = ?
                    ORDER BY display_order, id
                    LIMIT 1
                    """,
                    (reference_code,),
                ).fetchone()
                if referencia is None:
                    raise ValueError(
                        f"No se encontró el producto de referencia "
                        f"'{reference_code}' en el catálogo."
                    )

                orden = referencia["display_order"] + 1
                connection.execute(
                    """
                    UPDATE product_catalog_rows
                    SET display_order = display_order + 1
                    WHERE display_order >= ?
                    """,
                    (orden,),
                )
                connection.execute(
                    "INSERT INTO products (code, name, stock, stock_minimo, stock_maximo, cod_barras) VALUES (?, ?, ?, ?, ?, ?)",
                    (code, name, stock, stock_minimo, stock_maximo, cod_barras.strip()),
                )
                connection.execute(
                    """
                    INSERT INTO product_catalog_rows (
                        product_code, display_name, display_order, template_row
                    )
                    VALUES (?, ?, ?, NULL)
                    """,
                    (code, name, orden),
                )
                filas_plantilla = synchronize_template(orden)
                filas_catalogo = connection.execute(
                    """
                    SELECT id, display_order
                    FROM product_catalog_rows
                    ORDER BY display_order, id
                    """
                ).fetchall()
                if len(filas_plantilla) != len(filas_catalogo):
                    raise RuntimeError(
                        "La cantidad de filas de la plantilla no coincide "
                        "con el catálogo SQLite."
                    )
                for fila_catalogo, fila_plantilla in zip(
                    filas_catalogo, filas_plantilla
                ):
                    connection.execute(
                        """
                        UPDATE product_catalog_rows
                        SET template_row = ?
                        WHERE id = ?
                        """,
                        (fila_plantilla, fila_catalogo["id"]),
                    )
                connection.commit()
                return orden, referencia["display_name"]
            except BaseException:
                connection.rollback()
                try:
                    restore_template()
                except OSError as error:
                    raise RuntimeError(
                        "No se pudo revertir Productos.xlsx después de "
                        "cancelar el alta. Restaura la copia "
                        "Productos_backup.xlsx."
                    ) from error
                raise

    def update_product(
        self,
        old_code: str,
        new_code: str,
        name: str,
        stock: int,
        synchronize_template: Callable[[], list[int]],
        restore_template: Callable[[], None],
        stock_minimo: int | None = None,
        stock_maximo: int | None = None,
        cod_barras: str | None = None,
    ) -> None:
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                current = connection.execute(
                    "SELECT active, stock_minimo, stock_maximo, cod_barras FROM products WHERE code = ?", (old_code,)
                ).fetchone()
                if current is None:
                    raise ValueError(f"No se encontró el producto '{old_code}'.")
                if new_code != old_code and connection.execute(
                    "SELECT 1 FROM products WHERE code = ?", (new_code,)
                ).fetchone():
                    raise ValueError(
                        f"El código '{new_code}' ya está asignado a otro producto."
                    )

                val_min = stock_minimo if stock_minimo is not None else current["stock_minimo"]
                val_max = stock_maximo if stock_maximo is not None else current["stock_maximo"]
                val_barras = cod_barras.strip() if cod_barras is not None else (current["cod_barras"] or "")

                if new_code != old_code:
                    connection.execute(
                        """
                        INSERT INTO products (code, name, stock, active, created_at, stock_minimo, stock_maximo, cod_barras)
                        SELECT ?, ?, ?, active, created_at, ?, ?, ?
                        FROM products WHERE code = ?
                        """,
                        (new_code, name, stock, val_min, val_max, val_barras, old_code),
                    )
                    connection.execute(
                        """
                        UPDATE product_catalog_rows
                        SET product_code = ?, display_name = ?
                        WHERE product_code = ?
                        """,
                        (new_code, name, old_code),
                    )
                    connection.execute(
                        "DELETE FROM products WHERE code = ?", (old_code,)
                    )
                else:
                    connection.execute(
                        "UPDATE products SET name = ?, stock = ?, stock_minimo = ?, stock_maximo = ?, cod_barras = ? WHERE code = ?",
                        (name, stock, val_min, val_max, val_barras, old_code),
                    )
                    connection.execute(
                        """
                        UPDATE product_catalog_rows
                        SET display_name = ?
                        WHERE product_code = ?
                        """,
                        (name, old_code),
                    )

                filas_plantilla = synchronize_template()
                filas_catalogo = connection.execute(
                    """
                    SELECT id FROM product_catalog_rows
                    ORDER BY display_order, id
                    """
                ).fetchall()
                if len(filas_plantilla) != len(filas_catalogo):
                    raise RuntimeError(
                        "La cantidad de filas de la plantilla no coincide "
                        "con el catálogo SQLite."
                    )
                for fila_catalogo, fila_plantilla in zip(
                    filas_catalogo, filas_plantilla
                ):
                    connection.execute(
                        """
                        UPDATE product_catalog_rows
                        SET template_row = ?
                        WHERE id = ?
                        """,
                        (fila_plantilla, fila_catalogo["id"]),
                    )
                connection.commit()
            except BaseException:
                connection.rollback()
                try:
                    restore_template()
                except OSError as error:
                    raise RuntimeError(
                        "No se pudo revertir Productos.xlsx después de "
                        "cancelar la edición. Restaura la copia "
                        "Productos_backup.xlsx."
                    ) from error
                raise

    def get_product(self, code: str) -> sqlite3.Row | None:
        """Obtiene un producto por su código interno (SKU)."""
        with closing(self._connect()) as connection:
            return connection.execute(
                """
                SELECT code, name, stock, active, stock_minimo, stock_maximo, stock_fisico, cod_barras, ubicacion
                FROM products
                WHERE code = ?
                """,
                (code.strip(),),
            ).fetchone()

    def actualizar_ubicacion(self, code: str, ubicacion: str) -> bool:
        """Actualiza la ubicación física en el depósito para un producto (ej. 'A-01-2')."""
        with closing(self._connect()) as connection, connection:
            cur = connection.execute(
                "UPDATE products SET ubicacion = ? WHERE code = ?",
                (ubicacion.strip().upper(), code.strip()),
            )
            return cur.rowcount > 0

    def get_product_by_barcode(self, cod_barras: str) -> sqlite3.Row | None:
        """Obtiene un producto por su código de barras (EAN-13, QR, Code-128, etc.)."""
        barras = cod_barras.strip()
        if not barras:
            return None
        with closing(self._connect()) as connection:
            return connection.execute(
                """
                SELECT code, name, stock, active, stock_minimo, stock_maximo, stock_fisico, cod_barras
                FROM products
                WHERE cod_barras = ? AND cod_barras != ''
                LIMIT 1
                """,
                (barras,),
            ).fetchone()

    def find_product_by_code_or_barcode(self, query: str) -> sqlite3.Row | None:
        """Busca primero por código interno (SKU), luego por código de barras."""
        val = query.strip()
        if not val:
            return None
        with closing(self._connect()) as connection:
            # 1. Búsqueda por SKU exacto
            prod = connection.execute(
                """
                SELECT code, name, stock, active, stock_minimo, stock_maximo, stock_fisico, cod_barras
                FROM products
                WHERE code = ?
                """,
                (val,),
            ).fetchone()
            if prod is not None:
                return prod
            # 2. Búsqueda por código de barras exacto
            return connection.execute(
                """
                SELECT code, name, stock, active, stock_minimo, stock_maximo, stock_fisico, cod_barras
                FROM products
                WHERE cod_barras = ? AND cod_barras != ''
                LIMIT 1
                """,
                (val,),
            ).fetchone()

    def set_product_barcode(self, code: str, cod_barras: str) -> None:
        """Asigna o actualiza el código de barras de un producto."""
        with closing(self._connect()) as connection, connection:
            connection.execute(
                "UPDATE products SET cod_barras = ? WHERE code = ?",
                (cod_barras.strip(), code.strip()),
            )

    def set_product_active(self, code: str, active: bool) -> None:
        with closing(self._connect()) as connection, connection:
            cursor = connection.execute(
                "UPDATE products SET active = ? WHERE code = ?",
                (int(active), code),
            )
            if cursor.rowcount != 1:
                raise ValueError(f"No se encontró el producto '{code}'.")

    def update_product_thresholds(
        self, code: str, stock_minimo: int, stock_maximo: int
    ) -> None:
        """Actualiza los límites de stock mínimo y máximo de un producto."""
        if stock_minimo < 0 or stock_maximo < stock_minimo:
            raise ValueError(
                "El stock mínimo debe ser >= 0 y el máximo debe ser >= mínimo."
            )
        with closing(self._connect()) as connection, connection:
            cursor = connection.execute(
                """
                UPDATE products
                SET stock_minimo = ?, stock_maximo = ?
                WHERE code = ?
                """,
                (stock_minimo, stock_maximo, code),
            )
            if cursor.rowcount != 1:
                raise ValueError(f"No se encontró el producto '{code}'.")

    def get_replenishment_analysis(
        self, only_critical: bool = True
    ) -> list[sqlite3.Row]:
        """Consulta la vista v_analisis_reposicion.

        Si only_critical es True, devuelve solo productos en QUIEBRE_INMINENTE o AGOTADO.
        """
        filtro = (
            "WHERE estado_inventario IN ('AGOTADO', 'QUIEBRE_INMINENTE')"
            if only_critical
            else ""
        )
        with closing(self._connect()) as connection:
            return connection.execute(
                f"""
                SELECT
                    code,
                    name,
                    stock,
                    stock_minimo,
                    stock_maximo,
                    estado_inventario,
                    cantidad_sugerida_pedir
                FROM v_analisis_reposicion
                {filtro}
                ORDER BY
                    CASE estado_inventario
                        WHEN 'AGOTADO' THEN 1
                        WHEN 'QUIEBRE_INMINENTE' THEN 2
                        WHEN 'SOBRESTOCK' THEN 3
                        ELSE 4
                    END,
                    stock ASC
                """
            ).fetchall()

    def record_dispatch(
        self,
        tipo_origen: str,
        nombre_archivo: str,
        total_articulos: int,
        detalles: list[tuple[str, int, int, int]],
        reporte_archivo: str = "",
        usuario: str = "sistema",
    ) -> int:
        """Registra un lote de descuento en despachos y despacho_detalles.

        detalles: lista de (product_code, cantidad_descontada, stock_anterior, stock_nuevo).
        Retorna el id del despacho insertado.
        """
        with closing(self._connect()) as connection, connection:
            cursor = connection.execute(
                """
                INSERT INTO despachos (tipo_origen, nombre_archivo, total_articulos, reporte_archivo, usuario)
                VALUES (?, ?, ?, ?, ?)
                """,
                (tipo_origen, nombre_archivo, total_articulos, reporte_archivo, usuario),
            )
            despacho_id = cursor.lastrowid
            if detalles and despacho_id is not None:
                connection.executemany(
                    """
                    INSERT INTO despacho_detalles (
                        despacho_id, product_code, cantidad_descontada, stock_anterior, stock_nuevo
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    [
                        (despacho_id, cod, cant, ant, nvo)
                        for cod, cant, ant, nvo in detalles
                    ],
                )
                detalle_txt = f"{tipo_origen}: {nombre_archivo}"[:120]
                for cod, _, _, _ in detalles:
                    connection.execute(
                        """
                        UPDATE stock_movements
                        SET usuario = ?, detalle = ?
                        WHERE id = (
                            SELECT id FROM stock_movements
                            WHERE product_code = ?
                            ORDER BY id DESC LIMIT 1
                        ) AND (usuario = 'sistema' OR detalle = '')
                        """,
                        (usuario or "sistema", detalle_txt, cod),
                    )
            return despacho_id or 0

    def create_admin_notification(
        self,
        title: str,
        message: str,
        operator_username: str,
        notification_type: str = "descuento",
        details: str = "",
    ) -> int:
        with closing(self._connect()) as connection, connection:
            cursor = connection.execute(
                """
                INSERT INTO admin_notifications (title, message, operator_username, notification_type, details)
                VALUES (?, ?, ?, ?, ?)
                """,
                (title, message, operator_username, notification_type, details),
            )
            return int(cursor.lastrowid)

    def list_admin_notifications(
        self, unread_only: bool = False, limit: int = 50
    ) -> list[sqlite3.Row]:
        query = """
            SELECT id, title, message, operator_username, notification_type, details, created_at, is_read
            FROM admin_notifications
        """
        params: list = []
        if unread_only:
            query += " WHERE is_read = 0"
        query += " ORDER BY id DESC LIMIT ?"
        params.append(int(limit))
        with closing(self._connect()) as connection:
            return connection.execute(query, params).fetchall()

    def get_unread_notifications_count(self) -> int:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT COUNT(*) as count FROM admin_notifications WHERE is_read = 0"
            ).fetchone()
            return int(row["count"]) if row else 0

    def mark_notification_as_read(self, notification_id: int) -> None:
        with closing(self._connect()) as connection, connection:
            connection.execute(
                "UPDATE admin_notifications SET is_read = 1 WHERE id = ?",
                (notification_id,),
            )

    def mark_all_notifications_as_read(self) -> int:
        with closing(self._connect()) as connection, connection:
            cursor = connection.execute(
                "UPDATE admin_notifications SET is_read = 1 WHERE is_read = 0"
            )
            return cursor.rowcount

    def record_physical_inventory(
        self,
        usuario: str,
        nombre_archivo: str,
        reporte_unificado: str,
        detalles: list[tuple[str, str, int, int, int, str]],
    ) -> int:
        """Registra un relevamiento de stock físico, actualiza products.stock_fisico
        y guarda la comparativa detallada.

        Cada tupla de `detalles` es:
            (product_code, product_name, stock_digital, stock_fisico, diferencia, estado)
        Retorna el id del inventario insertado.
        """
        total_relevados = len(detalles)
        total_diferencias = sum(1 for _, _, _, _, dif, _ in detalles if dif != 0)
        with closing(self._connect()) as connection, connection:
            cursor = connection.execute(
                """
                INSERT INTO inventario_fisico (
                    usuario, nombre_archivo, reporte_unificado, total_relevados, total_diferencias
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (usuario, nombre_archivo, reporte_unificado, total_relevados, total_diferencias),
            )
            inventario_id = int(cursor.lastrowid or 0)
            for cod, nom, stk_dig, stk_fis, dif, estado in detalles:
                connection.execute(
                    "UPDATE products SET stock_fisico = ? WHERE code = ?",
                    (stk_fis, cod),
                )
                connection.execute(
                    """
                    INSERT INTO inventario_fisico_detalles (
                        inventario_id, product_code, product_name,
                        stock_digital, stock_fisico, diferencia, estado
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (inventario_id, cod, nom, stk_dig, stk_fis, dif, estado),
                )
            return inventario_id

    def list_physical_inventories(self, limit: int = 20) -> list[sqlite3.Row]:
        with closing(self._connect()) as connection:
            return connection.execute(
                """
                SELECT id, fecha, usuario, nombre_archivo, reporte_unificado,
                       total_relevados, total_diferencias
                FROM inventario_fisico
                ORDER BY id DESC
                LIMIT ?
                """,
                (int(limit),),
            ).fetchall()

    def get_physical_inventory_details(self, inventario_id: int) -> list[sqlite3.Row]:
        with closing(self._connect()) as connection:
            return connection.execute(
                """
                SELECT id, inventario_id, product_code, product_name,
                       stock_digital, stock_fisico, diferencia, estado
                FROM inventario_fisico_detalles
                WHERE inventario_id = ?
                ORDER BY ABS(diferencia) DESC, product_code ASC
                """,
                (int(inventario_id),),
            ).fetchall()

    def get_latest_physical_inventory(
        self,
    ) -> tuple[sqlite3.Row | None, list[sqlite3.Row]]:
        with closing(self._connect()) as connection:
            cabecera = connection.execute(
                """
                SELECT id, fecha, usuario, nombre_archivo, reporte_unificado,
                       total_relevados, total_diferencias
                FROM inventario_fisico
                ORDER BY id DESC
                LIMIT 1
                """
            ).fetchone()
            if cabecera is None:
                return None, []
            detalles = connection.execute(
                """
                SELECT id, inventario_id, product_code, product_name,
                       stock_digital, stock_fisico, diferencia, estado
                FROM inventario_fisico_detalles
                WHERE inventario_id = ?
                ORDER BY ABS(diferencia) DESC, product_code ASC
                """,
                (int(cabecera["id"]),),
            ).fetchall()
            return cabecera, detalles

    def register_movements(
        self,
        movements: list[tuple[str, str, int, str]],
        usuario: str = "sistema",
        detalle: str = "",
    ) -> None:
        """Registra movimientos de stock en el historial.

        Cada elemento de `movements` es (product_code, product_name, quantity, movement_type).
        movement_type: 'descuento' | 'ingreso_fabrica' | 'ajuste_manual'
        quantity: positivo para ingresos, negativo para descuentos.
        """
        if not movements:
            return
        with closing(self._connect()) as connection, connection:
            connection.executemany(
                """
                INSERT INTO stock_movements (product_code, product_name, quantity, movement_type, usuario, detalle)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [(cod, nom, qty, mtype, usuario, detalle) for cod, nom, qty, mtype in movements],
            )

    def enrich_latest_movements(
        self,
        product_codes: Iterable[str],
        usuario: str = "sistema",
        detalle: str = "",
        movement_type: str | None = None,
    ) -> None:
        """Asocia usuario y detalle al último movimiento registrado por el trigger para los códigos dados."""
        codigos = list(product_codes)
        if not codigos:
            return
        with closing(self._connect()) as connection, connection:
            for cod in codigos:
                if movement_type:
                    connection.execute(
                        """
                        UPDATE stock_movements
                        SET usuario = ?, detalle = ?, movement_type = ?
                        WHERE id = (
                            SELECT id FROM stock_movements
                            WHERE product_code = ?
                            ORDER BY id DESC LIMIT 1
                        ) AND (usuario = 'sistema' OR detalle = '')
                        """,
                        (usuario or "sistema", detalle, movement_type, cod),
                    )
                else:
                    connection.execute(
                        """
                        UPDATE stock_movements
                        SET usuario = ?, detalle = ?
                        WHERE id = (
                            SELECT id FROM stock_movements
                            WHERE product_code = ?
                            ORDER BY id DESC LIMIT 1
                        ) AND (usuario = 'sistema' OR detalle = '')
                        """,
                        (usuario or "sistema", detalle, cod),
                    )

    def list_recent_movements(
        self,
        product_code: str = "",
        movement_type: str = "",
        limit: int = 150,
    ) -> list[sqlite3.Row]:
        """Devuelve el historial detallado de movimientos de stock más recientes."""
        condiciones: list[str] = []
        params: list = []
        if product_code.strip():
            condiciones.append("(product_code LIKE ? OR product_name LIKE ?)")
            patron = f"%{product_code.strip()}%"
            params.extend([patron, patron])
        if movement_type.strip():
            condiciones.append("movement_type = ?")
            params.append(movement_type.strip())
        where_sql = f"WHERE {' AND '.join(condiciones)}" if condiciones else ""
        params.append(int(limit))
        with closing(self._connect()) as connection:
            return connection.execute(
                f"""
                SELECT
                    id,
                    product_code,
                    product_name,
                    quantity,
                    movement_type,
                    usuario,
                    detalle,
                    registered_at
                FROM stock_movements
                {where_sql}
                ORDER BY id DESC
                LIMIT ?
                """,
                params,
            ).fetchall()

    def query_movements(
        self,
        date_from: str,
        date_to: str,
        movement_type: str | None = None,
        top_n: int | None = None,
    ) -> list[sqlite3.Row]:
        """Consulta movimientos agrupados por producto en un rango de fechas.

        Retorna filas con (product_code, product_name, total_quantity) ordenadas
        por total_quantity descendente.
        movement_type: filtrar por tipo ('descuento', 'ingreso_fabrica', 'ajuste_manual').
        Si None, incluye todos.
        """
        tipo_filtro = "AND movement_type = ?" if movement_type else ""
        params: list = [date_from, date_to]
        if movement_type:
            params.append(movement_type)
        if top_n:
            limit = f"LIMIT {int(top_n)}"
        else:
            limit = ""
        with closing(self._connect()) as connection:
            return connection.execute(
                f"""
                SELECT
                    product_code,
                    product_name,
                    SUM(ABS(quantity)) AS total_quantity
                FROM stock_movements
                WHERE registered_at >= ?
                  AND registered_at <= ?
                  {tipo_filtro}
                GROUP BY product_code, product_name
                ORDER BY total_quantity DESC
                {limit}
                """,
                params,
            ).fetchall()

    def update_stocks(
        self,
        stocks: dict[str, int],
        synchronize_template: Callable[[], list[int]] | None = None,
        restore_template: Callable[[], None] | None = None,
    ) -> int:
        if not stocks:
            return 0
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                for code, stock in stocks.items():
                    cursor = connection.execute(
                        "UPDATE products SET stock = ? WHERE code = ?",
                        (stock, code),
                    )
                    if cursor.rowcount != 1:
                        raise ValueError(
                            f"No se encontró el producto '{code}' en la base de datos."
                        )

                if synchronize_template is not None:
                    filas_plantilla = synchronize_template()
                    filas_catalogo = connection.execute(
                        """
                        SELECT id FROM product_catalog_rows
                        ORDER BY display_order, id
                        """
                    ).fetchall()
                    if len(filas_plantilla) != len(filas_catalogo):
                        raise RuntimeError(
                            "La cantidad de filas de la plantilla no coincide "
                            "con el catálogo SQLite."
                        )
                    for fila_catalogo, fila_plantilla in zip(
                        filas_catalogo, filas_plantilla
                    ):
                        connection.execute(
                            """
                            UPDATE product_catalog_rows
                            SET template_row = ?
                            WHERE id = ?
                            """,
                            (fila_plantilla, fila_catalogo["id"]),
                        )
                connection.commit()
                return len(stocks)
            except BaseException:
                connection.rollback()
                if restore_template is not None:
                    try:
                        restore_template()
                    except OSError as error:
                        raise RuntimeError(
                            "No se pudo revertir Productos.xlsx después de "
                            "cancelar la actualización de stock. Restaura la copia "
                            "Productos_backup.xlsx."
                        ) from error
                raise
