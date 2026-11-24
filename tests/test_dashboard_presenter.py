"""Pruebas unitarias para el módulo de presentación del Dashboard (dashboard_presenter)."""

import unittest
from unittest.mock import MagicMock
from pathlib import Path
import flet as ft

from src.ui.dashboard_presenter import (
    actualizar_estado_dashboard,
    renderizar_auditoria_master,
    renderizar_pedidos_armados_por_fecha,
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
        iconos = [btn.icon for btn in tile.trailing.controls if isinstance(btn, ft.IconButton)]
        self.assertIn(ft.Icons.PRINT, iconos)

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

    def test_renderizar_pedidos_armados_por_fecha_descendente(self):
        """Verifica que la tarjeta derecha del operador muestre el resumen de pedidos por fecha y cantidad descendente."""
        resumen = [
            {"fecha": "2026-11-14", "cantidad_pedidos": 10, "total_bultos": 22, "total_articulos": 45},
            {"fecha": "2026-11-16", "cantidad_pedidos": 24, "total_bultos": 58, "total_articulos": 110},
            {"fecha": "2026-11-15", "cantidad_pedidos": 15, "total_bultos": 30, "total_articulos": 60},
        ]
        renderizar_pedidos_armados_por_fecha(self.interfaz, resumen)
        self.assertEqual(len(self.interfaz.lista_informes.controls), 3)

        def extraer_textos(ctrl):
            txts = []
            if isinstance(ctrl, ft.Text) and ctrl.value:
                txts.append(str(ctrl.value))
            if getattr(ctrl, "content", None) is not None:
                txts.extend(extraer_textos(ctrl.content))
            for ch in getattr(ctrl, "controls", []) or []:
                txts.extend(extraer_textos(ch))
            return txts

        txt_0 = " ".join(extraer_textos(self.interfaz.lista_informes.controls[0]))
        txt_1 = " ".join(extraer_textos(self.interfaz.lista_informes.controls[1]))
        txt_2 = " ".join(extraer_textos(self.interfaz.lista_informes.controls[2]))

        self.assertIn("16/11/2026", txt_0)
        self.assertIn("24 pedidos", txt_0)
        self.assertIn("58 bulto(s)", txt_0)

        self.assertIn("15/11/2026", txt_1)
        self.assertIn("15 pedidos", txt_1)

        self.assertIn("14/11/2026", txt_2)
        self.assertIn("10 pedidos", txt_2)

    def test_order_store_obtener_resumen_pedidos_por_fecha_sqlite(self):
        """Verifica que OrderStore agrupe los pedidos armados (no anulados) por fecha descendente."""
        import tempfile
        from src.orders import OrderStore

        with tempfile.TemporaryDirectory() as tmpdir:
            store = OrderStore(Path(tmpdir) / "pedidos.sqlite3")
            p1 = store.registrar_pedido(
                nota_pedido="R-001",
                numero_pedido="1",
                cliente="Cliente A",
                bultos=3,
                logistica="Transporte",
                armador="operador1",
                tipo_archivo="pdf",
                nombre_archivo="r1.pdf",
                articulos_descontados=10,
            )
            p2 = store.registrar_pedido(
                nota_pedido="R-002",
                numero_pedido="2",
                cliente="Cliente B",
                bultos=2,
                logistica="Domicilio",
                armador="operador1",
                tipo_archivo="pdf",
                nombre_archivo="r2.pdf",
                articulos_descontados=5,
            )
            p3 = store.registrar_pedido(
                nota_pedido="R-003",
                numero_pedido="3",
                cliente="Cliente C",
                bultos=4,
                logistica="Transporte",
                armador="operador1",
                tipo_archivo="pdf",
                nombre_archivo="r3.pdf",
                articulos_descontados=8,
            )
            with store._connect() as conn, conn:
                conn.execute("UPDATE pedidos SET created_at = '2026-11-15 10:00:00' WHERE id = ?", (p1.id,))
                conn.execute("UPDATE pedidos SET created_at = '2026-11-16 09:00:00' WHERE id IN (?, ?)", (p2.id, p3.id))

            resumen = store.obtener_resumen_pedidos_por_fecha()
            self.assertEqual(len(resumen), 2)
            self.assertEqual(resumen[0]["fecha"], "2026-11-16")
            self.assertEqual(resumen[0]["cantidad_pedidos"], 2)
            self.assertEqual(resumen[0]["total_bultos"], 6)
            self.assertEqual(resumen[0]["total_articulos"], 13)

            self.assertEqual(resumen[1]["fecha"], "2026-11-15")
            self.assertEqual(resumen[1]["cantidad_pedidos"], 1)
            self.assertEqual(resumen[1]["total_bultos"], 3)

    def test_tarjetas_operador_alineadas_misma_altura_y_redimensionables_en_desktop(self):
        """La tarjeta de pedidos en carga y la de pedidos armados comparten altura y alineación stretch en escritorio."""
        from src.ui.components.panels import (
            altura_tarjetas_actividad_desktop,
            construir_panel_informes_actividad,
        )
        from src.ui.controllers.responsive_controller import ResponsiveController

        self.interfaz.es_pantalla_movil = False
        self.interfaz.posicion_sidebar = "izquierda"
        self.interfaz.page = MagicMock(width=1280, height=900, client_user_agent="", platform="windows")
        self.interfaz.tarjeta = lambda contenido, expand=True: ft.Container(content=contenido, expand=expand)
        self.interfaz._modo_movil_previo = False

        panel = construir_panel_informes_actividad(self.interfaz)
        self.assertIsInstance(panel, ft.Row)
        self.assertEqual(panel.vertical_alignment, ft.CrossAxisAlignment.STRETCH)
        self.assertEqual(panel.height, altura_tarjetas_actividad_desktop(self.interfaz))
        self.assertEqual(panel.height, 490)
        self.assertEqual(len(panel.controls), 2)
        self.assertTrue(panel.controls[0].expand)
        self.assertTrue(panel.controls[1].expand)
        self.assertIs(self.interfaz._panel_tarjetas_row, panel)

        # Al redimensionar en desktop, recalcula la altura para mantener ambas tarjetas alineadas
        ctrl = ResponsiveController(self.interfaz)
        self.interfaz.page.height = 1000
        ctrl.al_redimensionar()
        self.assertEqual(panel.height, 590)
        self.interfaz.page.update.assert_called()

        # En móvil apila en Column y limpia la referencia desktop
        self.interfaz.es_pantalla_movil = True
        panel_movil = construir_panel_informes_actividad(self.interfaz)
        self.assertIsInstance(panel_movil, ft.Column)
        self.assertIsNone(self.interfaz._panel_tarjetas_row)


if __name__ == "__main__":
    unittest.main()
