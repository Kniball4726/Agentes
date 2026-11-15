"""Pruebas unitarias para la sincronización del estado inactivo de productos con Productos.xlsx."""

import tempfile
import unittest
from pathlib import Path
import openpyxl

from src.product_store import ProductStore
from src.stock_manager import StockManager


class TestExcelInactiveSync(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.excel_path = self.root / "Productos.xlsx"
        self.db_path = self.root / "productos.sqlite3"

        # Crear un archivo Excel inicial con 2 productos: P01 y P02
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["CÓDIGO", "PRODUCTOS", "STOCK"])
        ws.append([])
        ws.append([])
        ws.append(["P01", "Producto Uno", 100])
        ws.append(["P02", "Producto Dos", 200])
        wb.save(self.excel_path)

        # Inicializar StockManager
        self.sm = StockManager(self.excel_path, ruta_base_datos=self.db_path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_productos_iniciales_estan_activos(self):
        productos = self.sm.product_store.list_products()
        mapa = {p["code"]: p["active"] for p in productos}
        self.assertEqual(mapa.get("P01"), 1)
        self.assertEqual(mapa.get("P02"), 1)

    def test_producto_eliminado_de_excel_queda_inactivo_al_importar(self):
        # 1. Agregar un tercer producto directamente en la base de datos (activo)
        self.sm.product_store.add_product_after(
            code="P03",
            name="Producto Tres Exclusivo DB",
            reference_code="P02",
            stock=50,
            synchronize_template=lambda _pos: [],
            restore_template=lambda: None,
        )
        self.assertEqual(self.sm.product_store.get_product("P03")["active"], 1)

        # En el Excel solo están P01 y P02 (P03 no existe en el Excel)
        # 2. Ejecutar importar_catalogo_desde_excel()
        res = self.sm.importar_catalogo_desde_excel()
        self.assertGreaterEqual(res.importados, 2)
        self.assertGreaterEqual(res.desactivados, 1)

        # 3. Verificar que P03 ahora está inactivo en la base de datos
        p03_db = self.sm.product_store.get_product("P03")
        self.assertEqual(p03_db["active"], 0)

        # P01 y P02 deben seguir activos
        self.assertEqual(self.sm.product_store.get_product("P01")["active"], 1)
        self.assertEqual(self.sm.product_store.get_product("P02")["active"], 1)

        # 4. Verificar que P03 no está en el catálogo en memoria de StockManager
        self.assertNotIn("P03", self.sm.catalogo)

    def test_producto_inactivo_se_reactiva_si_reaparece_en_excel(self):
        # Desactivar P01 manualmente
        self.sm.product_store.set_product_active("P01", False)
        self.assertEqual(self.sm.product_store.get_product("P01")["active"], 0)

        # Al importar desde Excel (donde P01 sigue presente en la planilla)
        res = self.sm.importar_catalogo_desde_excel()
        self.assertEqual(self.sm.product_store.get_product("P01")["active"], 1)
        self.assertIn("P01", self.sm.catalogo)

    def test_volcado_a_excel_desactiva_productos_ausentes(self):
        # Agregar P04 solo en SQLite
        self.sm.product_store.add_product_after(
            code="P04",
            name="Producto Cuatro",
            reference_code="P02",
            stock=30,
            synchronize_template=lambda _pos: [],
            restore_template=lambda: None,
        )
        self.assertEqual(self.sm.product_store.get_product("P04")["active"], 1)

        # Volcar catálogo hacia Excel
        self.sm.sincronizar_catalogo_completo_excel()

        # P04 no estaba en Excel, por lo que debe quedar inactivo
        p04_db = self.sm.product_store.get_product("P04")
        self.assertEqual(p04_db["active"], 0)
        self.assertNotIn("P04", self.sm.catalogo)


if __name__ == "__main__":
    unittest.main()
