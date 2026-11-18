"""Pruebas para cierres parciales y finales de Mercado Full y opciones de DESPACHO."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import flet as ft

from src.flet_gui import InterfazFlet
from src.orders import OrderStore
from src.ui.controllers.dialog_coordinator import DialogCoordinator
from src.ui.dialogs.cierre.dlg_cierre_full_plan import (
    mostrar_cierre_final_mercado_full,
    mostrar_cierre_parcial_mercado_full,
    procesar_cierre_plan_full_sync,
)
from src.ui.dialogs.dlg_picking_guiado_full import mostrar_picking_guiado_full


def _crear_interfaz_mock(store: OrderStore, rol: str = "picker", username: str = "picker1") -> SimpleNamespace:
    mock_page = MagicMock()
    mock_page.overlay = []
    mock_page.dialog = None
    mock_page.width = 1280
    mock_page.theme_mode = ft.ThemeMode.LIGHT
    return SimpleNamespace(
        page=mock_page,
        order_store=store,
        usuario_actual=SimpleNamespace(username=username, nombre_identificador=username, rol=rol),
        modo_oscuro=False,
        texto=ft.Colors.BLACK,
        menu=SimpleNamespace(ruta_excel_base=Path("dummy.xlsx")),
        exigir_roles=lambda *roles: rol in roles,
        notificar=MagicMock(),
        sincronizar_sesiones=MagicMock(),
        actualizar_estado=MagicMock(),
        ancho_adaptable=lambda w: w,
    )


class TestMercadoFullClosures(unittest.TestCase):
    """Valida el flujo multidía (parcial y final) de Mercado Full en repositorio y UI."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmp.name) / "orders.sqlite3"
        self.store = OrderStore(self.db_path)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_cierre_parcial_y_final_multidia_sin_doble_descuento(self) -> None:
        plan_id = self.store.crear_plan_mercado_full(
            nombre_envio="Full Semanal #99",
            archivo_excel="full_99.xlsx",
            creado_por="admin",
            items=[
                ("SKU-A", "Producto A", 10),
                ("SKU-B", "Producto B", 5),
            ],
        )

        # Día 1: escaneo parcial (4 de A, 2 de B)
        self.store.registrar_escaneo_item_plan(plan_id, "SKU-A", cantidad=4, picker="picker1")
        self.store.registrar_escaneo_item_plan(plan_id, "SKU-B", cantidad=2, picker="picker1")

        res_d1 = self.store.registrar_cierre_parcial_mercado_full(plan_id, picker="picker1")
        self.assertTrue(res_d1["exito"])
        self.assertEqual(res_d1["estado"], "en_proceso")
        self.assertEqual(res_d1["total_descontado"], 6)
        self.assertEqual(res_d1["delta_items"], {"SKU-A": 4, "SKU-B": 2})
        self.assertEqual(res_d1["acumulado_descontado"], 6)

        # Reintentar cierre parcial sin nuevos escaneos no duplica descuento
        res_dup = self.store.registrar_cierre_parcial_mercado_full(plan_id, picker="picker1")
        self.assertFalse(res_dup["exito"])
        self.assertEqual(res_dup["total_descontado"], 0)

        # Día 2: escaneo incremental (+3 de A)
        self.store.registrar_escaneo_item_plan(plan_id, "SKU-A", cantidad=3, picker="picker1")
        res_d2 = self.store.registrar_cierre_parcial_mercado_full(plan_id, picker="picker1")
        self.assertTrue(res_d2["exito"])
        self.assertEqual(res_d2["estado"], "en_proceso")
        self.assertEqual(res_d2["total_descontado"], 3)
        self.assertEqual(res_d2["delta_items"], {"SKU-A": 3})
        self.assertEqual(res_d2["acumulado_descontado"], 9)

        # Día 3: +1 de B y cierre final incompleto (10/15 = 66.7%)
        self.store.registrar_escaneo_item_plan(plan_id, "SKU-B", cantidad=1, picker="picker1")
        res_fin = self.store.registrar_cierre_final_mercado_full(plan_id, picker="picker1")
        self.assertTrue(res_fin["exito"])
        self.assertEqual(res_fin["estado"], "completado")
        self.assertEqual(res_fin["total_descontado"], 1)
        self.assertEqual(res_fin["delta_items"], {"SKU-B": 1})
        self.assertEqual(res_fin["acumulado_descontado"], 10)
        self.assertAlmostEqual(res_fin["porcentaje"], 66.7, places=1)

        plan_final = self.store.obtener_plan_mercado_full(plan_id)
        self.assertEqual(plan_final["estado"], "completado")
        self.assertEqual(int(plan_final["articulos_descontados"]), 10)

        historial = self.store.listar_cierres_parciales_full(plan_id)
        self.assertEqual(len(historial), 3)
        self.assertEqual([h["tipo"] for h in historial], ["final", "parcial", "parcial"])

        # Plan completado rechaza nuevos cierres
        res_post = self.store.registrar_cierre_parcial_mercado_full(plan_id, picker="picker1")
        self.assertFalse(res_post["exito"])

    def test_cierre_final_sin_delta_pendiente_cierra_plan_limpiamente(self) -> None:
        plan_id = self.store.crear_plan_mercado_full(
            nombre_envio="Full Parcial Sin Resto",
            archivo_excel="full_resto.xlsx",
            creado_por="admin",
            items=[("SKU-1", "Item 1", 10)],
        )
        self.store.registrar_escaneo_item_plan(plan_id, "SKU-1", cantidad=6, picker="picker1")
        res_parcial = self.store.registrar_cierre_parcial_mercado_full(plan_id, picker="picker1")
        self.assertTrue(res_parcial["exito"])

        # Luego decide cerrar definitivamente con lo ya descontado
        res_final = self.store.registrar_cierre_final_mercado_full(plan_id, picker="picker1")
        self.assertTrue(res_final["exito"])
        self.assertEqual(res_final["estado"], "completado")
        self.assertEqual(res_final["total_descontado"], 0)
        self.assertEqual(res_final["acumulado_descontado"], 6)

    def test_procesar_cierre_plan_full_sync_descuenta_solo_delta_y_registra_lotes(self) -> None:
        plan_id = self.store.crear_plan_mercado_full(
            nombre_envio="Full Sync",
            archivo_excel="sync.xlsx",
            creado_por="admin",
            items=[("COD-1", "Artículo 1", 8)],
        )
        self.store.registrar_escaneo_item_plan(plan_id, "COD-1", cantidad=3, picker="picker1")
        interfaz = _crear_interfaz_mock(self.store)
        sm_mock = MagicMock()

        res1 = procesar_cierre_plan_full_sync(
            interfaz,
            plan_id,
            es_final=False,
            picker_nom="picker1",
            stock_manager_cls=lambda _r: sm_mock,
        )
        self.assertTrue(res1["exito"])
        sm_mock.descontar_mercado_full.assert_called_once_with(
            {"COD-1": 3},
            nombre_archivo="sync.xlsx",
            sincronizar_excel=True,
        )

        # Escanea 2 más y realiza cierre final
        self.store.registrar_escaneo_item_plan(plan_id, "COD-1", cantidad=2, picker="picker1")
        res2 = procesar_cierre_plan_full_sync(
            interfaz,
            plan_id,
            es_final=True,
            picker_nom="picker1",
            stock_manager_cls=lambda _r: sm_mock,
        )
        self.assertTrue(res2["exito"])
        self.assertEqual(sm_mock.descontar_mercado_full.call_count, 2)
        self.assertEqual(
            sm_mock.descontar_mercado_full.call_args_list[1].args[0],
            {"COD-1": 2},
        )

        pedidos_mercado = self.store.listar_pedidos_mercado_pendientes_cierre()
        self.assertEqual(len(pedidos_mercado), 2)
        self.assertEqual(sum(p.articulos_descontados for p in pedidos_mercado), 5)

    def test_migracion_columnas_full_en_bd_heredada(self) -> None:
        legacy_db = Path(self._tmp.name) / "legacy.sqlite3"
        with closing(sqlite3.connect(legacy_db)) as conn:
            conn.execute(
                """
                CREATE TABLE planes_mercado_full (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nombre_envio TEXT NOT NULL,
                    archivo_excel TEXT NOT NULL,
                    creado_por TEXT NOT NULL,
                    estado TEXT NOT NULL DEFAULT 'pendiente',
                    articulos_totales INTEGER NOT NULL DEFAULT 0,
                    articulos_pickeados INTEGER NOT NULL DEFAULT 0,
                    porcentaje REAL NOT NULL DEFAULT 0.0,
                    picker_asignado TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE plan_mercado_full_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    plan_id INTEGER NOT NULL,
                    codigo TEXT NOT NULL,
                    descripcion TEXT NOT NULL DEFAULT '',
                    cantidad_solicitada INTEGER NOT NULL,
                    cantidad_pickeada INTEGER NOT NULL DEFAULT 0,
                    completado INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            conn.commit()

        migrated_store = OrderStore(legacy_db)
        with closing(sqlite3.connect(legacy_db)) as conn:
            cols_plan = {r[1] for r in conn.execute("PRAGMA table_info(planes_mercado_full)").fetchall()}
            cols_items = {r[1] for r in conn.execute("PRAGMA table_info(plan_mercado_full_items)").fetchall()}
            tablas = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}

        self.assertIn("articulos_descontados", cols_plan)
        self.assertIn("cantidad_descontada", cols_items)
        self.assertIn("cierres_parciales_full", tablas)
        self.assertEqual(migrated_store.listar_planes_mercado_full(), [])

    def test_dialogos_cierre_parcial_y_final_desde_despacho_y_picking(self) -> None:
        plan_id = self.store.crear_plan_mercado_full(
            nombre_envio="Full UI",
            archivo_excel="full_ui.xlsx",
            creado_por="admin",
            items=[("A1", "Producto UI", 10)],
        )
        self.store.registrar_escaneo_item_plan(plan_id, "A1", cantidad=4, picker="picker1")
        interfaz = _crear_interfaz_mock(self.store)

        # Cierre parcial habilitado porque hay 4 unidades pendientes de descontar
        mostrar_cierre_parcial_mercado_full(interfaz)
        dlg_parcial = interfaz.page.show_dialog.call_args[0][0]
        self.assertIsInstance(dlg_parcial, ft.AlertDialog)
        self.assertFalse(dlg_parcial.actions[1].disabled)

        # Cierre final habilitado incluso con avance < 100%
        interfaz.page.show_dialog.reset_mock()
        mostrar_cierre_final_mercado_full(interfaz)
        dlg_final = interfaz.page.show_dialog.call_args[0][0]
        self.assertIsInstance(dlg_final, ft.AlertDialog)
        self.assertFalse(dlg_final.actions[1].disabled)

        # Picking guiado expone ambos botones (Cierre Parcial + Finalizar)
        interfaz.page.show_dialog.reset_mock()
        mostrar_picking_guiado_full(interfaz)
        dlg_picking = interfaz.page.show_dialog.call_args[0][0]
        row_botones = dlg_picking.actions[1]
        self.assertEqual(len(row_botones.controls), 2)
        self.assertFalse(row_botones.controls[0].disabled)
        self.assertFalse(row_botones.controls[1].disabled)

    def test_coordinator_e_interfaz_exponen_acciones_despacho_picker(self) -> None:
        self.assertTrue(hasattr(InterfazFlet, "mostrar_cierre_mercado_envios"))
        self.assertTrue(hasattr(InterfazFlet, "mostrar_cierre_parcial_mercado_full"))
        self.assertTrue(hasattr(InterfazFlet, "mostrar_cierre_final_mercado_full"))

        host_picker = _crear_interfaz_mock(self.store, rol="picker")
        host_picker.cerrar_drawer_si_movil = MagicMock()
        coord = DialogCoordinator(host_picker)
        with patch("src.ui.controllers.dialog_coordinator.mostrar_dialogo_cierre_mercado") as mock_cierre:
            coord.mostrar_cierre_mercado_envios()
            mock_cierre.assert_called_once_with(host_picker, tab_inicial=0)

        # Rol no autorizado no abre diálogo
        host_consulta = _crear_interfaz_mock(self.store, rol="consulta")
        coord_denegado = DialogCoordinator(host_consulta)
        with patch("src.ui.controllers.dialog_coordinator.mostrar_cierre_parcial_mercado_full") as mock_parcial:
            coord_denegado.mostrar_cierre_parcial_mercado_full()
            mock_parcial.assert_not_called()
