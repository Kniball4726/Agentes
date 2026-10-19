import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import openpyxl

from src.consolidator import ItemConsolidado
from src.remito_parser import ResultadoRemito
from src.stock_manager import RegistroDescuento, StockManager


class StockManagerTests(unittest.TestCase):
    def test_detects_catalog_layout_and_carries_forward_final_stock(self):
        with tempfile.TemporaryDirectory() as directorio:
            ruta = Path(directorio) / "Productos.xlsx"
            libro = openpyxl.Workbook()
            hoja = libro.active
            hoja.title = "Hoja1"
            hoja["A1"] = "Codigo"
            hoja["C1"] = "Productos"
            hoja["C3"] = "Línea"
            hoja["D3"] = "Stock Inicial"
            hoja["E3"] = "Descuento"
            hoja["F3"] = "Stock Final"
            hoja["A4"] = 100
            hoja["C4"] = "Producto duplicado"
            hoja["A5"] = 100
            hoja["C5"] = "Producto duplicado"
            hoja["A6"] = 200
            hoja["C6"] = "Producto con stock"
            hoja["D6"] = 7
            libro.save(ruta)

            manager = StockManager(ruta)

            self.assertEqual(len(manager.productos_base), 2)
            self.assertEqual(manager.catalogo["100"][2], 0)
            self.assertEqual(manager.catalogo["200"][2], 7)

            manager.actualizar_stock_base([
                RegistroDescuento(
                    codigo="100",
                    nombre_producto="Producto duplicado",
                    fila_excel=3,
                    stock_anterior=0,
                    cantidad_descontada=2,
                    stock_nuevo=-2,
                )
            ])

            libro_actualizado = openpyxl.load_workbook(ruta, data_only=True)
            hoja_actualizada = libro_actualizado["Hoja1"]
            for fila in (4, 5):
                self.assertEqual(hoja_actualizada.cell(fila, 4).value, 0)
                self.assertEqual(hoja_actualizada.cell(fila, 5).value, -2)
                self.assertEqual(hoja_actualizada.cell(fila, 6).value, -2)

            manager_siguiente_corrida = StockManager(ruta)
            self.assertEqual(manager_siguiente_corrida.catalogo["100"][2], -2)
            self.assertEqual(manager_siguiente_corrida.catalogo["200"][2], 7)

    def test_keeps_legacy_a_to_c_catalog_layout(self):
        with tempfile.TemporaryDirectory() as directorio:
            ruta = Path(directorio) / "Productos.xlsx"
            libro = openpyxl.Workbook()
            hoja = libro.active
            hoja.append(["CÓDIGO", "PRODUCTOS", "STOCK"])
            hoja.append([])
            hoja.append([345, "Producto clásico", 12])
            libro.save(ruta)

            manager = StockManager(ruta)

            self.assertEqual(manager.productos_base, [(3, "345", "Producto clásico", 12)])
            self.assertEqual(manager._col_stock, 3)
            self.assertIsNone(manager._col_stock_final)

    def test_adds_product_using_detected_catalog_columns(self):
        with tempfile.TemporaryDirectory() as directorio:
            ruta = Path(directorio) / "Productos.xlsx"
            libro = openpyxl.Workbook()
            hoja = libro.active
            hoja["A1"] = "Codigo"
            hoja["C1"] = "Productos"
            hoja["D3"] = "Stock Inicial"
            hoja["E3"] = "Descuento"
            hoja["F3"] = "Stock Final"
            hoja["A4"] = 100
            hoja["C4"] = "Producto existente"
            libro.save(ruta)

            manager = StockManager(ruta)
            exito, _, fila = manager.agregar_producto_en_posicion(
                codigo_nuevo="101",
                nombre_nuevo="Producto nuevo",
                codigo_arriba="100",
                stock_inicial=5,
            )

            self.assertTrue(exito)
            self.assertEqual(fila, 5)
            libro_actualizado = openpyxl.load_workbook(ruta, data_only=True)
            self.assertEqual(libro_actualizado.active["A5"].value, 101)
            self.assertEqual(libro_actualizado.active["C5"].value, "Producto nuevo")
            self.assertEqual(libro_actualizado.active["D5"].value, 5)
            self.assertEqual(StockManager(ruta).catalogo["101"][2], 5)

    def test_builds_professional_discount_report(self):
        with tempfile.TemporaryDirectory() as directorio:
            ruta = Path(directorio) / "Productos.xlsx"
            libro = openpyxl.Workbook()
            hoja = libro.active
            hoja.append(["CODIGO", "PRODUCTOS", "STOCK"])
            hoja.append([])
            hoja.append([101, "Producto con descuento", 10])
            hoja.append([202, "Producto sin descuento", 3])
            libro.save(ruta)

            manager = StockManager(ruta)
            documento = ResultadoRemito(
                archivo="pedido.docx",
                numero_remito="ML-pedido",
                fecha="Hoy",
                cliente="Cliente Ejemplo",
                articulos_declarados=3,
                articulos_extraidos=2,
                verificacion_ok=False,
                descripciones_sin_coincidencia=[
                    ("1 Producto pendiente", "No se encontró en el catálogo")
                ],
            )
            libros_guardados = []

            with patch.object(
                StockManager,
                "_guardar_informe_xls",
                side_effect=lambda libro_salida, _: libros_guardados.append(libro_salida),
            ):
                manager.aplicar_descuentos(
                    {"101": ItemConsolidado("101", "Producto con descuento", 2)},
                    Path(directorio) / "informes",
                    pedidos_procesados=[documento],
                )

            hoja_reporte = libros_guardados[0].active
            self.assertEqual(hoja_reporte["A1"].value, "REPORTE DE DESCUENTOS DE STOCK")
            self.assertEqual(hoja_reporte["A5"].value, 1)
            self.assertEqual(hoja_reporte["C5"].value, 2)
            self.assertEqual(hoja_reporte["D5"].value, 1)
            self.assertEqual(hoja_reporte["E5"].value, 1)
            self.assertEqual(hoja_reporte["A9"].value, 101)
            self.assertEqual(hoja_reporte["D9"].value, -2)
            self.assertEqual(hoja_reporte.freeze_panes, "A8")
            self.assertIn("A1:E1", {str(rango) for rango in hoja_reporte.merged_cells.ranges})
            self.assertTrue(hoja_reporte["A1"].font.bold)
            self.assertEqual(hoja_reporte["A9"].fill.fgColor.rgb, "00D9EAF7")
            self.assertEqual(hoja_reporte["B9"].font.color.rgb, "00263445")
            self.assertEqual(hoja_reporte["B10"].font.color.rgb, "007F8995")
            for fila in hoja_reporte.iter_rows():
                for celda in fila:
                    color = celda.fill.fgColor.rgb
                    if celda.fill.fill_type == "solid" and color:
                        rgb = tuple(int(color[indice:indice + 2], 16) for indice in (2, 4, 6))
                        luminancia = sum(
                            peso * canal
                            for peso, canal in zip((0.2126, 0.7152, 0.0722), rgb)
                        )
                        self.assertGreaterEqual(luminancia, 190)


if __name__ == "__main__":
    unittest.main()
