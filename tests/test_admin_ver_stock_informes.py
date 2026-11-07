"""Pruebas unitarias para:
1. Accesos rápidos de Administrador (Gestionar Productos, Ingreso y Egreso).
2. Nuevo módulo 'Ver Stock' en diálogo, sidebar y command palette.
3. Corrección de la función abrir_informe (descargas web, apertura nativa y diálogo selector).
"""

from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

from src.user_store import User
from src.ui.components.panels import construir_panel_acceso_rapido
from src.ui.components.sidebar import obtener_secciones_rol
from src.ui.dialogs.dlg_ver_stock import mostrar_dialogo_ver_stock
from src.ui.dialogs.dlg_informes import mostrar_dialogo_informes


class TestAdminVerStockEInformes(unittest.TestCase):
    def setUp(self):
        self.admin_user = User(
            id=2,
            username="admin_test",
            role="administrador",
            active=True,
            nombre="Admin Test",
        )
        self.mock_interfaz = MagicMock()
        self.mock_interfaz.usuario_actual = self.admin_user
        self.mock_interfaz.es_pantalla_movil = False
        self.mock_interfaz.modo_oscuro = True
        self.mock_interfaz.superficie = "#1e1e1e"
        self.mock_interfaz.texto = "#ffffff"
        self.mock_interfaz.secundario = "#aaaaaa"
        self.mock_interfaz.borde = "#333333"
        self.mock_interfaz.ancho_adaptable = lambda w: w
        self.mock_interfaz.alto_adaptable = lambda h: h

    def test_panel_acceso_rapido_administrador_contiene_gestionar_productos(self):
        """Verifica que el panel de accesos rápidos de Administrador incluya Gestionar Productos, Ingreso y Egreso."""
        panel = construir_panel_acceso_rapido(self.mock_interfaz)
        self.assertTrue(panel.visible is not False)
        # Buscar títulos en el árbol de controles
        titulos_encontrados = []
        def _buscar_textos(ctrl):
            if hasattr(ctrl, "value") and ctrl.value:
                titulos_encontrados.append(ctrl.value)
            for hijo in getattr(ctrl, "controls", []) or []:
                _buscar_textos(hijo)
            if hasattr(ctrl, "content") and ctrl.content:
                _buscar_textos(ctrl.content)

        _buscar_textos(panel)
        self.assertIn("Gestionar Productos", titulos_encontrados)
        self.assertIn("Ingreso de Stock", titulos_encontrados)
        self.assertIn("Egreso de Stock", titulos_encontrados)

    def test_sidebar_administrador_contiene_ver_stock_en_catalogo(self):
        """Verifica que en el menú de navegación de Administrador exista 'Ver Stock' dentro de CATÁLOGO."""
        secciones = obtener_secciones_rol(self.mock_interfaz)
        sec_catalogo = next((s for s in secciones if s.titulo == "CATÁLOGO"), None)
        self.assertIsNotNone(sec_catalogo, "La sección CATÁLOGO debe existir para administrador")
        items_catalogo = [nombre for nombre, _, _ in sec_catalogo.items]
        self.assertIn("Ver Stock", items_catalogo)
        self.assertIn("Gestionar productos", items_catalogo)

    def test_modulo_ver_stock_renderiza_y_filtra(self):
        """Verifica que mostrar_dialogo_ver_stock abra el diálogo con los productos de ProductStore."""
        self.mock_interfaz.product_store = MagicMock()
        self.mock_interfaz.product_store.list_products.return_value = [
            {
                "code": "1001",
                "name": "Proteína Whey 1kg",
                "stock": 25,
                "stock_minimo": 10,
                "cod_barras": "7791234567890",
                "ubicacion": "Rack A-01",
            },
            {
                "code": "1002",
                "name": "Creatina Monohidrato 300g",
                "stock": 0,
                "stock_minimo": 5,
                "cod_barras": "7791234567891",
                "ubicacion": "Rack B-03",
            },
        ]

        mostrar_dialogo_ver_stock(self.mock_interfaz)
        self.mock_interfaz.page.show_dialog.assert_called_once()
        dlg = self.mock_interfaz.page.show_dialog.call_args[0][0]
        self.assertIsNotNone(dlg)

    def test_dialogo_informes_muestra_documentos_disponibles(self):
        """Verifica que mostrar_dialogo_informes muestre los informes generados por el menú."""
        self.mock_interfaz.menu = MagicMock()
        ruta_dummy = Path("Descuentos/descuentos/Cierre_20261106_180000.xlsx")
        with patch.object(Path, "exists", return_value=True), \
             patch.object(Path, "stat") as mock_stat:
            mock_stat.return_value = MagicMock(st_mtime=1700000000.0, st_size=15420)
            self.mock_interfaz.menu._obtener_generados.return_value = [ruta_dummy]
            mostrar_dialogo_informes(self.mock_interfaz)
            self.mock_interfaz.page.show_dialog.assert_called_once()

    def test_abrir_informe_en_flet_gui_web_y_desktop(self):
        """Verifica la lógica de abrir_informe para modo web (launch_url) y modo escritorio (os.startfile)."""
        from src.flet_gui import InterfazFlet

        interfaz = InterfazFlet.__new__(InterfazFlet)
        interfaz.page = MagicMock()
        interfaz.menu = MagicMock()
        interfaz.informes = []
        interfaz.informe_seleccionado = None
        interfaz.notificar = MagicMock()
        interfaz.exigir_roles = MagicMock(return_value=True)

        # 1. Cuando no hay informes generados
        interfaz.menu._obtener_generados.return_value = []
        interfaz.abrir_informe(ruta_especifica=None)
        interfaz.notificar.assert_called_with("Todavía no hay informes generados.")

        # 2. En modo Web con ruta específica existente
        interfaz.page.web = True
        ruta_fake = Path("test_informe.pdf")
        with patch.object(Path, "exists", return_value=True):
            interfaz.abrir_informe(ruta_especifica=ruta_fake)
            interfaz.page.launch_url.assert_called_once()
            url_llamada = interfaz.page.launch_url.call_args[0][0]
            self.assertTrue(url_llamada.startswith("/descargas/informes/test_informe.pdf"))

        # 3. En modo Escritorio con ruta específica existente
        interfaz.page.web = False
        with patch.object(Path, "exists", return_value=True), \
             patch("os.startfile") as mock_startfile:
            interfaz.abrir_informe(ruta_especifica=ruta_fake)
            mock_startfile.assert_called_once()


if __name__ == "__main__":
    unittest.main()
