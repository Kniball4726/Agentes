"""Tests para el flujo guiado de planificación y picking de Mercado Envíos Full."""

import tempfile
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

from src.orders.store import OrderStore
from src.ui.dialogs.dlg_planificar_full import mostrar_planificar_full
from src.ui.dialogs.dlg_picking_guiado_full import mostrar_picking_guiado_full


class TestMercadoFullGuidedFlow(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_pedidos.sqlite3"
        self.store = OrderStore(self.db_path)

    def tearDown(self):
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_crear_y_obtener_plan_mercado_full(self):
        items = [
            ("SKU-100", "Remera Talle M", 10),
            ("SKU-200", "Pantalón Jean", 5),
            ("SKU-300", "Zapatillas Negras", 15),
        ]
        plan_id = self.store.crear_plan_mercado_full(
            nombre_envio="Envío Full Semanal",
            archivo_excel="Full_Planilla_12.xlsx",
            creado_por="admin",
            items=items,
        )
        self.assertGreater(plan_id, 0)

        plan = self.store.obtener_plan_mercado_full(plan_id)
        self.assertIsNotNone(plan)
        self.assertEqual(plan["nombre_envio"], "Envío Full Semanal")
        self.assertEqual(plan["archivo_excel"], "Full_Planilla_12.xlsx")
        self.assertEqual(plan["creado_por"], "admin")
        self.assertEqual(plan["estado"], "pendiente")
        self.assertEqual(plan["articulos_totales"], 30)
        self.assertEqual(plan["articulos_pickeados"], 0)
        self.assertEqual(plan["porcentaje"], 0.0)

        items_db = self.store.obtener_items_plan_full(plan_id)
        self.assertEqual(len(items_db), 3)

    def test_obtener_plan_activo(self):
        items = [("SKU-001", "Gorra", 5)]
        plan_id = self.store.crear_plan_mercado_full("Envío Activo", "doc.xlsx", "admin", items)

        activo = self.store.obtener_plan_activo_mercado_full()
        self.assertIsNotNone(activo)
        self.assertEqual(activo["id"], plan_id)

    def test_escaneo_incrementa_progreso_y_bloquea_excedente(self):
        items = [
            ("SKU-A", "Producto A", 2),
            ("SKU-B", "Producto B", 1),
        ]
        plan_id = self.store.crear_plan_mercado_full("Envío Rápido", "doc.xlsx", "admin", items)

        # 1er escaneo de SKU-A
        res1 = self.store.registrar_escaneo_item_plan(plan_id, "SKU-A", cantidad=1, picker="juan_picker")
        self.assertTrue(res1["exito"])
        self.assertEqual(res1["cantidad_actual"], 1)
        self.assertEqual(res1["articulos_pickeados"], 1)
        self.assertEqual(res1["articulos_totales"], 3)
        self.assertAlmostEqual(res1["porcentaje"], 33.3, places=1)
        self.assertFalse(res1["completado_item"])
        self.assertFalse(res1["plan_completo"])

        # 2do escaneo de SKU-A (completa SKU-A)
        res2 = self.store.registrar_escaneo_item_plan(plan_id, "SKU-A", cantidad=1, picker="juan_picker")
        self.assertTrue(res2["exito"])
        self.assertEqual(res2["cantidad_actual"], 2)
        self.assertTrue(res2["completado_item"])
        self.assertEqual(res2["articulos_pickeados"], 2)

        # 3er escaneo de SKU-A (debe fallar por excedido)
        res3 = self.store.registrar_escaneo_item_plan(plan_id, "SKU-A", cantidad=1, picker="juan_picker")
        self.assertFalse(res3["exito"])
        self.assertEqual(res3["motivo"], "excedido")

        # Escaneo de SKU no existente
        res_inexistente = self.store.registrar_escaneo_item_plan(plan_id, "SKU-INEXISTENTE", picker="juan_picker")
        self.assertFalse(res_inexistente["exito"])
        self.assertEqual(res_inexistente["motivo"], "no_encontrado")

        # Escaneo de SKU-B (completa todo el plan)
        res4 = self.store.registrar_escaneo_item_plan(plan_id, "SKU-B", cantidad=1, picker="juan_picker")
        self.assertTrue(res4["exito"])
        self.assertEqual(res4["articulos_pickeados"], 3)
        self.assertEqual(res4["porcentaje"], 100.0)
        self.assertTrue(res4["plan_completo"])

    def test_ajustar_cantidad_item(self):
        items = [("SKU-1", "Prod 1", 10)]
        plan_id = self.store.crear_plan_mercado_full("Envío Ajuste", "doc.xlsx", "admin", items)

        res = self.store.ajustar_cantidad_item_plan(plan_id, "SKU-1", nueva_cantidad=7, picker="picker_ajuste")
        self.assertTrue(res["exito"])
        self.assertEqual(res["cantidad_actual"], 7)
        self.assertEqual(res["porcentaje"], 70.0)

        plan = self.store.obtener_plan_mercado_full(plan_id)
        self.assertEqual(plan["articulos_pickeados"], 7)
        self.assertEqual(plan["porcentaje"], 70.0)

    def test_finalizar_plan(self):
        items = [("SKU-1", "Prod 1", 1)]
        plan_id = self.store.crear_plan_mercado_full("Envío Finalizar", "doc.xlsx", "admin", items)
        self.store.registrar_escaneo_item_plan(plan_id, "SKU-1", 1, picker="pedro")

        ok = self.store.finalizar_plan_mercado_full(plan_id, picker="pedro")
        self.assertTrue(ok)

        plan = self.store.obtener_plan_mercado_full(plan_id)
        self.assertEqual(plan["estado"], "completado")
        self.assertEqual(plan["picker_asignado"], "pedro")

        # No hay más activo
        activo = self.store.obtener_plan_activo_mercado_full()
        self.assertIsNone(activo)

    def test_cancelar_plan(self):
        items = [("SKU-1", "Prod 1", 5)]
        plan_id = self.store.crear_plan_mercado_full("Envío Cancelar", "doc.xlsx", "admin", items)
        ok = self.store.cancelar_plan_mercado_full(plan_id)
        self.assertTrue(ok)

        plan = self.store.obtener_plan_mercado_full(plan_id)
        self.assertEqual(plan["estado"], "cancelado")

    def test_ui_mostrar_planificar_full_carga_dialogo(self):
        mock_interfaz = MagicMock()
        mock_interfaz.order_store = self.store
        mock_interfaz.usuario_actual.nombre_identificador = "Admin"
        mock_interfaz.exigir_roles.return_value = True
        mock_interfaz.modo_oscuro = True
        mock_interfaz.secundario = "#888888"
        mock_interfaz.texto = "#ffffff"
        mock_interfaz.ancho_adaptable.return_value = 650
        mock_interfaz.menu.carpeta_mercado_full = Path(self.temp_dir.name)
        mock_interfaz.menu.ruta_excel_base = Path(self.temp_dir.name) / "Productos.xlsx"

        mostrar_planificar_full(mock_interfaz)
        mock_interfaz.page.show_dialog.assert_called_once()
        mock_interfaz.page.update.assert_called()

    def test_ui_mostrar_picking_guiado_full_escaneo(self):
        # Crear un plan previo
        items = [("SKU-TEST", "Remera Prueba", 3)]
        plan_id = self.store.crear_plan_mercado_full("Envío UI Test", "doc.xlsx", "Admin", items)

        mock_interfaz = MagicMock()
        mock_interfaz.order_store = self.store
        mock_interfaz.usuario_actual.nombre_identificador = "PickerJuan"
        mock_interfaz.exigir_roles.return_value = True
        mock_interfaz.modo_oscuro = True
        mock_interfaz.secundario = "#888888"
        mock_interfaz.texto = "#ffffff"
        mock_interfaz.ancho_adaptable.return_value = 650

        with patch("src.ui.audio_feedback.emitir_tono_exito") as mock_tono_exito:
            mostrar_picking_guiado_full(mock_interfaz)
            mock_interfaz.page.show_dialog.assert_called_once()

            # El diálogo fue mostrado
            dlg = mock_interfaz.page.show_dialog.call_args[0][0]
            self.assertIsNotNone(dlg)


if __name__ == "__main__":
    unittest.main()
