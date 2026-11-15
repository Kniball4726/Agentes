"""Tests de integración para arquitectura de reportes SQLite-Nativos, canales y cierre diario."""

from __future__ import annotations

import tempfile
import unittest
from contextlib import closing
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import openpyxl

from src.inventory import StockManager
from src.orders import OrderStore
from src.products import ProductStore
from src.stock.models import RegistroDescuento
from src.stock.reportes_service import (
    generar_reporte_auditoria_inventario_fisico,
    generar_reporte_descuento_operario_canales,
    generar_reporte_kardex_producto,
    generar_reporte_movimientos_estandar,
    generar_reporte_planilla_conteo_fisico,
    generar_reporte_rotacion_consumo,
)
from src.ui.dialogs.cierre.cierre_operario_exec import ejecutar_tarea_cierre_operario
from src.ui.dialogs.cierre.cierre_reportes_helper import generar_reporte_admin_para_cierre


class TestReportsMovementsArchitecture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.db_prod = self.root / "productos.sqlite3"
        self.db_ped = self.root / "pedidos.sqlite3"
        self.carpeta_desc = self.root / "Descuentos"
        self.carpeta_desc.mkdir(parents=True, exist_ok=True)
        self.excel_inexistente = self.root / "Productos_NoExiste.xlsx"

        self.product_store = ProductStore(self.db_prod)
        self.product_store.import_template_once(
            [
                (4, "SKU-A", "Producto Alpha", 50),
                (5, "SKU-B", "Producto Beta", 40),
                (6, "SKU-C", "Producto Gamma", 30),
                (7, "SKU-IDLE", "Producto Sin Movimiento", 100),
            ]
        )
        self.product_store.actualizar_ubicacion("SKU-A", "A-01")
        self.product_store.actualizar_ubicacion("SKU-B", "B-02")
        self.order_store = OrderStore(self.db_ped)

    def tearDown(self):
        self.tmp.cleanup()

    def test_canales_operario_discriminados_sin_filas_vacias(self):
        self.order_store.registrar_pedido(
            nota_pedido="REM-100",
            numero_pedido="100",
            cliente="Distribuidora Norte",
            bultos=2,
            logistica="Transporte",
            armador="oper1",
            tipo_archivo="pdf",
            nombre_archivo="Remito_100.pdf",
            articulos_descontados=15,
            items=[("SKU-A", "Producto Alpha", 10), ("SKU-B", "Producto Beta", 5)],
        )
        self.order_store.registrar_pedido(
            nota_pedido="ML-200",
            numero_pedido="ML-200",
            cliente="Mercado Libre",
            bultos=1,
            logistica="Transporte",
            armador="oper1",
            tipo_archivo="docx",
            nombre_archivo="ML_200.docx",
            articulos_descontados=5,
            items=[("SKU-A", "Producto Alpha", 3), ("SKU-C", "Producto Gamma", 2)],
        )
        self.order_store.registrar_pedido(
            nota_pedido="FULL-300",
            numero_pedido="ENV-300",
            cliente="Mercado Envíos Full",
            bultos=3,
            logistica="Transporte",
            armador="picker1",
            tipo_archivo="excel",
            nombre_archivo="Full_Pallet.xlsx",
            articulos_descontados=12,
            items=[("SKU-B", "Producto Beta", 12)],
        )

        canales = self.order_store.obtener_descuentos_operario_por_canal(solo_pendientes=True)
        mapa = {c["codigo"]: c for c in canales}
        self.assertEqual(set(mapa.keys()), {"SKU-A", "SKU-B", "SKU-C"})
        self.assertNotIn("SKU-IDLE", mapa)
        self.assertEqual((mapa["SKU-A"]["mayoristas"], mapa["SKU-A"]["mercado_libre"], mapa["SKU-A"]["full"]), (10, 3, 0))
        self.assertEqual((mapa["SKU-B"]["mayoristas"], mapa["SKU-B"]["mercado_libre"], mapa["SKU-B"]["full"]), (5, 0, 12))
        self.assertEqual((mapa["SKU-C"]["mayoristas"], mapa["SKU-C"]["mercado_libre"], mapa["SKU-C"]["full"]), (0, 2, 0))

        ruta_pdf = generar_reporte_descuento_operario_canales(
            items_canal=canales,
            carpeta_destino=self.carpeta_desc,
            formato="pdf",
            usuario="oper1",
            mapa_orden_catalogo={"SKU-A": 0, "SKU-B": 1, "SKU-C": 2, "SKU-IDLE": 3},
        )
        ruta_xlsx = generar_reporte_descuento_operario_canales(
            items_canal=canales,
            carpeta_destino=self.carpeta_desc,
            formato="xlsx",
            usuario="oper1",
            mapa_orden_catalogo={"SKU-A": 0, "SKU-B": 1, "SKU-C": 2, "SKU-IDLE": 3},
        )
        self.assertTrue(ruta_pdf.exists() and ruta_pdf.stat().st_size > 500)
        self.assertTrue(ruta_xlsx.exists())

        wb = openpyxl.load_workbook(ruta_xlsx, data_only=True)
        ws = wb.active
        codigos_en_hoja = [str(ws.cell(r, 1).value) for r in range(1, ws.max_row + 1)]
        self.assertIn("SKU-A", codigos_en_hoja)
        self.assertIn("SKU-B", codigos_en_hoja)
        self.assertIn("SKU-C", codigos_en_hoja)
        self.assertNotIn("SKU-IDLE", codigos_en_hoja)
        wb.close()

    def test_no_duplica_stock_movements_tras_trigger_en_register_movements(self):
        self.product_store.update_stocks({"SKU-A": 62})
        self.product_store.register_movements(
            [("SKU-A", "Producto Alpha", 12, "ingreso_rapido")],
            usuario="oper1",
            detalle="[Sobrante] Ajuste",
        )
        with closing(self.product_store._connect()) as conn:
            filas = conn.execute(
                "SELECT quantity, movement_type, usuario, detalle FROM stock_movements WHERE product_code = 'SKU-A'"
            ).fetchall()
        self.assertEqual(len(filas), 1)
        self.assertEqual(filas[0]["quantity"], 12)
        self.assertEqual(filas[0]["movement_type"], "ingreso_rapido")
        self.assertEqual(filas[0]["usuario"], "oper1")
        self.assertEqual(filas[0]["detalle"], "[Sobrante] Ajuste")

    def test_cierre_diario_sqlite_sin_excel_emite_operario_canales_y_admin_suma_total(self):
        sm = StockManager(ruta_excel_base=self.excel_inexistente, ruta_base_datos=self.db_prod)
        # 1. Descuentos de pedidos por distintos canales en tiempo real
        sm.actualizar_stock_base(
            [
                RegistroDescuento("SKU-A", "Producto Alpha", 4, 50, 4, 46),
                RegistroDescuento("SKU-B", "Producto Beta", 5, 40, 2, 38),
            ],
            sincronizar_excel=False,
            nombre_archivo="Remito_M1.pdf",
            usuario="oper1",
        )
        sm.actualizar_stock_base(
            [RegistroDescuento("SKU-A", "Producto Alpha", 4, 46, 3, 43)],
            sincronizar_excel=False,
            nombre_archivo="ML_M2.docx",
            usuario="oper1",
        )
        # 2. Ingreso de mercadería de fábrica en la misma jornada
        sm.registrar_ingreso_fabrica({"SKU-C": 15}, sobrescribir=False)
        sm.registrar_movimientos_historial({"SKU-C": 15}, tipo="ingreso_fabrica")

        # 3. Registrar pedidos pendientes de cierre
        self.order_store.registrar_pedido(
            nota_pedido="M-001",
            numero_pedido="1",
            cliente="Mayorista Sur",
            bultos=2,
            logistica="Domicilio",
            armador="oper1",
            tipo_archivo="pdf",
            nombre_archivo="M1.pdf",
            articulos_descontados=6,
            items=[("SKU-A", "Producto Alpha", 4), ("SKU-B", "Producto Beta", 2)],
        )
        self.order_store.registrar_pedido(
            nota_pedido="ML-002",
            numero_pedido="2",
            cliente="Mercado Libre",
            bultos=1,
            logistica="Transporte",
            armador="oper1",
            tipo_archivo="docx",
            nombre_archivo="ML2.docx",
            articulos_descontados=3,
            items=[("SKU-A", "Producto Alpha", 3)],
        )
        pendientes = self.order_store.listar_pedidos_pendientes_cierre()

        interfaz = SimpleNamespace(
            order_store=self.order_store,
            usuario_actual=SimpleNamespace(username="oper1", role="operador"),
            menu=SimpleNamespace(
                ruta_excel_base=self.excel_inexistente,
                carpeta_descuentos=self.carpeta_desc,
            ),
        )

        with patch("src.ui.dialogs.cierre.cierre_operario_exec._resolver_dependencias_cierre") as mock_deps:
            mock_deps.return_value = {
                "get_sm_cls": lambda: (lambda ruta_excel_base=None: StockManager(ruta_excel_base=ruta_excel_base, ruta_base_datos=self.db_prod)),
                "parsear_remito": MagicMock(),
                "parsear_canje": MagicMock(),
                "parsear_ml": MagicMock(),
                "generar_hr": MagicMock(return_value=self.carpeta_desc / "HR_1.pdf"),
                "crear_backup": MagicMock(return_value=self.carpeta_desc / "BK_1.zip"),
                "app_root": lambda: self.root,
            }
            res = ejecutar_tarea_cierre_operario(interfaz, pendientes)

        self.assertTrue(res["pdf_path"].exists())
        self.assertTrue(res["xls_path"].exists())
        self.assertTrue(res["admin_pdf_path"].exists())

        # Verificar Operario Excel: solo SKU-A y SKU-B en salidas (discriminado), solo SKU-C en ingresos, nada de SKU-IDLE
        wb_op = openpyxl.load_workbook(res["xls_path"], data_only=True)
        ws_op = wb_op.active
        filas_op = [[ws_op.cell(r, c).value for c in range(1, 8)] for r in range(1, ws_op.max_row + 1)]
        fila_a = next(f for f in filas_op if f[0] == "SKU-A")
        self.assertEqual((fila_a[2], fila_a[3], fila_a[4]), (4, 3, 0))
        self.assertTrue(any(f[0] == "SKU-C" and f[3] == 15 for f in filas_op))
        self.assertFalse(any(f[0] == "SKU-IDLE" for f in filas_op))
        wb_op.close()

        # Verificar Admin Consolidado bajo demanda: suma total de SKU-A = -7, ingreso SKU-C = +15
        cierres = self.order_store.listar_cierres()
        interfaz.ruta_base_datos = self.db_prod
        admin_xl = generar_reporte_admin_para_cierre(interfaz, cierres[0], formato="xlsx")
        wb_adm = openpyxl.load_workbook(admin_xl, data_only=True)
        ws_adm = wb_adm.active
        filas_adm = [[ws_adm.cell(r, c).value for c in range(1, 8)] for r in range(1, ws_adm.max_row + 1)]
        fila_adm_a = next(f for f in filas_adm if f[0] == "SKU-A")
        self.assertEqual(fila_adm_a[4], -7)
        self.assertFalse(any(f[0] == "SKU-IDLE" for f in filas_adm))
        wb_adm.close()

    def test_aplicar_descuentos_legacy_sin_excel_no_falla(self):
        sm = StockManager(ruta_excel_base=self.excel_inexistente, ruta_base_datos=self.db_prod)
        rep = sm.aplicar_descuentos({}, carpeta_destino=self.carpeta_desc, guardar_archivo=True)
        self.assertTrue(Path(rep.archivo_guardado).exists())
        self.assertTrue(Path(rep.archivo_pdf).exists())

    def test_reportes_estandar_inventario_kardex_y_rotacion(self):
        self.product_store.update_stocks({"SKU-A": 44, "SKU-B": 45})
        self.product_store.register_movements([("SKU-A", "Producto Alpha", -6, "descuento")], usuario="op1", detalle="Remito 1")
        self.product_store.record_physical_inventory(
            usuario="auditor1",
            nombre_archivo="conteo.xlsx",
            reporte_unificado="",
            detalles=[("SKU-A", "Producto Alpha", 44, 42, -2, "FALTANTE")],
        )
        hoy = datetime.now().strftime("%Y-%m-%d")
        resumen = self.product_store.get_period_movements_summary(hoy, hoy)
        for modo in ("salidas", "ingresos", "ambos"):
            p = generar_reporte_movimientos_estandar(resumen, self.carpeta_desc, formato="pdf", modo=modo)
            self.assertTrue(p.exists() and p.stat().st_size > 500)

        p_ciego = generar_reporte_planilla_conteo_fisico(self.product_store, self.carpeta_desc, formato="xlsx", conteo_ciego=True)
        wb_c = openpyxl.load_workbook(p_ciego, data_only=True)
        self.assertNotIn("Stock Sistema", [wb_c.active.cell(4, c).value for c in range(1, 8)])
        wb_c.close()

        self.assertTrue(generar_reporte_auditoria_inventario_fisico(self.product_store, self.carpeta_desc, formato="pdf").exists())
        self.assertTrue(generar_reporte_kardex_producto(self.product_store, "SKU-A", self.carpeta_desc, formato="pdf").exists())
        self.assertTrue(generar_reporte_rotacion_consumo(self.product_store, self.carpeta_desc, formato="pdf", dias=30).exists())


if __name__ == "__main__":
    unittest.main()
