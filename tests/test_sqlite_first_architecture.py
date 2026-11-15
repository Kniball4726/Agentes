"""Pruebas para la arquitectura SQLite-First (SQLite como fuente única de verdad)."""

import sqlite3
import tempfile
import unittest
from pathlib import Path

import openpyxl

from src.inventory import StockManager
from src.inventory.excel_exporter import exportar_catalogo_a_excel
from src.products import ProductStore


class TestSQLiteFirstArchitecture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.temp_dir = Path(self.tmp.name)
        self.db_path = self.temp_dir / "productos.sqlite3"
        self.excel_path = self.temp_dir / "Productos.xlsx"

        # Crear una base SQLite con 3 productos
        self.store = ProductStore(self.db_path)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO products (code, name, stock, active, stock_minimo, stock_maximo, cod_barras, ubicacion)
                VALUES 
                    ('SKU-100', 'Producto Activo Uno', 50, 1, 5, 100, '779000100', 'A-01'),
                    ('SKU-200', 'Producto Activo Dos', 10, 1, 5, 50, '779000200', 'A-02'),
                    ('SKU-999', 'Producto Inactivo Viejo', 0, 0, 0, 0, '779000999', 'Z-99')
                """
            )
            conn.execute(
                """
                INSERT INTO product_catalog_rows (product_code, display_name, display_order, template_row)
                VALUES 
                    ('SKU-100', 'Producto Activo Uno', 1, 4),
                    ('SKU-200', 'Producto Activo Dos', 2, 5)
                """
            )
            conn.execute(
                "INSERT INTO product_catalog_metadata (key, value) VALUES ('template_imported', '1')"
            )

    def tearDown(self):
        import gc
        gc.collect()
        try:
            self.tmp.cleanup()
        except Exception:
            pass

    def test_stock_manager_inicia_sin_archivo_excel_fisico(self):
        # El archivo Productos.xlsx NO existe físicamente
        self.assertFalse(self.excel_path.exists())

        sm = StockManager(self.excel_path, ruta_base_datos=self.db_path)
        # Debe haber cargado directamente los 2 productos activos desde SQLite
        self.assertEqual(len(sm.catalogo), 2)
        self.assertIn("SKU-100", sm.catalogo)
        self.assertIn("SKU-200", sm.catalogo)
        self.assertNotIn("SKU-999", sm.catalogo)  # Inactivo no está en el catálogo operativo

    def test_sincronizar_stocks_opera_100_por_ciento_en_sqlite_sin_crear_excel(self):
        sm = StockManager(self.excel_path, ruta_base_datos=self.db_path)
        self.assertFalse(self.excel_path.exists())

        # Descontar stock
        actualizados = sm.sincronizar_stocks({"SKU-100": 42, "SKU-200": 8})
        self.assertEqual(actualizados, 2)

        # El stock en memoria y en SQLite debe estar actualizado inmediatamente
        self.assertEqual(sm.catalogo["SKU-100"][2], 42)
        self.assertEqual(sm.catalogo["SKU-200"][2], 8)
        p1 = sm.product_store.get_product("SKU-100")
        self.assertEqual(p1["stock"], 42)

        # El archivo Excel NO debe haberse creado ni bloqueado
        self.assertFalse(self.excel_path.exists())

    def test_exportar_catalogo_a_excel_genera_hojas_stock_e_inactivos(self):
        sm = StockManager(self.excel_path, ruta_base_datos=self.db_path)
        total_exportados = sm.exportar_catalogo_a_excel(self.excel_path)
        self.assertEqual(total_exportados, 2)
        self.assertTrue(self.excel_path.exists())

        wb = openpyxl.load_workbook(self.excel_path)
        self.assertIn("Stock", wb.sheetnames)
        self.assertIn("Inactivos", wb.sheetnames)

        hoja_stock = wb["Stock"]
        self.assertEqual(hoja_stock["A4"].value, "SKU-100")
        self.assertEqual(hoja_stock["B4"].value, "Producto Activo Uno")
        self.assertEqual(hoja_stock["C4"].value, 50)
        self.assertEqual(hoja_stock["E4"].value, 50)

        hoja_inactivos = wb["Inactivos"]
        self.assertEqual(hoja_inactivos["A4"].value, "SKU-999")
        self.assertEqual(hoja_inactivos["B4"].value, "Producto Inactivo Viejo")
        wb.close()

    def test_importar_catalogo_desde_excel_actualiza_sqlite(self):
        # Crear un archivo Excel con un producto nuevo y uno existente
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Stock"
        ws["A1"] = "Codigo"
        ws["B1"] = "Productos"
        ws["C1"] = "Descuento"
        ws["A3"] = "Codigo"
        ws["B3"] = "Productos"
        ws["C3"] = "Stock Inicial"
        ws["D3"] = "Descuento"
        ws["E3"] = "Stock Final"

        # Fila 4: SKU-100 con nuevo stock
        ws.cell(4, 1, "SKU-100")
        ws.cell(4, 2, "Producto Activo Uno Modificado")
        ws.cell(4, 3, 99)
        ws.cell(4, 5, 99)

        # Fila 5: SKU-300 nuevo
        ws.cell(5, 1, "SKU-300")
        ws.cell(5, 2, "Producto Nuevo Tres")
        ws.cell(5, 3, 15)
        ws.cell(5, 5, 15)
        wb.save(self.excel_path)
        wb.close()

        sm = StockManager(self.excel_path, ruta_base_datos=self.db_path)
        res = sm.importar_catalogo_desde_excel()

        self.assertEqual(res.importados, 2)
        # SKU-200 no estaba en el Excel importado, por lo que debe quedar inactivo
        p200 = sm.product_store.get_product("SKU-200")
        self.assertEqual(p200["active"], 0)

        # SKU-300 debe estar activo
        p300 = sm.product_store.get_product("SKU-300")
        self.assertEqual(p300["active"], 1)
        self.assertEqual(p300["stock"], 15)


if __name__ == "__main__":
    unittest.main()
