"""Repositorio mixin de solo lectura y caché para el catálogo de productos y códigos de barras."""

from __future__ import annotations

import sqlite3
import time
from contextlib import closing
from typing import Any, Callable

_COLS_PRODUCT_SELECT = (
    "code, name, stock, active, stock_minimo, stock_maximo, "
    "stock_fisico, cod_barras, ubicacion"
)


class CatalogReadMixin:
    """Mixin de consultas rápidas, listados y búsqueda cacheada por SKU/código de barras."""

    _connect: Callable[[], sqlite3.Connection]
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

    def list_catalog_rows(
        self, include_inactive: bool = False
    ) -> list[sqlite3.Row]:
        """Lista las filas del catálogo ordenadas según su posición en plantilla."""
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

    def list_products(self, solo_activos: bool = False) -> list[sqlite3.Row]:
        """Lista todos los productos del catálogo junto con sus métricas de stock."""
        where_clause = "WHERE product.active = 1" if solo_activos else ""
        with closing(self._connect()) as connection:
            return connection.execute(
                f"""
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
                {where_clause}
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

        for cand in candidatos:
            row = connection.execute(
                f"SELECT {_COLS_PRODUCT_SELECT} FROM products WHERE {columna} = ?{filtro_exacto} LIMIT 1",
                (cand,),
            ).fetchone()
            if row is not None:
                return row

        expr_texto = f"TRIM(CAST({columna} AS TEXT))"
        expr_sin_decimal = (
            f"CASE WHEN {expr_texto} GLOB '[0-9]*.0' "
            f"AND NOT (SUBSTR({expr_texto}, 1, LENGTH({expr_texto}) - 2) GLOB '*[^0-9]*') "
            f"THEN SUBSTR({expr_texto}, 1, LENGTH({expr_texto}) - 2) "
            f"ELSE {expr_texto} END"
        )
        for cand in candidatos:
            row = connection.execute(
                f"SELECT {_COLS_PRODUCT_SELECT} FROM products WHERE {expr_sin_decimal} = ? COLLATE NOCASE{filtro_norm} LIMIT 1",
                (cand,),
            ).fetchone()
            if row is not None:
                return row

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
                SELECT {_COLS_PRODUCT_SELECT}
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
                f"SELECT {_COLS_PRODUCT_SELECT} FROM products WHERE code = ?",
                (code.strip(),),
            ).fetchone()

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

        prod = self._consultar_producto_cacheado("code", val, permitir_variantes=False)
        if prod is not None:
            return prod
        prod = self._consultar_producto_cacheado("cod_barras", val, permitir_variantes=False)
        if prod is not None:
            return prod

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
