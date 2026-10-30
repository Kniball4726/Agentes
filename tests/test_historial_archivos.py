"""Tests unitarios para la visualización, consulta y reimpresión de comprobantes en el Historial de Pedidos."""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import flet as ft

from src.orders_store import Pedido
from src.ui.dialogs.dlg_historial_pedidos import (
    abrir_comprobante_pedido,
    abrir_descuento_pedido,
    buscar_archivo_comprobante,
    buscar_archivo_descuento,
    mostrar_detalle_pedido_modal,
    mostrar_historial_pedidos,
)


class TestHistorialArchivosComprobantes(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "data" / "pedidos_archivos").mkdir(parents=True, exist_ok=True)
        (self.root / "Descuentos").mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        self.tmp.cleanup()

    def test_buscar_archivo_comprobante_en_pedidos_archivos(self):
        archivo_test = self.root / "data" / "pedidos_archivos" / "Remito_10542.pdf"
        archivo_test.write_bytes(b"%PDF-1.4 test")

        pedido = Pedido(
            id=1,
            nota_pedido="R-10542",
            numero_pedido="10542",
            cliente="Electrónica Sur",
            bultos=2,
            logistica="Transporte",
            armador="Juan",
            tipo_archivo="pdf",
            nombre_archivo="Remito_10542.pdf",
            agregado=False,
            articulos_descontados=5,
            resumen_items="5x Sensor",
            created_at="2026-10-29 10:00:00",
            estado="descontado",
        )

        with patch("src.ui.dialogs.dlg_historial_pedidos.application_root", return_value=self.root):
            encontrado = buscar_archivo_comprobante(pedido)
            self.assertIsNotNone(encontrado)
            self.assertEqual(encontrado, archivo_test)

    def test_buscar_archivo_comprobante_inexistente(self):
        pedido = Pedido(
            id=2,
            nota_pedido="R-99999",
            numero_pedido="99999",
            cliente="Cliente Desconocido",
            bultos=1,
            logistica="Retiro",
            armador="Pedro",
            tipo_archivo="pdf",
            nombre_archivo="NoExiste.pdf",
            agregado=False,
            articulos_descontados=1,
            resumen_items="1x Cable",
            created_at="2026-10-29 11:00:00",
            estado="descontado",
        )

        with patch("src.ui.dialogs.dlg_historial_pedidos.application_root", return_value=self.root):
            encontrado = buscar_archivo_comprobante(pedido)
            self.assertIsNone(encontrado)

    def test_abrir_comprobante_pedido_llama_abrir_informe(self):
        archivo_test = self.root / "data" / "pedidos_archivos" / "Canje_882.xlsx"
        archivo_test.write_bytes(b"PK test excel")

        pedido = Pedido(
            id=3,
            nota_pedido="C-882",
            numero_pedido="882",
            cliente="Distribuidora Central",
            bultos=1,
            logistica="Transporte",
            armador="Ana",
            tipo_archivo="excel",
            nombre_archivo="Canje_882.xlsx",
            agregado=False,
            articulos_descontados=10,
            resumen_items="10x Resistencia",
            created_at="2026-10-29 12:00:00",
            estado="descontado",
        )

        mock_interfaz = MagicMock()
        with patch("src.ui.dialogs.dlg_historial_pedidos.application_root", return_value=self.root):
            abrir_comprobante_pedido(mock_interfaz, pedido)
            mock_interfaz.abrir_informe.assert_called_once_with(ruta_especifica=archivo_test)

    def test_abrir_comprobante_inexistente_notifica(self):
        pedido = Pedido(
            id=4,
            nota_pedido="C-404",
            numero_pedido="404",
            cliente="Inexistente",
            bultos=1,
            logistica="Retiro",
            armador="Ana",
            tipo_archivo="excel",
            nombre_archivo="FaltaArchivo.xlsx",
            agregado=False,
            articulos_descontados=1,
            resumen_items="1x Item",
            created_at="2026-10-29 12:30:00",
            estado="descontado",
        )

        mock_interfaz = MagicMock()
        with patch("src.ui.dialogs.dlg_historial_pedidos.application_root", return_value=self.root):
            abrir_comprobante_pedido(mock_interfaz, pedido)
            mock_interfaz.notificar.assert_called_once()
            mock_interfaz.abrir_informe.assert_not_called()

    def test_mostrar_detalle_pedido_modal_construye_dialogo(self):
        archivo_test = self.root / "data" / "pedidos_archivos" / "Pedido_Doc.docx"
        archivo_test.write_bytes(b"DOCX test")

        pedido = Pedido(
            id=5,
            nota_pedido="ML-771",
            numero_pedido="771",
            cliente="Mercado Libre Usuario",
            bultos=1,
            logistica="Transporte",
            armador="Carlos",
            tipo_archivo="docx",
            nombre_archivo="Pedido_Doc.docx",
            agregado=False,
            articulos_descontados=2,
            resumen_items="2x Modulo WiFi",
            created_at="2026-10-29 14:00:00",
            estado="descontado",
            archivo_descuento="Descuento_20261029.pdf",
        )

        page_mock = MagicMock()
        interfaz_mock = MagicMock()
        interfaz_mock.page = page_mock
        interfaz_mock.modo_oscuro = True
        interfaz_mock.texto = ft.Colors.WHITE
        interfaz_mock.secundario = ft.Colors.GREY_400
        interfaz_mock.fondo = ft.Colors.BLACK
        interfaz_mock.fondo_acento = ft.Colors.GREY_900
        interfaz_mock.borde = ft.Colors.GREY_800

        with patch("src.ui.dialogs.dlg_historial_pedidos.application_root", return_value=self.root):
            mostrar_detalle_pedido_modal(interfaz_mock, pedido)
            page_mock.show_dialog.assert_called_once()
            dialogo = page_mock.show_dialog.call_args[0][0]
            self.assertIsInstance(dialogo, ft.AlertDialog)


if __name__ == "__main__":
    unittest.main()
