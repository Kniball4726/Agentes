"""Mixin de carga rápida desde SQLite, detección de esquema Excel y caché en memoria."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import openpyxl

from ..remito_parser import normalizar_codigo
from .excel_sync import detectar_esquema, leer_stock, normalizar_encabezado


class CatalogLoaderMixin:
    """Encapsula carga inicial desde Excel/SQLite, esquema de columnas y caché en memoria."""

    ruta_excel_base: Path
    nombre_hoja: str
    product_store: object
    productos_base: List[Tuple[int, str, str, int]]
    filas_catalogo: List[Tuple[int, str, str, int]]
    catalogo: Dict[str, Tuple[int, str, int]]
    _filas_por_codigo: Dict[str, List[int]]
    _col_codigo: int
    _col_nombre: int
    _col_stock: int
    _col_stock_inicial: Optional[int]
    _col_descuento: Optional[int]
    _col_stock_final: Optional[int]
    _fila_inicio_datos: int

    @staticmethod
    def _normalizar_encabezado(valor) -> str:
        return normalizar_encabezado(valor)

    def _detectar_esquema(self, sheet) -> None:
        esquema = detectar_esquema(sheet)
        self._col_codigo = esquema["col_codigo"] or 1
        self._col_nombre = esquema["col_nombre"] or 2
        self._col_stock = esquema["col_stock"] or 3
        self._col_stock_inicial = esquema["col_stock_inicial"]
        self._col_descuento = esquema["col_descuento"]
        self._col_stock_final = esquema["col_stock_final"]
        self._fila_inicio_datos = esquema["fila_inicio_datos"] or 3

    def _leer_stock(self, sheet, fila: int) -> int:
        return leer_stock(
            sheet=sheet,
            fila=fila,
            col_stock_final=self._col_stock_final,
            col_stock_inicial=self._col_stock_inicial,
            col_stock=self._col_stock,
        )

    def _asegurar_esquema(self) -> None:
        """Detecta el esquema del archivo Excel si no fue detectado aún."""
        if not self.ruta_excel_base.exists():
            return
        wb = openpyxl.load_workbook(str(self.ruta_excel_base), data_only=True)
        try:
            sheet = wb[self.nombre_hoja] if self.nombre_hoja in wb.sheetnames else wb.active
            if sheet is not None:
                self._detectar_esquema(sheet)
        finally:
            wb.close()

    def _serializar_esquema_meta(self) -> dict[str, str]:
        return {
            "col_codigo": str(self._col_codigo),
            "col_nombre": str(self._col_nombre),
            "col_stock": str(self._col_stock),
            "col_stock_inicial": str(self._col_stock_inicial) if self._col_stock_inicial is not None else "",
            "col_descuento": str(self._col_descuento) if self._col_descuento is not None else "",
            "col_stock_final": str(self._col_stock_final) if self._col_stock_final is not None else "",
            "fila_inicio_datos": str(self._fila_inicio_datos),
        }

    def _aplicar_esquema_meta(self, meta: dict[str, str]) -> None:
        for attr, key in (
            ("_fila_inicio_datos", "fila_inicio_datos"),
            ("_col_codigo", "col_codigo"),
            ("_col_nombre", "col_nombre"),
            ("_col_stock", "col_stock"),
            ("_col_stock_inicial", "col_stock_inicial"),
            ("_col_descuento", "col_descuento"),
            ("_col_stock_final", "col_stock_final"),
        ):
            if meta.get(key):
                try:
                    setattr(self, attr, int(meta[key]))
                except ValueError:
                    pass

    def _cargar_desde_sqlite(
        self,
        meta_precargada: Optional[dict[str, str]] = None,
        filas_precargadas: Optional[list[sqlite3.Row]] = None,
    ) -> None:
        """Carga el catálogo directamente desde SQLite utilizando metadatos de esquema cacheados."""
        if meta_precargada is not None and filas_precargadas is not None:
            meta = meta_precargada
            filas_iter = filas_precargadas
        else:
            _, meta, filas_iter = self.product_store.load_catalog_fast()

        if "fila_inicio_datos" not in meta:
            try:
                self._asegurar_esquema()
                schema_meta = self._serializar_esquema_meta()
                for k, v in schema_meta.items():
                    self.product_store.set_metadata(k, v)
                meta.update(schema_meta)
            except Exception:
                pass

        self._aplicar_esquema_meta(meta)

        primera_aparicion: set[str] = set()
        for indice, producto in enumerate(filas_iter):
            cod = str(producto["code"])
            nombre = str(producto["display_name"])
            nombre_catalogo = str(producto["name"])
            stock_num = int(producto["stock"])
            fila_plantilla = producto["template_row"]
            fila_estilo = int(fila_plantilla) if fila_plantilla is not None else 0
            fila_catalogo = indice + self._fila_inicio_datos

            self.filas_catalogo.append((fila_estilo, cod, nombre, stock_num))
            self._filas_por_codigo.setdefault(cod, []).append(fila_catalogo)
            if cod in primera_aparicion:
                continue

            primera_aparicion.add(cod)
            self.productos_base.append((fila_catalogo, cod, nombre_catalogo, stock_num))
            self.catalogo[cod] = (fila_catalogo, nombre_catalogo, stock_num)

    def _cargar_catalogo(self, forzar_excel: bool = False) -> None:
        """Importa el catálogo inicial y después carga productos desde SQLite (fast-path)."""
        if not self.ruta_excel_base.exists():
            raise FileNotFoundError(f"No se encontró el archivo de stock en: {self.ruta_excel_base}")

        self.productos_base.clear()
        self.filas_catalogo.clear()
        self.catalogo.clear()
        self._filas_por_codigo.clear()

        if not forzar_excel:
            importado, meta_fast, filas_fast = self.product_store.load_catalog_fast()
            if importado:
                self._cargar_desde_sqlite(meta_fast, filas_fast)
                return

        wb = openpyxl.load_workbook(str(self.ruta_excel_base), data_only=True)
        try:
            sheet = wb[self.nombre_hoja] if self.nombre_hoja in wb.sheetnames else wb.active
            if sheet is None:
                raise ValueError(f"No se encontró una hoja activa en {self.ruta_excel_base}.")
            self._detectar_esquema(sheet)
            productos_plantilla = []
            for fila in range(self._fila_inicio_datos, sheet.max_row + 1):
                val_cod = sheet.cell(row=fila, column=self._col_codigo).value
                if val_cod is not None and str(val_cod).strip() != "":
                    cod = normalizar_codigo(str(val_cod))
                    nombre = str(sheet.cell(row=fila, column=self._col_nombre).value or "").strip()
                    if not nombre:
                        continue
                    stock_num = self._leer_stock(sheet, fila)
                    productos_plantilla.append((fila, cod, nombre, stock_num))
        finally:
            wb.close()

        self.product_store.import_template_once(
            productos_plantilla,
            metadata=self._serializar_esquema_meta(),
        )
        self._cargar_desde_sqlite()

    def listar_productos(self) -> List[sqlite3.Row]:
        """Devuelve todos los productos para la pantalla de administración."""
        return self.product_store.list_products()

    def _actualizar_stocks_en_memoria(self, stocks: Dict[str, int]) -> None:
        """Actualiza los saldos de stock en las estructuras en memoria sin releer toda la base SQLite."""
        for cod, nuevo_stock in stocks.items():
            if cod in self.catalogo:
                fila_cat, nombre_cat, _ = self.catalogo[cod]
                self.catalogo[cod] = (fila_cat, nombre_cat, int(nuevo_stock))
        self.productos_base = [
            (fila_c, cod, nom, int(stocks.get(cod, stk)))
            for fila_c, cod, nom, stk in self.productos_base
        ]
        self.filas_catalogo = [
            (fila_est, cod, nom, int(stocks.get(cod, stk)))
            for fila_est, cod, nom, stk in self.filas_catalogo
        ]
