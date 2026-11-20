"""Servicio de sincronización transaccional entre SQLite y Productos.xlsx."""

from __future__ import annotations

import logging
from contextlib import closing
import os
import shutil
import tempfile
from copy import copy
from pathlib import Path
from typing import Callable, Dict, Optional, Tuple

import openpyxl

from ..core.sanitize_utils import sanitizar_celda_excel
from ..parsers.remito_parser import normalizar_codigo
from .protocols import InventoryHostProtocol

logger = logging.getLogger(__name__)


class ResultadoSincronizacionExcel(dict):
    """Contenedor de resultados de sincronización con Productos.xlsx compatible con int."""

    def __init__(self, importados: int = 0, desactivados: int = 0, reactivados: int = 0):
        super().__init__(importados=importados, desactivados=desactivados, reactivados=reactivados)
        self.importados = importados
        self.desactivados = desactivados
        self.reactivados = reactivados

    def __int__(self) -> int:
        return self.importados

    def __index__(self) -> int:
        return self.importados

    def __format__(self, format_spec: str) -> str:
        return format(self.importados, format_spec)


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


class TemplateSyncService:
    """Encapsula mutaciones de catálogo/stock sincronizadas con respaldo y rollback sobre Excel."""

    def __init__(self, host: InventoryHostProtocol) -> None:
        self._host = host

    def _escribir_stock_en_celdas(self, hoja, fila: int, stock: int) -> None:
        if self._host._col_stock_final is not None:
            columna_inicial = self._host._col_stock_inicial or self._host._col_stock
            hoja.cell(fila, columna_inicial, stock)
            if self._host._col_descuento is not None:
                hoja.cell(fila, self._host._col_descuento, None)
            hoja.cell(fila, self._host._col_stock_final, stock)
        else:
            hoja.cell(fila, self._host._col_stock, stock)

    def _abrir_libro_editable(self) -> tuple[openpyxl.Workbook, object]:
        libro = openpyxl.load_workbook(str(self._host.ruta_excel_base))
        hoja = libro[self._host.nombre_hoja] if self._host.nombre_hoja in libro.sheetnames else libro.active
        if hoja is None:
            libro.close()
            raise ValueError("No se encontró una hoja para actualizar.")
        return libro, hoja

    def _restaurar_desde_bytes(self, contenido_original: bytes) -> None:
        _reemplazar_atomicamente(
            self._host.ruta_excel_base,
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
        """Actualiza código, descripción, stock y parámetros en SQLite y opcionalmente en Productos.xlsx."""
        codigo_actual = normalizar_codigo(codigo_actual)
        codigo_nuevo = normalizar_codigo(codigo_nuevo)
        nombre = nombre.strip()
        if not codigo_actual or not codigo_nuevo or not nombre:
            raise ValueError("El código y el nombre del producto son obligatorios.")

        ruta_excel = getattr(self._host, "ruta_excel_base", None)
        tiene_excel = bool(ruta_excel and ruta_excel.exists())
        sync_fn = None
        restore_fn = None

        if tiene_excel:
            contenido_original = ruta_excel.read_bytes()
            respaldo = ruta_excel.with_name(
                f"{ruta_excel.stem}_backup{ruta_excel.suffix}"
            )
            plantilla_actualizada = False

            def sincronizar_plantilla() -> list[int]:
                nonlocal plantilla_actualizada
                shutil.copy2(ruta_excel, respaldo)
                libro, hoja = self._abrir_libro_editable()
                try:
                    filas_producto: list[int] = []
                    filas_validas: list[int] = []
                    for fila in range(self._host._fila_inicio_datos, hoja.max_row + 1):
                        val_c = hoja.cell(fila, self._host._col_codigo).value
                        val_n = hoja.cell(fila, self._host._col_nombre).value
                        if val_c is not None and str(val_n or "").strip():
                            filas_validas.append(fila)
                            if normalizar_codigo(str(val_c)) == codigo_actual:
                                filas_producto.append(fila)

                    filas_catalogo_producto = [
                        producto
                        for producto in self._host.product_store.list_catalog_rows(include_inactive=True)
                        if str(producto["code"]) == codigo_actual
                    ]
                    if not filas_producto or len(filas_producto) != len(filas_catalogo_producto):
                        raise RuntimeError(
                            f"Las filas de '{codigo_actual}' en Productos.xlsx no coinciden con el catálogo."
                        )

                    codigo_excel = int(codigo_nuevo) if codigo_nuevo.isdigit() else sanitizar_celda_excel(codigo_nuevo)
                    for fila in filas_producto:
                        hoja.cell(fila, self._host._col_codigo, codigo_excel)
                        hoja.cell(fila, self._host._col_nombre, sanitizar_celda_excel(nombre))
                        self._escribir_stock_en_celdas(hoja, fila, stock)

                    _reemplazar_atomicamente(ruta_excel, lambda p: libro.save(p))
                    plantilla_actualizada = True
                    return filas_validas
                finally:
                    libro.close()

            def restaurar_plantilla() -> None:
                if plantilla_actualizada:
                    self._restaurar_desde_bytes(contenido_original)

            sync_fn = sincronizar_plantilla
            restore_fn = restaurar_plantilla

        self._host.product_store.update_product(
            old_code=codigo_actual,
            new_code=codigo_nuevo,
            name=nombre,
            stock=stock,
            synchronize_template=sync_fn,
            restore_template=restore_fn,
            stock_minimo=stock_minimo,
            stock_maximo=stock_maximo,
            cod_barras=cod_barras,
        )
        self._host._cargar_catalogo()

    def cambiar_estado_producto(self, codigo: str, activo: bool) -> None:
        """Activa o desactiva un producto y refresca el caché en memoria."""
        self._host.product_store.set_product_active(normalizar_codigo(codigo), activo)
        self._host._cargar_catalogo()

    def agregar_producto_en_posicion(
        self,
        codigo_nuevo: str,
        nombre_nuevo: str,
        codigo_arriba: str,
        stock_inicial: Optional[int] = None,
        cod_barras: str = "",
    ) -> Tuple[bool, str, Optional[int]]:
        """Inserta un nuevo producto en SQLite (y en Excel si está presente) inmediatamente debajo de `codigo_arriba`."""
        cod_nuevo_norm = normalizar_codigo(codigo_nuevo)
        cod_arriba_norm = normalizar_codigo(codigo_arriba)

        if cod_nuevo_norm in self._host.catalogo:
            fila_exist, nombre_exist, _ = self._host.catalogo[cod_nuevo_norm]
            return False, f"El codigo '{cod_nuevo_norm}' ya existe en la fila {fila_exist} ('{nombre_exist}').", None

        if cod_arriba_norm not in self._host.catalogo:
            return False, f"No se encontro el producto de referencia con codigo '{cod_arriba_norm}' en el catalogo.", None

        ruta_excel = getattr(self._host, "ruta_excel_base", None)
        tiene_excel = bool(ruta_excel and ruta_excel.exists())
        sync_fn = None
        restore_fn = None

        if tiene_excel:
            contenido_original = ruta_excel.read_bytes()
            respaldo = ruta_excel.with_name(
                f"{ruta_excel.stem}_backup{ruta_excel.suffix}"
            )
            plantilla_actualizada = False

            def sincronizar_plantilla(orden: int) -> list[int]:
                nonlocal plantilla_actualizada
                shutil.copy2(ruta_excel, respaldo)
                libro, hoja = self._abrir_libro_editable()
                try:
                    fila_referencia = next(
                        (
                            fila
                            for fila in range(self._host._fila_inicio_datos, hoja.max_row + 1)
                            if normalizar_codigo(str(hoja.cell(fila, self._host._col_codigo).value or "")) == cod_arriba_norm
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

                    codigo_excel = int(cod_nuevo_norm) if cod_nuevo_norm.isdigit() else sanitizar_celda_excel(cod_nuevo_norm)
                    hoja.cell(fila_nueva, self._host._col_codigo, codigo_excel)
                    hoja.cell(fila_nueva, self._host._col_nombre, sanitizar_celda_excel(str(nombre_nuevo).strip()))
                    self._escribir_stock_en_celdas(hoja, fila_nueva, stock_inicial or 0)

                    _reemplazar_atomicamente(ruta_excel, lambda p: libro.save(p))
                    plantilla_actualizada = True
                finally:
                    libro.close()

                libro_verif = openpyxl.load_workbook(str(ruta_excel), data_only=True, read_only=True)
                try:
                    hoja_verif = (
                        libro_verif[self._host.nombre_hoja]
                        if self._host.nombre_hoja in libro_verif.sheetnames
                        else libro_verif.active
                    )
                    if hoja_verif is None:
                        raise ValueError("No se pudo verificar la plantilla después del alta.")
                    filas_plantilla = [
                        fila
                        for fila in range(self._host._fila_inicio_datos, hoja_verif.max_row + 1)
                        if hoja_verif.cell(fila, self._host._col_codigo).value is not None
                        and str(hoja_verif.cell(fila, self._host._col_nombre).value or "").strip()
                    ]
                    if orden >= len(filas_plantilla) or filas_plantilla[orden] != fila_nueva:
                        raise RuntimeError("El orden insertado en Productos.xlsx no coincide con el orden de SQLite.")
                    return filas_plantilla
                finally:
                    libro_verif.close()

            def restaurar_plantilla() -> None:
                if plantilla_actualizada:
                    self._restaurar_desde_bytes(contenido_original)

            sync_fn = sincronizar_plantilla
            restore_fn = restaurar_plantilla

        try:
            orden, nombre_arriba = self._host.product_store.add_product_after(
                code=cod_nuevo_norm,
                name=str(nombre_nuevo).strip(),
                reference_code=cod_arriba_norm,
                stock=stock_inicial or 0,
                synchronize_template=sync_fn,
                restore_template=restore_fn,
                cod_barras=cod_barras,
            )
        except (ValueError, OSError, RuntimeError) as error:
            return False, str(error), None

        self._host._cargar_catalogo()
        fila_nueva = orden + self._host._fila_inicio_datos
        return True, (
            f"Producto '{nombre_nuevo}' [{cod_nuevo_norm}] insertado en la "
            f"posición {fila_nueva} del catálogo (debajo de [{cod_arriba_norm}] {nombre_arriba})."
        ), fila_nueva

    def sincronizar_stocks(self, stocks: Dict[str, int]) -> int:
        """Actualiza el stock en la base SQLite de forma atómica e instantánea (sin tocar Excel)."""
        if not stocks:
            return 0

        stocks_normalizados = {normalizar_codigo(k): int(v) for k, v in stocks.items()}
        filas_actualizadas = self._host.product_store.update_stocks(stocks=stocks_normalizados)
        self._host._actualizar_stocks_en_memoria(stocks_normalizados)
        return filas_actualizadas

    def exportar_catalogo_a_excel(self, ruta_destino: Path | str | None = None) -> int:
        """Exporta el catálogo completo y saldos vigentes desde SQLite hacia un archivo Excel."""
        from .excel_exporter import exportar_catalogo_a_excel as _exportar

        destino = Path(ruta_destino) if ruta_destino else self._host.ruta_excel_base
        return _exportar(
            product_store=self._host.product_store,
            ruta_destino=destino,
            nombre_hoja=self._host.nombre_hoja,
        )

    def sincronizar_catalogo_completo_excel(self) -> int:
        """Sincroniza y vuelca el stock de SQLite con Productos.xlsx.

        Si Productos.xlsx ya existe, valida los códigos presentes desactivando
        en SQLite los que hayan sido quitados de la planilla. Luego exporta/actualiza.
        """
        if not getattr(self._host, "product_store", None):
            return 0
        ruta_excel = getattr(self._host, "ruta_excel_base", None)
        if ruta_excel and ruta_excel.exists():
            try:
                with closing(openpyxl.load_workbook(str(ruta_excel), data_only=True, read_only=True)) as wb:
                    sheet = wb[self._host.nombre_hoja] if self._host.nombre_hoja in wb.sheetnames else wb.active
                    if sheet:
                        codigos_en_plantilla = set()
                        for r in range(self._host._fila_inicio_datos, sheet.max_row + 1):
                            val = sheet.cell(r, self._host._col_codigo).value
                            if val is not None and str(val).strip():
                                codigos_en_plantilla.add(normalizar_codigo(str(val)))
                        if codigos_en_plantilla:
                            _, desact = self._host.product_store.sync_active_status_with_codes(codigos_en_plantilla)
                            self._host._ultimos_desactivados = desact
                            self._host._cargar_catalogo(forzar_excel=False)
            except Exception as e:
                logger.warning("No se pudo leer códigos existentes de la plantilla: %s", e)

        return self._host.exportar_catalogo_a_excel()

    def importar_catalogo_desde_excel(
        self, ruta_excel: Path | str | None = None
    ) -> ResultadoSincronizacionExcel:
        """Lee Productos.xlsx (o una ruta provista) e importa o actualiza los productos y stocks en SQLite.

        Aquellos productos en la base de datos que ya no figuren en la planilla
        se marcan automáticamente como inactivos (active = 0).
        """
        origen = Path(ruta_excel) if ruta_excel else self._host.ruta_excel_base
        if not origen.exists():
            raise FileNotFoundError(f"No se encontró el archivo: {origen}")
        wb = openpyxl.load_workbook(str(origen), data_only=True)
        try:
            sheet = wb[self._host.nombre_hoja] if self._host.nombre_hoja in wb.sheetnames else wb.active
            if sheet is None:
                raise ValueError("No se encontró una hoja activa en la planilla de stock.")
            self._host._detectar_esquema(sheet)
            productos: list[tuple[int, str, str, int]] = []
            codigos_en_excel: set[str] = set()
            for fila in range(self._host._fila_inicio_datos, sheet.max_row + 1):
                val_cod = sheet.cell(row=fila, column=self._host._col_codigo).value
                if val_cod is not None and str(val_cod).strip():
                    cod = normalizar_codigo(str(val_cod))
                    nombre = str(sheet.cell(row=fila, column=self._host._col_nombre).value or "").strip()
                    if not nombre:
                        continue
                    stock_num = self._host._leer_stock(sheet, fila)
                    productos.append((fila, cod, nombre, stock_num))
                    codigos_en_excel.add(cod)
        finally:
            wb.close()

        if not productos:
            return ResultadoSincronizacionExcel(importados=0, desactivados=0, reactivados=0)

        with closing(self._host.product_store._connect()) as conn, conn:
            conn.execute("BEGIN IMMEDIATE")
            for fila, cod, nom, stk in productos:
                conn.execute(
                    """
                    INSERT INTO products (code, name, stock, active)
                    VALUES (?, ?, ?, 1)
                    ON CONFLICT(code) DO UPDATE SET
                        name = excluded.name,
                        stock = excluded.stock,
                        active = 1
                    """,
                    (cod, nom, stk),
                )
                conn.execute(
                    """
                    INSERT INTO product_catalog_rows (product_code, display_name, display_order, template_row)
                    SELECT ?, ?, (SELECT COALESCE(MAX(display_order), 0) + 1 FROM product_catalog_rows), ?
                    WHERE NOT EXISTS (
                        SELECT 1 FROM product_catalog_rows WHERE product_code = ?
                    )
                    """,
                    (cod, nom, fila, cod),
                )
            conn.commit()

        # Desactivar en SQLite los productos ausentes en Productos.xlsx y activar presentes
        activados, desactivados = self._host.product_store.sync_active_status_with_codes(codigos_en_excel)
        self._host._ultimos_desactivados = desactivados

        self._host.product_store.invalidar_cache()
        self._host._cargar_catalogo(forzar_excel=False)
        return ResultadoSincronizacionExcel(
            importados=len(productos),
            desactivados=desactivados,
            reactivados=activados,
        )
