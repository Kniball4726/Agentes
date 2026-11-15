"""Pruebas unitarias para el panel y diálogo adaptativo de alerta de quiebre de stock."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock

import flet as ft
from src.ui.dialogs.dlg_quiebre import actualizar_alerta_quiebre, mostrar_detalle_quiebre
from tests.test_flet_gui import FakeMenu, FakePage, InterfazFlet


class TestAdaptiveQuiebrePanel(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.page = FakePage()
        self.page.width = 1200
        self.menu = FakeMenu()
        self.interfaz = InterfazFlet(self.page)
        self.interfaz.menu = self.menu
        self.interfaz.usuario_actual = MagicMock(role="administrador", active=True, username="admin1")
        self.interfaz.banner_alerta_quiebre = ft.Container(visible=False)
        self.page.dialogos.clear()

        self.criticos_muestra = [
            {
                "code": "PROD-01",
                "name": "Proteína Whey 1kg",
                "stock": 0,
                "stock_minimo": 10,
                "cantidad_sugerida_pedir": 50,
            },
            {
                "code": "PROD-02",
                "name": "Creatina Monohidrato 300g",
                "stock": 4,
                "stock_minimo": 15,
                "cantidad_sugerida_pedir": 30,
            },
            {
                "code": "PROD-03",
                "name": "BCAA 2:1:1 250g",
                "stock": -2,
                "stock_minimo": 8,
                "cantidad_sugerida_pedir": 20,
            },
        ]

    def tearDown(self):
        self.tmp.cleanup()

    def test_actualizar_alerta_quiebre_renderiza_banner_adaptativo_escritorio(self):
        self.page.width = 1280
        actualizar_alerta_quiebre(self.interfaz, self.criticos_muestra)

        self.assertTrue(self.interfaz.banner_alerta_quiebre.visible)
        contenido = self.interfaz.banner_alerta_quiebre.content
        self.assertIsInstance(contenido, ft.Column)
        # Fila principal con info y botones
        fila_principal = contenido.controls[0]
        self.assertIsInstance(fila_principal, ft.Row)

        # Verificar que NO existe el botón "Cargar pedido fábrica" y que sí está "Generar pedido fábrica"
        bloque_botones = fila_principal.controls[1]
        textos_botones = [
            str(getattr(b, "content", "") or getattr(b, "text", "") or "")
            for b in bloque_botones.controls
        ]
        self.assertIn("Generar pedido fábrica", textos_botones)
        self.assertNotIn("Cargar pedido fábrica", textos_botones)

    def test_actualizar_alerta_quiebre_renderiza_banner_adaptativo_movil(self):
        self.page.width = 375
        actualizar_alerta_quiebre(self.interfaz, self.criticos_muestra)

        self.assertTrue(self.interfaz.banner_alerta_quiebre.visible)
        contenido = self.interfaz.banner_alerta_quiebre.content
        self.assertIsInstance(contenido, ft.Column)
        # En móvil la estructura principal debe ser una columna para evitar desborde
        col_principal = contenido.controls[0]
        self.assertIsInstance(col_principal, ft.Column)

    def test_mostrar_detalle_quiebre_abre_modal_con_busqueda_y_filtros(self):
        mostrar_detalle_quiebre(self.interfaz, self.criticos_muestra)
        self.assertEqual(len(self.page.dialogos), 1)
        dlg = self.page.dialogos[0]
        self.assertIn("quiebre de stock", dlg.title.controls[1].value)

        # Verificar que el modal contiene la barra de búsqueda y los botones de filtro
        contenedor = dlg.content
        col_modal = contenedor.content
        self.assertTrue(any(isinstance(c, ft.Row) and any(isinstance(child, ft.TextField) for child in c.controls) for c in col_modal.controls))

        # Verificar que en las acciones no exista "Cargar ingreso fábrica"
        textos_acciones = [
            str(getattr(a, "content", "") or getattr(a, "text", "") or "")
            for a in dlg.actions
        ]
        self.assertIn("Generar pedido Excel", textos_acciones)
        self.assertNotIn("Cargar ingreso fábrica", textos_acciones)
        self.assertNotIn("Cargar pedido fábrica", textos_acciones)


if __name__ == "__main__":
    unittest.main()
