"""Tests unitarios para el Centro Unificado de Reportes (PDF y Excel)."""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import openpyxl

from src.stock.reportes_service import (
    generar_reporte_stock_critico,
    generar_reporte_catalogo_stock,
    generar_reporte_pedidos_despacho,
    generar_reporte_cierres_historicos,
)
from src.ui.dialogs.dlg_reportes import mostrar_centro_reportes
from src.orders import Pedido, CierreJornada


class TestReportesService(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.carpeta = Path(self.temp_dir.name)

        # Mock de ProductStore
        self.product_store = MagicMock()
        self.product_store.get_replenishment_analysis.return_value = [
            {
                "code": "PROD001",
                "name": "Tornillos 1/2",
                "stock": 0,
                "min_stock": 20,
                "suggested_order": 40,
                "status": "OUT_OF_STOCK",
                "ubicacion": "A-01",
            },
            {
                "code": "PROD002",
                "name": "Arandelas 3/4",
                "stock": 5,
                "min_stock": 15,
                "suggested_order": 25,
                "status": "CRITICAL",
                "ubicacion": "A-02",
            },
        ]
        self.product_store.list_products.return_value = [
            {
                "code": "PROD001",
                "name": "Tornillos 1/2",
                "stock": 100,
                "barcode": "7791234567890",
                "ubicacion": "A-01",
                "active": 1,
            },
            {
                "code": "PROD002",
                "name": "Tuercas 3/8",
                "stock": 50,
                "barcode": "7791234567891",
                "ubicacion": "B-03",
                "active": 1,
            },
        ]

        # Mock de OrderStore
        self.order_store = MagicMock()
        self.order_store.listar_pedidos.return_value = [
            Pedido(
                id=1,
                nota_pedido="0001-00012345",
                numero_pedido="NP-12345",
                cliente="Ferretería Central",
                bultos=3,
                logistica="Expreso Sur",
                armador="Carlos",
                tipo_archivo="pdf",
                nombre_archivo="Remito.pdf",
                agregado=True,
                articulos_descontados=10,
                resumen_items="PROD001 x10",
                created_at="2026-11-12 10:30:00",
                estado="cerrado",
                estado_despacho="armado",
            ),
        ]
        self.order_store.listar_cierres.return_value = [
            CierreJornada(
                id=1,
                usuario="Carlos",
                cantidad_pedidos=12,
                articulos_totales=35,
                resumen_pedidos="Resumen",
                archivo_pdf="Cierre_20261112.pdf",
                archivo_excel="Cierre_20261112.xlsx",
                created_at="2026-11-12 18:00:00",
            )
        ]

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_reporte_stock_critico_pdf(self):
        ruta_pdf = generar_reporte_stock_critico(
            product_store=self.product_store,
            carpeta_destino=self.carpeta,
            formato="pdf",
            usuario="AdminTest",
        )
        self.assertTrue(ruta_pdf.exists())
        self.assertEqual(ruta_pdf.suffix, ".pdf")
        self.assertGreater(ruta_pdf.stat().st_size, 500)

    def test_reporte_stock_critico_excel(self):
        ruta_xls = generar_reporte_stock_critico(
            product_store=self.product_store,
            carpeta_destino=self.carpeta,
            formato="xlsx",
            usuario="AdminTest",
        )
        self.assertTrue(ruta_xls.exists())
        self.assertEqual(ruta_xls.suffix, ".xlsx")

        wb = openpyxl.load_workbook(str(ruta_xls))
        self.assertIn("Stock Crítico", wb.sheetnames)
        ws = wb["Stock Crítico"]
        self.assertGreaterEqual(ws.max_row, 5)

    def test_reporte_catalogo_stock_pdf_y_excel(self):
        ruta_pdf = generar_reporte_catalogo_stock(
            product_store=self.product_store,
            carpeta_destino=self.carpeta,
            formato="pdf",
            usuario="AdminTest",
        )
        self.assertTrue(ruta_pdf.exists())

        ruta_xls = generar_reporte_catalogo_stock(
            product_store=self.product_store,
            carpeta_destino=self.carpeta,
            formato="excel",
            usuario="AdminTest",
        )
        self.assertTrue(ruta_xls.exists())
        wb = openpyxl.load_workbook(str(ruta_xls))
        self.assertIn("Catálogo Stock", wb.sheetnames)

    def test_reporte_pedidos_despacho_pdf_y_excel(self):
        ruta_pdf = generar_reporte_pedidos_despacho(
            order_store=self.order_store,
            carpeta_destino=self.carpeta,
            formato="pdf",
            usuario="OperadorTest",
        )
        self.assertTrue(ruta_pdf.exists())

        ruta_xls = generar_reporte_pedidos_despacho(
            order_store=self.order_store,
            carpeta_destino=self.carpeta,
            formato="xlsx",
            usuario="OperadorTest",
        )
        self.assertTrue(ruta_xls.exists())
        wb = openpyxl.load_workbook(str(ruta_xls))
        self.assertIn("Despacho Pedidos", wb.sheetnames)

    def test_reporte_cierres_historicos_pdf_y_excel(self):
        ruta_pdf = generar_reporte_cierres_historicos(
            order_store=self.order_store,
            carpeta_destino=self.carpeta,
            formato="pdf",
            usuario="AdminTest",
        )
        self.assertTrue(ruta_pdf.exists())

        ruta_xls = generar_reporte_cierres_historicos(
            order_store=self.order_store,
            carpeta_destino=self.carpeta,
            formato="xlsx",
            usuario="AdminTest",
        )
        self.assertTrue(ruta_xls.exists())
        wb = openpyxl.load_workbook(str(ruta_xls))
        self.assertIn("Cierres Históricos", wb.sheetnames)

    def test_mostrar_centro_reportes_dialogo(self):
        """Valida que la función visual instancie el diálogo modal correctamente."""
        dialogos_abiertos = []
        page = SimpleNamespace(
            show_dialog=lambda d: dialogos_abiertos.append(d),
            pop_dialog=lambda: None,
            update=lambda: None,
        )
        interfaz = SimpleNamespace(
            usuario_actual=SimpleNamespace(display_name="Operador Test"),
            product_store=self.product_store,
            order_store=self.order_store,
            page=page,
            secundario="#64748b",
            texto="#0f172a",
            borde="#cbd5e1",
            boton_dialogo=lambda txt, fn: txt,
            abrir_informe=MagicMock(),
        )

        mostrar_centro_reportes(interfaz)
        self.assertEqual(len(dialogos_abiertos), 1)
        dialogo = dialogos_abiertos[0]
        self.assertIsNotNone(dialogo.content)


if __name__ == "__main__":
    unittest.main()
