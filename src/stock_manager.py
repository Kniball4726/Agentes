"""
Módulo de Gestión de Stock (Excel).
Lee la planilla de productos original y genera el archivo de descuentos cumpliendo:
1. Estructura de 5 columnas (A: CÓDIGO, B: PRODUCTOS, C: STOCK INICIAL, D: DESCUENTO, E: STOCK FINAL).
2. Sin formatos de moneda o decimales (0.00).
3. Descuento en columna D (valor negativo) y Stock Final en columna E.
4. Agregado de productos no encontrados al final con leyenda explicativa.
5. Inclusión al final de los pedidos descontados (Cliente, Tipo de Descuento y N° de Remito).
6. Guardado en 'Descuento<fecha>.xls' (Excel 97–2003) en la carpeta 'descuentos'.
7. Actualización automática de Productos.xlsx con el Stock Final para encadenar corridas.
"""

from dataclasses import dataclass
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
                if cod in self.catalogo:
                    continue

                stock_num = self._leer_stock(sheet, fila)
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
        """
        Construye una planilla de descuento con 5 columnas:
          A: CÓDIGO | B: PRODUCTOS | C: STOCK INICIAL | D: DESCUENTO | E: STOCK FINAL

        - Stock Inicial: valor actual leído de Productos.xlsx antes del descuento.
        - Descuento: cantidad descontada en esta corrida (valor negativo).
        - Stock Final: Stock Inicial + Descuento (el nuevo stock resultante).

        El Stock Final se escribe de vuelta en Productos.xlsx mediante
        actualizar_stock_base(), haciendo que sea el Stock Inicial de la próxima corrida.
        """
        carpeta_destino = Path(carpeta_destino)
        fecha_hora_str = datetime.now().strftime("%d-%m-%Y_%H-%M-%S")
        nombre_archivo = f"Descuento{fecha_hora_str}.xls"
        ruta_guardado = carpeta_destino / nombre_archivo

        # 1. Crear nuevo libro de trabajo limpio
        wb_salida = openpyxl.Workbook()
        ws_salida = wb_salida.active
        ws_salida.title = "Stock"
        ws_salida.sheet_view.showGridLines = False
        ws_salida.freeze_panes = "A8"
        ws_salida.page_setup.orientation = "landscape"
        ws_salida.page_setup.fitToWidth = 1
        ws_salida.page_setup.fitToHeight = 0
        ws_salida.sheet_properties.pageSetUpPr.fitToPage = True
        ws_salida.print_title_rows = "1:7"
        ws_salida.sheet_properties.outlinePr.summaryBelow = True

        for columna, ancho in {"A": 19, "B": 64, "C": 17, "D": 17, "E": 17}.items():
            ws_salida.column_dimensions[columna].width = ancho

        ws_salida.merge_cells("A1:E1")
        ws_salida["A1"] = "REPORTE DE DESCUENTOS DE STOCK"
        ws_salida.row_dimensions[1].height = 32
        ws_salida.merge_cells("A2:E2")
        ws_salida["A2"] = (
            f"Generado el {datetime.now().strftime('%d/%m/%Y a las %H:%M:%S')} "
            "| Informe de movimientos de inventario"
        )
        ws_salida.row_dimensions[2].height = 23

        metricas = [
            ("PRODUCTOS CON DESCUENTO", "A4:B4", "A5:B5"),
            ("UNIDADES DESCONTADAS", "C4:C4", "C5:C5"),
            ("PEDIDOS PROCESADOS", "D4:D4", "D5:D5"),
            ("PENDIENTES DE REVISIÓN", "E4:E4", "E5:E5"),
        ]
        for titulo, rango_titulo, rango_valor in metricas:
            ws_salida.merge_cells(rango_titulo)
            ws_salida.merge_cells(rango_valor)
            celda_titulo = ws_salida[rango_titulo.split(":")[0]]
            celda_titulo.value = titulo
            celda_valor = ws_salida[rango_valor.split(":")[0]]
            celda_valor.value = 0
        ws_salida.row_dimensions[4].height = 22
        ws_salida.row_dimensions[5].height = 30

        ws_salida.merge_cells("A7:E7")
        ws_salida["A7"] = "DETALLE DE PRODUCTOS Y MOVIMIENTOS"
        ws_salida.row_dimensions[7].height = 23

        encabezados = ["CÓDIGO", "PRODUCTOS", "STOCK INICIAL", "DESCUENTO", "STOCK FINAL"]
        for c, titulo in enumerate(encabezados, start=1):
            ws_salida.cell(row=8, column=c, value=titulo).number_format = '@'

        descuentos: List[RegistroDescuento] = []
        fila_actual = 9

        # 2. Poblar los productos existentes en el catálogo
        for _, cod, nombre, stock_ant in self.productos_base:
            cod_val = int(cod) if cod.isdigit() else cod
            ws_salida.cell(row=fila_actual, column=1, value=cod_val)
            ws_salida.cell(row=fila_actual, column=2, value=nombre)

            # Columna C: Stock Inicial (siempre se muestra, haya o no descuento)
            celda_si = ws_salida.cell(row=fila_actual, column=3)
            celda_si.value = stock_ant
            celda_si.number_format = '0'

            if cod in items_consolidados:
                item = items_consolidados[cod]
                nuevo_stock = int(stock_ant - item.cantidad_total)

                # Columna D: Descuento (negativo → deja en claro que es una resta)
                celda_d = ws_salida.cell(row=fila_actual, column=4)
                celda_d.value = -item.cantidad_total
                celda_d.number_format = '0'

                # Columna E: Stock Final
                celda_sf = ws_salida.cell(row=fila_actual, column=5)
                celda_sf.value = nuevo_stock
                celda_sf.number_format = '0'

                descuentos.append(RegistroDescuento(
                    codigo=cod,
                    nombre_producto=nombre,
                    fila_excel=fila_actual,
                    stock_anterior=stock_ant,
                    cantidad_descontada=item.cantidad_total,
                    stock_nuevo=nuevo_stock,
                    es_nuevo_agregado=False
                ))
            # Si no tuvo descuento: columnas D y E quedan vacías (None)

            fila_actual += 1

        # 3. Agregar al final los productos que NO estaban en el catálogo original
        for cod, item in items_consolidados.items():
            if cod not in self.catalogo:
                nombre_explicativo = f"{item.descripcion} (NO SE ENCUENTRA EN LA LISTA ORIGINAL)"
                nuevo_stock = int(-item.cantidad_total)

                cod_val = int(cod) if cod.isdigit() else cod
                ws_salida.cell(row=fila_actual, column=1, value=cod_val)
                ws_salida.cell(row=fila_actual, column=2, value=nombre_explicativo)

                # SI = 0, Descuento = -cantidad, SF = -cantidad
                ws_salida.cell(row=fila_actual, column=3, value=0).number_format = '0'
                celda_d = ws_salida.cell(row=fila_actual, column=4)
                celda_d.value = -item.cantidad_total
                celda_d.number_format = '0'
                celda_sf = ws_salida.cell(row=fila_actual, column=5)
                celda_sf.value = nuevo_stock
                celda_sf.number_format = '0'

                descuentos.append(RegistroDescuento(
                    codigo=cod,
                    nombre_producto=nombre_explicativo,
                    fila_excel=fila_actual,
                    stock_anterior=0,
                    cantidad_descontada=item.cantidad_total,
                    stock_nuevo=nuevo_stock,
                    es_nuevo_agregado=True
                ))

                fila_actual += 1

        fila_ultimo_producto = fila_actual - 1
        total_unidades = sum(descuento.cantidad_descontada for descuento in descuentos)
        cantidad_pendientes = sum(
            len(doc.descripciones_sin_coincidencia)
            for doc in (pedidos_procesados or [])
        )
        for referencia, valor in (
            ("A5", len(descuentos)),
            ("C5", total_unidades),
            ("D5", len(pedidos_procesados or [])),
            ("E5", cantidad_pendientes),
        ):
            ws_salida[referencia] = valor

        # 4. Sección de resumen de pedidos procesados
        if pedidos_procesados:
            fila_actual += 2
            ws_salida.merge_cells(
                start_row=fila_actual,
                start_column=1,
                end_row=fila_actual,
                end_column=5,
            )
            ws_salida.cell(row=fila_actual, column=1, value="PEDIDOS PROCESADOS")
            ws_salida.row_dimensions[fila_actual].height = 23
            fila_actual += 1

            for columna, titulo in enumerate(
                ("TIPO", "CLIENTE", "N° REMITO / PEDIDO"), start=1
            ):
                ws_salida.cell(row=fila_actual, column=columna, value=titulo).number_format = '@'
            fila_actual += 1

            for doc in pedidos_procesados:
                if doc.archivo.lower().endswith(".pdf"):
                    tipo_desc = "Remito Mayorista"
                elif doc.archivo.lower().endswith(".docx"):
                    tipo_desc = "Mercado Libre"
                else:
                    tipo_desc = "Canje"
                ws_salida.cell(row=fila_actual, column=1, value=tipo_desc).number_format = '@'
                ws_salida.cell(row=fila_actual, column=2, value=doc.cliente).number_format = '@'
                ws_salida.cell(row=fila_actual, column=3, value=str(doc.numero_remito)).number_format = '@'
                fila_actual += 1

            pendientes_ml = [
                (doc.archivo, descripcion, motivo)
                for doc in pedidos_procesados
                for descripcion, motivo in doc.descripciones_sin_coincidencia
            ]
            if pendientes_ml:
                fila_actual += 2
                ws_salida.merge_cells(
                    start_row=fila_actual,
                    start_column=1,
                    end_row=fila_actual,
                    end_column=5,
                )
                ws_salida.cell(
                    row=fila_actual,
                    column=1,
                    value="LÍNEAS DE MERCADO LIBRE PENDIENTES DE REVISIÓN",
                )
                ws_salida.row_dimensions[fila_actual].height = 23
                fila_actual += 1
                for columna, titulo in enumerate(("ARCHIVO", "DESCRIPCIÓN", "MOTIVO"), start=1):
                    ws_salida.cell(row=fila_actual, column=columna, value=titulo).number_format = '@'
                fila_actual += 1
                for archivo, descripcion, motivo in pendientes_ml:
                    ws_salida.cell(row=fila_actual, column=1, value=archivo).number_format = '@'
                    ws_salida.cell(row=fila_actual, column=2, value=descripcion).number_format = '@'
                    ws_salida.cell(row=fila_actual, column=3, value=motivo).number_format = '@'
                    fila_actual += 1

        self._estilizar_informe(
            ws_salida,
            fila_ultimo_producto=fila_ultimo_producto,
            fila_final=fila_actual - 1,
        )

        # 5. Guardar archivo de salida si no es modo simulación
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

    @staticmethod
    def _estilizar_informe(ws, fila_ultimo_producto: int, fila_final: int) -> None:
        navy = "17365D"
        light_blue = "D9EAF7"
        pale_blue = "F3F7FB"
        border_color = "D6DEE8"
        slate = "5B6573"
        red = "FCE4D6"
        dark_red = "9C0006"

        thin_gray = Side(style="thin", color=border_color)
        for cell in ws[1]:
            cell.fill = PatternFill("solid", fgColor=light_blue)
            cell.font = Font(name="Aptos Display", size=19, bold=True, color=navy)
            cell.alignment = Alignment(vertical="center")
        for cell in ws[2]:
            cell.fill = PatternFill("solid", fgColor="EAF0F6")
            cell.font = Font(name="Aptos", size=10, italic=True, color=slate)
            cell.alignment = Alignment(vertical="center")

        for row in (4, 5):
            for cell in ws[row]:
                cell.border = Border(
                    left=thin_gray,
                    right=thin_gray,
                    top=thin_gray,
                    bottom=thin_gray,
                )
                cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        for cell in ws[4]:
            cell.fill = PatternFill("solid", fgColor=light_blue)
            cell.font = Font(name="Aptos", size=9, bold=True, color=navy)
        for cell in ws[5]:
            cell.fill = PatternFill("solid", fgColor=pale_blue)
            cell.font = Font(name="Aptos Display", size=15, bold=True, color=navy)

        for cell in ws[7]:
            cell.fill = PatternFill("solid", fgColor="EAF0F6")
            cell.font = Font(name="Aptos", size=11, bold=True, color=navy)
            cell.alignment = Alignment(vertical="center")

        for cell in ws[8]:
            cell.fill = PatternFill("solid", fgColor=light_blue)
            cell.font = Font(name="Aptos", size=10, bold=True, color=navy)
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.border = Border(bottom=Side(style="medium", color=border_color))
        ws.row_dimensions[8].height = 28

        for fila in range(9, fila_ultimo_producto + 1):
            tiene_descuento = ws.cell(row=fila, column=4).value is not None
            es_nuevo = "NO SE ENCUENTRA EN LA LISTA ORIGINAL" in str(
                ws.cell(row=fila, column=2).value or ""
            )
            for columna in range(1, 6):
                cell = ws.cell(row=fila, column=columna)
                cell.fill = PatternFill(
                    "solid",
                    fgColor=red if es_nuevo else (
                        light_blue if tiene_descuento else (
                            "FFFFFF" if fila % 2 else pale_blue
                        )
                    ),
                )
                cell.border = Border(bottom=thin_gray)
                cell.font = Font(
                    name="Aptos",
                    size=10,
                    color=dark_red if es_nuevo else (
                        "263445" if tiene_descuento else "7F8995"
                    ),
                    bold=es_nuevo,
                )
                cell.alignment = Alignment(
                    horizontal="left" if columna == 2 else "center",
                    vertical="center",
                    wrap_text=columna == 2,
                )
                if columna >= 3:
                    cell.number_format = '#,##0;[Red]-#,##0;0'
            ws.row_dimensions[fila].height = 20
            if tiene_descuento:
                ws.cell(row=fila, column=4).font = Font(
                    name="Aptos", size=10, bold=True, color=dark_red
                )
                ws.cell(row=fila, column=5).font = Font(
                    name="Aptos", size=10, bold=True, color=navy
                )
            if ws.cell(row=fila, column=5).value is not None and ws.cell(
                row=fila, column=5
            ).value < 0:
                ws.cell(row=fila, column=5).fill = PatternFill("solid", fgColor=red)
                ws.cell(row=fila, column=5).font = Font(
                    name="Aptos", size=10, bold=True, color=dark_red
                )

        for fila in range(1, fila_final + 1):
            if fila in (1, 2, 4, 5, 7, 8) or 9 <= fila <= fila_ultimo_producto:
                continue
            valor = ws.cell(row=fila, column=1).value
            if valor in ("PEDIDOS PROCESADOS", "LÍNEAS DE MERCADO LIBRE PENDIENTES DE REVISIÓN"):
                for cell in ws[fila]:
                    cell.fill = PatternFill("solid", fgColor="EAF0F6")
                    cell.font = Font(name="Aptos", size=11, bold=True, color=navy)
                    cell.alignment = Alignment(vertical="center")
            elif valor in ("TIPO", "ARCHIVO"):
                for cell in ws[fila]:
                    cell.fill = PatternFill("solid", fgColor=light_blue)
                    cell.font = Font(name="Aptos", size=10, bold=True, color=navy)
                    cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            else:
                for columna in range(1, 6):
                    cell = ws.cell(row=fila, column=columna)
                    cell.fill = PatternFill(
                        "solid",
                        fgColor="FFFFFF" if fila % 2 else pale_blue,
                    )
                    cell.font = Font(name="Aptos", size=10, color="263445")
                    cell.alignment = Alignment(vertical="top", wrap_text=True)
                    cell.border = Border(bottom=thin_gray)
                ws.row_dimensions[fila].height = 30

        ws.print_area = f"A1:E{max(1, fila_final)}"

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
                if indice_color is not None:
                    patron.pattern_fore_colour = indice_color
            estilo.pattern = patron
            estilo.num_format_str = celda.number_format or "General"
            estilos[celda.style_id] = estilo
            return estilo

        for columna in range(1, hoja_origen.max_column + 1):
            ancho = hoja_origen.column_dimensions[
                openpyxl.utils.get_column_letter(columna)
            ].width
            if ancho:
                hoja_xls.col(columna - 1).width = min(int(ancho * 256), 65_535)

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
        hoja_xls.set_panes_frozen(True)
        hoja_xls.set_horz_split_pos(7)

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
