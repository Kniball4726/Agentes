"""Pruebas unitarias para el diálogo y gestión exclusiva de Claves API para el Rol Master."""

import unittest
from unittest.mock import MagicMock
import flet as ft

from src.ui.dialogs.dlg_api_keys import mostrar_dialogo_api_keys
from src.ui.components.sidebar import construir_sidebar_controls


class TestApiKeysDialog(unittest.TestCase):
    def setUp(self):
        self.interfaz = MagicMock()
        self.interfaz.texto = ft.Colors.WHITE
        self.interfaz.secundario = ft.Colors.GREY_400
        self.interfaz.superficie = ft.Colors.GREY_900
        self.interfaz.borde = ft.Colors.GREY_800
        self.interfaz.fondo_acento = ft.Colors.BLACK
        self.interfaz.modo_oscuro = True
        self.interfaz.es_pantalla_movil = False
        self.interfaz.page = MagicMock()
        self.interfaz.dialogo_mostrado = None

        def _mock_show_dialog(dlg):
            self.interfaz.dialogo_mostrado = dlg
            self.interfaz.page.dialog = dlg

        self.interfaz.page.show_dialog = MagicMock(side_effect=_mock_show_dialog)
        self.interfaz.page.pop_dialog = MagicMock()
        self.interfaz.boton_dialogo = lambda texto, on_click: ft.TextButton(texto, on_click=on_click)
        self.interfaz.boton = lambda texto, icono, accion: ft.Button(content=texto, icon=icono, on_click=accion)

        self.user_store = MagicMock()
        self.interfaz.user_store = self.user_store

    def test_acceso_restringido_solo_master(self):
        """Verifica que operario y administrador no puedan abrir el diálogo de claves API."""
        # 1. Operador
        self.interfaz.usuario_actual = MagicMock(role="operador", username="oper1")
        self.interfaz.exigir_roles = lambda *roles: "operador" in roles
        mostrar_dialogo_api_keys(self.interfaz)
        self.assertFalse(self.interfaz.page.show_dialog.called)

        # 2. Administrador
        self.interfaz.usuario_actual = MagicMock(role="administrador", username="admin1")
        self.interfaz.exigir_roles = lambda *roles: "administrador" in roles
        mostrar_dialogo_api_keys(self.interfaz)
        self.assertFalse(self.interfaz.page.show_dialog.called)

        # 3. Master -> Permitido
        self.interfaz.usuario_actual = MagicMock(role="master", username="master1")
        self.interfaz.exigir_roles = lambda *roles: "master" in roles
        self.user_store.list_api_keys.return_value = []
        mostrar_dialogo_api_keys(self.interfaz)
        self.assertTrue(self.interfaz.page.show_dialog.called)

    def test_sidebar_master_incluye_claves_api(self):
        """Verifica que el menú lateral del rol Master incluya la opción 'Claves de API Externas'."""
        self.interfaz.usuario_actual = MagicMock(role="master", username="master1")
        self.interfaz.exigir_roles = lambda *roles: "master" in roles

        controles = construir_sidebar_controls(self.interfaz)
        textos = []
        for c in controles:
            if isinstance(c, ft.ExpansionTile):
                for btn in getattr(c, "controls", []):
                    c_val = getattr(btn, "content", "")
                    if isinstance(c_val, str):
                        textos.append(c_val)

        self.assertIn("Claves de API Externas", textos)

    def test_sidebar_admin_y_operador_no_incluyen_claves_api(self):
        """Verifica que ni Admin ni Operador vean 'Claves de API Externas' en sus menús."""
        for rol in ("operador", "administrador"):
            self.interfaz.usuario_actual = MagicMock(role=rol, username=f"{rol}1")
            self.interfaz.exigir_roles = lambda *roles: rol in roles

            controles = construir_sidebar_controls(self.interfaz)
            textos = []
            for c in controles:
                if isinstance(c, ft.ExpansionTile):
                    for btn in getattr(c, "controls", []):
                        c_val = getattr(btn, "content", "")
                        if isinstance(c_val, str):
                            textos.append(c_val)

            self.assertNotIn("Claves de API Externas", textos)


if __name__ == "__main__":
    unittest.main()
