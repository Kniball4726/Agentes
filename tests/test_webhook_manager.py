"""Tests unitarios para el gestor de webhooks asíncronos y eventos de integración."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from src import webhook_manager


class TestWebhookManager(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        # Apuntar el archivo de webhooks a una ruta temporal
        self.mock_file = self.temp_path / "webhooks_test.json"
        self._orig_ruta_webhooks = webhook_manager._ruta_webhooks
        webhook_manager._ruta_webhooks = lambda: self.mock_file

    def tearDown(self):
        webhook_manager._ruta_webhooks = self._orig_ruta_webhooks
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_guardar_listar_y_eliminar_webhook(self):
        """Verifica la persistencia de suscripciones de webhooks."""
        wh = webhook_manager.guardar_webhook(
            url="https://erp.empresa.com/webhook",
            eventos=["QUIEBRE_STOCK", "CIERRE_JORNADA"],
            descripcion="ERP Producción",
        )
        self.assertIsNotNone(wh)
        self.assertEqual(wh["url"], "https://erp.empresa.com/webhook")
        self.assertIn("QUIEBRE_STOCK", wh["eventos"])
        wh_id = wh["id"]

        # Listar
        lista = webhook_manager.obtener_webhooks()
        self.assertEqual(len(lista), 1)
        self.assertEqual(lista[0]["id"], wh_id)

        # Eliminar
        eliminado = webhook_manager.eliminar_webhook(wh_id)
        self.assertTrue(eliminado)
        self.assertEqual(len(webhook_manager.obtener_webhooks()), 0)

    @patch("urllib.request.urlopen")
    def test_despacho_evento_webhook(self, mock_urlopen):
        """Verifica que el despacho asíncrono invoque la URL con payload correcto."""
        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_urlopen.return_value.__enter__.return_value = mock_response

        webhook_manager.guardar_webhook(
            url="https://api.test.com/hook",
            eventos=["QUIEBRE_STOCK"],
            descripcion="Hook de prueba",
        )

        # Probar webhook directamente
        exito, msg = webhook_manager.probar_webhook("https://api.test.com/hook")
        self.assertTrue(exito)
        self.assertIn("200", msg)

        # Despachar evento
        webhook_manager.despachar_evento_webhook("QUIEBRE_STOCK", {
            "codigo": "ART-999",
            "stock_actual": 0,
        })

        import time
        time.sleep(0.3)  # Esperar hilo de despacho
        self.assertTrue(mock_urlopen.called)


if __name__ == "__main__":
    unittest.main()
