"""Pruebas unitarias para el módulo de presentación del Dashboard (dashboard_presenter)."""

import unittest
from unittest.mock import MagicMock
from pathlib import Path
import flet as ft

from src.ui.dashboard_presenter import (
    actualizar_estado_dashboard,
    renderizar_auditoria_master,
    renderizar_pedidos_preparados_turno,
    renderizar_informes_generados,
)


class TestDashboardPresenter(unittest.TestCase):
    def setUp(self):
        self.interfaz = MagicMock()
        self.interfaz.texto = ft.Colors.WHITE
        self.interfaz.secundario = ft.Colors.GREY_400
        self.interfaz.superficie = ft.Colors.GREY_900
        self.interfaz.borde = ft.Colors.GREY_800
        self.interfaz.modo_oscuro = True

        self.interfaz.lista_informes = ft.Column()
        self.interfaz.lista_pedidos_preparados = ft.Column()
        self.interfaz.header_pedidos_fecha = ft.Text("")
        self.interfaz.header_pedidos_subtitulo = ft.Text("")
        self.interfaz.header_pedidos_bultos = ft.Text("")
        self.interfaz.pendientes_texto = ft.Text("")
        self.interfaz.contadores = {
            "pdf": ft.Text("0"),
            "canjes": ft.Text("0"),
            "ml": ft.Text("0"),
            "total": ft.Text("0"),
            "informes": ft.Text("0"),
        }
        self.interfaz.banner_alerta_quiebre = MagicMock()

        self.usuario_operador = MagicMock()
        self.usuario_operador.role = "operador"
        self.usuario_operador.username = "operador1"
        self.interfaz.usuario_actual = self.usuario_operador

        self.interfaz.menu = MagicMock()
        self.interfaz.menu._obtener_pendientes.return_value = ([], [], [])
        self.interfaz.menu._obtener_archivados.return_value = []
        self.interfaz.menu._obtener_generados.return_value = []

        self.interfaz.order_store = MagicMock()
        self.interfaz.order_store.contar_pedidos_pendientes_cierre_por_tipo.return_value = {
            "pdf": 3,
            "excel": 2,
            "docx": 1,
            "total": 6,
        }
        self.interfaz.order_store.listar_pedidos_pendientes_cierre.return_value = []

    def test_renderizar_auditoria_master_vacia(self):
        """Verifica el mensaje cuando no hay auditoría en rol Master."""
        renderizar_auditoria_master(self.interfaz, [])
        self.assertEqual(len(self.interfaz.lista_informes.controls), 1)
        self.assertIn("todavía no hay eventos", self.interfaz.lista_informes.controls[0].value.lower())

    def test_renderizar_auditoria_master_con_eventos(self):
        """Verifica la generación de tarjetas de eventos con iconos diferenciados."""
        ev1 = MagicMock(accion="LOGIN_SUCCESS", usuario="admin", fecha="2026-11-05 10:00", detalle="Inicio de sesión")
        ev2 = MagicMock(accion="INGRESO_RAPIDO", usuario="juan", fecha="2026-11-05 10:15", detalle="[Devolución] x5")
        ev3 = MagicMock(accion="SALIDA_RAPIDA", usuario="juan", fecha="2026-11-05 10:20", detalle="[Rotura] x2")

        renderizar_auditoria_master(self.interfaz, [ev1, ev2, ev3])
        self.assertEqual(len(self.interfaz.lista_informes.controls), 3)

        tile_ingreso = self.interfaz.lista_informes.controls[1]
        self.assertIn("INGRESO_RAPIDO", tile_ingreso.title.value)
        self.assertEqual(tile_ingreso.leading.icon, ft.Icons.ADD_CIRCLE_OUTLINE)

        tile_salida = self.interfaz.lista_informes.controls[2]
        self.assertIn("SALIDA_RAPIDA", tile_salida.title.value)
        self.assertEqual(tile_salida.leading.icon, ft.Icons.REMOVE_CIRCLE_OUTLINE)

    def test_renderizar_pedidos_preparados_con_items(self):
        """Verifica el armado de tarjetas para los pedidos preparados."""
        ped = MagicMock()
        ped.id = 101
        ped.numero_pedido = "554"
        ped.nota_pedido = "NP-9988"
        ped.cliente = "Ferretería Central"
        ped.logistica = "Expreso Brio"
        ped.bultos = 4
        ped.created_at = "2026-11-05 14:30:00"
        ped.resumen_items = "Taladro x2, Amoladora x2"
        ped.articulos_descontados = 4

        renderizar_pedidos_preparados_turno(self.interfaz, [ped])
        self.assertEqual(len(self.interfaz.lista_pedidos_preparados.controls), 1)
        self.assertIn("4 bultos", self.interfaz.header_pedidos_bultos.value)

    def test_actualizar_estado_dashboard_operador(self):
        """Verifica la orquestación completa de actualización para el rol operador."""
        actualizar_estado_dashboard(self.interfaz)

        # Contadores actualizados según order_store
        self.assertEqual(self.interfaz.contadores["pdf"].value, "3")
        self.assertEqual(self.interfaz.contadores["canjes"].value, "2")
        self.assertEqual(self.interfaz.contadores["ml"].value, "1")
        self.assertEqual(self.interfaz.contadores["total"].value, "6")
        self.interfaz._actualizar_estado_boton_cierre.assert_called_with(6)

    def test_renderizar_informes_generados_formato_en_linea(self):
        """Verifica que los informes se muestren en línea con tight=True y no_wrap."""
        ruta_informe = Path("Remito_0001-00024922_20261105_145238.pdf")
        mtimes = {ruta_informe: 1730825558.0}

        renderizar_informes_generados(self.interfaz, [ruta_informe], mtimes)

        self.assertEqual(len(self.interfaz.lista_informes.controls), 1)
        tile = self.interfaz.lista_informes.controls[0]
        self.assertIsInstance(tile, ft.ListTile)
        self.assertEqual(tile.title.value, ruta_informe.name)
        self.assertTrue(tile.title.no_wrap)
        self.assertEqual(tile.title.max_lines, 1)
        self.assertEqual(tile.title.overflow, ft.TextOverflow.ELLIPSIS)
        self.assertTrue(tile.subtitle.no_wrap)
        self.assertTrue(tile.trailing.tight)

    def test_renderizar_pedidos_preparados_boton_editar_operador(self):
        """Verifica que para un operador aparezca el botón de editar pedido."""
        ped = MagicMock()
        ped.id = 101
        ped.numero_pedido = "10"
        ped.nota_pedido = "0001-00024922"
        ped.cliente = "Distribuidora JBM"
        ped.logistica = "Centro de distribución"
        ped.bultos = 1
        ped.created_at = "2026-11-06 17:07:00"
        ped.resumen_items = "1 productos (3 un.)"
        ped.articulos_descontados = 3

        renderizar_pedidos_preparados_turno(self.interfaz, [ped])

        self.assertEqual(len(self.interfaz.lista_pedidos_preparados.controls), 1)
        card = self.interfaz.lista_pedidos_preparados.controls[0]
        col_der = card.content.controls[1]
        botones = [c for c in col_der.controls if isinstance(c, ft.IconButton)]
        self.assertEqual(len(botones), 1)
        self.assertEqual(botones[0].icon, ft.Icons.EDIT_OUTLINED)


if __name__ == "__main__":
    unittest.main()
