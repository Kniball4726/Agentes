"""Repositorio mixin para el catálogo de productos, códigos de barras y sincronización."""

from __future__ import annotations

import sqlite3
import time
from contextlib import closing
from typing import Any, Callable, Iterable


class CatalogRepositoryMixin:
    """Mixin que encapsula consultas, altas, bajas, ediciones y búsqueda del catálogo."""

    _connect: Callable[[], sqlite3.Connection]
    invalidar_cache: Callable[[], None]
    _es_cache_valido: Callable[[sqlite3.Connection | None], bool]
    _cache_sku: dict[str, sqlite3.Row]
    _cache_barcode: dict[str, sqlite3.Row]
    _cache_lock: Any
    _cache_data_version: int | None
    _cache_ts: float

    def load_catalog_fast(
        self,
    ) -> tuple[bool, dict[str, str], list[sqlite3.Row]]:
        """Carga en una única conexión el estado de plantilla, metadatos y filas activas del catálogo."""
        with closing(self._connect()) as connection:
            meta_rows = connection.execute(
                "SELECT key, value FROM product_catalog_metadata"
            ).fetchall()
            meta = {row["key"]: row["value"] for row in meta_rows}
            if "template_imported" not in meta:
                return False, meta, []
            rows = connection.execute(
                """
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
                WHERE product.active = 1
                ORDER BY catalog_row.display_order, catalog_row.id
                """
            ).fetchall()
            return True, meta, rows

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

    def buscar_productos(self, termino: str, limite: int = 50) -> list[sqlite3.Row]:
        """Busca productos por codigo, nombre o codigo de barras."""
        termino = (termino or "").strip()
        if not termino:
            return self.list_products()[:limite]
        patron = f"%{termino}%"
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
                LEFT JOIN product_catalog_rows AS catalog_row
                    ON catalog_row.product_code = product.code
                WHERE product.code LIKE ? OR product.name LIKE ? OR product.cod_barras LIKE ?
                GROUP BY product.code, product.name, product.stock, product.active, product.stock_minimo, product.stock_maximo, product.stock_fisico, product.cod_barras, product.ubicacion
                ORDER BY display_order, product.code
                LIMIT ?
                """,
                (patron, patron, patron, limite),
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
                    SELECT id, display_order, template_row
                    FROM product_catalog_rows
                    ORDER BY display_order, id
                    """
                ).fetchall()
                if len(filas_plantilla) != len(filas_catalogo):
                    raise RuntimeError(
                        "La cantidad de filas de la plantilla no coincide "
                        "con el catálogo SQLite."
                    )
                cambios_fila = [
                    (fila_plantilla, fila_catalogo["id"])
                    for fila_catalogo, fila_plantilla in zip(
                        filas_catalogo, filas_plantilla
                    )
                    if fila_catalogo["template_row"] != fila_plantilla
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
                connection.commit()
                self.invalidar_cache()
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

    def update_product(self, *args, **kwargs):
        self.invalidar_cache()
        return self._update_product_inner(*args, **kwargs)

    def _update_product_inner(
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
                    SELECT id, template_row FROM product_catalog_rows
                    ORDER BY display_order, id
                    """
                ).fetchall()
                if len(filas_plantilla) != len(filas_catalogo):
                    raise RuntimeError(
                        "La cantidad de filas de la plantilla no coincide "
                        "con el catálogo SQLite."
                    )
                cambios_fila = [
                    (fila_plantilla, fila_catalogo["id"])
                    for fila_catalogo, fila_plantilla in zip(
                        filas_catalogo, filas_plantilla
                    )
                    if fila_catalogo["template_row"] != fila_plantilla
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

    def _buscar_producto_sql_por_columna(
        self,
        connection: sqlite3.Connection,
        columna: str,
        variantes: list[str],
        *,
        solo_no_vacio: bool = False,
    ) -> sqlite3.Row | None:
        """Ejecuta búsqueda escalonada (exacta, casteada/case-insensitive y sin ceros)."""
        if columna not in ("code", "cod_barras"):
            raise ValueError(f"Columna de búsqueda no permitida: {columna}")
        candidatos = [v for v in variantes if v]
        if not candidatos:
            return None

        filtro_exacto = " AND cod_barras != ''" if solo_no_vacio else ""
        filtro_norm = " AND COALESCE(TRIM(CAST(cod_barras AS TEXT)), '') != ''" if solo_no_vacio else ""
        cols_select = (
            "code, name, stock, active, stock_minimo, stock_maximo, "
            "stock_fisico, cod_barras, ubicacion"
        )

        # 1. Ruta rápida indexada por igualdad exacta
        for cand in candidatos:
            row = connection.execute(
                f"SELECT {cols_select} FROM products WHERE {columna} = ?{filtro_exacto} LIMIT 1",
                (cand,),
            ).fetchone()
            if row is not None:
                return row

        # 2. Ruta casteada a TEXT, sin espacios, sin sufijo '.0' y case-insensitive
        expr_texto = f"TRIM(CAST({columna} AS TEXT))"
        expr_sin_decimal = (
            f"CASE WHEN {expr_texto} GLOB '[0-9]*.0' "
            f"AND NOT (SUBSTR({expr_texto}, 1, LENGTH({expr_texto}) - 2) GLOB '*[^0-9]*') "
            f"THEN SUBSTR({expr_texto}, 1, LENGTH({expr_texto}) - 2) "
            f"ELSE {expr_texto} END"
        )
        for cand in candidatos:
            row = connection.execute(
                f"SELECT {cols_select} FROM products WHERE {expr_sin_decimal} = ? COLLATE NOCASE{filtro_norm} LIMIT 1",
                (cand,),
            ).fetchone()
            if row is not None:
                return row

        # 3. Equivalencia numérica sin ceros a la izquierda (solo cadenas puramente numéricas)
        vistos_num: set[str] = set()
        for cand in candidatos:
            if not cand.isdigit():
                continue
            sin_ceros = cand.lstrip("0") or "0"
            if sin_ceros in vistos_num:
                continue
            vistos_num.add(sin_ceros)
            row = connection.execute(
                f"""
                SELECT {cols_select}
                FROM products
                WHERE {expr_texto} != ''
                  AND NOT ({expr_texto} GLOB '*[^0-9]*')
                  AND COALESCE(NULLIF(LTRIM({expr_texto}, '0'), ''), '0') = ?{filtro_norm}
                LIMIT 1
                """,
                (sin_ceros,),
            ).fetchone()
            if row is not None:
                return row
        return None

    def _consultar_producto_cacheado(
        self,
        columna: str,
        raw_query: object,
        *,
        permitir_variantes: bool = True,
    ) -> sqlite3.Row | None:
        """Consulta un producto por SKU o código de barras con casteo, variantes y caché."""
        from src.products.barcode_utils import (
            generar_variantes_codigo_lector,
            normalizar_codigo_lector,
        )

        if permitir_variantes:
            variantes = generar_variantes_codigo_lector(raw_query)
        else:
            unico = normalizar_codigo_lector(raw_query)
            variantes = [unico] if unico else []

        if not variantes:
            return None

        cache_destino = self._cache_sku if columna == "code" else self._cache_barcode
        with self._cache_lock:
            if self._es_cache_valido():
                for cand in variantes:
                    cached = cache_destino.get(cand)
                    if cached is not None:
                        return cached

        with closing(self._connect()) as connection:
            dv = connection.execute("PRAGMA data_version").fetchone()[0]
            row = self._buscar_producto_sql_por_columna(
                connection,
                columna,
                variantes,
                solo_no_vacio=(columna == "cod_barras"),
            )

            with self._cache_lock:
                if not self._es_cache_valido(connection):
                    self._cache_sku.clear()
                    self._cache_barcode.clear()
                if row is not None:
                    code_canonical = normalizar_codigo_lector(row["code"]) or str(row["code"]).strip()
                    if code_canonical:
                        self._cache_sku[code_canonical] = row
                    bar_canonical = normalizar_codigo_lector(row["cod_barras"]) if row["cod_barras"] else ""
                    if bar_canonical:
                        self._cache_barcode[bar_canonical] = row
                    cache_destino[variantes[0]] = row
                self._cache_data_version = dv
                self._cache_ts = time.monotonic()
            return row

    def get_product(self, code: object) -> sqlite3.Row | None:
        """Obtiene un producto por su código interno (SKU) con casteo y soporte de caché."""
        return self._consultar_producto_cacheado("code", code, permitir_variantes=True)

    def _query_producto_raw(self, code: str) -> sqlite3.Row | None:
        """Consulta directa a SQLite sin pasar por el caché."""
        with closing(self._connect()) as conn:
            return conn.execute(
                "SELECT code, name, stock, active, stock_minimo, stock_maximo, stock_fisico, cod_barras, ubicacion FROM products WHERE code = ?",
                (code.strip(),),
            ).fetchone()

    def _unused_raw(self, code: str):
        return self._query_producto_raw(code)

    def _deprecated_stub(self):
        return None

    def actualizar_ubicacion(self, code: str, ubicacion: str) -> bool:
        """Actualiza la ubicación física en el depósito para un producto (ej. 'A-01-2')."""
        with closing(self._connect()) as connection, connection:
            cur = connection.execute(
                "UPDATE products SET ubicacion = ? WHERE code = ?",
                (ubicacion.strip().upper(), code.strip()),
            )
            self.invalidar_cache()
            return cur.rowcount > 0

    def get_product_by_barcode(self, cod_barras: object) -> sqlite3.Row | None:
        """Obtiene un producto por su código de barras con casteo y soporte de caché."""
        return self._consultar_producto_cacheado("cod_barras", cod_barras, permitir_variantes=True)

    def _query_barcode_raw(self, cod_barras: str) -> sqlite3.Row | None:
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

    def find_product_by_code_or_barcode(self, query: object) -> sqlite3.Row | None:
        """Busca primero por código interno (SKU) y luego por código de barras con casteo."""
        from src.products.barcode_utils import normalizar_codigo_lector

        val = normalizar_codigo_lector(query)
        if not val:
            return None

        # 1. Priorizar coincidencia exacta normalizada (SKU -> Código de barras)
        prod = self._consultar_producto_cacheado("code", val, permitir_variantes=False)
        if prod is not None:
            return prod
        prod = self._consultar_producto_cacheado("cod_barras", val, permitir_variantes=False)
        if prod is not None:
            return prod

        # 2. Respaldo por variantes (teclado US->ES/LA, ceros a la izquierda, EAN-13/UPC-A)
        prod = self.get_product(query)
        if prod is not None:
            return prod
        return self.get_product_by_barcode(query)

    def _find_product_raw(self, query: str) -> sqlite3.Row | None:
        """Busca primero por código interno (SKU), luego por código de barras."""
        val = query.strip()
        if not val:
            return None
        with closing(self._connect()) as connection:
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
            return connection.execute(
                """
                SELECT code, name, stock, active, stock_minimo, stock_maximo, stock_fisico, cod_barras
                FROM products
                WHERE cod_barras = ? AND cod_barras != ''
                LIMIT 1
                """,
                (val,),
            ).fetchone()

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
        self.invalidar_cache()
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
                    filas_plantilla = synchronize_template()
                    filas_catalogo = connection.execute(
                        """
                        SELECT id, template_row FROM product_catalog_rows
                        ORDER BY display_order, id
                        """
                    ).fetchall()
                    if len(filas_plantilla) != len(filas_catalogo):
                        raise RuntimeError(
                            "La cantidad de filas de la plantilla no coincide "
                            "con el catálogo SQLite."
                        )
                    cambios_fila = [
                        (fila_plantilla, fila_catalogo["id"])
                        for fila_catalogo, fila_plantilla in zip(
                            filas_catalogo, filas_plantilla
                        )
                        if fila_catalogo["template_row"] != fila_plantilla
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
