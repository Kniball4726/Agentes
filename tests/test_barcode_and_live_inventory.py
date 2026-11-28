"""Pruebas unitarias para el campo cod_barras y el módulo de inventario en vivo con escáner."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import openpyxl

from src.auth import User
from src.inventory import StockManager
from src.products import ProductStore


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

    def test_barcode_casting_variants_and_cross_instance_cache(self):
        """Valida casteo int/float, variantes HID ES/LA, ceros a la izquierda y caché entre instancias."""
        import sqlite3
        from contextlib import closing
        from src.products.barcode_utils import (
            coincide_codigo_o_barras,
            generar_variantes_codigo_lector,
            normalizar_codigo_lector,
        )

        # 1. Casteo seguro de tipos int / float / NaN / AIM / Code-39
        self.assertEqual(normalizar_codigo_lector(7791234567890), "7791234567890")
        self.assertEqual(normalizar_codigo_lector(7791234567890.0), "7791234567890")
        self.assertEqual(normalizar_codigo_lector("2156.0\r\n"), "2156")
        self.assertEqual(normalizar_codigo_lector("]C1*UT-100*\n"), "UT-100")
        self.assertEqual(normalizar_codigo_lector(float("nan")), "")
        self.assertIn("UT-100", generar_variantes_codigo_lector("+C1UT'100"))
        self.assertIn("012345678905", generar_variantes_codigo_lector("0012345678905"))

        StockManager(self.excel_path, ruta_base_datos=self.db_path)
        store_escritura = ProductStore(self.db_path)
        store_lectura = ProductStore(self.db_path)

        # 2. Búsqueda negativa previa no debe envenenar la caché tras asignar desde otra instancia
        self.assertIsNone(store_lectura.find_product_by_code_or_barcode("7790001112223"))
        store_escritura.set_product_barcode("PROD-1", 7790001112223)
        encontrado = store_lectura.find_product_by_code_or_barcode("]C17790001112223\r\n")
        self.assertIsNotNone(encontrado)
        self.assertEqual(encontrado["code"], "PROD-1")

        # 3. Variante de teclado US->ES/LA (' en lugar de -) y case-insensitive sobre SKU
        por_teclado = store_lectura.find_product_by_code_or_barcode("prod'1")
        self.assertIsNotNone(por_teclado)
        self.assertEqual(por_teclado["code"], "PROD-1")

        # 4. UPC-A (12 dígitos con cero inicial) vs EAN-13 (13 dígitos con doble cero)
        store_escritura.set_product_barcode("PROD-2", "012345678905")
        por_ean = store_lectura.find_product_by_code_or_barcode("0012345678905")
        self.assertIsNotNone(por_ean)
        self.assertEqual(por_ean["code"], "PROD-2")

        # 5. Valores almacenados en SQLite con espacios, ".0" o tipo numérico entero
        with closing(sqlite3.connect(self.db_path)) as conn, conn:
            conn.execute(
                "UPDATE products SET cod_barras = ' 8887776665554.0 ' WHERE code = ?",
                ("PROD-3",),
            )
        por_float_db = store_lectura.find_product_by_code_or_barcode(8887776665554)
        self.assertIsNotNone(por_float_db)
        self.assertEqual(por_float_db["code"], "PROD-3")
        self.assertTrue(coincide_codigo_o_barras(por_float_db, "8887776665554.0"))

        with closing(sqlite3.connect(self.db_path)) as conn, conn:
            conn.execute(
                "UPDATE products SET cod_barras = '002156' WHERE code = ?",
                ("PROD-1",),
            )
        store_lectura.invalidar_cache()
        por_sin_ceros = store_lectura.find_product_by_code_or_barcode("2156")
        self.assertIsNotNone(por_sin_ceros)
        self.assertEqual(por_sin_ceros["code"], "PROD-1")
