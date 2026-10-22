"""Lee el catálogo como plantilla y genera informes de descuentos en Excel."""

from dataclasses import dataclass
from copy import copy
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import unicodedata
import openpyxl
import xlwt
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from .consolidator import ItemConsolidado
from .remito_parser import ResultadoRemito, normalizar_codigo


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


class StockManager:
    def __init__(self, ruta_excel_base: str | Path, nombre_hoja: str = "Stock"):
        self.ruta_excel_base = Path(ruta_excel_base)
        self.nombre_hoja = nombre_hoja
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
        """Carga productos desde el esquema detectado o desde el formato tradicional A:C."""
        if not self.ruta_excel_base.exists():
            raise FileNotFoundError(f"No se encontró el archivo de stock en: {self.ruta_excel_base}")

        wb = openpyxl.load_workbook(str(self.ruta_excel_base))
        sheet = wb[self.nombre_hoja] if self.nombre_hoja in wb.sheetnames else wb.active
        self._detectar_esquema(sheet)

        self.productos_base.clear()
        self.filas_catalogo.clear()
        self.catalogo.clear()
        self._filas_por_codigo.clear()

        for fila in range(self._fila_inicio_datos, sheet.max_row + 1):
            val_cod = sheet.cell(row=fila, column=self._col_codigo).value
            if val_cod is not None and str(val_cod).strip() != "":
                cod = normalizar_codigo(str(val_cod))
                nombre = str(sheet.cell(row=fila, column=self._col_nombre).value or "").strip()
                if not nombre:
                    continue

                self._filas_por_codigo.setdefault(cod, []).append(fila)
                stock_num = self._leer_stock(sheet, fila)
                self.filas_catalogo.append((fila, cod, nombre, stock_num))
                if cod in self.catalogo:
                    continue

                self.productos_base.append((fila, cod, nombre, stock_num))
                self.catalogo[cod] = (fila, nombre, stock_num)

    def agregar_producto_en_posicion(
        self,
        codigo_nuevo: str,
        nombre_nuevo: str,
        codigo_arriba: str,
        stock_inicial: Optional[int] = None
    ) -> Tuple[bool, str, Optional[int]]:
        """
        Inserta un nuevo producto en la planilla Productos.xlsx inmediatamente
        debajo del producto indicado por codigo_arriba.

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

        fila_arriba, nombre_arriba, _ = self.catalogo[cod_arriba_norm]
        fila_nueva = fila_arriba + 1

        # 3. Cargar el libro base y realizar la inserción
        wb = openpyxl.load_workbook(str(self.ruta_excel_base))
        sheet = wb[self.nombre_hoja] if self.nombre_hoja in wb.sheetnames else wb.active

        # Insertar fila debajo de fila_arriba
        sheet.insert_rows(fila_nueva, 1)

        # Configurar valores y formato
        cod_val = int(cod_nuevo_norm) if cod_nuevo_norm.isdigit() else cod_nuevo_norm
        sheet.cell(row=fila_nueva, column=self._col_codigo, value=cod_val)
        sheet.cell(row=fila_nueva, column=self._col_nombre, value=str(nombre_nuevo).strip())

        celda_stock = sheet.cell(row=fila_nueva, column=self._col_stock)
        celda_stock.value = int(stock_inicial) if stock_inicial is not None else None
        celda_stock.number_format = '0'

        # 4. Guardar archivo base y actualizar respaldo
        wb.save(str(self.ruta_excel_base))
        backup_path = self.ruta_excel_base.with_name(f"{self.ruta_excel_base.stem}_backup{self.ruta_excel_base.suffix}")
        wb.save(str(backup_path))

        # 5. Recargar catálogo en memoria
        self._cargar_catalogo()

        return True, f"Producto '{nombre_nuevo}' [{cod_nuevo_norm}] insertado con exito en la fila {fila_nueva} (debajo de [{cod_arriba_norm}] {nombre_arriba}).", fila_nueva

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
                "Código no encontrado en Productos.xlsx",
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
            fecha_generacion.strftime("%d/%m/%y"),
            filas_productos,
            pedidos_descontados,
            productos_sin_coincidencia,
        )

        if guardar_archivo:
            carpeta_destino.mkdir(parents=True, exist_ok=True)
            self._guardar_informe_xls(wb_salida, ruta_guardado)
            archivo_final = str(ruta_guardado)
        else:
            archivo_final = f"[SIMULACIÓN - NO GUARDADO] {ruta_guardado.name}"

        return ReporteStock(
            descuentos_aplicados=descuentos,
            archivo_guardado=archivo_final
        )

    def _crear_informe_desde_plantilla(
        self,
        cantidad_descuentos: int,
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
        hoja_salida.page_setup.orientation = hoja_plantilla.page_setup.orientation
        hoja_salida.page_setup.fitToWidth = 1
        hoja_salida.page_setup.fitToHeight = 0
        hoja_salida.sheet_properties.pageSetUpPr.fitToPage = True
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

        def aplicar_encabezado(fila: int, color_fondo: str) -> None:
            for columna in range(1, 5):
                celda = hoja_salida.cell(fila, columna)
                celda.fill = PatternFill("solid", fgColor=color_fondo)
                celda.font = Font(
                    name="Arial",
                    size=12 if fila == 1 else 10,
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
            2,
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
            if columna_salida == 4:
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

        for encabezado in ("A1:A2", "B1:B2", "C1:C2", "D1:D2"):
            hoja_salida.merge_cells(encabezado)
        hoja_salida["A1"] = (
            hoja_plantilla.cell(1, self._col_codigo).value or "CODIGO"
        )
        hoja_salida["B1"] = (
            hoja_plantilla.cell(1, 2).value or "UNIDADES"
        )
        hoja_salida["C1"] = (
            hoja_plantilla.cell(1, self._col_nombre).value or "PRODUCTOS"
        )
        hoja_salida["D1"] = f"FECHA: {fecha_generacion}"
        aplicar_encabezado(1, "D9EAF7")

        encabezado_productos = hoja_plantilla.cell(3, self._col_nombre).value
        hoja_salida["C3"] = (
            encabezado_productos
            if self._col_stock_inicial is not None and encabezado_productos
            else "PRODUCTOS"
        )
        hoja_salida["D3"] = "DESCUENTO"
        hoja_salida["D3"].number_format = "@"
        aplicar_encabezado(3, "D9EAF7")
        hoja_salida.row_dimensions[1].height = 25
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
                if fila_original <= hoja_plantilla.max_row
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
            hoja_salida.cell(fila_salida, 2, unidades)
            hoja_salida.cell(fila_salida, 3, nombre)
            if descuento is not None:
                hoja_salida.cell(fila_salida, 4, descuento).number_format = "0"

        fila_actual = 4 + len(filas_productos)
        hoja_salida.cell(fila_actual, 3, "TOTAL PRODUCTOS DESCONTADOS:")
        hoja_salida.cell(fila_actual, 4, cantidad_descuentos)
        self._copiar_estilo_fila(
            hoja_plantilla, hoja_salida, 3, fila_actual, 4
        )
        for columna in range(1, 5):
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
            2,
            self._col_nombre,
            self._col_descuento or self._col_stock,
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

        hoja_xls.portrait = False
        hoja_xls.fit_width_to_pages = 1
        hoja_xls.fit_height_to_pages = 0
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

    def actualizar_stock_base(self, descuentos: List[RegistroDescuento]) -> int:
        """
        Guarda los saldos en las columnas de stock detectadas. En el esquema con
        Stock Inicial/Descuento/Stock Final, el Stock Final será el saldo de partida
        de la siguiente corrida.

        Si hay códigos repetidos, sincroniza todas sus filas sin duplicar el descuento.

        Retorna la cantidad de filas actualizadas.
        """
        existentes = [d for d in descuentos if not d.es_nuevo_agregado]
        if not existentes:
            return 0

        actualizaciones = {d.codigo: d for d in existentes}

        wb = openpyxl.load_workbook(str(self.ruta_excel_base))
        sheet = wb[self.nombre_hoja] if self.nombre_hoja in wb.sheetnames else wb.active

        actualizados = 0
        for cod, filas in self._filas_por_codigo.items():
            descuento = actualizaciones.get(cod)
            if descuento is None:
                continue
            for fila in filas:
                if self._col_stock_final is not None:
                    celda_inicial = sheet.cell(row=fila, column=self._col_stock_inicial or self._col_stock)
                    celda_inicial.value = descuento.stock_anterior
                    celda_inicial.number_format = '0'
                    if self._col_descuento is not None:
                        celda_descuento = sheet.cell(row=fila, column=self._col_descuento)
                        celda_descuento.value = -descuento.cantidad_descontada
                        celda_descuento.number_format = '0'
                    celda_final = sheet.cell(row=fila, column=self._col_stock_final)
                    celda_final.value = descuento.stock_nuevo
                    celda_final.number_format = '0'
                else:
                    celda = sheet.cell(row=fila, column=self._col_stock)
                    celda.value = descuento.stock_nuevo
                    celda.number_format = '0'
                actualizados += 1

        wb.save(str(self.ruta_excel_base))

        # Actualizar también el backup automático
        backup_path = self.ruta_excel_base.with_name(
            f"{self.ruta_excel_base.stem}_backup{self.ruta_excel_base.suffix}"
        )
        wb.save(str(backup_path))

        # Recargar catálogo en memoria con los valores nuevos
        self._cargar_catalogo()

        return actualizados
