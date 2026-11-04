import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock
import flet as ft

from src.orders_store import OrderStore
from src.product_store import ProductStore
from src.stock_manager import StockManager
from src.ui.dialogs.dlg_stock_ops import mostrar_descuento_mercado_libre
from src.user_store import User


class TestMercadoLibreScannerWorkflow(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.temp_dir.name)
        self.carpeta_ml = self.base_dir / "Descuentos" / "MercadoLibre"
        self.carpeta_ml.mkdir(parents=True, exist_ok=True)
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
                ("TERM-01", "Termo Acero 1L", 15, "7791234567890"),
            )
            conn.execute(
                "INSERT INTO products (code, name, stock, cod_barras) VALUES (?, ?, ?, ?)",
                ("MATE-02", "Mate Uruguayo Camionero", 20, "7799876543210"),
            )
            conn.commit()

        # Excel base mock
        self.excel_base = self.base_dir / "Productos.xlsx"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_scanner_tab_and_scanning_flow(self):
        """Verifica que el diálogo inicie en modo escáner y permita pistolear productos por código de barras o SKU."""
        dialogo_capturado = None
        def capturar_dialogo(d):
            nonlocal dialogo_capturado
            dialogo_capturado = d

        interfaz = MagicMock()
        interfaz.exigir_roles.return_value = True
        interfaz.usuario_actual = User(
            id=1, username="operador1", role="operador",
            active=True, must_change_password=False, nombre="Operario ML", email="op@test.com"
        )
        interfaz.menu.carpeta_mercado_libre = self.carpeta_ml
        interfaz.menu.carpeta_descontados = self.carpeta_desc
        interfaz.menu.ruta_excel_base = self.excel_base
        interfaz.order_store = self.order_store
        interfaz.page.show_dialog = capturar_dialogo
        interfaz.secundario = ft.Colors.GREY
        interfaz.texto = ft.Colors.WHITE
        interfaz.modo_oscuro = True
        interfaz.ancho_adaptable = lambda w: w

        # Mock de StockManager para la interfaz
        mock_sm = MagicMock(spec=StockManager)
        mock_sm.product_store = self.product_store
        mock_sm.catalogo = {
            "TERM-01": (2, "Termo Acero 1L", 15),
            "MATE-02": (3, "Mate Uruguayo Camionero", 20),
        }
        mock_sm.actualizar_stock_base = MagicMock(return_value=1)

        import src.ui.dialogs.dlg_stock_ops as mod_ops
        orig_get_sm = mod_ops._get_stock_manager
        mod_ops._get_stock_manager = lambda: (lambda _ruta: mock_sm)

        try:
            mostrar_descuento_mercado_libre(interfaz)
            self.assertIsNotNone(dialogo_capturado)

            # Verificar que tiene pestañas (Tabs)
            tabs = dialogo_capturado.content.content
            self.assertIsInstance(tabs, ft.Tabs)
            self.assertEqual(tabs.length, 2)

            # Controles de vista_escaner
            vista_escaner = tabs.content.controls[1].controls[0]
            self.assertIsInstance(vista_escaner, ft.Column)

            # Fila de inputs de escaneo
            fila_escaneo = vista_escaner.controls[1]
            input_codigo = fila_escaneo.controls[0]
            self.assertIsInstance(input_codigo, ft.TextField)
            self.assertTrue(input_codigo.autofocus)

            # 1. Escanear por código de barras de empaque (EAN-13)
            input_codigo.value = "7791234567890"
            input_codigo.on_submit(None)

            # Verificar feedback sonoro y mensaje
            interfaz.reproducir_sonido.assert_called_with("exito")
            texto_feedback = vista_escaner.controls[3]
            self.assertIn("TERM-01", texto_feedback.value)
            self.assertIn("Termo Acero 1L", texto_feedback.value)

            # 2. Escanear por SKU interno
            input_codigo.value = "MATE-02"
            input_codigo.on_submit(None)
            self.assertIn("MATE-02", texto_feedback.value)

            # 3. Escanear código inexistente
            input_codigo.value = "CODIGO_INEXISTENTE"
            input_codigo.on_submit(None)
            self.assertIn("no encontrado", texto_feedback.value)
            interfaz.reproducir_sonido.assert_called_with("error")

            # 4. Confirmar y Descontar el paquete
            async def mock_ejecutar_tarea(nombre, func):
                func()
                return True

            interfaz.ejecutar_tarea = mock_ejecutar_tarea
            btn_confirmar = dialogo_capturado.actions[0]
            self.assertEqual(btn_confirmar.content, "Confirmar y Descontar")

            # Ejecutar confirmación
            asyncio.run(btn_confirmar.on_click(None))

            # Verificar que se llamó actualizar_stock_base con los descuentos
            mock_sm.actualizar_stock_base.assert_called_once()
            descuentos_aplicados = mock_sm.actualizar_stock_base.call_args[1]["descuentos"]
            codigos_descontados = [d.codigo for d in descuentos_aplicados]
            self.assertIn("TERM-01", codigos_descontados)
            self.assertIn("MATE-02", codigos_descontados)

            # Verificar que el pedido se registró en OrderStore como tipo 'docx'
            pedidos_pendientes = self.order_store.listar_pedidos_pendientes_cierre()
            self.assertEqual(len(pedidos_pendientes), 1)
            ped = pedidos_pendientes[0]
            self.assertEqual(ped.tipo_archivo, "docx")
            self.assertEqual(ped.articulos_descontados, 2)
            self.assertEqual(ped.cliente, "Mercado Libre")

        finally:
            mod_ops._get_stock_manager = orig_get_sm


if __name__ == "__main__":
    unittest.main()
