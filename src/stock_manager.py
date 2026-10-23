"""Carga el catálogo desde SQLite y genera informes Excel con la plantilla visual."""

from dataclasses import dataclass
from copy import copy
from datetime import datetime
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
from typing import Dict, List, Literal, Optional, Tuple
import unicodedata
import openpyxl
from openpyxl.utils import get_column_letter
import xlwt
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from xml.sax.saxutils import escape
from .consolidator import ItemConsolidado
from .product_store import ProductStore
from .remito_parser import ResultadoRemito, normalizar_codigo


_ALINEACIONES_PDF: dict[str, Literal[0, 1, 2]] = {
    "left": 0,
    "center": 1,
    "right": 2,
}


@dataclass
class RegistroDescuento:
    codigo: str
    nombre_producto: str
    fila_excel: int
    stock_anterior: int
    cantidad_descontada: int
    stock_nuevo: int
    es_nuevo_agregado: bool = False


@dataclass
class ReporteStock:
    descuentos_aplicados: List[RegistroDescuento]
    archivo_guardado: str
    archivo_pdf: Optional[str] = None


class StockManager:
    def __init__(
        self,
        ruta_excel_base: str | Path,
        nombre_hoja: str = "Stock",
        ruta_base_datos: str | Path | None = None,
    ):
        self.ruta_excel_base = Path(ruta_excel_base)
        self.nombre_hoja = nombre_hoja
        carpeta_base_datos = (
            self.ruta_excel_base.parent.parent
            if self.ruta_excel_base.parent.name.casefold() == "descuentos"
            else self.ruta_excel_base.parent
        )
        self.ruta_base_datos = (
            Path(ruta_base_datos)
            if ruta_base_datos is not None
            else carpeta_base_datos / "data" / "productos.sqlite3"
        )
        self.product_store = ProductStore(self.ruta_base_datos)
        # Lista ordenada de productos únicos: (fila_original, codigo, nombre, stock_actual)
        self.productos_base: List[Tuple[int, str, str, int]] = []
        self.filas_catalogo: List[Tuple[int, str, str, int]] = []
        self.catalogo: Dict[str, Tuple[int, str, int]] = {}
        self._filas_por_codigo: Dict[str, List[int]] = {}
        self._col_codigo = 1
        self._col_nombre = 2
        self._col_stock = 3
        self._col_stock_inicial: Optional[int] = None
        self._col_descuento: Optional[int] = None
        self._col_stock_final: Optional[int] = None
        self._fila_inicio_datos = 3
        self._cargar_catalogo()

    @staticmethod
    def _normalizar_encabezado(valor) -> str:
        texto = unicodedata.normalize("NFKD", str(valor or ""))
        return "".join(caracter for caracter in texto if not unicodedata.combining(caracter)).strip().upper()

    def _detectar_esquema(self, sheet) -> None:
        encabezados_codigo = {"CODIGO", "COD"}
        encabezados_nombre = {"PRODUCTO", "PRODUCTOS", "DESCRIPCION", "ARTICULO"}
        fila_encabezados = None
        columnas = {}
        filas_stock = []

        for fila in range(1, min(sheet.max_row, 14) + 1):
            fila_actual = {}
            for columna in range(1, sheet.max_column + 1):
                valor = self._normalizar_encabezado(sheet.cell(fila, columna).value)
                if valor in encabezados_codigo:
                    fila_actual["codigo"] = columna
                elif valor in encabezados_nombre:
                    fila_actual["nombre"] = columna
                elif valor == "STOCK INICIAL":
                    self._col_stock_inicial = columna
                    filas_stock.append(fila)
                elif valor == "DESCUENTO":
                    self._col_descuento = columna
                    filas_stock.append(fila)
                elif valor == "STOCK FINAL":
                    self._col_stock_final = columna
                    filas_stock.append(fila)

            if "codigo" in fila_actual and "nombre" in fila_actual:
                fila_encabezados = fila
                columnas = fila_actual

        if fila_encabezados is None:
            self._col_codigo = 1
            self._col_nombre = 2
            self._col_stock = 3
            self._col_stock_inicial = None
            self._col_descuento = None
            self._col_stock_final = None
            self._fila_inicio_datos = 3
            return

        self._col_codigo = columnas["codigo"]
        self._col_nombre = columnas["nombre"]
        self._col_stock = self._col_stock_inicial or 3
        self._fila_inicio_datos = max(3, fila_encabezados + 1, *(fila + 1 for fila in filas_stock))

    def _leer_stock(self, sheet, fila: int) -> int:
        columnas_stock = [self._col_stock_final, self._col_stock_inicial or self._col_stock]
        for columna in columnas_stock:
            if columna is None:
                continue
            valor = sheet.cell(row=fila, column=columna).value
            if valor is None or not str(valor).strip():
                continue
            try:
                return int(round(float(str(valor).replace(",", "."))))
            except (ValueError, TypeError):
                continue
        return 0

    def _cargar_catalogo(self):
        """Importa el catálogo inicial y después carga productos desde SQLite."""
        if not self.ruta_excel_base.exists():
            raise FileNotFoundError(f"No se encontró el archivo de stock en: {self.ruta_excel_base}")

        self.productos_base.clear()
        self.filas_catalogo.clear()
        self.catalogo.clear()
        self._filas_por_codigo.clear()

        wb = openpyxl.load_workbook(str(self.ruta_excel_base), data_only=True)
        sheet = wb[self.nombre_hoja] if self.nombre_hoja in wb.sheetnames else wb.active
        if sheet is None:
            wb.close()
            raise ValueError(
                f"No se encontró una hoja activa en {self.ruta_excel_base}."
            )
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
        wb.close()

        self.product_store.import_template_once(productos_plantilla)
        primera_aparicion: set[str] = set()
        for indice, producto in enumerate(self.product_store.list_catalog_rows()):
            cod = str(producto["code"])
            nombre = str(producto["display_name"])
            nombre_catalogo = str(producto["name"])
            stock_num = int(producto["stock"])
            fila_plantilla = producto["template_row"]
            fila_estilo = int(fila_plantilla) if fila_plantilla is not None else 0
            fila_catalogo = indice + self._fila_inicio_datos

            self.filas_catalogo.append(
                (fila_estilo, cod, nombre, stock_num)
            )
            self._filas_por_codigo.setdefault(cod, []).append(fila_catalogo)
            if cod in primera_aparicion:
                continue

            primera_aparicion.add(cod)
            self.productos_base.append(
                (fila_catalogo, cod, nombre_catalogo, stock_num)
            )
            self.catalogo[cod] = (fila_catalogo, nombre_catalogo, stock_num)

    def listar_productos(self) -> List[sqlite3.Row]:
        """Devuelve todos los productos para la pantalla de administración."""
        return self.product_store.list_products()

    def actualizar_producto(
        self, codigo_actual: str, codigo_nuevo: str, nombre: str, stock: int
    ) -> None:
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
            libro = openpyxl.load_workbook(str(self.ruta_excel_base))
            try:
                hoja = (
                    libro[self.nombre_hoja]
                    if self.nombre_hoja in libro.sheetnames
                    else libro.active
                )
                if hoja is None:
                    raise ValueError("No se encontró una hoja para actualizar.")

                filas_producto = [
                    fila
                    for fila in range(self._fila_inicio_datos, hoja.max_row + 1)
                    if normalizar_codigo(
                        str(hoja.cell(fila, self._col_codigo).value or "")
                    )
                    == codigo_actual
                ]
                filas_catalogo_producto = [
                    producto
                    for producto in self.product_store.list_catalog_rows(
                        include_inactive=True
                    )
                    if str(producto["code"]) == codigo_actual
                ]
                if not filas_producto or len(filas_producto) != len(
                    filas_catalogo_producto
                ):
                    raise RuntimeError(
                        f"Las filas de '{codigo_actual}' en Productos.xlsx "
                        "no coinciden con el catálogo."
                    )

                codigo_excel = (
                    int(codigo_nuevo)
                    if codigo_nuevo.isdigit()
                    else codigo_nuevo
                )
                for fila in filas_producto:
                    hoja.cell(fila, self._col_codigo, codigo_excel)
                    hoja.cell(fila, self._col_nombre, nombre)
                    if self._col_stock_final is not None:
                        columna_inicial = self._col_stock_inicial or self._col_stock
                        hoja.cell(fila, columna_inicial, stock)
                        if self._col_descuento is not None:
                            hoja.cell(fila, self._col_descuento, None)
                        hoja.cell(fila, self._col_stock_final, stock)
                    else:
                        hoja.cell(fila, self._col_stock, stock)

                with tempfile.NamedTemporaryFile(
                    suffix=self.ruta_excel_base.suffix,
                    dir=self.ruta_excel_base.parent,
                    delete=False,
                ) as temporal:
                    ruta_temporal = Path(temporal.name)
                try:
                    libro.save(ruta_temporal)
                finally:
                    libro.close()
                try:
                    os.replace(ruta_temporal, self.ruta_excel_base)
                    plantilla_actualizada = True
                finally:
                    if ruta_temporal.exists():
                        ruta_temporal.unlink()

            except Exception:
                libro.close()
                raise

            libro_verificacion = openpyxl.load_workbook(
                str(self.ruta_excel_base), data_only=True, read_only=True
            )
            try:
                hoja_verificacion = (
                    libro_verificacion[self.nombre_hoja]
                    if self.nombre_hoja in libro_verificacion.sheetnames
                    else libro_verificacion.active
                )
                if hoja_verificacion is None:
                    raise ValueError(
                        "No se pudo verificar la plantilla después de la edición."
                    )
                return [
                    fila
                    for fila in range(
                        self._fila_inicio_datos,
                        hoja_verificacion.max_row + 1,
                    )
                    if hoja_verificacion.cell(
                        fila, self._col_codigo
                    ).value is not None
                    and str(
                        hoja_verificacion.cell(fila, self._col_nombre).value or ""
                    ).strip()
                ]
            finally:
                libro_verificacion.close()

        def restaurar_plantilla() -> None:
            if not plantilla_actualizada:
                return
            with tempfile.NamedTemporaryFile(
                suffix=self.ruta_excel_base.suffix,
                dir=self.ruta_excel_base.parent,
                delete=False,
            ) as temporal:
                temporal.write(contenido_original)
                ruta_temporal = Path(temporal.name)
            try:
                os.replace(ruta_temporal, self.ruta_excel_base)
            finally:
                if ruta_temporal.exists():
                    ruta_temporal.unlink()

        self.product_store.update_product(
            old_code=codigo_actual,
            new_code=codigo_nuevo,
            name=nombre,
            stock=stock,
            synchronize_template=sincronizar_plantilla,
            restore_template=restaurar_plantilla,
        )
        self._cargar_catalogo()

    def cambiar_estado_producto(self, codigo: str, activo: bool) -> None:
        self.product_store.set_product_active(normalizar_codigo(codigo), activo)
        self._cargar_catalogo()

    def agregar_producto_en_posicion(
        self,
        codigo_nuevo: str,
        nombre_nuevo: str,
        codigo_arriba: str,
        stock_inicial: Optional[int] = None
    ) -> Tuple[bool, str, Optional[int]]:
        """
        Inserta un nuevo producto en SQLite inmediatamente debajo del código
        indicado por codigo_arriba, conservando el orden del catálogo.

        Retorna: (exito: bool, mensaje: str, fila_insertada: Optional[int])
        """
        cod_nuevo_norm = normalizar_codigo(codigo_nuevo)
        cod_arriba_norm = normalizar_codigo(codigo_arriba)

        # 1. Validar que el nuevo código no exista ya
        if cod_nuevo_norm in self.catalogo:
            fila_exist, nombre_exist, _ = self.catalogo[cod_nuevo_norm]
            return False, f"El codigo '{cod_nuevo_norm}' ya existe en la fila {fila_exist} ('{nombre_exist}').", None

        # 2. Localizar la fila del producto superior de referencia
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
            libro = openpyxl.load_workbook(str(self.ruta_excel_base))
            try:
                hoja = (
                    libro[self.nombre_hoja]
                    if self.nombre_hoja in libro.sheetnames
                    else libro.active
                )
                if hoja is None:
                    raise ValueError("No se encontró una hoja para actualizar.")
                fila_referencia = next(
                    (
                        fila
                        for fila in range(
                            self._fila_inicio_datos, hoja.max_row + 1
                        )
                        if normalizar_codigo(
                            str(
                                hoja.cell(fila, self._col_codigo).value or ""
                            )
                        )
                        == cod_arriba_norm
                    ),
                    None,
                )
                if fila_referencia is None:
                    raise ValueError(
                        f"No se encontró el código de referencia "
                        f"'{cod_arriba_norm}' en Productos.xlsx."
                    )

                fila_nueva = fila_referencia + 1
                hoja.insert_rows(fila_nueva, 1)
                for columna in range(1, hoja.max_column + 1):
                    origen = hoja.cell(fila_referencia, columna)
                    destino = hoja.cell(fila_nueva, columna)
                    if origen.has_style:
                        destino._style = copy(origen._style)
                    if origen.number_format:
                        destino.number_format = origen.number_format
                hoja.row_dimensions[fila_nueva].height = (
                    hoja.row_dimensions[fila_referencia].height
                )

                codigo_excel = (
                    int(cod_nuevo_norm)
                    if cod_nuevo_norm.isdigit()
                    else cod_nuevo_norm
                )
                hoja.cell(fila_nueva, self._col_codigo, codigo_excel)
                hoja.cell(
                    fila_nueva,
                    self._col_nombre,
                    str(nombre_nuevo).strip(),
                )
                stock = stock_inicial or 0
                if self._col_stock_final is not None:
                    columna_inicial = self._col_stock_inicial or self._col_stock
                    hoja.cell(fila_nueva, columna_inicial, stock)
                    if self._col_descuento is not None:
                        hoja.cell(fila_nueva, self._col_descuento, None)
                    hoja.cell(fila_nueva, self._col_stock_final, stock)
                else:
                    hoja.cell(fila_nueva, self._col_stock, stock)

                with tempfile.NamedTemporaryFile(
                    suffix=self.ruta_excel_base.suffix,
                    dir=self.ruta_excel_base.parent,
                    delete=False,
                ) as temporal:
                    ruta_temporal = Path(temporal.name)
                try:
                    libro.save(ruta_temporal)
                finally:
                    libro.close()
                try:
                    os.replace(ruta_temporal, self.ruta_excel_base)
                    plantilla_actualizada = True
                finally:
                    if ruta_temporal.exists():
                        ruta_temporal.unlink()
            except Exception:
                libro.close()
                raise

            libro_verificacion = openpyxl.load_workbook(
                str(self.ruta_excel_base), data_only=True, read_only=True
            )
            try:
                hoja_verificacion = (
                    libro_verificacion[self.nombre_hoja]
                    if self.nombre_hoja in libro_verificacion.sheetnames
                    else libro_verificacion.active
                )
                if hoja_verificacion is None:
                    raise ValueError(
                        "No se pudo verificar la plantilla después del alta."
                    )
                filas_plantilla = [
                    fila
                    for fila in range(
                        self._fila_inicio_datos,
                        hoja_verificacion.max_row + 1,
                    )
                    if hoja_verificacion.cell(
                        fila, self._col_codigo
                    ).value is not None
                    and str(
                        hoja_verificacion.cell(
                            fila, self._col_nombre
                        ).value
                        or ""
                    ).strip()
                ]
                if (
                    orden >= len(filas_plantilla)
                    or filas_plantilla[orden] != fila_nueva
                ):
                    raise RuntimeError(
                        "El orden insertado en Productos.xlsx no coincide "
                        "con el orden de SQLite."
                    )
                return filas_plantilla
            finally:
                libro_verificacion.close()

        def restaurar_plantilla() -> None:
            if not plantilla_actualizada:
                return
            with tempfile.NamedTemporaryFile(
                suffix=self.ruta_excel_base.suffix,
                dir=self.ruta_excel_base.parent,
                delete=False,
            ) as temporal:
                temporal.write(contenido_original)
                ruta_temporal = Path(temporal.name)
            try:
                os.replace(ruta_temporal, self.ruta_excel_base)
            finally:
                if ruta_temporal.exists():
                    ruta_temporal.unlink()

        try:
            orden, nombre_arriba = self.product_store.add_product_after(
                code=cod_nuevo_norm,
                name=str(nombre_nuevo).strip(),
                reference_code=cod_arriba_norm,
                stock=stock_inicial or 0,
                synchronize_template=sincronizar_plantilla,
                restore_template=restaurar_plantilla,
            )
        except (ValueError, OSError, RuntimeError) as error:
            return False, str(error), None

        self._cargar_catalogo()

        fila_nueva = orden + self._fila_inicio_datos
        return True, (
            f"Producto '{nombre_nuevo}' [{cod_nuevo_norm}] insertado en la "
            f"posición {fila_nueva} del catálogo (debajo de [{cod_arriba_norm}] "
            f"{nombre_arriba})."
        ), fila_nueva

    def aplicar_descuentos(
        self,
        items_consolidados: Dict[str, ItemConsolidado],
        carpeta_destino: str | Path,
        pedidos_procesados: Optional[List[ResultadoRemito]] = None,
        guardar_archivo: bool = True
    ) -> ReporteStock:
        """Genera un informe con el diseño del catálogo, sin modificarlo."""
        carpeta_destino = Path(carpeta_destino)
        fecha_generacion = datetime.now()
        fecha_hora_str = fecha_generacion.strftime("%d-%m-%Y_%H-%M-%S")
        nombre_archivo = f"Descuento{fecha_hora_str}.xls"
        ruta_guardado = carpeta_destino / nombre_archivo
        ruta_pdf = ruta_guardado.with_suffix(".pdf")

        descuentos: List[RegistroDescuento] = []
        for _, cod, nombre, stock_ant in self.productos_base:
            item = items_consolidados.get(cod)
            if item is None:
                continue
            descuentos.append(RegistroDescuento(
                codigo=cod,
                nombre_producto=nombre,
                fila_excel=4 + len(descuentos),
                stock_anterior=stock_ant,
                cantidad_descontada=item.cantidad_total,
                stock_nuevo=int(stock_ant - item.cantidad_total),
            ))

        filas_productos = []
        for fila_original, cod, nombre, _ in self.filas_catalogo:
            item = items_consolidados.get(cod)
            filas_productos.append((
                fila_original,
                cod,
                item.cantidad_total if item else None,
                nombre,
                -item.cantidad_total if item else None,
            ))

        codigos_descontados = {registro.codigo for registro in descuentos}
        pedidos_descontados = [
            documento
            for documento in (pedidos_procesados or [])
            if any(
                normalizar_codigo(item.codigo) in codigos_descontados
                for item in documento.items
            )
        ]
        productos_sin_coincidencia = [
            (
                cod,
                ", ".join(item.remitos_origen),
                item.descripcion,
                "Código no encontrado en el catálogo SQLite",
            )
            for cod, item in items_consolidados.items()
            if cod not in self.catalogo
        ]
        productos_sin_coincidencia.extend(
            (
                "",
                documento.archivo,
                descripcion,
                motivo,
            )
            for documento in (pedidos_procesados or [])
            for descripcion, motivo in documento.descripciones_sin_coincidencia
        )

        wb_salida, ws_salida = self._crear_informe_desde_plantilla(
            len(descuentos),
            sum(descuento.cantidad_descontada for descuento in descuentos),
            fecha_generacion.strftime("%d/%m/%y"),
            filas_productos,
            pedidos_descontados,
            productos_sin_coincidencia,
        )

        if guardar_archivo:
            carpeta_destino.mkdir(parents=True, exist_ok=True)
            self._guardar_informe_xls(wb_salida, ruta_guardado)
            self._guardar_informe_pdf(wb_salida, ruta_pdf)
            archivo_final = str(ruta_guardado)
            archivo_pdf = str(ruta_pdf)
        else:
            archivo_final = f"[SIMULACIÓN - NO GUARDADO] {ruta_guardado.name}"
            archivo_pdf = None

        return ReporteStock(
            descuentos_aplicados=descuentos,
            archivo_guardado=archivo_final,
            archivo_pdf=archivo_pdf,
        )

    def _crear_informe_desde_plantilla(
        self,
        cantidad_descuentos: int,
        unidades_descontadas: int,
        fecha_generacion: str,
        filas_productos: List[Tuple[int, str, Optional[int], str, Optional[int]]],
        pedidos_descontados: List[ResultadoRemito],
        productos_sin_coincidencia: List[Tuple[str, str, str, str]],
    ):
        libro_plantilla = openpyxl.load_workbook(self.ruta_excel_base)
        hoja_plantilla = (
            libro_plantilla[self.nombre_hoja]
            if self.nombre_hoja in libro_plantilla.sheetnames
            else libro_plantilla.active
        )
        libro_salida = openpyxl.Workbook()
        hoja_salida = libro_salida.active
        hoja_salida.title = hoja_plantilla.title[:31]
        hoja_salida.sheet_view.showGridLines = hoja_plantilla.sheet_view.showGridLines
        hoja_salida.page_setup.orientation = "portrait"
        hoja_salida.page_setup.paperSize = hoja_salida.PAPERSIZE_A4
        hoja_salida.page_setup.fitToWidth = 1
        hoja_salida.page_setup.fitToHeight = 0
        hoja_salida.sheet_properties.pageSetUpPr.fitToPage = True
        margen_cm = 2 / 2.54
        hoja_salida.page_margins.left = margen_cm
        hoja_salida.page_margins.right = margen_cm
        hoja_salida.page_margins.top = margen_cm
        hoja_salida.page_margins.bottom = margen_cm
        hoja_salida.freeze_panes = "A4"

        def copiar_estilo(origen, destino) -> None:
            if not origen.has_style:
                return
            destino.font = copy(origen.font)
            destino.fill = copy(origen.fill)
            destino.border = copy(origen.border)
            destino.alignment = copy(origen.alignment)
            destino.number_format = origen.number_format
            destino.protection = copy(origen.protection)

        def aplicar_encabezado(
            fila: int, color_fondo: str, cantidad_columnas: int = 4
        ) -> None:
            for columna in range(1, cantidad_columnas + 1):
                celda = hoja_salida.cell(fila, columna)
                celda.fill = PatternFill("solid", fgColor=color_fondo)
                celda.font = Font(
                    name="Arial",
                    size=9,
                    bold=True,
                    color="17365D",
                )
                celda.alignment = Alignment(
                    horizontal="center",
                    vertical="center",
                    wrap_text=True,
                )
                celda.border = Border(
                    bottom=Side(style="thin", color="D9E2F3")
                )

        def aplicar_titulo_seccion(fila: int, color_fondo: str) -> None:
            celda = hoja_salida.cell(fila, 1)
            celda.fill = PatternFill("solid", fgColor=color_fondo)
            celda.font = Font(name="Arial", size=11, bold=True, color="17365D")
            celda.alignment = Alignment(vertical="center", wrap_text=True)
        columnas_plantilla = (
            self._col_codigo,
            self._col_nombre,
            self._col_descuento or self._col_stock,
        )
        for columna_salida, columna_plantilla in enumerate(
            columnas_plantilla, start=1
        ):
            letra_salida = openpyxl.utils.get_column_letter(columna_salida)
            letra_plantilla = openpyxl.utils.get_column_letter(columna_plantilla)
            dimension = hoja_plantilla.column_dimensions[letra_plantilla]
            ancho = dimension.width
            if columna_salida == 3:
                ancho = max(ancho or 0, 22)
            hoja_salida.column_dimensions[letra_salida].width = ancho
            hoja_salida.column_dimensions[letra_salida].hidden = dimension.hidden

        for fila in range(1, 4):
            hoja_salida.row_dimensions[fila].height = (
                hoja_plantilla.row_dimensions[fila].height
            )
            for columna_salida, columna_plantilla in enumerate(
                columnas_plantilla, start=1
            ):
                origen = hoja_plantilla.cell(fila, columna_plantilla)
                destino = hoja_salida.cell(fila, columna_salida)
                copiar_estilo(origen, destino)

        for encabezado in ("A1:A2", "B1:B2", "C1:D2"):
            hoja_salida.merge_cells(encabezado)
        hoja_salida["A1"] = (
            hoja_plantilla.cell(1, self._col_codigo).value or "CODIGO"
        )
        hoja_salida["B1"] = (
            hoja_plantilla.cell(1, self._col_nombre).value or "PRODUCTOS"
        )
        hoja_salida["C1"] = f"FECHA: {fecha_generacion}"
        aplicar_encabezado(1, "D9EAF7", 3)
        hoja_salida["D1"].fill = PatternFill("solid", fgColor="D9EAF7")
        hoja_salida["D1"].border = Border(
            bottom=Side(style="thin", color="D9E2F3")
        )

        encabezado_productos = hoja_plantilla.cell(3, self._col_nombre).value
        hoja_salida["B3"] = (
            encabezado_productos
            if self._col_stock_inicial is not None and encabezado_productos
            else "PRODUCTOS"
        )
        hoja_salida["C3"] = "DESCUENTO"
        hoja_salida["C3"].number_format = "@"
        aplicar_encabezado(3, "D9EAF7", 3)
        hoja_salida.row_dimensions[1].height = 48
        hoja_salida.row_dimensions[2].height = 10
        hoja_salida.row_dimensions[3].height = 24

        fila_estilo_producto = min(
            max(self._fila_inicio_datos, 1),
            max(hoja_plantilla.max_row, 1),
        )
        for fila_salida, producto in enumerate(filas_productos, start=4):
            fila_original, codigo, unidades, nombre, descuento = producto
            fila_estilo = (
                fila_original
                if 0 < fila_original <= hoja_plantilla.max_row
                else fila_estilo_producto
            )
            hoja_salida.row_dimensions[fila_salida].height = (
                hoja_plantilla.row_dimensions[fila_estilo].height
            )
            for columna_salida, columna_plantilla in enumerate(
                columnas_plantilla, start=1
            ):
                origen = hoja_plantilla.cell(fila_estilo, columna_plantilla)
                destino = hoja_salida.cell(fila_salida, columna_salida)
                copiar_estilo(origen, destino)
            codigo_salida = int(codigo) if codigo.isdigit() else codigo
            hoja_salida.cell(fila_salida, 1, codigo_salida)
            hoja_salida.cell(fila_salida, 2, nombre)
            if descuento is not None:
                hoja_salida.cell(fila_salida, 3, descuento).number_format = "0"

        fila_actual = 4 + len(filas_productos)
        hoja_salida.cell(fila_actual, 2, "TOTAL CÓDIGOS DE PRODUCTO DESCONTADOS:")
        hoja_salida.cell(fila_actual, 3, cantidad_descuentos)
        self._copiar_estilo_fila(
            hoja_plantilla, hoja_salida, 3, fila_actual, 3
        )
        for columna in range(1, 4):
            celda = hoja_salida.cell(fila_actual, columna)
            celda.fill = PatternFill("solid", fgColor="D9EAF7")
            celda.font = Font(name="Arial", size=10, bold=True, color="17365D")
            celda.alignment = Alignment(vertical="center", wrap_text=True)
        fila_actual += 1
        hoja_salida.cell(fila_actual, 2, "TOTAL UNIDADES DESCONTADAS:")
        hoja_salida.cell(fila_actual, 3, unidades_descontadas)
        self._copiar_estilo_fila(
            hoja_plantilla, hoja_salida, 3, fila_actual, 3
        )
        for columna in range(1, 4):
            celda = hoja_salida.cell(fila_actual, columna)
            celda.fill = PatternFill("solid", fgColor="D9EAF7")
            celda.font = Font(name="Arial", size=10, bold=True, color="17365D")
            celda.alignment = Alignment(vertical="center", wrap_text=True)
        fila_actual += 1
        hoja_salida.merge_cells(
            start_row=fila_actual,
            start_column=1,
            end_row=fila_actual,
            end_column=4,
        )
        hoja_salida.cell(fila_actual, 1, "PEDIDOS CON PRODUCTOS DESCONTADOS")
        self._copiar_estilo_fila(
            hoja_plantilla, hoja_salida, 3, fila_actual, 4
        )
        aplicar_titulo_seccion(fila_actual, "EAF0F6")
        fila_actual += 1
        for columna, titulo in enumerate(
            ("TIPO", "CLIENTE", "N° REMITO / PEDIDO"), start=1
        ):
            hoja_salida.cell(fila_actual, columna, titulo)
        self._copiar_estilo_fila(
            hoja_plantilla, hoja_salida, 3, fila_actual, 4
        )
        aplicar_encabezado(fila_actual, "D9EAF7")
        if pedidos_descontados:
            for documento in pedidos_descontados:
                fila_actual += 1
                if documento.archivo.lower().endswith(".pdf"):
                    tipo = "Remito Mayorista"
                elif documento.archivo.lower().endswith(".docx"):
                    tipo = "Mercado Libre"
                else:
                    tipo = "Canje"
                for columna, valor in enumerate(
                    (tipo, documento.cliente, str(documento.numero_remito)),
                    start=1,
                ):
                    hoja_salida.cell(fila_actual, columna, valor)
                self._copiar_estilo_fila(
                    hoja_plantilla, hoja_salida, fila_estilo_producto,
                    fila_actual, 4,
                )
        else:
            fila_actual += 1
            hoja_salida.merge_cells(
                start_row=fila_actual,
                start_column=1,
                end_row=fila_actual,
                end_column=4,
            )
            hoja_salida.cell(fila_actual, 1, "No hubo pedidos con productos descontados.")
            self._copiar_estilo_fila(
                hoja_plantilla, hoja_salida, fila_estilo_producto,
                fila_actual, 4,
            )
        fila_actual += 1

        if productos_sin_coincidencia:
            hoja_salida.merge_cells(
                start_row=fila_actual,
                start_column=1,
                end_row=fila_actual,
                end_column=4,
            )
            hoja_salida.cell(
                fila_actual,
                1,
                "PRODUCTOS NO DESCONTADOS - SIN COINCIDENCIA",
            )
            self._copiar_estilo_fila(
                hoja_plantilla, hoja_salida, 3, fila_actual, 4
            )
            aplicar_titulo_seccion(fila_actual, "FCE4D6")
            fila_actual += 1
            for columna, titulo in enumerate(
                ("CÓDIGO", "ARCHIVO / PEDIDO", "PRODUCTO / DESCRIPCIÓN", "MOTIVO"),
                start=1,
            ):
                hoja_salida.cell(fila_actual, columna, titulo)
            self._copiar_estilo_fila(
                hoja_plantilla, hoja_salida, 3, fila_actual, 4
            )
            aplicar_encabezado(fila_actual, "D9EAF7")
            for codigo, archivo, descripcion, motivo in productos_sin_coincidencia:
                fila_actual += 1
                hoja_salida.cell(fila_actual, 1, codigo)
                hoja_salida.cell(fila_actual, 2, archivo)
                hoja_salida.cell(fila_actual, 3, descripcion)
                hoja_salida.cell(fila_actual, 4, motivo)
                self._copiar_estilo_fila(
                    hoja_plantilla, hoja_salida, fila_estilo_producto,
                    fila_actual, 4,
                )

        libro_plantilla.close()
        hoja_salida.print_area = f"A1:D{max(3, fila_actual)}"
        return libro_salida, hoja_salida

    def _copiar_estilo_fila(
        self,
        hoja_plantilla,
        hoja_salida,
        fila_plantilla: int,
        fila_salida: int,
        cantidad_columnas: int,
    ) -> None:
        hoja_salida.row_dimensions[fila_salida].height = (
            hoja_plantilla.row_dimensions[fila_plantilla].height
        )
        columnas_plantilla = (
            self._col_codigo,
            self._col_nombre,
            self._col_descuento or self._col_stock,
            self._col_stock_final or self._col_stock,
        )
        for columna in range(1, cantidad_columnas + 1):
            origen = hoja_plantilla.cell(
                fila_plantilla, columnas_plantilla[columna - 1]
            )
            destino = hoja_salida.cell(fila_salida, columna)
            if origen.has_style:
                destino.font = copy(origen.font)
                destino.fill = copy(origen.fill)
                destino.border = copy(origen.border)
                destino.alignment = copy(origen.alignment)
                destino.number_format = origen.number_format
                destino.protection = copy(origen.protection)

    @staticmethod
    def _guardar_informe_xls(libro: openpyxl.Workbook, ruta: Path) -> None:
        hoja_origen = libro.active
        if hoja_origen.max_row > 65_536:
            raise ValueError(
                "El informe supera el límite de 65.536 filas del formato XLS."
            )

        libro_xls = xlwt.Workbook(encoding="utf-8")
        hoja_xls = libro_xls.add_sheet(hoja_origen.title[:31])
        colores = {
            "17365D": 0x21,
            "1F4E78": 0x22,
            "D9EAF7": 0x23,
            "F3F7FB": 0x24,
            "D6DEE8": 0x25,
            "5B6573": 0x26,
            "E2F0D9": 0x27,
            "FCE4D6": 0x28,
            "9C0006": 0x29,
            "263445": 0x2A,
            "EAF0F6": 0x2B,
            "7F8995": 0x2C,
        }
        rgb_por_indice = {
            0x21: (23, 54, 93),
            0x22: (31, 78, 120),
            0x23: (217, 234, 247),
            0x24: (243, 247, 251),
            0x25: (214, 222, 232),
            0x26: (91, 101, 115),
            0x27: (226, 240, 217),
            0x28: (252, 228, 214),
            0x29: (156, 0, 6),
            0x2A: (38, 52, 69),
            0x2B: (234, 240, 246),
            0x2C: (127, 137, 149),
        }
        for indice, rgb in rgb_por_indice.items():
            libro_xls.set_colour_RGB(indice, *rgb)

        siguiente_color = 0x2D
        for fila in hoja_origen.iter_rows():
            for celda in fila:
                colores_celda = (
                    celda.font.color,
                    celda.fill.fgColor,
                    celda.fill.bgColor,
                    *(
                        getattr(getattr(celda.border, lado), "color", None)
                        for lado in ("left", "right", "top", "bottom")
                    ),
                )
                for color in colores_celda:
                    if color is None or color.type != "rgb" or not color.rgb:
                        continue
                    codigo_rgb = str(color.rgb)[-6:].upper()
                    if codigo_rgb in colores:
                        continue
                    if siguiente_color > 0x3F:
                        break
                    colores[codigo_rgb] = siguiente_color
                    rgb = tuple(
                        int(codigo_rgb[indice:indice + 2], 16)
                        for indice in (0, 2, 4)
                    )
                    rgb_por_indice[siguiente_color] = rgb
                    libro_xls.set_colour_RGB(siguiente_color, *rgb)
                    siguiente_color += 1

        colores_borde = {
            "hair": xlwt.Borders.HAIR,
            "thin": xlwt.Borders.THIN,
            "medium": xlwt.Borders.MEDIUM,
            "dashed": xlwt.Borders.DASHED,
            "dotted": xlwt.Borders.DOTTED,
            "thick": xlwt.Borders.THICK,
        }
        horizontal = {
            "left": xlwt.Alignment.HORZ_LEFT,
            "center": xlwt.Alignment.HORZ_CENTER,
            "right": xlwt.Alignment.HORZ_RIGHT,
        }
        vertical = {
            "top": xlwt.Alignment.VERT_TOP,
            "center": xlwt.Alignment.VERT_CENTER,
            "bottom": xlwt.Alignment.VERT_BOTTOM,
        }
        estilos: Dict[int, xlwt.XFStyle] = {}

        def color_index(color) -> Optional[int]:
            if color is None or color.type != "rgb" or not color.rgb:
                return None
            return colores.get(str(color.rgb)[-6:].upper())

        def estilo_para(celda) -> xlwt.XFStyle:
            estilo = estilos.get(celda.style_id)
            if estilo is not None:
                return estilo

            estilo = xlwt.XFStyle()
            fuente = xlwt.Font()
            fuente.name = celda.font.name or "Arial"
            fuente.height = int((celda.font.sz or 10) * 20)
            fuente.bold = bool(celda.font.bold)
            fuente.italic = bool(celda.font.italic)
            fuente.struck_out = bool(celda.font.strike)
            if celda.font.underline:
                fuente.underline = xlwt.Font.UNDERLINE_SINGLE
            indice_color = color_index(celda.font.color)
            if indice_color is not None:
                fuente.colour_index = indice_color
            estilo.font = fuente

            alineacion = xlwt.Alignment()
            alineacion.horz = horizontal.get(celda.alignment.horizontal, xlwt.Alignment.HORZ_GENERAL)
            alineacion.vert = vertical.get(celda.alignment.vertical, xlwt.Alignment.VERT_BOTTOM)
            alineacion.wrap = bool(celda.alignment.wrap_text)
            alineacion.shrink_to_fit = bool(celda.alignment.shrink_to_fit)
            estilo.alignment = alineacion

            bordes = xlwt.Borders()
            for nombre in ("left", "right", "top", "bottom"):
                borde = getattr(celda.border, nombre)
                setattr(
                    bordes,
                    nombre,
                    colores_borde.get(
                        getattr(borde, "style", None),
                        xlwt.Borders.NO_LINE,
                    ),
                )
                indice_color = color_index(getattr(borde, "color", None))
                if indice_color is not None:
                    setattr(bordes, f"{nombre}_colour", indice_color)
            estilo.borders = bordes

            patron = xlwt.Pattern()
            if celda.fill.fill_type == "solid":
                patron.pattern = xlwt.Pattern.SOLID_PATTERN
                indice_color = color_index(celda.fill.fgColor)
                rgb_relleno = rgb_por_indice.get(indice_color)
                luminancia = (
                    sum(
                        peso * canal
                        for peso, canal in zip(
                            (0.2126, 0.7152, 0.0722),
                            rgb_relleno,
                        )
                    )
                    if rgb_relleno
                    else 255
                )
                patron.pattern_fore_colour = (
                    indice_color
                    if indice_color is not None and luminancia >= 190
                    else 9
                )
            estilo.pattern = patron
            estilo.num_format_str = celda.number_format or "General"
            estilos[celda.style_id] = estilo
            return estilo

        for columna in range(1, hoja_origen.max_column + 1):
            dimension = hoja_origen.column_dimensions[
                openpyxl.utils.get_column_letter(columna)
            ]
            ancho = dimension.width
            if ancho:
                hoja_xls.col(columna - 1).width = min(int(ancho * 256), 65_535)
            hoja_xls.col(columna - 1).hidden = dimension.hidden

        rangos_combinados = {}
        celdas_combinadas = set()
        for rango in hoja_origen.merged_cells.ranges:
            min_col, min_row, max_col, max_row = rango.bounds
            rangos_combinados[(min_row, min_col)] = (
                min_row - 1,
                max_row - 1,
                min_col - 1,
                max_col - 1,
            )
            for fila in range(min_row, max_row + 1):
                for columna in range(min_col, max_col + 1):
                    if (fila, columna) != (min_row, min_col):
                        celdas_combinadas.add((fila, columna))

        for fila in hoja_origen.iter_rows():
            for celda in fila:
                if (celda.row, celda.column) in celdas_combinadas:
                    continue
                estilo = estilo_para(celda)
                valor = celda.value if celda.value is not None else ""
                rango = rangos_combinados.get((celda.row, celda.column))
                if rango:
                    hoja_xls.write_merge(*rango, valor, estilo)
                else:
                    hoja_xls.write(celda.row - 1, celda.column - 1, valor, estilo)

        for fila, dimension in hoja_origen.row_dimensions.items():
            if dimension.height is not None:
                hoja_xls.row(fila - 1).height = int(dimension.height * 20)

        hoja_xls.portrait = hoja_origen.page_setup.orientation == "portrait"
        hoja_xls.paper_size_code = int(hoja_origen.page_setup.paperSize)
        hoja_xls.left_margin = hoja_origen.page_margins.left
        hoja_xls.right_margin = hoja_origen.page_margins.right
        hoja_xls.top_margin = hoja_origen.page_margins.top
        hoja_xls.bottom_margin = hoja_origen.page_margins.bottom
        hoja_xls.fit_width_to_pages = hoja_origen.page_setup.fitToWidth
        hoja_xls.fit_height_to_pages = hoja_origen.page_setup.fitToHeight
        if hoja_origen.freeze_panes:
            fila_inmovilizada, columna_inmovilizada = (
                openpyxl.utils.cell.coordinate_to_tuple(hoja_origen.freeze_panes)
            )
            if fila_inmovilizada > 1 or columna_inmovilizada > 1:
                hoja_xls.set_panes_frozen(True)
                if fila_inmovilizada > 1:
                    hoja_xls.set_horz_split_pos(fila_inmovilizada - 1)
                if columna_inmovilizada > 1:
                    hoja_xls.set_vert_split_pos(columna_inmovilizada - 1)

        libro_xls.save(str(ruta))

    @staticmethod
    def _guardar_informe_pdf(libro: openpyxl.Workbook, ruta: Path) -> None:
        hoja = libro.active
        if hoja is None:
            raise ValueError("El informe no contiene una hoja activa para exportar.")

        def color_excel(color) -> colors.Color | None:
            if color is None or color.type != "rgb" or not color.rgb:
                return None
            codigo = str(color.rgb)[-6:]
            try:
                return colors.HexColor(f"#{codigo}")
            except ValueError:
                return None

        def formatear_valor(celda) -> str:
            val = celda.value
            if val is None:
                return ""
            if isinstance(val, float) and val.is_integer():
                val = int(val)
            res = escape(str(val))
            return res.replace("\n", "<br/>")

        ancho_util = A4[0] - 4 * cm  # Exactamente 481.8898 pt

        # Detectar si la hoja tiene las secciones estándar del reporte
        fila_inicio_pedidos = None
        fila_inicio_no_descontados = None

        for num_f in range(1, hoja.max_row + 1):
            val_a = str(hoja.cell(num_f, 1).value or "").strip().upper()
            if "PEDIDOS CON PRODUCTOS DESCONTADOS" in val_a and fila_inicio_pedidos is None:
                fila_inicio_pedidos = num_f
            elif "PRODUCTOS NO DESCONTADOS" in val_a and fila_inicio_no_descontados is None:
                fila_inicio_no_descontados = num_f

        tiene_secciones = (fila_inicio_pedidos is not None) or (fila_inicio_no_descontados is not None)

        def pie_pagina(canvas, documento) -> None:
            canvas.saveState()
            canvas.setFont("Helvetica", 8)
            canvas.setFillColor(colors.HexColor("#5B6573"))
            canvas.setStrokeColor(colors.HexColor("#D6DEE8"))
            canvas.setLineWidth(0.4)
            canvas.line(2 * cm, 1.8 * cm + 6, A4[0] - 2 * cm, 1.8 * cm + 6)
            canvas.drawString(
                2 * cm,
                1.8 * cm - 6,
                "StockAgent · Informe de Control de Stock",
            )
            canvas.drawRightString(
                A4[0] - 2 * cm,
                1.8 * cm - 6,
                f"Página {documento.page}",
            )
            canvas.restoreState()

        elementos = []

        if tiene_secciones:
            # 1. TABLA PRINCIPAL: CATÁLOGO Y DESCUENTOS (3 Columnas)
            fin_catalogo = (
                fila_inicio_pedidos
                if fila_inicio_pedidos is not None
                else (
                    fila_inicio_no_descontados
                    if fila_inicio_no_descontados is not None
                    else (hoja.max_row + 1)
                )
            )

            # Anchos perfectamente calibrados para hoja A4 (Suma = 481.89 pt)
            col_widths_cat = [68, 348.89, 65]

            contenido_cat = []
            estilos_cat = [
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 1.8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1.8),
            ]

            for num_f in range(1, fin_catalogo):
                fila_celdas = []
                es_encabezado_principal = num_f in (1, 2)
                es_encabezado_secundario = num_f == 3
                es_total = False

                val_b = str(hoja.cell(num_f, 2).value or "").upper()
                if (
                    "TOTAL CÓDIGOS" in val_b
                    or "TOTAL UNIDADES" in val_b
                    or "TOTAL CODIGOS" in val_b
                ):
                    es_total = True

                for col_idx in (1, 2, 3):
                    celda = hoja.cell(num_f, col_idx)
                    texto_html = formatear_valor(celda)

                    if es_encabezado_principal:
                        tam_fuente = 8.5
                        leading = 10
                        es_negrita = True
                        color_texto = colors.HexColor("#17365D")
                        align = 1  # CENTER
                    elif es_encabezado_secundario:
                        tam_fuente = 8.5
                        leading = 10
                        es_negrita = True
                        color_texto = colors.HexColor("#17365D")
                        align = 1 if col_idx != 2 else 0
                    elif es_total:
                        tam_fuente = 8.5
                        leading = 10
                        es_negrita = True
                        color_texto = colors.HexColor("#17365D")
                        align = 1 if col_idx == 3 else 0
                    else:
                        tam_fuente = 8
                        leading = 9.5
                        es_negrita = col_idx == 3 and texto_html != ""
                        color_texto = (
                            colors.HexColor("#C00000")
                            if (col_idx == 3 and "-" in texto_html)
                            else (
                                color_excel(celda.font.color)
                                or colors.HexColor("#263445")
                            )
                        )
                        align = 1 if col_idx in (1, 3) else 0

                    p_style = ParagraphStyle(
                        name=f"cat_{num_f}_{col_idx}",
                        fontName="Helvetica-Bold" if es_negrita else "Helvetica",
                        fontSize=tam_fuente,
                        leading=leading,
                        alignment=align,
                        textColor=color_texto,
                        splitLongWords=True,
                    )
                    fila_celdas.append(Paragraph(texto_html, p_style))

                    if celda.fill.fill_type == "solid":
                        cf = color_excel(celda.fill.fgColor)
                        if cf is not None:
                            estilos_cat.append(
                                (
                                    "BACKGROUND",
                                    (col_idx - 1, num_f - 1),
                                    (col_idx - 1, num_f - 1),
                                    cf,
                                )
                            )

                    estilos_cat.append(
                        (
                            "GRID",
                            (0, num_f - 1),
                            (-1, num_f - 1),
                            0.35,
                            colors.HexColor("#D6DEE8"),
                        )
                    )

                contenido_cat.append(fila_celdas)

            if len(contenido_cat) >= 2:
                estilos_cat.append(("SPAN", (0, 0), (0, 1)))
                estilos_cat.append(("SPAN", (1, 0), (1, 1)))
                estilos_cat.append(("SPAN", (2, 0), (2, 1)))
                estilos_cat.append(("VALIGN", (0, 0), (2, 1), "MIDDLE"))

            tabla_cat = Table(
                contenido_cat,
                colWidths=col_widths_cat,
                repeatRows=min(3, len(contenido_cat)),
                hAlign="LEFT",
                splitByRow=1,
            )
            tabla_cat.setStyle(TableStyle(estilos_cat))
            elementos.append(tabla_cat)

            # 2. TABLA DE PEDIDOS CON PRODUCTOS DESCONTADOS (3 Columnas)
            if fila_inicio_pedidos is not None:
                fin_pedidos = (
                    fila_inicio_no_descontados
                    if fila_inicio_no_descontados is not None
                    else (hoja.max_row + 1)
                )
                col_widths_ped = [95, 250, 136.89]

                contenido_ped = []
                estilos_ped = [
                    ("LEFTPADDING", (0, 0), (-1, -1), 3),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ]

                fila_rel = 0
                for num_f in range(fila_inicio_pedidos, fin_pedidos):
                    fila_celdas = []
                    es_titulo = num_f == fila_inicio_pedidos
                    es_encabezado = num_f == fila_inicio_pedidos + 1
                    val_1 = str(hoja.cell(num_f, 1).value or "").strip()
                    es_vacio_info = "No hubo pedidos" in val_1

                    for col_idx in (1, 2, 3):
                        celda = hoja.cell(num_f, col_idx)
                        texto_html = formatear_valor(celda)

                        if es_titulo:
                            tam_fuente = 9
                            leading = 11
                            es_negrita = True
                            color_texto = colors.HexColor("#17365D")
                            align = 0
                        elif es_encabezado:
                            tam_fuente = 8.5
                            leading = 10
                            es_negrita = True
                            color_texto = colors.HexColor("#17365D")
                            align = 1 if col_idx != 2 else 0
                        elif es_vacio_info:
                            tam_fuente = 8
                            leading = 9.5
                            es_negrita = False
                            color_texto = colors.HexColor("#5B6573")
                            align = 1
                        else:
                            tam_fuente = 7.5
                            leading = 9
                            es_negrita = False
                            color_texto = colors.HexColor("#263445")
                            align = 1 if col_idx == 1 else 0

                        p_style = ParagraphStyle(
                            name=f"ped_{num_f}_{col_idx}",
                            fontName="Helvetica-Bold" if es_negrita else "Helvetica",
                            fontSize=tam_fuente,
                            leading=leading,
                            alignment=align,
                            textColor=color_texto,
                            splitLongWords=True,
                        )
                        fila_celdas.append(Paragraph(texto_html, p_style))

                        if celda.fill.fill_type == "solid":
                            cf = color_excel(celda.fill.fgColor)
                            if cf is not None:
                                estilos_ped.append(
                                    (
                                        "BACKGROUND",
                                        (col_idx - 1, fila_rel),
                                        (col_idx - 1, fila_rel),
                                        cf,
                                    )
                                )

                    if es_titulo:
                        estilos_ped.append(("SPAN", (0, fila_rel), (2, fila_rel)))
                        estilos_ped.append(
                            (
                                "BACKGROUND",
                                (0, fila_rel),
                                (2, fila_rel),
                                colors.HexColor("#EAF0F6"),
                            )
                        )
                    elif es_vacio_info:
                        estilos_ped.append(("SPAN", (0, fila_rel), (2, fila_rel)))

                    estilos_ped.append(
                        (
                            "GRID",
                            (0, fila_rel),
                            (-1, fila_rel),
                            0.35,
                            colors.HexColor("#D6DEE8"),
                        )
                    )
                    contenido_ped.append(fila_celdas)
                    fila_rel += 1

                elementos.append(Spacer(1, 12))
                tabla_ped = Table(
                    contenido_ped,
                    colWidths=col_widths_ped,
                    repeatRows=2,
                    hAlign="LEFT",
                    splitByRow=1,
                )
                tabla_ped.setStyle(TableStyle(estilos_ped))
                elementos.append(tabla_ped)

            # 3. TABLA DE PRODUCTOS NO DESCONTADOS - SIN COINCIDENCIA (4 Columnas)
            if fila_inicio_no_descontados is not None:
                col_widths_no = [55, 95, 195, 136.89]

                contenido_no = []
                estilos_no = [
                    ("LEFTPADDING", (0, 0), (-1, -1), 3),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ]

                fila_rel = 0
                for num_f in range(fila_inicio_no_descontados, hoja.max_row + 1):
                    fila_celdas = []
                    es_titulo = num_f == fila_inicio_no_descontados
                    es_encabezado = num_f == fila_inicio_no_descontados + 1

                    for col_idx in (1, 2, 3, 4):
                        celda = hoja.cell(num_f, col_idx)
                        texto_html = formatear_valor(celda)

                        if es_titulo:
                            tam_fuente = 9
                            leading = 11
                            es_negrita = True
                            color_texto = colors.HexColor("#C00000")
                            align = 0
                        elif es_encabezado:
                            tam_fuente = 8
                            leading = 9.5
                            es_negrita = True
                            color_texto = colors.HexColor("#17365D")
                            align = 1 if col_idx in (1, 2) else 0
                        else:
                            tam_fuente = 7.5
                            leading = 8.5
                            es_negrita = False
                            color_texto = colors.HexColor("#263445")
                            align = 1 if col_idx == 1 else 0

                        p_style = ParagraphStyle(
                            name=f"no_{num_f}_{col_idx}",
                            fontName="Helvetica-Bold" if es_negrita else "Helvetica",
                            fontSize=tam_fuente,
                            leading=leading,
                            alignment=align,
                            textColor=color_texto,
                            splitLongWords=True,
                        )
                        fila_celdas.append(Paragraph(texto_html, p_style))

                        if celda.fill.fill_type == "solid":
                            cf = color_excel(celda.fill.fgColor)
                            if cf is not None:
                                estilos_no.append(
                                    (
                                        "BACKGROUND",
                                        (col_idx - 1, fila_rel),
                                        (col_idx - 1, fila_rel),
                                        cf,
                                    )
                                )

                    if es_titulo:
                        estilos_no.append(("SPAN", (0, fila_rel), (3, fila_rel)))
                        estilos_no.append(
                            (
                                "BACKGROUND",
                                (0, fila_rel),
                                (3, fila_rel),
                                colors.HexColor("#FCE4D6"),
                            )
                        )

                    estilos_no.append(
                        (
                            "GRID",
                            (0, fila_rel),
                            (-1, fila_rel),
                            0.35,
                            colors.HexColor("#D6DEE8"),
                        )
                    )
                    contenido_no.append(fila_celdas)
                    fila_rel += 1

                elementos.append(Spacer(1, 12))
                tabla_no = Table(
                    contenido_no,
                    colWidths=col_widths_no,
                    repeatRows=2,
                    hAlign="LEFT",
                    splitByRow=1,
                )
                tabla_no.setStyle(TableStyle(estilos_no))
                elementos.append(tabla_no)

        else:
            # FALLBACK GENERAL: Si es un libro sin secciones específicas
            usa_3_cols = (
                hoja.max_column == 3
                or (
                    hoja.max_column == 4
                    and all(
                        hoja.cell(r, 4).value is None
                        for r in range(4, min(hoja.max_row + 1, 25))
                    )
                )
            )

            if usa_3_cols:
                cantidad_columnas = 3
                anchos_columnas = [68, 348.89, 65]
            else:
                cantidad_columnas = max(hoja.max_column, 1)
                anchos_excel = [
                    max(
                        hoja.column_dimensions[
                            get_column_letter(columna)
                        ].width
                        or 10,
                        8,
                    )
                    for columna in range(1, cantidad_columnas + 1)
                ]
                suma_anchos = sum(anchos_excel)
                anchos_columnas = [
                    ancho_util * ancho / suma_anchos for ancho in anchos_excel
                ]

            contenido = []
            estilos = [
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]

            for numero_fila in range(1, hoja.max_row + 1):
                fila_contenido = []
                es_encabezado = numero_fila <= 3
                for numero_columna in range(1, cantidad_columnas + 1):
                    celda = hoja.cell(numero_fila, numero_columna)
                    valor = formatear_valor(celda)
                    alineacion = _ALINEACIONES_PDF.get(
                        celda.alignment.horizontal or "", 0
                    )
                    tamano_fuente = 8.5 if es_encabezado else 8
                    leading = 10 if es_encabezado else 9.5
                    estilo_parrafo = ParagraphStyle(
                        name=f"celda_{numero_fila}_{numero_columna}",
                        fontName=(
                            "Helvetica-Bold"
                            if (celda.font.bold or es_encabezado)
                            else "Helvetica-Oblique"
                            if celda.font.italic
                            else "Helvetica"
                        ),
                        fontSize=tamano_fuente,
                        leading=leading,
                        alignment=alineacion,
                        textColor=color_excel(celda.font.color)
                        or colors.HexColor("#263445"),
                        splitLongWords=True,
                    )
                    fila_contenido.append(Paragraph(valor, estilo_parrafo))
                    if celda.fill.fill_type == "solid":
                        color_fondo = color_excel(celda.fill.fgColor)
                        if color_fondo is not None:
                            estilos.append(
                                (
                                    "BACKGROUND",
                                    (numero_columna - 1, numero_fila - 1),
                                    (numero_columna - 1, numero_fila - 1),
                                    color_fondo,
                                )
                            )
                    estilos.append(
                        (
                            "GRID",
                            (0, numero_fila - 1),
                            (-1, numero_fila - 1),
                            0.35,
                            colors.HexColor("#D6DEE8"),
                        )
                    )
                contenido.append(fila_contenido)

            for rango in hoja.merged_cells.ranges:
                min_col, min_row, max_col, max_row = rango.bounds
                if min_col <= cantidad_columnas and min_row <= hoja.max_row:
                    c_fin = min(max_col, cantidad_columnas)
                    r_fin = min(max_row, hoja.max_row)
                    if (min_col, min_row) != (c_fin, r_fin):
                        estilos.append(
                            (
                                "SPAN",
                                (min_col - 1, min_row - 1),
                                (c_fin - 1, r_fin - 1),
                            )
                        )

            tabla = Table(
                contenido,
                colWidths=anchos_columnas,
                repeatRows=min(3, len(contenido)),
                hAlign="LEFT",
                splitByRow=1,
            )
            tabla.setStyle(TableStyle(estilos))
            elementos.append(tabla)

        documento = SimpleDocTemplate(
            str(ruta),
            pagesize=A4,
            leftMargin=2 * cm,
            rightMargin=2 * cm,
            topMargin=2 * cm,
            bottomMargin=2 * cm,
            title=ruta.stem,
        )
        documento.build(elementos, onFirstPage=pie_pagina, onLaterPages=pie_pagina)

    def actualizar_stock_base(self, descuentos: List[RegistroDescuento]) -> int:
        """Persiste en SQLite los saldos nuevos de cada producto descontado."""
        existentes = [d for d in descuentos if not d.es_nuevo_agregado]
        if not existentes:
            return 0

        actualizaciones = {
            descuento.codigo: descuento.stock_nuevo for descuento in existentes
        }
        filas_actualizadas = self.product_store.update_stocks(actualizaciones)
        self._cargar_catalogo()
        return filas_actualizadas
