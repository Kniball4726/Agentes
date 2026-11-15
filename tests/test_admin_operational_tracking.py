"""Pruebas unitarias para el seguimiento operativo en el panel superior del Administrador (Mercado Full y Fábrica)."""

import tempfile
from pathlib import Path
import unittest
from unittest.mock import MagicMock

import flet as ft

from src.orders.store import OrderStore
from src.ui.components.admin_operations_bar import (
    construir_panel_seguimiento_admin,
    actualizar_seguimiento_operativo_admin,
)
from src.ui.components.header import construir_encabezado


class TestAdminOperationalTracking(unittest.TestCase):
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
        self.mock_interfaz.panel_seguimiento_admin = None
        self.mock_interfaz.panel_seguimiento_admin_movil = None
        self.mock_interfaz.pendientes_texto = ft.Text("Pendientes")
        self.mock_interfaz.contenedor_notificaciones = ft.Container()
        self.mock_interfaz.contadores = {}
        self.mock_interfaz.boton = MagicMock(return_value=ft.Button("Actualizar"))
        self.mock_interfaz.ancho_adaptable = MagicMock(side_effect=lambda x: x)

    def tearDown(self):
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_exclusividad_rol_administrador_bloquea_master_y_otros(self):
        """Verifica que el panel superior de seguimiento NO se muestre para master, picker, operador ni consulta."""
        for rol_bloqueado in ("master", "picker", "operador", "consulta"):
            self.mock_interfaz.usuario_actual.role = rol_bloqueado
            panel = construir_panel_seguimiento_admin(self.mock_interfaz)
            self.assertIsNone(panel, f"El rol {rol_bloqueado} no debería tener panel de seguimiento operativo.")

    def test_administrador_recibe_panel_seguimiento(self):
        """Verifica que el usuario administrador sí recibe el panel de seguimiento operativo."""
        self.mock_interfaz.usuario_actual.role = "administrador"
        panel = construir_panel_seguimiento_admin(self.mock_interfaz)
        self.assertIsNotNone(panel)
        self.assertIsInstance(panel, ft.Container)

    def test_badges_visibles_incluso_sin_planes_previos(self):
        """Verifica que si la DB está limpia (por zapping), los badges se muestren igualmente en estado 'sin activos'."""
        self.mock_interfaz.usuario_actual.role = "administrador"
        panel = construir_panel_seguimiento_admin(self.mock_interfaz)
        self.assertTrue(panel.visible)
        fila = panel.content
        self.assertEqual(len(fila.controls), 2)
        self.assertIn("Full: Sin envíos activos", fila.controls[0].content.controls[1].value)
        self.assertIn("Fábrica: Sin remitos activos", fila.controls[1].content.controls[1].value)

    def test_seguimiento_mercado_full_proceso_y_cierre_total(self):
        """
        Verifica que muestre el porcentaje en preparación y cambie a 'Cerrado con XX%'
        al finalizar, persistiendo hasta que se cree un nuevo plan.
        """
        self.mock_interfaz.usuario_actual.role = "administrador"
        panel = construir_panel_seguimiento_admin(self.mock_interfaz)

        # 1. Crear plan de Mercado Full
        items = [("SKU-1", "Remera", 10)]
        plan_id = self.store.crear_plan_mercado_full("Full Tanda 1", "full1.xlsx", "admin", items)

        # Picker escanea 4 unidades (40%)
        self.store.registrar_escaneo_item_plan(plan_id, "SKU-1", cantidad=4, picker="carlos")

        actualizar_seguimiento_operativo_admin(self.mock_interfaz)
        self.assertTrue(panel.visible)

        fila = panel.content
        self.assertGreaterEqual(len(fila.controls), 1)
        badge_full = fila.controls[0]
        texto_full = badge_full.content.controls[1].value
        self.assertIn("Full: 40% (En preparación)", texto_full)

        # 2. Picker finaliza el plan (cierre total al 40%)
        self.store.finalizar_plan_mercado_full(plan_id, picker="carlos")

        actualizar_seguimiento_operativo_admin(self.mock_interfaz)
        badge_full_cerrado = panel.content.controls[0]
        texto_cerrado = badge_full_cerrado.content.controls[1].value
        self.assertIn("Full: Cerrado con 40%", texto_cerrado)

        # 3. Administrador sube un nuevo archivo / plan
        items2 = [("SKU-2", "Pantalón", 20)]
        plan2_id = self.store.crear_plan_mercado_full("Full Tanda 2", "full2.xlsx", "admin", items2)

        actualizar_seguimiento_operativo_admin(self.mock_interfaz)
        badge_nuevo = panel.content.controls[0]
        texto_nuevo = badge_nuevo.content.controls[1].value
        self.assertIn("Full: 0% (En preparación)", texto_nuevo)

    def test_seguimiento_ingreso_fabrica_proceso_y_cierre_total(self):
        """
        Verifica que el remito de fábrica muestre porcentaje en control y cambie a
        'Cerrado con XX%' al cierre final, persistiendo hasta que se cargue un nuevo remito.
        """
        self.mock_interfaz.usuario_actual.role = "administrador"
        panel = construir_panel_seguimiento_admin(self.mock_interfaz)

        # 1. Cargar remito de fábrica
        items = [("101", "Proteína", 50)]
        plan_id = self.store.crear_plan_ingreso_fabrica("Remito Fabrica 100", "remito100.xlsx", "admin", items)

        # Picker controla 25 unidades (50%)
        self.store.registrar_escaneo_item_ingreso_fabrica(plan_id, "101", cantidad=25, picker="carlos")

        actualizar_seguimiento_operativo_admin(self.mock_interfaz)
        self.assertTrue(panel.visible)

        # Debe mostrarse el badge de fábrica
        badge_fab = panel.content.controls[-1]
        texto_fab = badge_fab.content.controls[1].value
        self.assertIn("Fábrica: 50% (En control)", texto_fab)

        # 2. Picker hace el cierre definitivo del remito
        self.store.finalizar_plan_ingreso_fabrica(plan_id, picker="carlos")

        actualizar_seguimiento_operativo_admin(self.mock_interfaz)
        badge_fab_cerrado = panel.content.controls[-1]
        texto_cerrado = badge_fab_cerrado.content.controls[1].value
        self.assertIn("Fábrica: Cerrado con 50%", texto_cerrado)

        # 3. Administrador carga un nuevo remito de fábrica
        items2 = [("201", "Creatina", 10)]
        self.store.crear_plan_ingreso_fabrica("Remito Fabrica 101", "remito101.xlsx", "admin", items2)

        actualizar_seguimiento_operativo_admin(self.mock_interfaz)
        badge_fab_nuevo = panel.content.controls[-1]
        texto_nuevo = badge_fab_nuevo.content.controls[1].value
        self.assertIn("Fábrica: 0% (En control)", texto_nuevo)

    def test_panel_acceso_rapido_incluye_seguimiento_solo_para_administrador(self):
        """Verifica que el panel de acceso rápido integre el seguimiento para admin y no para master."""
        from src.ui.components.panels import construir_panel_acceso_rapido

        self.mock_interfaz.usuario_actual.role = "master"
        self.mock_interfaz.panel_seguimiento_admin = None
        panel_master = construir_panel_acceso_rapido(self.mock_interfaz)
        self.assertIsNone(self.mock_interfaz.panel_seguimiento_admin)

        self.mock_interfaz.usuario_actual.role = "administrador"
        panel_admin = construir_panel_acceso_rapido(self.mock_interfaz)
        self.assertIsNotNone(self.mock_interfaz.panel_seguimiento_admin)


if __name__ == "__main__":
    unittest.main()
