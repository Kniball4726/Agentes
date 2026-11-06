"""Pruebas unitarias para la persistencia de preferencias de usuario (user_preferences)."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.ui.user_preferences import (
    obtener_preferencias_usuario,
    guardar_preferencia_usuario,
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


if __name__ == "__main__":
    unittest.main()
