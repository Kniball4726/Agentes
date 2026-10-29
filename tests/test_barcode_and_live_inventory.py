"""Pruebas unitarias para el campo cod_barras y el módulo de inventario en vivo con escáner."""

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import openpyxl

from src.product_store import ProductStore
from src.stock_manager import StockManager
from src.user_store import User


class BarcodeAndLiveInventoryTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.dir_path = Path(self.temp_dir.name)
        self.db_path = self.dir_path / "productos.sqlite3"
        self.excel_path = self.dir_path / "Productos.xlsx"

        # Crear plantilla Excel mínima
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Stock"
        ws.append(["CÓDIGO", "PRODUCTOS", "STOCK"])
        ws.append([])
        ws.append(["PROD-1", "Aceite 1L", 15])
        ws.append(["PROD-2", "Filtro Aire", 5])
        ws.append(["PROD-3", "Bujía Platino", 20])
        wb.save(self.excel_path)
        wb.close()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_product_store_barcode_column_and_methods(self):
        """Verifica la persistencia del campo cod_barras y sus métodos de consulta en ProductStore."""
        sm = StockManager(self.excel_path, ruta_base_datos=self.db_path)
        store = sm.product_store

        # 1. Asignar código de barras a un producto existente
        store.set_product_barcode("PROD-1", "7791234567890")
        prod = store.get_product("PROD-1")
        self.assertIsNotNone(prod)
        self.assertEqual(prod["cod_barras"], "7791234567890")

        # 2. Búsqueda por código de barras
        by_barcode = store.get_product_by_barcode("7791234567890")
        self.assertIsNotNone(by_barcode)
        self.assertEqual(by_barcode["code"], "PROD-1")

        # 3. Búsqueda dual (por SKU o por código de barras)
        found_by_sku = store.find_product_by_code_or_barcode("PROD-1")
        self.assertIsNotNone(found_by_sku)
        self.assertEqual(found_by_sku["code"], "PROD-1")

        found_by_barcode = store.find_product_by_code_or_barcode("7791234567890")
        self.assertIsNotNone(found_by_barcode)
        self.assertEqual(found_by_barcode["code"], "PROD-1")

        # 4. Búsqueda de código inexistente devuelve None
        self.assertIsNone(store.find_product_by_code_or_barcode("9999999999999"))

    def test_stock_manager_barcode_integration(self):
        """Verifica que StockManager interactúe correctamente con el código de barras."""
        sm = StockManager(self.excel_path, ruta_base_datos=self.db_path)

        # Asignar código de barras
        sm.asignar_codigo_barras("PROD-2", "8809876543210")
        res = sm.buscar_producto_por_codigo_o_barras("8809876543210")
        self.assertIsNotNone(res)
        self.assertEqual(res["code"], "PROD-2")

        # Editar producto actualizando código de barras
        sm.actualizar_producto(
            codigo_actual="PROD-2",
            codigo_nuevo="PROD-2",
            nombre="Filtro Aire Premium",
            stock=8,
            stock_minimo=3,
            stock_maximo=50,
            cod_barras="8809876543211",
        )
        res_edit = sm.buscar_producto_por_codigo_o_barras("8809876543211")
        self.assertIsNotNone(res_edit)
        self.assertEqual(res_edit["name"], "Filtro Aire Premium")
        self.assertEqual(res_edit["stock"], 8)

    def test_live_inventory_difference_calculation_and_report(self):
        """Simula el relevamiento físico de inventario y la generación del informe de diferencias."""
        sm = StockManager(self.excel_path, ruta_base_datos=self.db_path)
        sm.asignar_codigo_barras("PROD-1", "7791234567890")
        sm.asignar_codigo_barras("PROD-2", "8809876543210")

        # Simular conteo físico escaneado:
        # PROD-1: digital 15 -> físico 15 (COINCIDE)
        # PROD-2: digital 5  -> físico 3  (FALTANTE -2)
        # PROD-3: digital 20 -> físico 22 (SOBRANTE +2)
        conteo_escaneado = {
            "PROD-1": 15,
            "PROD-2": 3,
            "PROD-3": 22,
        }

        salida_excel = self.dir_path / "Comparativa_Inventario_Test.xlsx"
        ruta_doc, comparativa = sm.procesar_stock_fisico(
            conteo_fisico=conteo_escaneado,
            usuario="operario_movil",
            nombre_archivo="Inventario_Escaner_Test.xlsx",
            ruta_salida=salida_excel,
        )

        self.assertTrue(ruta_doc.exists())
        self.assertEqual(len(comparativa), 3)

        estados = {item["code"]: item["estado"] for item in comparativa}
        self.assertEqual(estados["PROD-1"], "COINCIDE")
        self.assertEqual(estados["PROD-2"], "FALTANTE")
        self.assertEqual(estados["PROD-3"], "SOBRANTE")

        # Verificar que se creó la notificación al administrador
        notifs = sm.product_store.list_admin_notifications()
        self.assertTrue(len(notifs) >= 1)
        self.assertIn("operario_movil", notifs[0]["title"])

    def test_mostrar_dialogo_inventario_vivo_ui_controls(self):
        """Verifica que el diálogo de inventario en vivo se inicialice correctamente sin errores de atributos ni iconos."""
        from unittest.mock import MagicMock
        from src.ui.dialogs.dlg_inventario_vivo import mostrar_dialogo_inventario_vivo
        import flet as ft

        class FakePage:
            def __init__(self):
                self.dialogos = []
            def show_dialog(self, dlg):
                self.dialogos.append(dlg)
            def update(self):
                pass
            def pop_dialog(self):
                if self.dialogos:
                    return self.dialogos.pop()

        page = FakePage()
        interfaz_mock = MagicMock()
        interfaz_mock.page = page
        interfaz_mock.usuario_actual = User(1, "operador1", "operador", True)
        interfaz_mock.modo_oscuro = False
        interfaz_mock.borde = "#cccccc"
        interfaz_mock.fondo = "#ffffff"
        interfaz_mock.texto = "#000000"
        interfaz_mock.secundario = "#666666"

        sm = StockManager(self.excel_path, ruta_base_datos=self.db_path)
        with patch("src.ui.dialogs.dlg_inventario_vivo._get_stock_manager", return_value=lambda _ruta: sm):
            mostrar_dialogo_inventario_vivo(interfaz_mock)

        self.assertEqual(len(page.dialogos), 1)
        dlg = page.dialogos[0]
        self.assertIsInstance(dlg, ft.AlertDialog)

        # Simular escaneo de producto y controles optimizados para celulares
        col = dlg.content.content
        row_escaneo = col.controls[0]
        input_escaneo = row_escaneo.controls[0]
        row_acciones = col.controls[1]
        stepper_cantidad = row_acciones.controls[0]
        btn_sumar = row_acciones.controls[1]
        btn_camara = row_acciones.controls[2]

        self.assertEqual(input_escaneo.prefix_icon, ft.Icons.BARCODE_READER)
        self.assertEqual(btn_camara.url, "/scanner.html")

        # Probar stepper de cantidad
        btn_menos, input_cant, btn_mas = stepper_cantidad.controls
        btn_mas.on_click(None)
        self.assertEqual(input_cant.value, "2")
        btn_menos.on_click(None)
        self.assertEqual(input_cant.value, "1")

        # Poner código y ejecutar on_click del botón Sumar
        input_escaneo.value = "PROD-1"
        btn_sumar.on_click(None)

        # Verificar que la lista de contados tiene el item en el nuevo layout móvil
        lista_contados = col.controls[6]
        self.assertEqual(len(lista_contados.controls), 1)
