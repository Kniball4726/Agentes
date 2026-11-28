"""Tests unitarios para el diálogo de opciones de Windows (Descargar o Imprimir documentos)."""

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.ui.dialogs.dlg_document_options import (
    mostrar_dialogo_opciones_documento,
    _formatear_tamano,
)


class TestDocumentOptionsDialog(unittest.TestCase):
    def setUp(self):
        self.mock_interfaz = MagicMock()
        self.mock_interfaz.page = MagicMock()
        self.mock_interfaz.page.web = False
        self.mock_interfaz.modo_oscuro = True
        self.mock_interfaz.es_pantalla_movil = False
        self.mock_interfaz.texto = "#FFFFFF"
        self.mock_interfaz.secundario = "#90A4AE"
        self.mock_interfaz.borde = "#37474F"

        # Archivo temporal ficticio
        self.temp_file = Path("test_documento_opciones.pdf")
        self.temp_file.write_bytes(b"%PDF-1.4 test content")

        self.temp_excel = Path("test_documento_opciones.xlsx")
        self.temp_excel.write_bytes(b"PK test excel content")

    def tearDown(self):
        if self.temp_file.exists():
            self.temp_file.unlink()
        if self.temp_excel.exists():
            self.temp_excel.unlink()

    def test_formatear_tamano(self):
        self.assertEqual(_formatear_tamano(500), "500 B")
        self.assertEqual(_formatear_tamano(2048), "2.0 KB")
        self.assertEqual(_formatear_tamano(2 * 1024 * 1024), "2.0 MB")

    def test_documento_inexistente_notifica(self):
        ruta_falsa = Path("no_existe_archivo.pdf")
        mostrar_dialogo_opciones_documento(self.mock_interfaz, ruta_falsa)
        self.mock_interfaz.notificar.assert_called_once()
        self.mock_interfaz.page.show_dialog.assert_not_called()

    def test_documento_pdf_construye_dialogo_con_opciones(self):
        with patch("src.ui.dialogs.dlg_document_options.listar_impresoras_sistema", return_value=["Impresora Termica Zebra", "HP LaserJet"]):
            mostrar_dialogo_opciones_documento(self.mock_interfaz, self.temp_file)

        self.mock_interfaz.page.show_dialog.assert_called_once()
        dialogo = self.mock_interfaz.page.show_dialog.call_args[0][0]
        self.assertIsNotNone(dialogo)
        self.assertTrue("Opciones de Documento" in dialogo.title.controls[1].value)

    def test_documento_excel_construye_dialogo(self):
        with patch("src.ui.dialogs.dlg_document_options.listar_impresoras_sistema", return_value=[]):
            mostrar_dialogo_opciones_documento(self.mock_interfaz, self.temp_excel)
        self.mock_interfaz.page.show_dialog.assert_called_once()

    def test_interfaz_flet_tiene_mostrar_opciones_documento(self):
        from src.flet_gui import InterfazFlet
        self.assertTrue(hasattr(InterfazFlet, "mostrar_opciones_documento"))


if __name__ == "__main__":
    unittest.main()
