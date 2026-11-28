"""Pruebas de UI Flet para Etapa A: Reposición/FEFO en Mapa de Calor y Modal Ubicaciones/Lotes."""

from __future__ import annotations

from contextlib import closing
from datetime import date, timedelta
import gc
from pathlib import Path
import tempfile
from types import SimpleNamespace
from typing import Any
import unittest
from unittest.mock import MagicMock

import flet as ft

from src.auth import User
from src.ui.protocols import AppDependencies
from src.flet_gui import InterfazFlet
from src.products import ProductStore
from src.ui.dialogs import (
    mostrar_dialogo_gestion_productos,
    mostrar_dialogo_ubicaciones_lotes,
)
from src.ui.dialogs.dlg_heatmap import mostrar_dialogo_heatmap


def _crear_interfaz_prueba(store: ProductStore) -> tuple[InterfazFlet, list[Any]]:
    dialogos: list = []
    controls: list = []
    fake_page = SimpleNamespace(
        width=1280,
        height=800,
        controls=controls,
        overlay=[],
        services=[],
        window=SimpleNamespace(),
        add=lambda *c: controls.extend(c),
        show_dialog=dialogos.append,
        pop_dialog=lambda: dialogos.pop() if dialogos else None,
        update=lambda: None,
    )
    fake_user_store = MagicMock()
    fake_user_store.has_users = True
    fake_order_store = MagicMock()
    fake_order_store.obtener_metricas_dashboard.return_value = {
        "total_pedidos": 0,
        "total_bultos": 0,
        "pedidos_cerrados": 0,
        "pedidos_pendientes": 0,
        "total_cierres": 0,
    }
    fake_order_store.listar_pedidos_cerrados.return_value = []
    fake_sm_cls = lambda _ruta: SimpleNamespace(  # noqa: E731
        product_store=store,
        listar_productos=lambda: store.list_products(),
    )
    deps = AppDependencies(
        user_store=fake_user_store,
        order_store=fake_order_store,
        product_store=store,
        menu=MagicMock(ruta_excel_base="Productos.xlsx"),
        stock_manager_factory=fake_sm_cls,
    )
    interfaz = InterfazFlet(fake_page, deps=deps)
    interfaz.usuario_actual = User(1, "admin", "administrador", True)
    dialogos.clear()
    return interfaz, dialogos


def _buscar_controles(raiz: object, predicado) -> list:
    encontrados = []
    pila = [raiz]
    visitados: set[int] = set()
    while pila:
        actual = pila.pop()
        if actual is None or id(actual) in visitados:
            continue
        visitados.add(id(actual))
        if predicado(actual):
            encontrados.append(actual)
        for attr in ("content", "controls", "tabs", "actions"):
            val = getattr(actual, attr, None)
            if isinstance(val, (list, tuple)):
                pila.extend(reversed(val))
            elif val is not None:
                pila.append(val)
    return encontrados


class TestEtapaAUiFefoMultiloc(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = ProductStore(Path(self.temp_dir.name) / "productos.sqlite3")
        with closing(self.store._connect()) as conn, conn:
            conn.execute(
                """
                INSERT INTO products (code, name, stock, stock_minimo, stock_maximo, active, ubicacion)
                VALUES ('REP-1', 'Adhesivo Industrial', 26, 5, 20, 1, 'A-01-1')
                """
            )
        self.store.asignar_ubicacion_producto(
            "REP-1", "A-01-1", tipo_zona="picking", stock=1, capacidad_max=20, es_principal=True
        )
        self.store.asignar_ubicacion_producto(
            "REP-1", "P-01-1", tipo_zona="pulmon", stock=25, capacidad_max=80, es_principal=False
        )
        fv_critica = (date.today() + timedelta(days=5)).isoformat()
        self.store.registrar_lote(
            "REP-1", "L-URG", 15, fecha_vencimiento=fv_critica, ubicacion="P-01-1"
        )

    def tearDown(self) -> None:
        del self.store
        gc.collect()
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_01_heatmap_cuarta_pestana_reposicion_y_traslado(self) -> None:
        interfaz, dialogos = _crear_interfaz_prueba(self.store)
        mostrar_dialogo_heatmap(interfaz)

        dlg_heatmap = dialogos[0]
        self.assertIsInstance(dlg_heatmap, ft.AlertDialog)
        tabs = dlg_heatmap.content.content.controls[2]
        self.assertEqual(tabs.length, 4)

        tab_bar = tabs.content.controls[0]
        self.assertEqual(tab_bar.tabs[3].label, "Reposición y FEFO")

        panel_fefo = tabs.content.controls[1].controls[3]
        lista_fefo = panel_fefo.controls[1]
        botones_traslado = _buscar_controles(
            lista_fefo,
            lambda c: isinstance(c, ft.Button) and c.content == "Ejecutar Traslado",
        )
        self.assertEqual(len(botones_traslado), 1)

        # Ejecutar traslado directo desde el botón de la 4ta pestaña
        botones_traslado[0].on_click(None)

        self.assertIsInstance(dialogos[-1], ft.SnackBar)
        self.assertEqual(dialogos[-1].bgcolor, ft.Colors.GREEN_600)
        ubics = {u["ubicacion"]: u for u in self.store.listar_ubicaciones_producto("REP-1")}
        self.assertGreater(ubics["A-01-1"]["stock"], 1)
        self.assertLess(ubics["P-01-1"]["stock"], 25)

        # Verificar filtrado de alertas FEFO por nivel
        filtro_fefo = panel_fefo.controls[0].controls[1]
        filtro_fefo.value = "VENCIDO"
        filtro_fefo.on_change(None)
        cards_alerta_venc = _buscar_controles(
            lista_fefo,
            lambda c: isinstance(c, ft.Text) and "No hay lotes vencidos" in str(c.value or ""),
        )
        self.assertTrue(cards_alerta_venc)

        filtro_fefo.value = "CRITICO"
        filtro_fefo.on_change(None)
        textos_lote = _buscar_controles(
            lista_fefo,
            lambda c: isinstance(c, ft.Text) and "L-URG" in str(c.value or ""),
        )
        self.assertTrue(textos_lote)

    def test_02_catalogo_abre_modal_ubicaciones_lotes_y_muta_estado(self) -> None:
        interfaz, dialogos = _crear_interfaz_prueba(self.store)
        mostrar_dialogo_gestion_productos(interfaz)
        self.assertIsInstance(dialogos[0], ft.AlertDialog)

        botones_wh = _buscar_controles(
            dialogos[0],
            lambda c: isinstance(c, ft.IconButton) and c.icon == ft.Icons.WAREHOUSE_OUTLINED,
        )
        self.assertGreaterEqual(len(botones_wh), 1)

        # Abrir el modal de ubicaciones/lotes desde el botón de catálogo
        botones_wh[0].on_click(None)
        dlg_sku = dialogos[-1]
        self.assertIsInstance(dlg_sku, ft.AlertDialog)
        self.assertIn("REP-1", dlg_sku.title.controls[0].value)

        # Asignar nueva ubicación desde el formulario del modal
        campos_texto = _buscar_controles(dlg_sku, lambda c: isinstance(c, ft.TextField))
        por_label = {c.label: c for c in campos_texto}
        por_label["Ubicación (ej: P-01-2)"].value = "P-05-2"
        por_label["Stock"].value = "12"
        por_label["Cap. máx"].value = "40"
        btn_guardar_ubic = _buscar_controles(
            dlg_sku, lambda c: isinstance(c, ft.Button) and c.content == "Guardar Ubic."
        )[0]
        btn_guardar_ubic.on_click(None)

        ubics = {u["ubicacion"]: u for u in self.store.listar_ubicaciones_producto("REP-1")}
        self.assertIn("P-05-2", ubics)
        self.assertEqual(ubics["P-05-2"]["stock"], 12)

        # Transferir desde P-05-2 hacia A-01-1
        stock_a_prev = ubics["A-01-1"]["stock"]
        dropdowns = {
            c.label: c for c in _buscar_controles(dlg_sku, lambda c: isinstance(c, ft.Dropdown))
        }
        dropdowns["Origen"].value = "P-05-2"
        por_label["Destino"].value = "A-01-1"
        por_label["Cant. traslado"].value = "4"
        btn_transf = _buscar_controles(
            dlg_sku, lambda c: isinstance(c, ft.Button) and c.content == "Transferir"
        )[0]
        btn_transf.on_click(None)

        ubics_post = {u["ubicacion"]: u for u in self.store.listar_ubicaciones_producto("REP-1")}
        self.assertEqual(ubics_post["P-05-2"]["stock"], 8)
        self.assertEqual(ubics_post["A-01-1"]["stock"], stock_a_prev + 4)

        # Registrar lote FEFO desde la pestaña 2 del modal
        por_label["Lote *"].value = "L-CAT-99"
        por_label["Cant. lote"].value = "9"
        por_label["Vencimiento (YYYY-MM-DD)"].value = (date.today() + timedelta(days=45)).isoformat()
        por_label["Ubicación"].value = "A-01-1"
        btn_lote = _buscar_controles(
            dlg_sku, lambda c: isinstance(c, ft.Button) and c.content == "Registrar Lote"
        )[0]
        btn_lote.on_click(None)

        lotes = [lote["lote"] for lote in self.store.listar_lotes_fefo("REP-1")]
        self.assertIn("L-CAT-99", lotes)

        # Verificar que el acceso directo mostrar_dialogo_ubicaciones_lotes también notifique callback
        llamado = []
        mostrar_dialogo_ubicaciones_lotes(
            interfaz,
            SimpleNamespace(product_store=self.store),
            {"code": "REP-1", "name": "Adhesivo Industrial"},
            on_actualizado=lambda: llamado.append(True),
        )
        dlg_directo = dialogos[-1]
        campos_d = {
            c.label: c for c in _buscar_controles(dlg_directo, lambda c: isinstance(c, ft.TextField))
        }
        campos_d["Ubicación (ej: P-01-2)"].value = "PAL-09"
        _buscar_controles(
            dlg_directo, lambda c: isinstance(c, ft.Button) and c.content == "Guardar Ubic."
        )[0].on_click(None)
        self.assertTrue(llamado)


if __name__ == "__main__":
    unittest.main()
