"""Tests unitarios para el módulo de Cierre de Mercado (Mercado Libre y Mercado Full) para pickers."""

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.orders import OrderStore
from src.ui.dialogs.cierre.cierre_mercado_exec import ejecutar_tarea_cierre_mercado
from src.ui.dialogs.cierre.dlg_cierre_mercado import mostrar_dialogo_cierre_mercado
from src.flet_gui import InterfazFlet


class TestCierreMercadoPicker(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp_dir.name) / "pedidos_test.db"
        self.store = OrderStore(self.db_path)

        # Crear pedidos de prueba
        self.p_ml = self.store.registrar_pedido(
            nota_pedido="ML-20261114-001",
            numero_pedido="43219876",
            cliente="Mercado Libre",
            bultos=1,
            logistica="Transporte",
            armador="picker1",
            tipo_archivo="docx",
            nombre_archivo="ML_SCAN_ML-20261114-001.docx",
            agregado=False,
            articulos_descontados=10,
            resumen_items="2 productos (10 un.)",
            items=[("101", "Whey Protein 1kg", 6), ("202", "Creatina 300g", 4)],
        )

        self.p_full = self.store.registrar_pedido(
            nota_pedido="FULL-EnvioPalletA",
            numero_pedido="EnvioPalletA",
            cliente="Mercado Envíos Full",
            bultos=2,
            logistica="Transporte",
            armador="picker1",
            tipo_archivo="excel",
            nombre_archivo="Full_EnvioPalletA.xlsx",
            agregado=False,
            articulos_descontados=20,
            resumen_items="1 producto (20 un.)",
            items=[("101", "Whey Protein 1kg", 20)],
        )

        # Pedido mayorista común (no de mercado)
        self.p_mayorista = self.store.registrar_pedido(
            nota_pedido="REM-9999",
            numero_pedido="9999",
            cliente="Distribuidora Norte",
            bultos=3,
            logistica="Transporte",
            armador="operario1",
            tipo_archivo="pdf",
            nombre_archivo="Remito_9999.pdf",
            agregado=False,
            articulos_descontados=5,
            resumen_items="1 producto (5 un.)",
            items=[("202", "Creatina 300g", 5)],
        )

    def tearDown(self):
        try:
            self.tmp_dir.cleanup()
        except Exception:
            pass

    def test_schema_incluye_cierres_mercado_y_columna(self):
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            tables = {r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
            self.assertIn("cierres_mercado", tables)

            cols_pedidos = {r["name"] for r in conn.execute("PRAGMA table_info(pedidos)").fetchall()}
            self.assertIn("cierre_mercado_id", cols_pedidos)
        finally:
            conn.close()

    def test_listar_pedidos_mercado_pendientes_filtra_solo_mercado(self):
        pendientes = self.store.listar_pedidos_mercado_pendientes_cierre(tipo="TODOS")
        ids = [p.id for p in pendientes]
        self.assertIn(self.p_ml.id, ids)
        self.assertIn(self.p_full.id, ids)
        self.assertNotIn(self.p_mayorista.id, ids)

    def test_listar_pedidos_mercado_filtro_tipo(self):
        solo_ml = self.store.listar_pedidos_mercado_pendientes_cierre(tipo="MERCADO_LIBRE")
        self.assertEqual(len(solo_ml), 1)
        self.assertEqual(solo_ml[0].id, self.p_ml.id)

        solo_full = self.store.listar_pedidos_mercado_pendientes_cierre(tipo="MERCADO_FULL")
        self.assertEqual(len(solo_full), 1)
        self.assertEqual(solo_full[0].id, self.p_full.id)

    def test_registrar_cierre_mercado_sella_pedidos(self):
        peds = [self.p_ml, self.p_full]
        cierre_id = self.store.registrar_cierre_mercado(
            usuario="picker1",
            tipo_mercado="TODOS",
            pedidos_ids=[p.id for p in peds],
            articulos_totales=30,
            resumen_pedidos="2 pedidos (30 un.)",
            archivo_pdf="Cierre_Mercado_TODOS_test.pdf",
            archivo_excel="Cierre_Mercado_TODOS_test.xlsx",
        )
        self.assertGreater(cierre_id, 0)

        # Ahora la lista de pendientes de mercado debe estar vacía
        pendientes_post = self.store.listar_pedidos_mercado_pendientes_cierre(tipo="TODOS")
        self.assertEqual(len(pendientes_post), 0)

        # El historial de cierres de mercado debe registrar el cierre
        cierres = self.store.listar_cierres_mercado()
        self.assertEqual(len(cierres), 1)
        self.assertEqual(cierres[0].id, cierre_id)
        self.assertEqual(cierres[0].usuario, "picker1")
        self.assertEqual(cierres[0].articulos_totales, 30)

    def test_pedidos_cerrados_en_mercado_se_mantienen_para_cierre_final_operador(self):
        """Verifica que el cierre de mercado NO inhabilite el cierre final de jornada del operador."""
        # Picker cierra su tanda de mercado
        self.store.registrar_cierre_mercado(
            usuario="picker1",
            tipo_mercado="TODOS",
            pedidos_ids=[self.p_ml.id, self.p_full.id],
            articulos_totales=30,
            resumen_pedidos="2 pedidos (30 un.)",
        )

        # Para el operador, todos los pedidos siguen pendientes de cierre de jornada general (cierre_id IS NULL)
        pendientes_operador = self.store.listar_pedidos_pendientes_cierre()
        ids_operador = [p.id for p in pendientes_operador]
        self.assertIn(self.p_ml.id, ids_operador)
        self.assertIn(self.p_full.id, ids_operador)
        self.assertIn(self.p_mayorista.id, ids_operador)

        # Y la sumatoria de items consolidada para el operador incluye los productos de mercado
        items_consolidados = self.store.obtener_items_pendientes_cierre()
        dict_cantidades = {cod: cant for cod, desc, cant, remitos in items_consolidados}

        # Whey Protein 1kg: 6 (de ML) + 20 (de Full) = 26
        self.assertEqual(dict_cantidades.get("101"), 26)
        # Creatina 300g: 4 (de ML) + 5 (de Mayorista) = 9
        self.assertEqual(dict_cantidades.get("202"), 9)

    def test_preparacion_multidia_full_cierres_diarios_y_cierre_final_picker(self):
        """Valida que un Full preparado a lo largo de varios días se cierre diariamente por el operador y luego se consolide el miércoles por el picker."""
        # Lunes: Se prepara y descuenta Full Lote 1 (50 Whey)
        ped_lunes = self.store.registrar_pedido(
            nota_pedido="FULL-Lunes",
            numero_pedido="Lunes",
            cliente="Mercado Envíos Full",
            bultos=1,
            logistica="Transporte",
            armador="picker1",
            tipo_archivo="excel",
            nombre_archivo="Full_Lunes.xlsx",
            agregado=False,
            articulos_descontados=50,
            resumen_items="1 producto (50 un.)",
            items=[("101", "Whey Protein 1kg", 50)],
        )

        # Lunes a la noche: El operador hace su Cierre de Jornada del Lunes
        cierre_lunes_id = self.store.registrar_cierre(
            usuario="operador1",
            pedidos_ids=[self.p_mayorista.id, ped_lunes.id],
            articulos_totales=55,
            resumen_pedidos="Cierre Lunes (Mayorista + Full Lunes)",
        )
        self.assertGreater(cierre_lunes_id, 0)

        # Martes: Se prepara y descuenta Full Lote 2 (30 Creatina)
        ped_martes = self.store.registrar_pedido(
            nota_pedido="FULL-Martes",
            numero_pedido="Martes",
            cliente="Mercado Envíos Full",
            bultos=1,
            logistica="Transporte",
            armador="picker1",
            tipo_archivo="excel",
            nombre_archivo="Full_Martes.xlsx",
            agregado=False,
            articulos_descontados=30,
            resumen_items="1 producto (30 un.)",
            items=[("202", "Creatina 300g", 30)],
        )

        # Martes a la noche: El operador hace su Cierre de Jornada del Martes
        cierre_martes_id = self.store.registrar_cierre(
            usuario="operador1",
            pedidos_ids=[ped_martes.id],
            articulos_totales=30,
            resumen_pedidos="Cierre Martes (Full Martes)",
        )
        self.assertGreater(cierre_martes_id, 0)

        # Miércoles: El picker finalmente termina el pallet y hace "Cerrar Mercado"
        # Debe poder ver TANTO el lote del Lunes como el del Martes (porque cierre_mercado_id sigue NULL)
        pendientes_picker = self.store.listar_pedidos_mercado_pendientes_cierre(tipo="MERCADO_FULL")
        ids_pendientes = [p.id for p in pendientes_picker]
        self.assertIn(ped_lunes.id, ids_pendientes)
        self.assertIn(ped_martes.id, ids_pendientes)

        # El picker cierra la tanda completa de Full acumulada de los días anteriores
        items_full_consolidados = self.store.obtener_items_mercado_pendientes([ped_lunes.id, ped_martes.id])
        cantidades_full = {cod: cant for cod, desc, cant, remitos in items_full_consolidados}
        self.assertEqual(cantidades_full["101"], 50)
        self.assertEqual(cantidades_full["202"], 30)

        cierre_full_total_id = self.store.registrar_cierre_mercado(
            usuario="picker1",
            tipo_mercado="MERCADO_FULL",
            pedidos_ids=[ped_lunes.id, ped_martes.id],
            articulos_totales=80,
            resumen_pedidos="2 pedidos Full (80 un. totales acumuladas)",
        )
        self.assertGreater(cierre_full_total_id, 0)

        # Ahora el picker ya no tiene pendientes de Full
        self.assertEqual(len(self.store.listar_pedidos_mercado_pendientes_cierre(tipo="MERCADO_FULL")), 1) # Solo queda self.p_full del setUp

    def test_ejecutar_tarea_cierre_mercado_usa_descuento_ya_aplicado(self):
        mock_interfaz = MagicMock()
        mock_interfaz.order_store = self.store
        mock_interfaz.usuario_actual.username = "picker1"
        mock_interfaz.menu.ruta_excel_base = Path("Productos.xlsx")
        mock_interfaz.menu.carpeta_descuentos = Path(self.tmp_dir.name)

        mock_stock_mgr = MagicMock()
        mock_stock_mgr.aplicar_descuentos.return_value = MagicMock(
            archivo_pdf=str(Path(self.tmp_dir.name) / "Cierre_Mercado.pdf"),
            archivo_guardado=str(Path(self.tmp_dir.name) / "Cierre_Mercado.xlsx"),
        )

        with patch("src.ui.dialogs.cierre.cierre_mercado_exec._resolver_sm_cls", return_value=lambda **_kw: mock_stock_mgr):
            resultado = ejecutar_tarea_cierre_mercado(
                interfaz=mock_interfaz,
                pedidos_seleccionados=[self.p_ml, self.p_full],
                tipo_mercado="TODOS",
            )

        self.assertIn("cierre_id", resultado)
        mock_stock_mgr.aplicar_descuentos.assert_called_once()
        _, kwargs = mock_stock_mgr.aplicar_descuentos.call_args
        self.assertTrue(kwargs.get("descuento_ya_aplicado"))
        self.assertTrue(kwargs.get("guardar_archivo"))

    def test_interfaz_flet_tiene_mostrar_cierre_mercado(self):
        self.assertTrue(hasattr(InterfazFlet, "mostrar_cierre_mercado"))

    def test_mostrar_dialogo_cierre_mercado_construye_alert_dialog(self):
        mock_interfaz = MagicMock()
        mock_interfaz.exigir_roles.return_value = True
        mock_interfaz.modo_oscuro = True
        mock_interfaz.es_pantalla_movil = False
        mock_interfaz.texto = "#FFFFFF"
        mock_interfaz.secundario = "#90A4AE"
        mock_interfaz.borde = "#37474F"
        mock_interfaz.fondo_acento = "#263238"
        mock_interfaz.order_store = self.store
        mock_interfaz.usuario_actual.username = "picker1"
        mock_interfaz.usuario_actual.role = "picker"

        mostrar_dialogo_cierre_mercado(mock_interfaz)
        mock_interfaz.page.show_dialog.assert_called_once()
        dialogo = mock_interfaz.page.show_dialog.call_args[0][0]
        self.assertIsNotNone(dialogo)
        self.assertTrue("Cierre de Mercado" in dialogo.title.controls[1].value)


if __name__ == "__main__":
    unittest.main()
