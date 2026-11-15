"""Pruebas unitarias para el diálogo de sincronización con Productos.xlsx."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock

import flet as ft
from src.ui.dialogs.dlg_sincronizar_excel import mostrar_dialogo_sincronizar_excel
from tests.test_flet_gui import FakeMenu, FakePage, InterfazFlet


class TestSincronizarExcelDialog(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.page = FakePage()
        self.menu = FakeMenu()
        self.menu.ruta_excel_base = self.root / "Productos.xlsx"
        self.interfaz = InterfazFlet(self.page)
        self.interfaz.menu = self.menu
        self.interfaz.usuario_actual = MagicMock(role="administrador", active=True, username="admin1")
        self.page.dialogos.clear()

    def tearDown(self):
        self.tmp.cleanup()

    def test_mostrar_dialogo_abre_modal(self):
        mostrar_dialogo_sincronizar_excel(self.interfaz)
        self.assertEqual(len(self.page.dialogos), 1)
        dlg = self.page.dialogos[0]
        self.assertIn("Sincronización con Productos.xlsx", dlg.title.controls[1].value)

    def test_operador_no_puede_abrir_dialogo(self):
        self.interfaz.usuario_actual = MagicMock(role="operador", active=True, username="oper1")
        mostrar_dialogo_sincronizar_excel(self.interfaz)
        # No debe abrir el modal de sincronización, sino el aviso de permisos
        self.assertEqual(len(self.page.dialogos), 1)
        dlg = self.page.dialogos[0]
        self.assertEqual(dlg.title.value, "Aviso")
        self.assertIn("permiso", dlg.content.value)


if __name__ == "__main__":
    unittest.main()
