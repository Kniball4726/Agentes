"""Pruebas unitarias para la persistencia y diálogo de preferencias de usuario."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.ui.controllers.theme_controller import ThemeController
from src.ui.dialogs.dlg_preferencias import (
    _construir_opciones_impresoras,
    mostrar_dialogo_preferencias,
)
from src.ui.user_preferences import (
    guardar_preferencia_usuario,
    obtener_preferencias_usuario,
)


class TestUserPreferences(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name) / "preferencias_ui.json"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_obtener_preferencias_inexistente(self):
        """Verifica que devuelve dict vacío si no existe el archivo o el usuario."""
        with patch("src.ui.user_preferences._ruta_preferencias", return_value=self.temp_path):
            prefs = obtener_preferencias_usuario("usuario_inexistente")
            self.assertEqual(prefs, {})

    def test_guardar_y_obtener_preferencia(self):
        """Verifica el guardado y recuperación de preferencias de tema y sección abierta."""
        with patch("src.ui.user_preferences._ruta_preferencias", return_value=self.temp_path):
            guardar_preferencia_usuario("operador1", "modo_oscuro", False)
            guardar_preferencia_usuario("operador1", "seccion_abierta", "CLIENTES")
            guardar_preferencia_usuario("admin", "modo_oscuro", True)

            prefs_op = obtener_preferencias_usuario("operador1")
            self.assertFalse(prefs_op.get("modo_oscuro"))
            self.assertEqual(prefs_op.get("seccion_abierta"), "CLIENTES")

            prefs_admin = obtener_preferencias_usuario("admin")
            self.assertTrue(prefs_admin.get("modo_oscuro"))

    def test_construir_opciones_impresoras_deduplica_y_valida(self):
        """Verifica deduplicación de impresoras y respaldo cuando la guardada no existe."""
        opciones, valor = _construir_opciones_impresoras(
            ["Zebra ZD220", "Zebra ZD220", "HP Laser"],
            "Zebra ZD220",
        )
        self.assertEqual(len(opciones), 3)
        self.assertEqual(valor, "Zebra ZD220")

        opciones_missing, valor_missing = _construir_opciones_impresoras(
            ["HP Laser"],
            "Zebra Desconectada",
        )
        self.assertEqual(len(opciones_missing), 2)
        self.assertEqual(valor_missing, "")

    def test_mostrar_dialogo_preferencias_abre_y_guarda_cambios(self):
        """Verifica que Preferencias de Interfaz abra sin errores e interactúe con controles."""
        interfaz = MagicMock()
        interfaz.usuario_actual = MagicMock(username="operador1")
        interfaz.modo_oscuro = True
        interfaz.posicion_sidebar = "posicion_invalida"
        interfaz.texto = "#FFFFFF"
        interfaz.secundario = "#AAAAAA"
        interfaz.borde = "#333333"
        interfaz.page = MagicMock()

        def _toggle_tema():
            interfaz.modo_oscuro = not interfaz.modo_oscuro
            interfaz.texto = "#000000" if not interfaz.modo_oscuro else "#FFFFFF"

        interfaz.alternar_tema.side_effect = _toggle_tema

        with patch("src.ui.user_preferences._ruta_preferencias", return_value=self.temp_path), \
             patch(
                 "src.ui.dialogs.dlg_preferencias.listar_impresoras_sistema",
                 return_value=["Zebra ZD220", "Microsoft Print to PDF"],
             ):
            mostrar_dialogo_preferencias(interfaz)

            interfaz.page.show_dialog.assert_called_once()
            dialogo = interfaz.page.show_dialog.call_args[0][0]
            controles = dialogo.content.controls

            switch_tema = controles[3]
            dropdown_pos = controles[6]
            dropdown_imp = controles[9]
            switch_directa = controles[10]

            self.assertEqual(dropdown_pos.value, "izquierda")
            self.assertEqual(dropdown_imp.value, "")

            # Probar cambio de tema
            evento_tema = MagicMock()
            evento_tema.control.value = False
            switch_tema.on_change(evento_tema)
            interfaz.alternar_tema.assert_called_once()

            # Probar cambio de posición
            evento_pos = MagicMock()
            evento_pos.control.value = "arriba"
            dropdown_pos.on_select(evento_pos)
            interfaz.cambiar_posicion_sidebar.assert_called_once_with("arriba")

            # Probar selección de impresora e impresión directa
            evento_imp = MagicMock()
            evento_imp.control.value = "Zebra ZD220"
            dropdown_imp.on_select(evento_imp)

            evento_dir = MagicMock()
            evento_dir.control.value = True
            switch_directa.on_change(evento_dir)

            prefs = obtener_preferencias_usuario("operador1")
            self.assertFalse(prefs.get("modo_oscuro"))
            self.assertEqual(prefs.get("posicion_sidebar"), "arriba")
            self.assertEqual(prefs.get("impresora_termica"), "Zebra ZD220")
            self.assertTrue(prefs.get("impresion_directa"))

    def test_sonido_chat_preferencia_y_switch(self):
        """Verifica el interruptor de campana del chatbot y su restauración por ThemeController."""
        interfaz = MagicMock()
        interfaz.usuario_actual = MagicMock(username="operador1")
        interfaz.modo_oscuro = True
        interfaz.posicion_sidebar = "izquierda"
        interfaz.sonido_chat_activo = True
        interfaz._prefs_cargadas_usuario = False
        interfaz.texto = "#FFFFFF"
        interfaz.secundario = "#AAAAAA"
        interfaz.borde = "#333333"
        interfaz.page = MagicMock()

        with patch("src.ui.user_preferences._ruta_preferencias", return_value=self.temp_path), \
             patch(
                 "src.ui.dialogs.dlg_preferencias.listar_impresoras_sistema",
                 return_value=[],
             ):
            mostrar_dialogo_preferencias(interfaz)
            dialogo = interfaz.page.show_dialog.call_args[0][0]
            switch_sonido = dialogo.content.controls[13]
            self.assertTrue(switch_sonido.value)

            ev_mute = MagicMock()
            ev_mute.control.value = False
            switch_sonido.on_change(ev_mute)

            self.assertFalse(interfaz.sonido_chat_activo)
            prefs = obtener_preferencias_usuario("operador1")
            self.assertFalse(prefs.get("sonido_chat_activo"))

            interfaz.sonido_chat_activo = True
            ThemeController(interfaz).aplicar_preferencias_usuario(interfaz.usuario_actual)
            self.assertFalse(interfaz.sonido_chat_activo)


if __name__ == "__main__":
    unittest.main()
