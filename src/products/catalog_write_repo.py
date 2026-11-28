"""Repositorio desacoplado de escritura, mutaciones y sincronización de plantilla del catálogo."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from typing import Callable, Iterable

from .protocols import CatalogWriteHostProtocol


def _sincronizar_filas_plantilla(
    connection: sqlite3.Connection,
    filas_plantilla: list[int],
) -> None:
    """Sincroniza `template_row` en SQLite con las filas actualizadas de Productos.xlsx."""
    filas_catalogo = connection.execute(
        """
        SELECT id, template_row FROM product_catalog_rows
        ORDER BY display_order, id
        """
    ).fetchall()
    if not filas_catalogo or not filas_plantilla:
        return
    cambios_fila = [
        (fila_p, fila_c["id"])
        for fila_c, fila_p in zip(filas_catalogo, filas_plantilla, strict=False)
        if fila_c["template_row"] != fila_p
    ]
    if cambios_fila:
        connection.executemany(
            """
            UPDATE product_catalog_rows
            SET template_row = ?
            WHERE id = ?
            """,
            cambios_fila,
        )


def _revertir_plantilla(restore_template: Callable[[], None], accion: str) -> None:
    """Revierte Productos.xlsx ante un fallo de transacción o informa error de E/S."""
    try:
        restore_template()
    except OSError as error:
        raise RuntimeError(
            f"No se pudo revertir Productos.xlsx después de cancelar {accion}. "
            "Restaura la copia Productos_backup.xlsx."
        ) from error


class CatalogWriteRepository:
    """Repositorio de escrituras transaccionales en SQLite sincronizadas con la plantilla Excel."""

    def __init__(self, host: CatalogWriteHostProtocol) -> None:
        self._host = host

    def _connect(self) -> sqlite3.Connection:
        return self._host._connect()

    def invalidar_cache(self) -> None:
        self._host.invalidar_cache()

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
        """Importa la plantilla inicial en una transacción idempotente."""
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
                connection.execute(
                    """
                    INSERT OR REPLACE INTO product_catalog_metadata (key, value)
                    VALUES ('template_imported', '1')
                    """
                )
                return

            first_product_codes: set[str] = set()
            for orden, (fila, codigo, nombre, stock) in enumerate(products):
                if codigo not in first_product_codes:
                    first_product_codes.add(codigo)
                    connection.execute(
                        "INSERT INTO products (code, name, stock) VALUES (?, ?, ?)",
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
                connection.executemany(
                    """
                    INSERT INTO product_catalog_metadata (key, value)
                    VALUES (?, ?)
                    ON CONFLICT(key) DO UPDATE SET value = excluded.value
                    """,
                    [(k, str(v)) for k, v in metadata.items()],
                )

    def add_product_after(
        self,
        code: str,
        name: str,
        reference_code: str,
        stock: int,
        synchronize_template: Callable[[int], list[int]] | None = None,
        restore_template: Callable[[], None] | None = None,
        stock_minimo: int = 5,
        stock_maximo: int = 100,
        cod_barras: str = "",
    ) -> tuple[int, str]:
        """Inserta un nuevo producto inmediatamente después del producto de referencia."""
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
                        f"No se encontró el producto de referencia '{reference_code}' en el catálogo."
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
                if synchronize_template is not None:
                    _sincronizar_filas_plantilla(connection, synchronize_template(orden))
                connection.commit()
                self.invalidar_cache()
                return orden, referencia["display_name"]
            except BaseException:
                connection.rollback()
                if restore_template is not None:
                    _revertir_plantilla(restore_template, "el alta")
                raise

    def update_product(self, *args, **kwargs):
        """Actualiza código, nombre, stock y umbrales de un producto invalidando el caché."""
        self.invalidar_cache()
        return self._update_product_inner(*args, **kwargs)

    def _update_product_inner(
        self,
        old_code: str,
        new_code: str,
        name: str,
        stock: int,
        synchronize_template: Callable[[], list[int]] | None = None,
        restore_template: Callable[[], None] | None = None,
        stock_minimo: int | None = None,
        stock_maximo: int | None = None,
        cod_barras: str | None = None,
    ) -> None:
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                current = connection.execute(
                    "SELECT active, stock_minimo, stock_maximo, cod_barras FROM products WHERE code = ?",
                    (old_code,),
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
                        "UPDATE product_catalog_rows SET product_code = ?, display_name = ? WHERE product_code = ?",
                        (new_code, name, old_code),
                    )
                    connection.execute("DELETE FROM products WHERE code = ?", (old_code,))
                else:
                    connection.execute(
                        "UPDATE products SET name = ?, stock = ?, stock_minimo = ?, stock_maximo = ?, cod_barras = ? WHERE code = ?",
                        (name, stock, val_min, val_max, val_barras, old_code),
                    )
                    connection.execute(
                        "UPDATE product_catalog_rows SET display_name = ? WHERE product_code = ?",
                        (name, old_code),
                    )

                if synchronize_template is not None:
                    _sincronizar_filas_plantilla(connection, synchronize_template())
                connection.commit()
            except BaseException:
                connection.rollback()
                if restore_template is not None:
                    _revertir_plantilla(restore_template, "la edición")
                raise

    def actualizar_ubicacion(self, code: str, ubicacion: str) -> bool:
        """Actualiza la ubicación física en el depósito para un producto (ej. 'A-01-2')."""
        from .locations_lots_repo import (
            normalizar_ubicacion,
            sincronizar_ubicacion_principal_en_tx,
        )

        ubic_norm = normalizar_ubicacion(ubicacion)
        cod_norm = code.strip()
        with closing(self._connect()) as connection, connection:
            cur = connection.execute(
                "UPDATE products SET ubicacion = ? WHERE code = ?",
                (ubic_norm, cod_norm),
            )
            if cur.rowcount > 0:
                if ubic_norm:
                    sincronizar_ubicacion_principal_en_tx(connection, cod_norm, ubic_norm)
                else:
                    connection.execute(
                        "UPDATE product_locations SET es_principal = 0 WHERE product_code = ?",
                        (cod_norm,),
                    )
            self.invalidar_cache()
            return cur.rowcount > 0

    def set_product_barcode(self, code: object, cod_barras: object) -> None:
        """Asigna o actualiza el código de barras de un producto casteando tipos a texto."""
        from src.products.barcode_utils import normalizar_codigo_lector

        self.invalidar_cache()
        code_limpio = normalizar_codigo_lector(code)
        if not code_limpio:
            return
        barras_limpias = normalizar_codigo_lector(cod_barras)
        with closing(self._connect()) as connection, connection:
            cursor = connection.execute(
                "UPDATE products SET cod_barras = ? WHERE code = ?",
                (barras_limpias, code_limpio),
            )
            if cursor.rowcount == 0:
                connection.execute(
                    "UPDATE products SET cod_barras = ? WHERE TRIM(CAST(code AS TEXT)) = ? COLLATE NOCASE",
                    (barras_limpias, code_limpio),
                )

    def set_product_active(self, code: str, active: bool) -> None:
        """Activa o desactiva un producto dentro del catálogo."""
        self.invalidar_cache()
        with closing(self._connect()) as connection, connection:
            cursor = connection.execute(
                "UPDATE products SET active = ? WHERE code = ?",
                (int(active), code),
            )
            if cursor.rowcount != 1:
                raise ValueError(f"No se encontró el producto '{code}'.")

    def sync_active_status_with_codes(
        self, active_codes: Iterable[str]
    ) -> tuple[int, int]:
        """Marca active=1 a los productos en active_codes y active=0 a los productos ausentes en SQLite.

        Retorna una tupla (activados, desactivados) con el conteo de registros modificados.
        """
        self.invalidar_cache()
        codigos_norm = {
            str(c).strip()[:-2] if str(c).strip().endswith(".0") else str(c).strip()
            for c in active_codes
            if str(c).strip()
        }
        if not codigos_norm:
            return 0, 0

        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "CREATE TEMP TABLE IF NOT EXISTS temp_active_codes (code TEXT PRIMARY KEY COLLATE NOCASE)"
            )
            connection.execute("DELETE FROM temp_active_codes")
            connection.executemany(
                "INSERT OR IGNORE INTO temp_active_codes (code) VALUES (?)",
                [(c,) for c in codigos_norm],
            )

            # Desactivar los que no están en active_codes
            cursor_desactivados = connection.execute(
                """
                UPDATE products
                SET active = 0
                WHERE active = 1
                  AND TRIM(CAST(code AS TEXT)) NOT IN (SELECT code FROM temp_active_codes)
                """
            )
            desactivados = cursor_desactivados.rowcount

            # Reactivar los que sí están en active_codes pero estaban inactivos
            cursor_activados = connection.execute(
                """
                UPDATE products
                SET active = 1
                WHERE active = 0
                  AND TRIM(CAST(code AS TEXT)) IN (SELECT code FROM temp_active_codes)
                """
            )
            activados = cursor_activados.rowcount

            connection.execute("DROP TABLE IF EXISTS temp_active_codes")
            return activados, desactivados

    def update_product_thresholds(
        self, code: str, stock_minimo: int, stock_maximo: int
    ) -> None:
        """Actualiza los límites de stock mínimo y máximo de un producto."""
        self.invalidar_cache()
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

    def update_stocks(self, *args, **kwargs) -> int:
        """Actualiza por lote el stock de productos invalidando previamente el caché."""
        self.invalidar_cache()
        return self._update_stocks_inner(*args, **kwargs)

    def _update_stocks_inner(
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
                    _sincronizar_filas_plantilla(connection, synchronize_template())
                connection.commit()
                return len(stocks)
            except BaseException:
                connection.rollback()
                if restore_template is not None:
                    _revertir_plantilla(restore_template, "la actualización de stock")
                raise
