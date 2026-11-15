"""Tests para el flujo guiado de planificación y control de ingreso de fábrica."""

import tempfile
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

from src.orders.store import OrderStore
from src.ui.dialogs.dlg_planificar_ingreso_fabrica import mostrar_planificar_ingreso_fabrica
from src.ui.dialogs.dlg_control_ingreso_fabrica import mostrar_control_ingreso_fabrica


class TestFactoryEntryGuidedFlow(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_pedidos.sqlite3"
        self.store = OrderStore(self.db_path)

    def tearDown(self):
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_crear_y_obtener_plan_ingreso_fabrica(self):
        items = [
            ("101", "Proteína Whey 1kg Vainilla", 20),
            ("201", "Creatina Monohidrato 300g", 15),
            ("302", "Shaker Mezclador 700ml", 30),
        ]
        plan_id = self.store.crear_plan_ingreso_fabrica(
            nombre_remito="Remito Fábrica #8841",
            archivo_remito="Remito_8841.xlsx",
            creado_por="admin",
            items=items,
        )
        self.assertGreater(plan_id, 0)

        plan = self.store.obtener_plan_ingreso_fabrica(plan_id)
        self.assertIsNotNone(plan)
        self.assertEqual(plan["nombre_remito"], "Remito Fábrica #8841")
        self.assertEqual(plan["archivo_remito"], "Remito_8841.xlsx")
        self.assertEqual(plan["creado_por"], "admin")
        self.assertEqual(plan["estado"], "pendiente")
        self.assertEqual(plan["articulos_esperados"], 65)
        self.assertEqual(plan["articulos_controlados"], 0)
        self.assertEqual(plan["porcentaje"], 0.0)

        items_db = self.store.obtener_items_plan_ingreso_fabrica(plan_id)
        self.assertEqual(len(items_db), 3)

    def test_obtener_plan_activo_fabrica(self):
        items = [("101", "Proteína Whey", 10)]
        plan_id = self.store.crear_plan_ingreso_fabrica("Remito Activo", "doc.xlsx", "admin", items)

        activo = self.store.obtener_plan_activo_ingreso_fabrica()
        self.assertIsNotNone(activo)
        self.assertEqual(activo["id"], plan_id)

    def test_escaneo_incrementa_control_y_bloquea_excedente(self):
        items = [
            ("101", "Proteína Whey 1kg", 2),
            ("201", "Creatina 300g", 1),
        ]
        plan_id = self.store.crear_plan_ingreso_fabrica("Remito Control", "doc.xlsx", "admin", items)

        # 1er escaneo de 101
        res1 = self.store.registrar_escaneo_item_ingreso_fabrica(plan_id, "101", cantidad=1, picker="carlos_picker")
        self.assertTrue(res1["exito"])
        self.assertEqual(res1["cantidad_actual"], 1)
        self.assertEqual(res1["articulos_controlados"], 1)
        self.assertEqual(res1["articulos_esperados"], 3)
        self.assertAlmostEqual(res1["porcentaje"], 33.3, places=1)
        self.assertFalse(res1["completado_item"])
        self.assertFalse(res1["plan_completo"])

        # 2do escaneo de 101 (completa cuota esperada)
        res2 = self.store.registrar_escaneo_item_ingreso_fabrica(plan_id, "101", cantidad=1, picker="carlos_picker")
        self.assertTrue(res2["exito"])
        self.assertEqual(res2["cantidad_actual"], 2)
        self.assertTrue(res2["completado_item"])
        self.assertEqual(res2["articulos_controlados"], 2)

        # 3er escaneo de 101 (debe fallar por excedido)
        res3 = self.store.registrar_escaneo_item_ingreso_fabrica(plan_id, "101", cantidad=1, picker="carlos_picker")
        self.assertFalse(res3["exito"])
        self.assertEqual(res3["motivo"], "excedido")

        # Escaneo de artículo inexistente en el remito
        res_no = self.store.registrar_escaneo_item_ingreso_fabrica(plan_id, "SKU-DESCONOCIDO", picker="carlos_picker")
        self.assertFalse(res_no["exito"])
        self.assertEqual(res_no["motivo"], "no_encontrado")

        # Escaneo de 201 (completa todo el remito)
        res4 = self.store.registrar_escaneo_item_ingreso_fabrica(plan_id, "201", cantidad=1, picker="carlos_picker")
        self.assertTrue(res4["exito"])
        self.assertEqual(res4["articulos_controlados"], 3)
        self.assertEqual(res4["porcentaje"], 100.0)
        self.assertTrue(res4["plan_completo"])

    def test_finalizar_plan_retorna_solo_controlados(self):
        items = [
            ("101", "Prod A", 10),
            ("201", "Prod B", 5),
        ]
        plan_id = self.store.crear_plan_ingreso_fabrica("Remito Parcial", "doc.xlsx", "admin", items)

        # El picker solo controló físicamente 4 unidades de 101 y ninguna de 201
        self.store.registrar_escaneo_item_ingreso_fabrica(plan_id, "101", cantidad=4, picker="carlos")

        res_fin = self.store.finalizar_plan_ingreso_fabrica(plan_id, picker="carlos")
        self.assertTrue(res_fin["exito"])
        self.assertEqual(res_fin["items_controlados"], {"101": 4})
        self.assertNotIn("201", res_fin["items_controlados"])
        self.assertEqual(res_fin["articulos_controlados"], 4)
        self.assertEqual(res_fin["articulos_esperados"], 15)

        plan = self.store.obtener_plan_ingreso_fabrica(plan_id)
        self.assertEqual(plan["estado"], "completado")

    def test_cierre_parcial_ingreso_fabrica_multidia(self):
        items = [
            ("101", "Proteína Whey 1kg", 100),
            ("201", "Creatina 300g", 50),
        ]
        plan_id = self.store.crear_plan_ingreso_fabrica("Remito MultiDía", "doc.xlsx", "admin", items)

        # ---------------------------------------------------------
        # DÍA 1: Picker descarga y pistolea 40 un. de 101 y 20 un. de 201
        # ---------------------------------------------------------
        self.store.registrar_escaneo_item_ingreso_fabrica(plan_id, "101", cantidad=40, picker="carlos_picker")
        self.store.registrar_escaneo_item_ingreso_fabrica(plan_id, "201", cantidad=20, picker="carlos_picker")

        # Cierre parcial del Día 1
        res_p1 = self.store.registrar_cierre_parcial_ingreso_fabrica(plan_id, picker="carlos_picker")
        self.assertTrue(res_p1["exito"])
        self.assertEqual(res_p1["items_a_ingresar"], {"101": 40, "201": 20})
        self.assertEqual(res_p1["articulos_ingresados_parcial"], 60)
        self.assertEqual(res_p1["articulos_ingresados_acumulado"], 60)

        plan = self.store.obtener_plan_ingreso_fabrica(plan_id)
        self.assertEqual(plan["estado"], "en_proceso")
        self.assertEqual(plan["articulos_ingresados"], 60)

        # Si intenta hacer otro cierre sin escanear nada nuevo, se rechaza sin duplicar
        res_vacio = self.store.registrar_cierre_parcial_ingreso_fabrica(plan_id, picker="carlos_picker")
        self.assertFalse(res_vacio["exito"])
        self.assertEqual(res_vacio["motivo"], "sin_pendientes")

        # ---------------------------------------------------------
        # DÍA 2: Picker escanea 30 un. más de 101 y 10 un. más de 201
        # ---------------------------------------------------------
        self.store.registrar_escaneo_item_ingreso_fabrica(plan_id, "101", cantidad=30, picker="carlos_picker")
        self.store.registrar_escaneo_item_ingreso_fabrica(plan_id, "201", cantidad=10, picker="carlos_picker")

        # Cierre parcial del Día 2: solo acredita la diferencia nueva (30 y 10)
        res_p2 = self.store.registrar_cierre_parcial_ingreso_fabrica(plan_id, picker="carlos_picker")
        self.assertTrue(res_p2["exito"])
        self.assertEqual(res_p2["items_a_ingresar"], {"101": 30, "201": 10})
        self.assertEqual(res_p2["articulos_ingresados_parcial"], 40)
        self.assertEqual(res_p2["articulos_ingresados_acumulado"], 100)

        plan = self.store.obtener_plan_ingreso_fabrica(plan_id)
        self.assertEqual(plan["estado"], "en_proceso")

        # ---------------------------------------------------------
        # DÍA 3: Picker escanea 10 un. finales de 101 y cierra definitivamente el remito
        # ---------------------------------------------------------
        self.store.registrar_escaneo_item_ingreso_fabrica(plan_id, "101", cantidad=10, picker="carlos_picker")

        res_final = self.store.finalizar_plan_ingreso_fabrica(plan_id, picker="carlos_picker")
        self.assertTrue(res_final["exito"])
        # items_controlados en el cierre final solo contiene el saldo pendiente no ingresado
        self.assertEqual(res_final["items_controlados"], {"101": 10})
        self.assertEqual(res_final["articulos_ingresados_final"], 10)
        self.assertEqual(res_final["articulos_ingresados_total"], 110)
        self.assertEqual(res_final["items_totales_controlados"], {"101": 80, "201": 30})

        plan_final = self.store.obtener_plan_ingreso_fabrica(plan_id)
        self.assertEqual(plan_final["estado"], "completado")
        self.assertEqual(plan_final["articulos_ingresados"], 110)

        # Verificar historial de cierres
        historial = self.store.listar_cierres_parciales_fabrica(plan_id)
        self.assertEqual(len(historial), 3) # 2 parciales + 1 final
        self.assertEqual(historial[0]["tipo"], "parcial")
        self.assertEqual(historial[0]["articulos_ingresados"], 60)
        self.assertEqual(historial[1]["tipo"], "parcial")
        self.assertEqual(historial[1]["articulos_ingresados"], 40)
        self.assertEqual(historial[2]["tipo"], "final")
        self.assertEqual(historial[2]["articulos_ingresados"], 10)

    def test_cancelar_plan_fabrica(self):
        items = [("101", "Prod A", 5)]
        plan_id = self.store.crear_plan_ingreso_fabrica("Remito Cancelar", "doc.xlsx", "admin", items)
        ok = self.store.cancelar_plan_ingreso_fabrica(plan_id)
        self.assertTrue(ok)

        plan = self.store.obtener_plan_ingreso_fabrica(plan_id)
        self.assertEqual(plan["estado"], "cancelado")

    def test_ui_dialogo_planificar_ingreso_fabrica(self):
        mock_interfaz = MagicMock()
        mock_interfaz.order_store = self.store
        mock_interfaz.usuario_actual.nombre_identificador = "Admin"
        mock_interfaz.exigir_roles.return_value = True
        mock_interfaz.modo_oscuro = True
        mock_interfaz.secundario = "#888888"
        mock_interfaz.texto = "#ffffff"
        mock_interfaz.ancho_adaptable.return_value = 650
        mock_interfaz.menu.carpeta_fabrica = Path(self.temp_dir.name)
        mock_interfaz.menu.ruta_excel_base = Path(self.temp_dir.name) / "Productos.xlsx"

        mostrar_planificar_ingreso_fabrica(mock_interfaz)
        mock_interfaz.page.show_dialog.assert_called_once()
        mock_interfaz.page.update.assert_called()

    def test_ui_dialogo_control_ingreso_fabrica(self):
        items = [("101", "Prod A", 5)]
        self.store.crear_plan_ingreso_fabrica("Remito UI Test", "doc.xlsx", "Admin", items)

        mock_interfaz = MagicMock()
        mock_interfaz.order_store = self.store
        mock_interfaz.usuario_actual.nombre_identificador = "PickerCarlos"
        mock_interfaz.exigir_roles.return_value = True
        mock_interfaz.modo_oscuro = True
        mock_interfaz.secundario = "#888888"
        mock_interfaz.texto = "#ffffff"
        mock_interfaz.ancho_adaptable.return_value = 650

        with patch("src.ui.audio_feedback.emitir_tono_exito"):
            mostrar_control_ingreso_fabrica(mock_interfaz)
            mock_interfaz.page.show_dialog.assert_called_once()
            dlg = mock_interfaz.page.show_dialog.call_args[0][0]
            self.assertIsNotNone(dlg)


if __name__ == "__main__":
    unittest.main()
