"""Pruebas unitarias para el módulo de analítica y flujo de stock en tiempo real exclusivo del Administrador."""

from datetime import datetime
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock

import flet as ft

from src.orders.store import OrderStore
from src.ui.components.admin_flow_analytics import (
    construir_panel_analitica_flujo_admin,
    actualizar_panel_analitica_flujo_admin,
)
from src.ui.components.panels import construir_panel_informes_actividad


class TestAdminFlowAnalytics(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_pedidos.sqlite3"
        self.store = OrderStore(self.db_path)

        self.mock_interfaz = MagicMock()
        self.mock_interfaz.order_store = self.store
        self.mock_interfaz.modo_oscuro = True
        self.mock_interfaz.texto = "#ffffff"
        self.mock_interfaz.secundario = "#888888"
        self.mock_interfaz.fondo_acento = "#ff0000"
        self.mock_interfaz.borde = "#333333"
        self.mock_interfaz.superficie = "#1e1e1e"
        self.mock_interfaz.es_pantalla_movil = False
        self.mock_interfaz.lista_informes = ft.ListView()
        self.mock_interfaz.lista_pedidos_preparados = ft.ListView()
        self.mock_interfaz.header_pedidos_fecha = ft.Text("Hoy")
        self.mock_interfaz.header_pedidos_subtitulo = ft.Text("Subtitulo")
        self.mock_interfaz.header_pedidos_bultos = ft.Text("0 Bultos")
        self.mock_interfaz.tarjeta = MagicMock(side_effect=lambda c, expand=True: ft.Container(content=c, expand=expand))

    def tearDown(self):
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_calculos_flujo_stock_diario_en_store(self):
        """Verifica que el repositorio agregue y calcule correctamente entradas, salidas y balance del día."""
        # 1. Registrar pedido ML
        p_ml = self.store.registrar_pedido(
            nota_pedido="ML-101",
            numero_pedido="101",
            cliente="Comprador ML",
            bultos=1,
            logistica="Centro de distribución",
            armador="operario1",
            tipo_archivo="docx",
            nombre_archivo="ML_101.docx",
            agregado=False,
            articulos_descontados=10,
            resumen_items="1 producto (10 un.)",
            items=[("101", "Proteína Whey 1kg", 10)],
        )

        # 2. Registrar pedido Mayorista
        p_may = self.store.registrar_pedido(
            nota_pedido="MAY-201",
            numero_pedido="201",
            cliente="Distribuidor Sur",
            bultos=3,
            logistica="Transporte",
            armador="operario1",
            tipo_archivo="pdf",
            nombre_archivo="Remito_201.pdf",
            agregado=False,
            articulos_descontados=25,
            resumen_items="1 producto (25 un.)",
            items=[("202", "Creatina 300g", 25)],
        )

        # 3. Plan Mercado Full pickeado hoy
        plan_full = self.store.crear_plan_mercado_full(
            nombre_envio="Full Tanda",
            archivo_excel="full.xlsx",
            creado_por="admin",
            items=[("303", "BCAA 2:1:1", 15)],
        )
        self.store.registrar_escaneo_item_plan(plan_full, "303", cantidad=15, picker="carlos")

        # 4. Ingreso de fábrica cerrado hoy
        plan_fab = self.store.crear_plan_ingreso_fabrica(
            nombre_remito="Remito Fabrica",
            archivo_remito="fab.xlsx",
            creado_por="admin",
            items=[("101", "Proteína Whey 1kg", 50), ("202", "Creatina 300g", 30)],
        )
        self.store.registrar_escaneo_item_ingreso_fabrica(plan_fab, "101", cantidad=50, picker="carlos")
        self.store.registrar_escaneo_item_ingreso_fabrica(plan_fab, "202", cantidad=30, picker="carlos")
        self.store.registrar_cierre_parcial_ingreso_fabrica(plan_fab, picker="carlos")

        # Obtener flujo del día
        datos = self.store.obtener_flujo_stock_diario()

        self.assertEqual(datos["entradas_totales"], 80) # 50 + 30 de fábrica
        self.assertEqual(datos["salidas_totales"], 50)  # 10 (ML) + 25 (Mayorista) + 15 (Full)
        self.assertEqual(datos["balance_neto"], 30)     # 80 - 50 = +30 (superávit)
        self.assertEqual(datos["bultos_totales"], 4)    # 1 + 3

        # Canales
        canales = datos["salidas_canales"]
        self.assertEqual(canales["mercado_libre"]["unidades"], 10)
        self.assertEqual(canales["mayoristas"]["unidades"], 25)
        self.assertEqual(canales["mercado_full"]["unidades"], 15)

        # Top movimientos
        top_salidas = datos["top_salidas"]
        self.assertEqual(top_salidas[0]["codigo"], "202")
        self.assertEqual(top_salidas[0]["cantidad"], 25)

        top_entradas = datos["top_entradas"]
        self.assertEqual(top_entradas[0]["codigo"], "101")
        self.assertEqual(top_entradas[0]["cantidad"], 50)

    def test_exclusividad_panel_analitica_flujo_admin(self):
        """Verifica que el panel de analítica de flujo se construya únicamente para Administrador."""
        for rol in ("master", "picker", "operador", "consulta"):
            self.mock_interfaz.usuario_actual.role = rol
            panel = construir_panel_analitica_flujo_admin(self.mock_interfaz)
            self.assertIsNone(panel, f"El rol {rol} no debería acceder al panel de analítica de flujo.")

        self.mock_interfaz.usuario_actual.role = "administrador"
        panel_admin = construir_panel_analitica_flujo_admin(self.mock_interfaz)
        self.assertIsNotNone(panel_admin)
        self.assertIsInstance(panel_admin, ft.Column)

    def test_construir_panel_informes_actividad_integra_flujo_solo_para_administrador(self):
        """Verifica que el panel inferior muestre flujo para admin, informes para master/picker, y pedidos para operador."""
        # 1. Master: devuelve solo auditoría (tarjeta_der)
        self.mock_interfaz.usuario_actual.role = "master"
        ctrl_master = construir_panel_informes_actividad(self.mock_interfaz)
        self.assertIsInstance(ctrl_master, ft.Container)

        # 2. Picker: devuelve informes (tarjeta_der)
        self.mock_interfaz.usuario_actual.role = "picker"
        ctrl_picker = construir_panel_informes_actividad(self.mock_interfaz)
        self.assertIsInstance(ctrl_picker, ft.Container)

        # 3. Operador: devuelve pedidos + informes (Row de 2 tarjetas)
        self.mock_interfaz.usuario_actual.role = "operador"
        ctrl_operador = construir_panel_informes_actividad(self.mock_interfaz)
        self.assertIsInstance(ctrl_operador, ft.Row)

        # 4. Administrador: devuelve el panel de flujo en tiempo real (Column)
        self.mock_interfaz.usuario_actual.role = "administrador"
        ctrl_admin = construir_panel_informes_actividad(self.mock_interfaz)
        self.assertIsInstance(ctrl_admin, ft.Column)

    def test_actualizar_panel_analitica_flujo_admin_actualiza_kpis_y_barras(self):
        """Verifica que la función actualizadora refresque correctamente los textos y barras."""
        self.mock_interfaz.usuario_actual.role = "administrador"
        panel = construir_panel_analitica_flujo_admin(self.mock_interfaz)

        # Simular ventas y compras
        self.store.registrar_pedido(
            nota_pedido="ML-555",
            numero_pedido="555",
            cliente="Cliente Test",
            bultos=2,
            logistica="Centro de distribución",
            armador="operario1",
            tipo_archivo="docx",
            nombre_archivo="ML_555.docx",
            agregado=False,
            articulos_descontados=12,
            resumen_items="1 producto (12 un.)",
            items=[("101", "Proteína", 12)],
        )

        actualizar_panel_analitica_flujo_admin(self.mock_interfaz)

        ctrls = self.mock_interfaz.controles_flujo_admin
        self.assertEqual(ctrls["salidas_val"].value, "12 un.")
        self.assertEqual(ctrls["bultos_val"].value, "2 bultos")
        self.assertIn("-12 un.", ctrls["balance_val"].value)
        self.assertGreater(len(ctrls["col_salidas_grafico"].controls), 0)
        self.assertIn("col_armadores", ctrls)
        self.assertIn("col_stock_critico", ctrls)
        self.assertIn("col_tendencia_dias", ctrls)
        self.assertIn("semaforo_val", ctrls)
        self.assertGreater(len(ctrls["col_armadores"].controls), 0)
        self.assertGreater(len(ctrls["col_tendencia_dias"].controls), 0)
        self.assertGreater(len(ctrls["col_stock_critico"].controls), 0)


if __name__ == "__main__":
    unittest.main()
