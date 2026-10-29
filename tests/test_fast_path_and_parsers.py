"""
Pruebas unitarias para el mecanismo Fast-Path de StockManager (SQLite-First)
y el cierre seguro de descriptores de archivos en los parsers Excel.
"""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import openpyxl

from src.canjes_parser import parsear_canje_excel
from src.mercado_full_parser import parsear_archivo_mercado_full
from src.product_store import ProductStore
from src.stock_manager import StockManager


class FastPathAndParsersTests(unittest.TestCase):
    def test_stock_manager_fast_path_skips_openpyxl_when_template_imported(self):
        """Verifica que StockManager cargue directamente desde SQLite sin llamar a openpyxl."""
        with tempfile.TemporaryDirectory() as temp_dir:
            excel_path = Path(temp_dir) / "Productos.xlsx"
            db_path = Path(temp_dir) / "productos.sqlite3"

            wb = openpyxl.Workbook()
            ws = wb.active
            ws.append(["CÓDIGO", "PRODUCTOS", "STOCK"])
            ws.append([])
            ws.append(["P100", "Filtro Aire", 50])
            ws.append(["P200", "Bujía Platino", 30])
            wb.save(excel_path)
            wb.close()

            # 1. Primera instanciación: Debe importar desde Excel a SQLite
            sm1 = StockManager(excel_path, ruta_base_datos=db_path)
            self.assertIn("P100", sm1.catalogo)
            self.assertEqual(sm1.catalogo["P100"][2], 50)

            # Verificar que los metadatos de esquema quedaron guardados en SQLite
            store = ProductStore(db_path)
            self.assertTrue(store.is_template_imported())
            metadata = store.get_all_metadata()
            self.assertIn("col_codigo", metadata)
            self.assertIn("fila_inicio_datos", metadata)

            # 2. Segunda instanciación: Con openpyxl.load_workbook mockeado/espiado
            with patch("src.stock_manager.openpyxl.load_workbook") as mock_load:
                sm2 = StockManager(excel_path, ruta_base_datos=db_path)
                # openpyxl.load_workbook NO debió ser llamado gracias al fast-path
                mock_load.assert_not_called()
                self.assertIn("P100", sm2.catalogo)
                self.assertEqual(sm2.catalogo["P100"][2], 50)
                self.assertIn("P200", sm2.catalogo)
                self.assertEqual(sm2.catalogo["P200"][2], 30)

    def test_canjes_parser_closes_workbook_on_success_and_error(self):
        """Verifica que el parser de canjes cierre el workbook de openpyxl."""
        with tempfile.TemporaryDirectory() as temp_dir:
            excel_path = Path(temp_dir) / "Canje_Test.xlsx"
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.append(["Canje influencer"])
            ws.append(["Juan Pérez"])
            ws.append(["12345678"])
            ws.append([])
            ws.append(["PEDIDO", "CODIGO", "PRODUCTO"])
            ws.append([2, "P100", "Filtro Aire"])
            wb.save(excel_path)
            wb.close()

            resultado = parsear_canje_excel(excel_path)
            self.assertEqual(resultado.articulos_extraidos, 2)
            self.assertEqual(resultado.items[0].codigo, "P100")

    def test_mercado_full_parser_closes_workbook(self):
        """Verifica que el parser de Mercado Full procese y cierre el workbook."""
        with tempfile.TemporaryDirectory() as temp_dir:
            excel_path = Path(temp_dir) / "Full_Test.xlsx"
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.append(["SKU", "TITULO", "CANTIDAD"])
            ws.append(["SKU-1", "Aceite 10W40", 10])
            ws.append(["SKU-2", "Aceite 5W30", 5])
            wb.save(excel_path)
            wb.close()

            consolidado, items = parsear_archivo_mercado_full(excel_path)
            self.assertEqual(consolidado["SKU-1"], 10)
            self.assertEqual(consolidado["SKU-2"], 5)


if __name__ == "__main__":
    unittest.main()
