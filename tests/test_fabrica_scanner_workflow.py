import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock
import flet as ft

from src.orders_store import OrderStore
from src.product_store import ProductStore
from src.stock_manager import StockManager
from src.ui.dialogs.dlg_stock_ops import mostrar_ingreso_fabrica
from src.ui.components.sidebar import construir_sidebar_controls
from src.user_store import User


class TestFabricaScannerWorkflow(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.base_dir = Path(self.temp_dir.name)
        self.carpeta_fabrica = self.base_dir / "Descuentos" / "Fabrica"
        self.carpeta_fabrica.mkdir(parents=True, exist_ok=True)
        self.carpeta_desc = self.base_dir / "Descuentos" / "descontados"
        self.carpeta_desc.mkdir(parents=True, exist_ok=True)

        self.db_path = self.base_dir / "pedidos.sqlite3"
        self.order_store = OrderStore(self.db_path)

        # Configurar ProductStore con productos de prueba
        self.prod_db_path = self.base_dir / "productos.sqlite3"
        self.product_store = ProductStore(self.prod_db_path)
        with self.product_store._connect() as conn:
            conn.execute(
                "INSERT INTO products (code, name, stock, cod_barras) VALUES (?, ?, ?, ?)",
                ("TERM-01", "Termo Acero 1L", 10, "7791234567890"),
            )
            conn.execute(
                "INSERT INTO products (code, name, stock, cod_barras) VALUES (?, ?, ?, ?)",
                ("MATE-02", "Mate Uruguayo Camionero", 24, "7799876543210"),
            )
            conn.commit()

        self.excel_base = self.base_dir / "Productos.xlsx"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_sidebar_operador_has_ingreso_fabrica(self):
        """Verifica que el rol operador tenga el botón de Ingreso de Fábrica en el menú lateral."""
        interfaz = MagicMock()
        interfaz.usuario_actual = User(
            id=2, username="operador1", role="operador",
            active=True, must_change_password=False, nombre="Operario Depósito", email="op@test.com"
        )
        interfaz.modo_oscuro = True
        interfaz.borde = ft.Colors.GREY
        interfaz.texto = ft.Colors.WHITE
        interfaz.secundario = ft.Colors.GREY

        # Fake interfaz.boton que guarde el texto del botón
        botones_creados = []
        def fake_boton(texto, icono, handler):
            btn = ft.Button(content=texto)
            btn.data = handler
            botones_creados.append(texto)
            return btn

        interfaz.boton = fake_boton
        controls = construir_sidebar_controls(interfaz)
        self.assertIn("Ingreso de Fábrica", botones_creados)

    def test_operador_scanner_view_and_batch_buttons(self):
        """Verifica que el operador abra la vista exclusiva de escáner con botonera x12 y steppers +/-."""
        dialogo_capturado = None
        def capturar_dialogo(d):
            nonlocal dialogo_capturado
            dialogo_capturado = d

        interfaz = MagicMock()
        interfaz.exigir_roles.return_value = True
        interfaz.usuario_actual = User(
            id=2, username="operador1", role="operador",
            active=True, must_change_password=False, nombre="Operario Depósito", email="op@test.com"
        )
        interfaz.menu.carpeta_fabrica = self.carpeta_fabrica
        interfaz.menu.carpeta_descontados = self.carpeta_desc
        interfaz.menu.ruta_excel_base = self.excel_base
        def fake_ejecutar_tarea(nombre, func):
            func()
            return True

        interfaz.ejecutar_tarea = fake_ejecutar_tarea
        interfaz.menu._obtener_pendientes_fabrica.return_value = []
        interfaz.order_store = self.order_store
        interfaz.page.show_dialog = capturar_dialogo
        interfaz.secundario = ft.Colors.GREY
        interfaz.texto = ft.Colors.WHITE
        interfaz.modo_oscuro = True

        mock_sm = MagicMock(spec=StockManager)
        mock_sm.product_store = self.product_store
        mock_sm.catalogo = {
            "TERM-01": (2, "Termo Acero 1L", 10),
            "MATE-02": (3, "Mate Uruguayo Camionero", 24),
        }
        mock_sm.registrar_ingreso_fabrica.return_value = {"TERM-01": (10, 22)}

        import src.ui.dialogs.dlg_stock_ops as mod_ops
        orig_get_sm = mod_ops._get_stock_manager
        mod_ops._get_stock_manager = lambda: (lambda _ruta: mock_sm)

        try:
            mostrar_ingreso_fabrica(interfaz)
            self.assertIsNotNone(dialogo_capturado)

            # Verificar título para operador
            title_row = dialogo_capturado.title
            self.assertIsInstance(title_row, ft.Row)
            self.assertIn("Ingreso de Fábrica", title_row.controls[1].value)

            # El contenido es directo (sin tabs de archivo ni checkbox de sobrescribir)
            content_container = dialogo_capturado.content
            self.assertIsInstance(content_container, ft.Container)
            vista_col = content_container.content.content
            self.assertIsInstance(vista_col, ft.Column)

            # Fila de lotes x12
            fila_multiplos = vista_col.controls[0]
            self.assertIsInstance(fila_multiplos, ft.Row)
            botones_x12 = [c.content for c in fila_multiplos.controls if isinstance(c, ft.Button)]
            self.assertIn("12", botones_x12)
            self.assertIn("24", botones_x12)
            self.assertIn("36", botones_x12)
            self.assertIn("48", botones_x12)
            self.assertIn("60", botones_x12)
            self.assertIn("120", botones_x12)

            # Fila de cantidad por lectura con steppers + y -
            fila_cant = vista_col.controls[1]
            btn_menos = fila_cant.controls[1]
            input_cant = fila_cant.controls[2]
            btn_mas = fila_cant.controls[3]
            self.assertEqual(input_cant.value, "12")

            # Probar stepper + (ej: 13 no múltiplo de 12)
            btn_mas.on_click(None)
            self.assertEqual(input_cant.value, "13")
            btn_menos.on_click(None)
            self.assertEqual(input_cant.value, "12")

            # Fila de escaneo
            fila_escaneo = vista_col.controls[2]
            input_codigo = fila_escaneo.controls[0]
            self.assertTrue(input_codigo.autofocus)

            # Escanear por código de barras de fábrica
            input_codigo.value = "7791234567890"
            input_codigo.on_submit(None)

            # Verificar que se actualizó el texto de feedback y la lista
            texto_feedback = vista_col.controls[3]
            self.assertIn("Termo Acero 1L", texto_feedback.value)
            self.assertIn("+12 un.", texto_feedback.value)
            self.assertIn("Stock actual: 10 → Con ingreso: 22", texto_feedback.value)

            # Lista de escaneo
            lista_view = vista_col.controls[6]
            self.assertEqual(len(lista_view.controls), 1)

            # Botón confirmar
            btn_confirmar = dialogo_capturado.actions[2]
            self.assertFalse(btn_confirmar.disabled)

            # Confirmar ingreso
            btn_confirmar.on_click(None)
            mock_sm.registrar_ingreso_fabrica.assert_called_once_with({"TERM-01": 12}, sobrescribir=False)
            interfaz.actualizar_estado.assert_called_once()
        finally:
            mod_ops._get_stock_manager = orig_get_sm

    def test_administrador_has_both_scanner_and_archivo_tabs(self):
        """Verifica que el administrador cuente con las pestañas de escáner y de archivos."""
        dialogo_capturado = None
        def capturar_dialogo(d):
            nonlocal dialogo_capturado
            dialogo_capturado = d

        interfaz = MagicMock()
        interfaz.exigir_roles.return_value = True
        interfaz.usuario_actual = User(
            id=1, username="admin1", role="administrador",
            active=True, must_change_password=False, nombre="Admin Principal", email="admin@test.com"
        )
        interfaz.menu.carpeta_fabrica = self.carpeta_fabrica
        interfaz.menu.carpeta_descontados = self.carpeta_desc
        interfaz.menu.ruta_excel_base = self.excel_base
        def fake_ejecutar_tarea(nombre, func):
            func()
            return True

        interfaz.ejecutar_tarea = fake_ejecutar_tarea
        interfaz.menu._obtener_pendientes_fabrica.return_value = []
        interfaz.page.show_dialog = capturar_dialogo
        interfaz.secundario = ft.Colors.GREY
        interfaz.texto = ft.Colors.WHITE
        interfaz.modo_oscuro = True

        mock_sm = MagicMock(spec=StockManager)
        mock_sm.product_store = self.product_store
        mock_sm.catalogo = {}

        import src.ui.dialogs.dlg_stock_ops as mod_ops
        orig_get_sm = mod_ops._get_stock_manager
        mod_ops._get_stock_manager = lambda: (lambda _ruta: mock_sm)

        try:
            mostrar_ingreso_fabrica(interfaz)
            self.assertIsNotNone(dialogo_capturado)

            # En admin el contenido tiene pestañas y modo sobrescribir
            col = dialogo_capturado.content
            self.assertIsInstance(col, ft.Column)
            # Primer control es el Checkbox de sobrescribir
            self.assertIsInstance(col.controls[0], ft.Checkbox)
            # Segundo control es la fila de pestañas
            tabs_row = col.controls[1]
            self.assertIsInstance(tabs_row, ft.Row)
            self.assertEqual(len(tabs_row.controls), 2)
            self.assertIn("Escáner", tabs_row.controls[0].content)
            self.assertIn("archivo", tabs_row.controls[1].content)
        finally:
            mod_ops._get_stock_manager = orig_get_sm


if __name__ == "__main__":
    unittest.main()
