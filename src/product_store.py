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
        return connection

    def _initialize(self) -> None:
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS products (
                    code TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    stock INTEGER NOT NULL DEFAULT 0,
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

    def import_template_once(
        self, products: Iterable[tuple[int, str, str, int]]
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
                    MIN(catalog_row.display_order) AS display_order
                FROM products AS product
                JOIN product_catalog_rows AS catalog_row
                    ON catalog_row.product_code = product.code
                GROUP BY product.code, product.name, product.stock, product.active
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
                    "INSERT INTO products (code, name, stock) VALUES (?, ?, ?)",
                    (code, name, stock),
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
    ) -> None:
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                current = connection.execute(
                    "SELECT active FROM products WHERE code = ?", (old_code,)
                ).fetchone()
                if current is None:
                    raise ValueError(f"No se encontró el producto '{old_code}'.")
                if new_code != old_code and connection.execute(
                    "SELECT 1 FROM products WHERE code = ?", (new_code,)
                ).fetchone():
                    raise ValueError(
                        f"El código '{new_code}' ya está asignado a otro producto."
                    )

                if new_code != old_code:
                    connection.execute(
                        """
                        INSERT INTO products (code, name, stock, active, created_at)
                        SELECT ?, ?, ?, active, created_at
                        FROM products WHERE code = ?
                        """,
                        (new_code, name, stock, old_code),
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
                        "UPDATE products SET name = ?, stock = ? WHERE code = ?",
                        (name, stock, old_code),
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

    def set_product_active(self, code: str, active: bool) -> None:
        with closing(self._connect()) as connection, connection:
            cursor = connection.execute(
                "UPDATE products SET active = ? WHERE code = ?",
                (int(active), code),
            )
            if cursor.rowcount != 1:
                raise ValueError(f"No se encontró el producto '{code}'.")

    def update_stocks(self, stocks: dict[str, int]) -> int:
        if not stocks:
            return 0
        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            for code, stock in stocks.items():
                cursor = connection.execute(
                    "UPDATE products SET stock = ? WHERE code = ?",
                    (stock, code),
                )
                if cursor.rowcount != 1:
                    raise ValueError(
                        f"No se encontró el producto '{code}' en la base de datos."
                    )
            return len(stocks)
