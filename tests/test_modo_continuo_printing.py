"""Tests para impresión directa por Spooler de Windows y Modo Pistoleo Continuo."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.ui.components.print_labels import (
    listar_impresoras_sistema,
    imprimir_directo_spooler,
    imprimir_rotulos_termicos_pedido_ui,
)


class TestModoContinuoPrinting(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

    def tearDown(self):
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    @patch("subprocess.run")
    def test_listar_impresoras_sistema(self, mock_subproc):
        """Verifica que el listado de impresoras del sistema parsee correctamente la salida de PowerShell."""
        mock_res = MagicMock()
        mock_res.returncode = 0
        mock_res.stdout = "Zebra ZD220\r\nMicrosoft Print to PDF\r\nOneNote for Windows 10\r\n"
        mock_subproc.return_value = mock_res

        impresoras = listar_impresoras_sistema()
        self.assertIn("Zebra ZD220", impresoras)
        self.assertIn("Microsoft Print to PDF", impresoras)
        self.assertEqual(len(impresoras), 3)

    @patch("subprocess.run")
    def test_imprimir_directo_spooler(self, mock_subproc):
        """Verifica que el envío al spooler invoque PowerShell Start-Process con verbo printto."""
        mock_res = MagicMock()
        mock_res.returncode = 0
        mock_subproc.return_value = mock_res

        dummy_pdf = self.temp_path / "etiqueta.pdf"
        dummy_pdf.write_bytes(b"%PDF-1.4 dummy")

        exito = imprimir_directo_spooler(dummy_pdf, "Zebra ZD220")
        self.assertTrue(exito)
        self.assertTrue(mock_subproc.called)

    def test_imprimir_rotulos_termicos_pedido_ui_directo(self):
        """Verifica que la UI intente impresión directa si está configurada en las preferencias del usuario."""
        interfaz = MagicMock()
        interfaz.usuario_actual = MagicMock()
        interfaz.usuario_actual.username = "operador1"
        interfaz.notificar = MagicMock()

        pedido_mock = MagicMock()
        pedido_mock.id = 101
        pedido_mock.bultos = 2
        pedido_mock.numero_pedido = "PED-101"
        pedido_mock.cliente = "Cliente Test"
        pedido_mock.logistica = "Transporte"

        with patch("src.ui.components.print_labels.generar_etiquetas_termicas_pdf") as mock_gen, \
             patch("src.ui.components.print_labels.obtener_preferencias_usuario") as mock_prefs, \
             patch("src.ui.components.print_labels.imprimir_directo_spooler", return_value=True) as mock_print:
            
            mock_prefs.return_value = {
                "impresion_directa": True,
                "impresora_termica": "Zebra ZD220",
            }
            dummy_pdf = self.temp_path / "rotulo_101.pdf"
            dummy_pdf.write_bytes(b"%PDF-1.4")
            mock_gen.return_value = dummy_pdf

            imprimir_rotulos_termicos_pedido_ui(interfaz, pedido_mock)
            self.assertTrue(mock_gen.called)
            self.assertTrue(mock_print.called)
            self.assertTrue(any("enviado a la impresora 'Zebra ZD220'" in str(call) for call in interfaz.notificar.call_args_list))


if __name__ == "__main__":
    unittest.main()
