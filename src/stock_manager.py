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
import openpyxl
import xlwt
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
        # Lista ordenada de filas base: (fila_original, codigo, nombre, stock_inicial)
        self.productos_base: List[Tuple[int, str, str, int]] = []
        self.catalogo: Dict[str, Tuple[int, str, int]] = {}
        self._cargar_catalogo()

    def _cargar_catalogo(self):
        """Carga el catálogo base garantizando que no se arrastren columnas viejas."""
        if not self.ruta_excel_base.exists():
            raise FileNotFoundError(f"No se encontró el archivo de stock en: {self.ruta_excel_base}")

        wb = openpyxl.load_workbook(str(self.ruta_excel_base))
        sheet = wb[self.nombre_hoja] if self.nombre_hoja in wb.sheetnames else wb.active

        self.productos_base.clear()
        self.catalogo.clear()

        # Filas 3 en adelante (fila 1 encabezados, fila 2 vacía)
        for fila in range(3, sheet.max_row + 1):
            val_cod = sheet.cell(row=fila, column=1).value
            if val_cod is not None and str(val_cod).strip() != "":
                cod = normalizar_codigo(str(val_cod))
                nombre = str(sheet.cell(row=fila, column=2).value or "").strip()
                val_stock = sheet.cell(row=fila, column=3).value

                try:
                    stock_num = int(round(float(val_stock))) if val_stock is not None and str(val_stock).strip() != "" else 0
                except (ValueError, TypeError):
                    stock_num = 0

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
        sheet.cell(row=fila_nueva, column=1, value=cod_val)
        sheet.cell(row=fila_nueva, column=2, value=str(nombre_nuevo).strip())

        celda_c = sheet.cell(row=fila_nueva, column=3)
        celda_c.value = int(stock_inicial) if stock_inicial is not None else None
        celda_c.number_format = '0'

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

        # Configurar anchos para las 5 columnas
        ws_salida.column_dimensions['A'].width = 20
        ws_salida.column_dimensions['B'].width = 80
        ws_salida.column_dimensions['C'].width = 18
        ws_salida.column_dimensions['D'].width = 18
        ws_salida.column_dimensions['E'].width = 18

        # Fila 1: Encabezados
        encabezados = ["CÓDIGO", "PRODUCTOS", "STOCK INICIAL", "DESCUENTO", "STOCK FINAL"]
        for c, titulo in enumerate(encabezados, start=1):
            ws_salida.cell(row=1, column=c, value=titulo).number_format = '@'

        # Fila 2: Vacía (separador, como en la plantilla base)

        descuentos: List[RegistroDescuento] = []
        fila_actual = 3

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

        # 4. Sección de resumen de pedidos procesados (columnas A–C; D y E vacías)
        if pedidos_procesados:
            fila_actual += 1  # Fila vacía de separación

            ws_salida.cell(row=fila_actual, column=1, value="RESUMEN").number_format = '@'
            ws_salida.cell(row=fila_actual, column=2, value="PEDIDOS DESCONTADOS EN ESTA PLANILLA").number_format = '@'
            fila_actual += 1

            ws_salida.cell(row=fila_actual, column=1, value="TIPO DE DESCUENTO").number_format = '@'
            ws_salida.cell(row=fila_actual, column=2, value="CLIENTE").number_format = '@'
            ws_salida.cell(row=fila_actual, column=3, value="N° REMITO / PEDIDO").number_format = '@'
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
                fila_actual += 1
                ws_salida.cell(row=fila_actual, column=1, value="MERCADO LIBRE").number_format = '@'
                ws_salida.cell(row=fila_actual, column=2, value="DESCRIPCIONES NO DESCONTADAS").number_format = '@'
                fila_actual += 1
                for columna, titulo in enumerate(("ARCHIVO", "DESCRIPCIÓN", "MOTIVO"), start=1):
                    ws_salida.cell(row=fila_actual, column=columna, value=titulo).number_format = '@'
                fila_actual += 1
                for archivo, descripcion, motivo in pendientes_ml:
                    ws_salida.cell(row=fila_actual, column=1, value=archivo).number_format = '@'
                    ws_salida.cell(row=fila_actual, column=2, value=descripcion).number_format = '@'
                    ws_salida.cell(row=fila_actual, column=3, value=motivo).number_format = '@'
                    fila_actual += 1

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
    def _guardar_informe_xls(libro: openpyxl.Workbook, ruta: Path) -> None:
        hoja_origen = libro.active
        if hoja_origen.max_row > 65_536:
            raise ValueError(
                "El informe supera el límite de 65.536 filas del formato XLS."
            )

        libro_xls = xlwt.Workbook(encoding="utf-8")
        hoja_xls = libro_xls.add_sheet(hoja_origen.title[:31])
        estilo_texto = xlwt.easyxf(num_format_str="@")
        estilo_entero = xlwt.easyxf(num_format_str="0")

        for columna in range(1, hoja_origen.max_column + 1):
            ancho = hoja_origen.column_dimensions[
                openpyxl.utils.get_column_letter(columna)
            ].width
            if ancho:
                hoja_xls.col(columna - 1).width = min(int(ancho * 256), 65_535)

        for fila in hoja_origen.iter_rows():
            for celda in fila:
                if celda.value is None:
                    continue
                estilo = (
                    estilo_entero
                    if isinstance(celda.value, (int, float))
                    and not isinstance(celda.value, bool)
                    else estilo_texto
                )
                hoja_xls.write(celda.row - 1, celda.column - 1, celda.value, estilo)

        libro_xls.save(str(ruta))

    def actualizar_stock_base(self, descuentos: List[RegistroDescuento]) -> int:
        """
        Escribe el Stock Final de cada producto descontado en Productos.xlsx (columna C),
        para que la próxima corrida arranque con ese valor como Stock Inicial.

        Solo toca los productos que tuvieron descuento en esta corrida; los demás
        conservan su stock intacto en el archivo base.

        Retorna la cantidad de filas actualizadas.
        """
        existentes = [d for d in descuentos if not d.es_nuevo_agregado]
        if not existentes:
            return 0

        # Mapa: codigo → stock_nuevo (Stock Final de esta corrida)
        actualizaciones = {d.codigo: d.stock_nuevo for d in existentes}

        wb = openpyxl.load_workbook(str(self.ruta_excel_base))
        sheet = wb[self.nombre_hoja] if self.nombre_hoja in wb.sheetnames else wb.active

        actualizados = 0
        for fila in range(3, sheet.max_row + 1):
            val_cod = sheet.cell(row=fila, column=1).value
            if val_cod is not None and str(val_cod).strip() != "":
                cod = normalizar_codigo(str(val_cod))
                if cod in actualizaciones:
                    celda = sheet.cell(row=fila, column=3)
                    celda.value = actualizaciones[cod]
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
