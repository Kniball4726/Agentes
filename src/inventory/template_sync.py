"""Mixin de sincronización transaccional bidireccional entre SQLite y Productos.xlsx."""

from __future__ import annotations

import os
import shutil
import tempfile
from copy import copy
from pathlib import Path
from typing import Callable, Dict, Optional, Tuple

import openpyxl

from ..remito_parser import normalizar_codigo


def _reemplazar_atomicamente(ruta_destino: Path, guardar_en: Callable[[Path], None]) -> None:
    """Escribe contenido en un archivo temporal en el mismo directorio y reemplaza atómicamente."""
    with tempfile.NamedTemporaryFile(
        suffix=ruta_destino.suffix,
        dir=ruta_destino.parent,
        delete=False,
    ) as temporal:
        ruta_temporal = Path(temporal.name)
    try:
        guardar_en(ruta_temporal)
        os.replace(ruta_temporal, ruta_destino)
    finally:
        if ruta_temporal.exists():
            ruta_temporal.unlink()


class TemplateSyncMixin:
    """Encapsula mutaciones de catálogo/stock sincronizadas con respaldo y rollback sobre Excel."""

    ruta_excel_base: Path
    nombre_hoja: str
    product_store: object
    catalogo: Dict[str, Tuple[int, str, int]]
    _col_codigo: int
    _col_nombre: int
    _col_stock: int
    _col_stock_inicial: Optional[int]
    _col_descuento: Optional[int]
    _col_stock_final: Optional[int]
    _fila_inicio_datos: int

    def _escribir_stock_en_celdas(self, hoja, fila: int, stock: int) -> None:
        if self._col_stock_final is not None:
            columna_inicial = self._col_stock_inicial or self._col_stock
            hoja.cell(fila, columna_inicial, stock)
            if self._col_descuento is not None:
                hoja.cell(fila, self._col_descuento, None)
            hoja.cell(fila, self._col_stock_final, stock)
        else:
            hoja.cell(fila, self._col_stock, stock)

    def _abrir_libro_editable(self) -> tuple[openpyxl.Workbook, object]:
        libro = openpyxl.load_workbook(str(self.ruta_excel_base))
        hoja = libro[self.nombre_hoja] if self.nombre_hoja in libro.sheetnames else libro.active
        if hoja is None:
            libro.close()
            raise ValueError("No se encontró una hoja para actualizar.")
        return libro, hoja

    def _restaurar_desde_bytes(self, contenido_original: bytes) -> None:
        _reemplazar_atomicamente(
            self.ruta_excel_base,
            lambda p: p.write_bytes(contenido_original),
        )

    def actualizar_producto(
        self,
        codigo_actual: str,
        codigo_nuevo: str,
        nombre: str,
        stock: int,
        stock_minimo: Optional[int] = None,
        stock_maximo: Optional[int] = None,
        cod_barras: Optional[str] = None,
    ) -> None:
        """Actualiza código, descripción, stock y parámetros en SQLite y en Productos.xlsx."""
        codigo_actual = normalizar_codigo(codigo_actual)
        codigo_nuevo = normalizar_codigo(codigo_nuevo)
        nombre = nombre.strip()
        if not codigo_actual or not codigo_nuevo or not nombre:
            raise ValueError("El código y el nombre del producto son obligatorios.")

        contenido_original = self.ruta_excel_base.read_bytes()
        respaldo = self.ruta_excel_base.with_name(
            f"{self.ruta_excel_base.stem}_backup{self.ruta_excel_base.suffix}"
        )
        plantilla_actualizada = False

        def sincronizar_plantilla() -> list[int]:
            nonlocal plantilla_actualizada
            shutil.copy2(self.ruta_excel_base, respaldo)
            libro, hoja = self._abrir_libro_editable()
            try:
                filas_producto: list[int] = []
                filas_validas: list[int] = []
                for fila in range(self._fila_inicio_datos, hoja.max_row + 1):
                    val_c = hoja.cell(fila, self._col_codigo).value
                    val_n = hoja.cell(fila, self._col_nombre).value
                    if val_c is not None and str(val_n or "").strip():
                        filas_validas.append(fila)
                        if normalizar_codigo(str(val_c)) == codigo_actual:
                            filas_producto.append(fila)

                filas_catalogo_producto = [
                    producto
                    for producto in self.product_store.list_catalog_rows(include_inactive=True)
                    if str(producto["code"]) == codigo_actual
                ]
                if not filas_producto or len(filas_producto) != len(filas_catalogo_producto):
                    raise RuntimeError(
                        f"Las filas de '{codigo_actual}' en Productos.xlsx no coinciden con el catálogo."
                    )

                codigo_excel = int(codigo_nuevo) if codigo_nuevo.isdigit() else codigo_nuevo
                for fila in filas_producto:
                    hoja.cell(fila, self._col_codigo, codigo_excel)
                    hoja.cell(fila, self._col_nombre, nombre)
                    self._escribir_stock_en_celdas(hoja, fila, stock)

                _reemplazar_atomicamente(self.ruta_excel_base, lambda p: libro.save(p))
                plantilla_actualizada = True
                return filas_validas
            finally:
                libro.close()

        def restaurar_plantilla() -> None:
            if plantilla_actualizada:
                self._restaurar_desde_bytes(contenido_original)

        self.product_store.update_product(
            old_code=codigo_actual,
            new_code=codigo_nuevo,
            name=nombre,
            stock=stock,
            synchronize_template=sincronizar_plantilla,
            restore_template=restaurar_plantilla,
            stock_minimo=stock_minimo,
            stock_maximo=stock_maximo,
            cod_barras=cod_barras,
        )
        self._cargar_catalogo()

    def cambiar_estado_producto(self, codigo: str, activo: bool) -> None:
        """Activa o desactiva un producto y refresca el caché en memoria."""
        self.product_store.set_product_active(normalizar_codigo(codigo), activo)
        self._cargar_catalogo()

    def agregar_producto_en_posicion(
        self,
        codigo_nuevo: str,
        nombre_nuevo: str,
        codigo_arriba: str,
        stock_inicial: Optional[int] = None,
        cod_barras: str = "",
    ) -> Tuple[bool, str, Optional[int]]:
        """Inserta un nuevo producto en SQLite y Excel inmediatamente debajo de `codigo_arriba`."""
        cod_nuevo_norm = normalizar_codigo(codigo_nuevo)
        cod_arriba_norm = normalizar_codigo(codigo_arriba)

        if cod_nuevo_norm in self.catalogo:
            fila_exist, nombre_exist, _ = self.catalogo[cod_nuevo_norm]
            return False, f"El codigo '{cod_nuevo_norm}' ya existe en la fila {fila_exist} ('{nombre_exist}').", None

        if cod_arriba_norm not in self.catalogo:
            return False, f"No se encontro el producto de referencia con codigo '{cod_arriba_norm}' en el catalogo.", None

        contenido_original = self.ruta_excel_base.read_bytes()
        respaldo = self.ruta_excel_base.with_name(
            f"{self.ruta_excel_base.stem}_backup{self.ruta_excel_base.suffix}"
        )
        plantilla_actualizada = False

        def sincronizar_plantilla(orden: int) -> list[int]:
            nonlocal plantilla_actualizada
            shutil.copy2(self.ruta_excel_base, respaldo)
            libro, hoja = self._abrir_libro_editable()
            try:
                fila_referencia = next(
                    (
                        fila
                        for fila in range(self._fila_inicio_datos, hoja.max_row + 1)
                        if normalizar_codigo(str(hoja.cell(fila, self._col_codigo).value or "")) == cod_arriba_norm
                    ),
                    None,
                )
                if fila_referencia is None:
                    raise ValueError(f"No se encontró el código de referencia '{cod_arriba_norm}' en Productos.xlsx.")

                fila_nueva = fila_referencia + 1
                hoja.insert_rows(fila_nueva, 1)
                for columna in range(1, hoja.max_column + 1):
                    origen = hoja.cell(fila_referencia, columna)
                    destino = hoja.cell(fila_nueva, columna)
                    if origen.has_style:
                        destino._style = copy(origen._style)
                    if origen.number_format:
                        destino.number_format = origen.number_format
                hoja.row_dimensions[fila_nueva].height = hoja.row_dimensions[fila_referencia].height

                codigo_excel = int(cod_nuevo_norm) if cod_nuevo_norm.isdigit() else cod_nuevo_norm
                hoja.cell(fila_nueva, self._col_codigo, codigo_excel)
                hoja.cell(fila_nueva, self._col_nombre, str(nombre_nuevo).strip())
                self._escribir_stock_en_celdas(hoja, fila_nueva, stock_inicial or 0)

                _reemplazar_atomicamente(self.ruta_excel_base, lambda p: libro.save(p))
                plantilla_actualizada = True
            finally:
                libro.close()

            libro_verif = openpyxl.load_workbook(str(self.ruta_excel_base), data_only=True, read_only=True)
            try:
                hoja_verif = (
                    libro_verif[self.nombre_hoja]
                    if self.nombre_hoja in libro_verif.sheetnames
                    else libro_verif.active
                )
                if hoja_verif is None:
                    raise ValueError("No se pudo verificar la plantilla después del alta.")
                filas_plantilla = [
                    fila
                    for fila in range(self._fila_inicio_datos, hoja_verif.max_row + 1)
                    if hoja_verif.cell(fila, self._col_codigo).value is not None
                    and str(hoja_verif.cell(fila, self._col_nombre).value or "").strip()
                ]
                if orden >= len(filas_plantilla) or filas_plantilla[orden] != fila_nueva:
                    raise RuntimeError("El orden insertado en Productos.xlsx no coincide con el orden de SQLite.")
                return filas_plantilla
            finally:
                libro_verif.close()

        def restaurar_plantilla() -> None:
            if plantilla_actualizada:
                self._restaurar_desde_bytes(contenido_original)

        try:
            orden, nombre_arriba = self.product_store.add_product_after(
                code=cod_nuevo_norm,
                name=str(nombre_nuevo).strip(),
                reference_code=cod_arriba_norm,
                stock=stock_inicial or 0,
                synchronize_template=sincronizar_plantilla,
                restore_template=restaurar_plantilla,
                cod_barras=cod_barras,
            )
        except (ValueError, OSError, RuntimeError) as error:
            return False, str(error), None

        self._cargar_catalogo()
        fila_nueva = orden + self._fila_inicio_datos
        return True, (
            f"Producto '{nombre_nuevo}' [{cod_nuevo_norm}] insertado en la "
            f"posición {fila_nueva} del catálogo (debajo de [{cod_arriba_norm}] {nombre_arriba})."
        ), fila_nueva

    def sincronizar_stocks(self, stocks: Dict[str, int]) -> int:
        """Actualiza el stock en la base SQLite y sincroniza Productos.xlsx."""
        if not stocks:
            return 0

        stocks_normalizados = {normalizar_codigo(k): int(v) for k, v in stocks.items()}
        contenido_original = self.ruta_excel_base.read_bytes()
        respaldo = self.ruta_excel_base.with_name(
            f"{self.ruta_excel_base.stem}_backup{self.ruta_excel_base.suffix}"
        )
        plantilla_actualizada = False

        def sincronizar_plantilla() -> list[int]:
            nonlocal plantilla_actualizada
            shutil.copy2(self.ruta_excel_base, respaldo)
            libro, hoja = self._abrir_libro_editable()
            try:
                filas_validas: list[int] = []
                for fila in range(self._fila_inicio_datos, hoja.max_row + 1):
                    val_cod = hoja.cell(fila, self._col_codigo).value
                    if val_cod is None:
                        continue
                    val_nom = hoja.cell(fila, self._col_nombre).value
                    if str(val_nom or "").strip():
                        filas_validas.append(fila)
                    cod = normalizar_codigo(str(val_cod))
                    if cod in stocks_normalizados:
                        self._escribir_stock_en_celdas(hoja, fila, stocks_normalizados[cod])

                _reemplazar_atomicamente(self.ruta_excel_base, lambda p: libro.save(p))
                plantilla_actualizada = True
                return filas_validas
            finally:
                libro.close()

        def restaurar_plantilla() -> None:
            if plantilla_actualizada:
                self._restaurar_desde_bytes(contenido_original)

        filas_actualizadas = self.product_store.update_stocks(
            stocks=stocks_normalizados,
            synchronize_template=sincronizar_plantilla,
            restore_template=restaurar_plantilla,
        )
        self._actualizar_stocks_en_memoria(stocks_normalizados)
        return filas_actualizadas

    def sincronizar_catalogo_completo_excel(self) -> int:
        """Vuelca todo el stock y productos consolidados desde SQLite hacia Productos.xlsx."""
        if not hasattr(self, "product_store") or not self.product_store:
            return 0
        rows = self.product_store.list_products()
        if not rows:
            return 0
        stocks = {str(r["code"]).strip(): int(r["stock"]) for r in rows}
        return self.sincronizar_stocks(stocks)
