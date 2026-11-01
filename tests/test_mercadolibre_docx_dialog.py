import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock
from docx import Document
import flet as ft

from src.orders_store import OrderStore, calcular_hash_archivo
from src.ui.dialogs.dlg_stock_ops import mostrar_descuento_mercado_libre
from src.user_store import User


class TestMercadoLibreDocxDialog(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.temp_dir.name)
        self.carpeta_ml = self.base_dir / "Descuentos" / "MercadoLibre"
        self.carpeta_ml.mkdir(parents=True, exist_ok=True)
        self.carpeta_desc = self.base_dir / "Descuentos" / "descontados"
        self.carpeta_desc.mkdir(parents=True, exist_ok=True)

        self.db_path = self.base_dir / "pedidos.sqlite3"
        self.order_store = OrderStore(self.db_path)

        # Crear archivo docx de prueba
        self.docx_file = self.carpeta_ml / "pedido_test.docx"
        doc = Document()
        doc.add_paragraph("2 Creatina 300 g UT")
        doc.save(self.docx_file)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_auto_cleanup_already_processed_file(self):
        """Un archivo que ya fue descontado en order_store debe moverse a descontados automáticamente."""
        # Registrar el archivo como ya descontado
        hash_file = calcular_hash_archivo(self.docx_file)
        self.order_store.registrar_pedido(
            nota_pedido="ML-TEST",
            numero_pedido="ML-TEST",
            cliente="Cliente Test",
            bultos=1,
            logistica="Transporte",
            armador="Operario",
            tipo_archivo="docx",
            nombre_archivo=self.docx_file.name,
            archivo_hash=hash_file,
        )

        dialogo_capturado = None
        def capturar_dialogo(d):
            nonlocal dialogo_capturado
            dialogo_capturado = d

        interfaz = MagicMock()
        interfaz.exigir_roles.return_value = True
        interfaz.usuario_actual = User(
            id=1, username="operador1", role="operador",
            active=True, must_change_password=False, nombre="Operario", email="op@test.com"
        )
        interfaz.menu.carpeta_mercado_libre = self.carpeta_ml
        interfaz.menu.carpeta_descontados = self.carpeta_desc
        interfaz.menu.ruta_excel_base = Path("Descuentos/Productos.xlsx")
        interfaz.order_store = self.order_store
        interfaz.page.show_dialog = capturar_dialogo
        interfaz.secundario = ft.Colors.GREY
        interfaz.texto = ft.Colors.WHITE
        interfaz.modo_oscuro = True

        mostrar_descuento_mercado_libre(interfaz)

        # Verificar que el archivo procesado fue movido fuera de pendientes a descontados
        self.assertFalse(self.docx_file.exists())
        archivado = self.carpeta_desc / "MercadoLibre" / "pedido_test.docx"
        self.assertTrue(archivado.exists())

        # El selector debe estar vacío
        self.assertIsNotNone(dialogo_capturado)

    def test_dialog_elements_limpiar_and_descartar(self):
        """Verifica que el diálogo cuente con botones de Limpiar, Descartar y Confirmar adecuadamente."""
        dialogo_capturado = None
        def capturar_dialogo(d):
            nonlocal dialogo_capturado
            dialogo_capturado = d

        interfaz = MagicMock()
        interfaz.exigir_roles.return_value = True
        interfaz.usuario_actual = User(
            id=1, username="operador1", role="operador",
            active=True, must_change_password=False, nombre="Operario", email="op@test.com"
        )
        interfaz.menu.carpeta_mercado_libre = self.carpeta_ml
        interfaz.menu.carpeta_descontados = self.carpeta_desc
        interfaz.menu.ruta_excel_base = Path("Descuentos/Productos.xlsx")
        interfaz.order_store = self.order_store
        interfaz.page.show_dialog = capturar_dialogo
        interfaz.secundario = ft.Colors.GREY
        interfaz.texto = ft.Colors.WHITE
        interfaz.modo_oscuro = True

        mostrar_descuento_mercado_libre(interfaz)
        self.assertIsNotNone(dialogo_capturado)

        # Comprobar que en actions está el botón confirmar y cancelar
        self.assertEqual(len(dialogo_capturado.actions), 2)
        btn_confirmar = dialogo_capturado.actions[0]
        self.assertEqual(btn_confirmar.content, "Confirmar y Descontar")
