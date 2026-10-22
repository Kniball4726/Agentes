import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import openpyxl

from src.consolidator import ItemConsolidado
from src.remito_parser import ItemRemito, ResultadoRemito
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

    def test_builds_discount_report_from_read_only_template(self):
        with tempfile.TemporaryDirectory() as directorio:
            ruta = Path(directorio) / "Productos.xlsx"
            libro = openpyxl.Workbook()
            hoja = libro.active
            hoja.merge_cells("A1:A2")
            hoja.merge_cells("B1:B2")
            hoja.merge_cells("C1:C2")
            hoja.merge_cells("D1:F2")
            hoja["A1"] = "Codigo"
            hoja["B1"] = "UNIDADES"
            hoja["C1"] = "Productos"
            hoja["D1"] = "Descuento"
            hoja["C3"] = "Línea"
            hoja["D3"] = "Stock Inicial"
            hoja["E3"] = "Descuento"
            hoja["F3"] = "Stock Final"
            hoja["A4"] = 101
            hoja["B4"] = "Producto con descuento"
            hoja["C4"] = "Producto con descuento"
            hoja["D4"] = 10
            hoja["A5"] = 202
            hoja["B5"] = "Producto sin descuento"
            hoja["C5"] = "Producto sin descuento"
            hoja["D5"] = 3
            hoja["A4"].fill = openpyxl.styles.PatternFill("solid", fgColor="CCCCFF")
            hoja["E4"].fill = openpyxl.styles.PatternFill("solid", fgColor="FF8080")
            hoja.column_dimensions["B"].hidden = True
            hoja.column_dimensions["C"].width = 42
            libro.save(ruta)
            contenido_plantilla = ruta.read_bytes()

            manager = StockManager(ruta)
            pedido = ResultadoRemito(
                archivo="pedido.pdf",
                numero_remito="R-123",
                fecha="Hoy",
                cliente="Cliente Ejemplo",
                articulos_declarados=3,
                articulos_extraidos=1,
                verificacion_ok=False,
                items=[ItemRemito("101", "Producto con descuento", 2, "R-123")],
                descripciones_sin_coincidencia=[
                    ("Producto sin coincidencia", "No se encontró en el catálogo")
                ],
            )
            with patch.object(StockManager, "_guardar_informe_xls", wraps=StockManager._guardar_informe_xls) as guardar:
                manager.aplicar_descuentos(
                    {
                        "101": ItemConsolidado("101", "Producto con descuento", 2),
                        "999": ItemConsolidado("999", "Producto no catalogado", 1),
                    },
                    Path(directorio) / "informes",
                    pedidos_procesados=[pedido],
                )

            libro_salida = guardar.call_args.args[0]
            hoja_reporte = libro_salida.active
            self.assertRegex(hoja_reporte["D1"].value, r"^FECHA: \d{2}/\d{2}/\d{2}$")
            self.assertEqual(hoja_reporte["A1"].value, "Codigo")
            self.assertEqual(hoja_reporte["C3"].value, "Línea")
            self.assertEqual(hoja_reporte["D3"].value, "DESCUENTO")
            self.assertEqual(
                [hoja_reporte.cell(4, columna).value for columna in range(1, 5)],
                [101, 2, "Producto con descuento", -2],
            )
            self.assertEqual(
                [hoja_reporte.cell(5, columna).value for columna in range(1, 5)],
                [202, None, "Producto sin descuento", None],
            )
            self.assertEqual(hoja_reporte["C6"].value, "TOTAL PRODUCTOS DESCONTADOS:")
            self.assertEqual(hoja_reporte["D6"].value, 1)
            self.assertEqual(hoja_reporte["A1"].fill.fgColor.rgb, "00D9EAF7")
            self.assertEqual(hoja_reporte["A1"].font.color.rgb, "0017365D")
            self.assertTrue(hoja_reporte["A1"].font.bold)
            self.assertGreaterEqual(hoja_reporte.column_dimensions["D"].width, 22)
            self.assertEqual(hoja_reporte["A3"].fill.fgColor.rgb, "00D9EAF7")
            self.assertEqual(hoja_reporte["A7"].fill.fgColor.rgb, "00EAF0F6")
            self.assertEqual(hoja_reporte["A8"].fill.fgColor.rgb, "00D9EAF7")
            self.assertEqual(hoja_reporte.max_column, 4)
            self.assertIn("D1:D2", {str(rango) for rango in hoja_reporte.merged_cells.ranges})
            valores_informe = [
                celda.value
                for fila in hoja_reporte.iter_rows()
                for celda in fila
                if celda.value is not None
            ]
            self.assertIn("PEDIDOS CON PRODUCTOS DESCONTADOS", valores_informe)
            self.assertIn("Cliente Ejemplo", valores_informe)
            self.assertIn("R-123", valores_informe)
            self.assertIn("PRODUCTOS NO DESCONTADOS - SIN COINCIDENCIA", valores_informe)
            self.assertIn("Producto sin coincidencia", valores_informe)
            self.assertIn("Producto no catalogado", valores_informe)
            self.assertEqual(hoja_reporte.freeze_panes, "A4")
            self.assertTrue(hoja_reporte.column_dimensions["B"].hidden)
            self.assertEqual(hoja_reporte["A4"].fill.fgColor.rgb, "00CCCCFF")
            self.assertEqual(hoja_reporte["D4"].fill.fgColor.rgb, "00FF8080")
            self.assertFalse(any("STOCK INICIAL" in str(valor).upper() for valor in valores_informe))
            self.assertFalse(any("STOCK FINAL" in str(valor).upper() for valor in valores_informe))
            self.assertEqual(
                len([fila for fila in range(4, hoja_reporte.max_row + 1)
                     if hoja_reporte.cell(fila, 1).value in (101, 202)]),
                2,
            )
            self.assertTrue(Path(guardar.call_args.args[1]).exists())
            self.assertEqual(ruta.read_bytes(), contenido_plantilla)


if __name__ == "__main__":
    unittest.main()
