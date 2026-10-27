import asyncio
import os
import socket
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from unittest.mock import patch

import flet as ft

from src.flet_gui import InterfazFlet
from src.user_store import User, UserRole


def _loopback_disponible() -> bool:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", 0))
        s.listen(1)
        s.settimeout(0.05)
        c = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            c.settimeout(0.05)
            c.connect(s.getsockname())
            conn, _ = s.accept()
            conn.close()
            return True
        finally:
            c.close()
    except OSError:
        return False
    finally:
        s.close()


if not _loopback_disponible():
    async def _sync_to_thread(func, /, *args, **kwargs):
        return func(*args, **kwargs)

    def _run_coro_sync(coro):
        try:
            while True:
                coro.send(None)
        except StopIteration as exc:
            return exc.value

    asyncio.to_thread = _sync_to_thread  # type: ignore[assignment]
    asyncio.run = _run_coro_sync  # type: ignore[assignment]


class FakeMenu:
    ruta_excel_base = "Productos.xlsx"
    base_dir = Path(".")
    carpeta_mercado_full = Path("Descuentos/MercadoFull")
    carpeta_stock_fisico = Path("Descuentos/StockFisico")

    def __init__(self):
        self.procesamientos = []
        self.restauraciones = []

    def _obtener_pendientes(self):
        return [], [], []

    def _obtener_pendientes_fabrica(self):
        return []

    def _obtener_pendientes_mercado_full(self):
        return []

    def _obtener_pendientes_stock_fisico(self):
        return []

    def _obtener_archivados(self):
        return [], [], []

    def _obtener_generados(self):
        return []

    def procesar(self, **opciones):
        self.procesamientos.append(opciones)
        print("Simulación comprobada")

    def fechas_descuento_disponibles(self):
        return ["2026-10-22", "2026-10-21"]

    def restaurar_para_pruebas(self, fecha):
        self.restauraciones.append(fecha)
        print(f"Restaurando {fecha}")


class FakePage:
    def __init__(self):
        self.controls = []
        self.window = SimpleNamespace()
        self.dialogos = []

    def add(self, *controls):
        self.controls.extend(controls)

    def update(self):
        pass

    def show_dialog(self, dialog):
        self.dialogos.append(dialog)

    def pop_dialog(self):
        if self.dialogos:
            self.dialogos.pop()


class FakeUserStore:
    def __init__(self, has_users=True):
        self.has_users = has_users
        self.user = User(1, "admin", "administrador", True)

    def get_user(self, user_id):
        return self.user if user_id == self.user.id else None

    def list_users(self):
        return [self.user]


class FletGuiTests(unittest.TestCase):
    def crear_interfaz(self, role: UserRole = "administrador"):
        menu = FakeMenu()
        page = FakePage()
        user_store = FakeUserStore()
        user_store.user = User(1, "test-user", role, True)
        with patch("src.flet_gui.MenuAgente", return_value=menu), patch(
            "src.flet_gui.UserStore", return_value=user_store
        ):
            interfaz = InterfazFlet(cast(ft.Page, page))
        interfaz.usuario_actual = user_store.user
        interfaz.construir()
        return interfaz, menu, page

    def test_builds_dashboard_and_local_chat(self):
        interfaz, _, page = self.crear_interfaz()

        self.assertEqual(len(page.controls), 1)
        self.assertTrue(page.window.maximized)
        self.assertEqual(
            page.window.icon,
            str(Path(__file__).resolve().parent.parent / "src" / "img" / "ultratech.ico"),
        )
        self.assertEqual(len(interfaz.controles_tarea), 17)
        bienvenida = cast(ft.Container, interfaz.conversacion.controls[0])
        contenido = cast(ft.Column, bienvenida.content)
        self.assertEqual(cast(ft.Text, contenido.controls[0]).value, "Agente")
        self.assertEqual(interfaz.estado_tarea.value, "Listo")

    def test_sidebar_displays_the_selected_logo(self):
        interfaz, _, _ = self.crear_interfaz()

        logo_row = cast(ft.Row, interfaz._sidebar_controls()[0])
        logo_container = cast(ft.Container, logo_row.controls[0])
        logo = cast(ft.Image, logo_container.content)

        self.assertIsInstance(logo, ft.Image)
        self.assertTrue(cast(bytes, logo.src).startswith(b"\x89PNG\r\n\x1a\n"))

    def test_simulation_calls_agent_in_read_only_mode(self):
        interfaz, menu, _ = self.crear_interfaz(role="operador")

        asyncio.run(interfaz.procesar(simulacion=True))

        self.assertEqual(
            menu.procesamientos,
            [
                {
                    "incluir_mayoristas": True,
                    "incluir_canjes": True,
                    "incluir_mercado_libre": True,
                    "simulacion": True,
                    "usuario": "test-user",
                }
            ],
        )
        self.assertEqual(interfaz.estado_tarea.value, "Simulación finalizada.")
        self.assertFalse(interfaz.ocupado)
        salida = cast(ft.Text, interfaz.actividad.controls[0])
        self.assertIn(
            "Simulación comprobada",
            salida.value,
        )
        self.assertEqual(salida.color, ft.Colors.WHITE)
        self.assertEqual(salida.size, 14)

    def test_chat_uses_local_status_command(self):
        interfaz, _, _ = self.crear_interfaz()
        interfaz.entrada_chat.value = "/estado"

        asyncio.run(interfaz.enviar_chat())

        self.assertEqual(len(interfaz.conversacion.controls), 3)
        respuesta_control = cast(ft.Container, interfaz.conversacion.controls[-1])
        respuesta_columna = cast(ft.Column, respuesta_control.content)
        respuesta = cast(ft.Text, respuesta_columna.controls[1]).value
        self.assertIn("Pendientes:", respuesta)

    def test_login_screen_is_shown_before_dashboard(self):
        page = FakePage()
        with patch("src.flet_gui.MenuAgente", return_value=FakeMenu()), patch(
            "src.flet_gui.UserStore", return_value=FakeUserStore()
        ):
            interfaz = InterfazFlet(cast(ft.Page, page))

        self.assertIsNone(interfaz.usuario_actual)
        self.assertEqual(len(page.controls), 1)
        self.assertEqual(len(interfaz.controles_tarea), 0)
        self.assertTrue(page.window.maximized)
        self.assertIsNone(getattr(page, "floating_action_button", None))
        self.assertEqual(len(getattr(page, "overlay", [])), 0)

    def test_assistant_hidden_on_logout(self):
        interfaz, _, page = self.crear_interfaz()
        self.assertIsNotNone(getattr(page, "floating_action_button", None))

        interfaz.cerrar_sesion(None)
        self.assertIsNone(interfaz.usuario_actual)
        self.assertIsNone(getattr(page, "floating_action_button", None))
        self.assertEqual(len(getattr(page, "overlay", [])), 0)
        self.assertFalse(interfaz.chat_visible)

    def test_first_run_shows_administrator_setup(self):
        page = FakePage()
        with patch("src.flet_gui.MenuAgente", return_value=FakeMenu()), patch(
            "src.flet_gui.UserStore", return_value=FakeUserStore(has_users=False)
        ):
            interfaz = InterfazFlet(cast(ft.Page, page))

        self.assertIsNone(interfaz.usuario_actual)
        self.assertEqual(len(page.controls), 1)

    def test_admin_can_open_user_management(self):
        interfaz, _, page = self.crear_interfaz()

        interfaz.mostrar_gestion_usuarios(None)

        self.assertEqual(len(page.dialogos), 1)

    def test_admin_can_open_product_management_dashboard(self):
        interfaz, _, page = self.crear_interfaz()
        productos = [
            {
                "code": "100",
                "name": "Producto",
                "stock": 5,
                "active": 1,
            }
        ]
        with patch(
            "src.flet_gui.StockManager",
            return_value=SimpleNamespace(listar_productos=lambda: productos),
        ):
            interfaz.mostrar_gestion_productos()

        self.assertEqual(len(page.dialogos), 1)
        dialogo = page.dialogos[0]
        self.assertEqual(cast(ft.Text, dialogo.title).value, "Gestión de productos")
        lista = cast(ft.Container, dialogo.content.controls[3])
        self.assertEqual(len(cast(ft.Column, lista.content).controls), 1)

    def test_admin_restores_documents_for_selected_discount_date(self):
        interfaz, menu, page = self.crear_interfaz()

        interfaz.confirmar_restaurar(None)

        dialogo = page.dialogos[-1]
        selector = cast(ft.Dropdown, dialogo.content.controls[1])
        self.assertEqual(selector.value, "2026-10-22")
        selector.value = "2026-10-21"
        asyncio.run(interfaz.restaurar(None))

        self.assertEqual(menu.restauraciones, ["2026-10-21"])
        self.assertEqual(page.dialogos, [])

    def test_consultation_role_cannot_process_or_simulate(self):
        interfaz, menu, page = self.crear_interfaz(role="consulta")

        asyncio.run(interfaz.procesar(simulacion=True))

        self.assertEqual(menu.procesamientos, [])
        self.assertEqual(len(page.dialogos), 1)
        self.assertEqual(len(interfaz.controles_tarea), 4)

    def test_admin_cannot_process_or_simulate(self):
        interfaz, menu, page = self.crear_interfaz(role="administrador")

        asyncio.run(interfaz.procesar(simulacion=True))

        self.assertEqual(menu.procesamientos, [])
        self.assertEqual(len(page.dialogos), 1)
        self.assertIn("no tiene permiso", cast(ft.Text, page.dialogos[0].content).value)

    def test_admin_can_open_mercado_full_discount(self):
        interfaz, _, page = self.crear_interfaz(role="administrador")
        with patch("src.flet_gui.StockManager", return_value=SimpleNamespace(catalogo={})):
            interfaz.mostrar_descuento_mercado_full()
        self.assertEqual(len(page.dialogos), 1)

    def test_non_admin_cannot_open_mercado_full_discount(self):
        interfaz, _, page = self.crear_interfaz(role="operador")
        interfaz.mostrar_descuento_mercado_full()
        self.assertEqual(len(page.dialogos), 1)
        self.assertIn("no tiene permiso", cast(ft.Text, page.dialogos[0].content).value)

    def test_admin_can_open_notifications_dialog(self):
        interfaz, _, page = self.crear_interfaz(role="administrador")
        with patch("src.flet_gui.StockManager", return_value=SimpleNamespace(
            obtener_notificaciones_admin=lambda solo_no_leidas=False: [],
            marcar_notificaciones_leidas=lambda nid=None: None,
        )):
            interfaz.mostrar_notificaciones_admin()
        self.assertEqual(len(page.dialogos), 1)

    def test_non_admin_cannot_open_notifications_dialog(self):
        interfaz, _, page = self.crear_interfaz(role="operador")
        interfaz.mostrar_notificaciones_admin()
        self.assertEqual(len(page.dialogos), 1)
        self.assertIn("no tiene permiso", cast(ft.Text, page.dialogos[0].content).value)

    def test_operator_can_open_physical_stock_dialog(self):
        interfaz, _, page = self.crear_interfaz(role="operador")
        with patch("src.flet_gui.StockManager", return_value=SimpleNamespace(
            catalogo={},
            comparar_stock_fisico=lambda totales: [],
        )):
            interfaz.mostrar_stock_fisico_operario()
        self.assertEqual(len(page.dialogos), 1)

    def test_admin_can_open_physical_stock_comparison(self):
        interfaz, _, page = self.crear_interfaz(role="administrador")
        with patch("src.flet_gui.StockManager", return_value=SimpleNamespace(
            listar_inventarios_fisicos=lambda limit=25: [],
            obtener_detalle_inventario_fisico=lambda inv_id: [],
        )):
            interfaz.mostrar_comparativa_stock_fisico_admin()
        self.assertEqual(len(page.dialogos), 1)


    def test_floating_action_button_and_chat_toggle(self):
        interfaz, _, page = self.crear_interfaz()
        self.assertIsNotNone(interfaz.boton_chat_flotante)
        self.assertIsNotNone(interfaz.ventana_chat_flotante)
        self.assertFalse(interfaz.chat_visible)
        self.assertFalse(interfaz.ventana_chat_flotante.visible)

        interfaz.alternar_chat_flotante()
        self.assertTrue(interfaz.chat_visible)
        self.assertTrue(interfaz.ventana_chat_flotante.visible)

        interfaz.cerrar_chat_flotante()
        self.assertFalse(interfaz.chat_visible)
        self.assertFalse(interfaz.ventana_chat_flotante.visible)

    def test_chat_responds_to_stock_and_critical_queries(self):
        interfaz, _, _ = self.crear_interfaz()
        productos = [
            {"code": "1001", "name": "Filtro", "stock": 2, "active": 1},
            {"code": "1002", "name": "Bujía", "stock": 20, "active": 1},
        ]
        with patch("src.flet_gui.StockManager", return_value=SimpleNamespace(listar_productos=lambda: productos)):
            interfaz.entrada_chat.value = "/criticos"
            asyncio.run(interfaz.enviar_chat())
            respuesta_control = cast(ft.Container, interfaz.conversacion.controls[-1])
            columna = cast(ft.Column, respuesta_control.content)
            texto = cast(ft.Text, columna.controls[1]).value
            self.assertIn("Filtro", texto)

            interfaz.entrada_chat.value = "/stock 1002"
            asyncio.run(interfaz.enviar_chat())
            respuesta_control = cast(ft.Container, interfaz.conversacion.controls[-1])
            columna = cast(ft.Column, respuesta_control.content)
            texto = cast(ft.Text, columna.controls[1]).value
            self.assertIn("Bujía", texto)
            self.assertIn("20 unidades", texto)


    def test_admin_can_open_statistics_dashboard(self):
        interfaz, _, page = self.crear_interfaz()
        with patch("src.flet_gui.StockManager") as mock_sm:
            mock_inst = mock_sm.return_value
            mock_inst.consultar_movimientos.return_value = [
                {"product_code": "100", "product_name": "Prod A", "total_quantity": 25},
                {"product_code": "200", "product_name": "Prod B", "total_quantity": 10},
            ]
            interfaz.mostrar_estadisticas()

        self.assertEqual(len(page.dialogos), 1)
        dialogo = page.dialogos[0]
        self.assertEqual(
            cast(ft.Text, dialogo.title).value,
            "Estadísticas de movimiento de stock",
        )

    def test_non_admin_cannot_open_statistics(self):
        interfaz, _, page = self.crear_interfaz(role="operador")
        interfaz.mostrar_estadisticas()
        self.assertEqual(len(page.dialogos), 1)
        dialogo = page.dialogos[0]
        self.assertEqual(cast(ft.Text, dialogo.title).value, "Aviso")
        self.assertIn("no tiene permiso", cast(ft.Text, dialogo.content).value)

    def test_admin_alerta_quiebre_visible_when_critical_stock(self):
        interfaz, _, _ = self.crear_interfaz(role="administrador")
        criticos = [
            {"code": "P1", "name": "Producto A", "stock": 0, "stock_minimo": 5, "estado": "AGOTADO", "cantidad_sugerida_pedir": 100},
            {"code": "P2", "name": "Producto B", "stock": 2, "stock_minimo": 5, "estado": "QUIEBRE_INMINENTE", "cantidad_sugerida_pedir": 98},
        ]
        interfaz.actualizar_alerta_quiebre(criticos)
        self.assertTrue(interfaz.banner_alerta_quiebre.visible)

    def test_admin_alerta_quiebre_hidden_when_no_critical_stock(self):
        interfaz, _, _ = self.crear_interfaz(role="administrador")
        interfaz.actualizar_alerta_quiebre([])
        self.assertFalse(interfaz.banner_alerta_quiebre.visible)

    def test_non_admin_alerta_quiebre_always_hidden(self):
        interfaz, _, _ = self.crear_interfaz(role="operador")
        criticos = [
            {"code": "P1", "name": "Producto A", "stock": 0, "stock_minimo": 5, "estado": "AGOTADO", "cantidad_sugerida_pedir": 100},
        ]
        interfaz.actualizar_alerta_quiebre(criticos)
        self.assertFalse(interfaz.banner_alerta_quiebre.visible)

    def test_mostrar_detalle_quiebre_opens_dialog(self):
        interfaz, _, page = self.crear_interfaz(role="administrador")
        criticos = [
            {"code": "P1", "name": "Producto A", "stock": -2, "stock_minimo": 5, "estado": "AGOTADO", "cantidad_sugerida_pedir": 102},
        ]
        interfaz.mostrar_detalle_quiebre(criticos)
        self.assertEqual(len(page.dialogos), 1)
        dialogo = page.dialogos[0]
        self.assertIn("quiebre de stock", cast(ft.Text, dialogo.title.controls[1]).value)

    def test_generar_pedido_fabrica_forbidden_for_operator(self):
        interfaz, _, page = self.crear_interfaz(role="operador")
        interfaz.generar_pedido_fabrica()
        self.assertEqual(len(page.dialogos), 1)
        dialogo = page.dialogos[0]
        self.assertEqual(cast(ft.Text, dialogo.title).value, "Aviso")
        self.assertIn("no tiene permiso", cast(ft.Text, dialogo.content).value)

    def test_generar_pedido_fabrica_allowed_for_admin(self):
        interfaz, _, page = self.crear_interfaz(role="administrador")
        mock_analisis = [
            {"code": "P1", "name": "Item A", "stock": 2, "stock_minimo": 5, "stock_maximo": 100, "estado_inventario": "QUIEBRE_INMINENTE", "cantidad_sugerida_pedir": 98}
        ]
        with patch("src.flet_gui.StockManager") as mock_sm_cls:
            mock_inst = mock_sm_cls.return_value
            mock_inst.obtener_analisis_reposicion.return_value = mock_analisis
            mock_inst.generar_pedido_sugerido_fabrica.return_value = Path("Descuentos/Fabrica/Pedidos_Sugeridos/Pedido_Fabrica_Test.xlsx")
            interfaz.generar_pedido_fabrica()

        self.assertEqual(len(page.dialogos), 1)
        dialogo = page.dialogos[0]
        self.assertIn("Sugerencia de Pedido a Fábrica", cast(ft.Text, dialogo.title.controls[1]).value)

    def test_reports_list_displays_newest_first(self):
        interfaz, menu, _ = self.crear_interfaz()
        with tempfile.TemporaryDirectory() as temp_dir:
            file_old = Path(temp_dir) / "Descuento_Viejo.xlsx"
            file_new = Path(temp_dir) / "Descuento_Nuevo.xlsx"
            file_old.write_text("old")
            file_new.write_text("new")
            os.utime(file_old, (1000, 1000))
            os.utime(file_new, (2000, 2000))
            # _obtener_generados returns already sorted by mtime asc; actualizar_estado re-sorts desc
            menu._obtener_generados = lambda: [file_old, file_new]

            interfaz.actualizar_estado()
            self.assertEqual(len(interfaz.lista_informes.controls), 2)
            first_tile = cast(ft.ListTile, interfaz.lista_informes.controls[0])
            self.assertEqual(cast(ft.Text, first_tile.title).value, "Descuento_Nuevo.xlsx")
            second_tile = cast(ft.ListTile, interfaz.lista_informes.controls[1])
            self.assertEqual(cast(ft.Text, second_tile.title).value, "Descuento_Viejo.xlsx")

    def test_iniciar_runs_web_browser_mode_by_default(self):
        from src import flet_gui

        with patch("src.flet_gui.ft.run") as mock_run:
            flet_gui.iniciar(modo_web=True, host="0.0.0.0", port=8550)
            mock_run.assert_called_once()
            _, kwargs = mock_run.call_args
            self.assertEqual(kwargs["view"], ft.AppView.WEB_BROWSER)
            self.assertEqual(kwargs["host"], "0.0.0.0")
            self.assertEqual(kwargs["port"], 8550)
            self.assertFalse(kwargs["no_cdn"])
            self.assertEqual(kwargs["web_renderer"], ft.WebRenderer.AUTO)

    def test_web_upload_and_download_helpers(self):
        interfaz, _, page = self.crear_interfaz(role="administrador")
        with tempfile.TemporaryDirectory() as temp_dir:
            dest_dir = Path(temp_dir) / "MercadoFull"
            fake_file = SimpleNamespace(name="full_envio.xlsx", bytes=b"DATA123", path=None)

            async def fake_pick_files(**_kwargs):
                return [fake_file]

            saved_calls = []

            async def fake_save_file(**kwargs):
                saved_calls.append(kwargs)
                return kwargs["file_name"]

            interfaz.file_picker.pick_files = fake_pick_files
            interfaz.file_picker.save_file = fake_save_file

            guardados = asyncio.run(
                interfaz.subir_archivos_desde_pc(
                    carpeta_destino=dest_dir,
                    extensiones=["xlsx"],
                    titulo="Subir",
                )
            )
            self.assertEqual(len(guardados), 1)
            self.assertEqual(guardados[0].read_bytes(), b"DATA123")

            asyncio.run(interfaz._descargar_archivo_navegador(guardados[0]))
            self.assertEqual(len(saved_calls), 1)
            self.assertEqual(saved_calls[0]["file_name"], "full_envio.xlsx")
            self.assertEqual(saved_calls[0]["src_bytes"], b"DATA123")

    def test_actualizar_estado_refleja_pedidos_descontados_de_la_jornada(self):
        from src.orders_store import OrderStore

        interfaz, _, _ = self.crear_interfaz()
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "test_pedidos.sqlite3"
            store = OrderStore(db_path)
            interfaz.order_store = store

            # 1 PDF remito
            store.registrar_pedido("R-001", "1", "Cliente A", 1, "Transporte", "Armador", "pdf", "r1.pdf", False, 5, items=[("C1", "P1", 5)])
            # 1 Canje (excel)
            store.registrar_pedido("C-001", "2", "Cliente B", 1, "Transporte", "Armador", "excel", "c1.xlsx", False, 3, items=[("C2", "P2", 3)])
            # 1 Mercado Libre (docx)
            store.registrar_pedido("ML-001", "3", "Cliente ML", 1, "Transporte", "Armador", "docx", "ml1.docx", False, 2, items=[("C3", "P3", 2)])

            interfaz.actualizar_estado()
            self.assertEqual(interfaz.contadores["pdf"].value, "1")
            self.assertEqual(interfaz.contadores["canjes"].value, "1")
            self.assertEqual(interfaz.contadores["ml"].value, "1")
            self.assertEqual(interfaz.contadores["total"].value, "3")
            self.assertIn("Jornada en curso: 3 pedido(s) descontado(s)", interfaz.pendientes_texto.value)

            # Al hacer cierre de jornada, los pedidos quedan cerrados y los contadores se reinician a 0
            peds = store.listar_pedidos_pendientes_cierre()
            store.registrar_cierre("Operario", [p.id for p in peds], 10, "3 pedidos", "cierre.pdf", "cierre.xlsx")

            interfaz.actualizar_estado()
            self.assertEqual(interfaz.contadores["pdf"].value, "0")
            self.assertEqual(interfaz.contadores["canjes"].value, "0")
            self.assertEqual(interfaz.contadores["ml"].value, "0")
            self.assertEqual(interfaz.contadores["total"].value, "0")
            self.assertIn("Jornada en curso: 0 pedido(s) descontado(s)", interfaz.pendientes_texto.value)


if __name__ == "__main__":
    unittest.main()
