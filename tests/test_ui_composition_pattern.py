"""Pruebas unitarias para el patrón de Composición e Inyección de Dependencias de la UI."""

from __future__ import annotations

import asyncio
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import flet as ft

from src.flet_gui import InterfazFlet
from src.ui.components import procesar_mensaje_chat_agente
from src.ui.components.audio_manager import (
    TONOS_FRECUENCIAS,
    _sintetizar_wav_tono,
    reproducir_sonido_web,
)
from src.ui.controllers import (
    AuthSessionController,
    BatchTaskController,
    ChatAssistantController,
    DialogCoordinator,
    DocumentViewerService,
    FileTransferService,
    ResponsiveController,
    SessionSyncService,
    ThemeController,
)
from src.ui.protocols import (
    AppDependencies,
    AuthHostProtocol,
    BatchHostProtocol,
    ChatHostProtocol,
    DialogHostProtocol,
    DocumentViewerHostProtocol,
    FileTransferHostProtocol,
    ResponsiveHostProtocol,
    SessionSyncHostProtocol,
    ThemeHostProtocol,
)
from src.auth import User


class _DummyText:
    def __init__(self, value: str = "") -> None:
        self.value = value
        self.visible = True


class _DummyProgress:
    def __init__(self) -> None:
        self.visible = False
        self.value = None


class _DummyListView:
    def __init__(self) -> None:
        self.controls: list = []


class TestUICompositionPattern(unittest.TestCase):
    """Verifica el desacoplamiento por composición, Protocols e inyección de dependencias."""

    def test_interfaz_flet_no_hereda_mixins_y_usa_composicion(self):
        # La clase principal no debe heredar de ningún Mixin en su MRO.
        self.assertEqual(InterfazFlet.__mro__, (InterfazFlet, object))
        # Compatibilidad de atributos a nivel de clase.
        for attr in (
            "alternar_tema",
            "es_pantalla_movil",
            "exigir_roles",
            "abrir_informe",
            "mostrar_cierre_mercado",
            "mostrar_opciones_documento",
            "subir_archivos_desde_pc",
            "sincronizar_sesiones",
            "ejecutar_tarea",
            "enviar_chat",
        ):
            self.assertTrue(hasattr(InterfazFlet, attr), f"Falta descriptor delegado {attr}")

    def test_inyeccion_dependencias_en_interfaz_flet_sin_patch_globals(self):
        fake_page = MagicMock()
        fake_page.width = 1280
        fake_page.height = 800
        fake_page.overlay = []
        fake_page.services = []
        fake_page.controls = []

        fake_user_store = MagicMock()
        fake_user_store.has_users = False
        fake_order_store = MagicMock()
        fake_product_store = MagicMock()
        fake_menu = MagicMock()
        deps = AppDependencies(
            user_store=fake_user_store,
            order_store=fake_order_store,
            product_store=fake_product_store,
            menu=fake_menu,
        )

        with patch("src.ui.controllers.auth_controller.mostrar_configuracion_inicial") as mock_setup:
            interfaz = InterfazFlet(fake_page, deps=deps)

        self.assertIs(interfaz.user_store, fake_user_store)
        self.assertIs(interfaz.order_store, fake_order_store)
        self.assertIs(interfaz.product_store, fake_product_store)
        self.assertIs(interfaz.menu, fake_menu)
        mock_setup.assert_called_once()

        self.assertIsInstance(interfaz.theme_ctrl, ThemeController)
        self.assertIsInstance(interfaz.responsive_ctrl, ResponsiveController)
        self.assertIsInstance(interfaz.file_transfer_svc, FileTransferService)
        self.assertIsInstance(interfaz.doc_viewer_svc, DocumentViewerService)
        self.assertIsInstance(interfaz.auth_ctrl, AuthSessionController)
        self.assertIsInstance(interfaz.batch_ctrl, BatchTaskController)
        self.assertIsInstance(interfaz.chat_ctrl, ChatAssistantController)
        self.assertIsInstance(interfaz.session_sync_svc, SessionSyncService)
        self.assertIsInstance(interfaz.dialog_coord, DialogCoordinator)

        for proto in (
            ThemeHostProtocol,
            ResponsiveHostProtocol,
            FileTransferHostProtocol,
            DocumentViewerHostProtocol,
            AuthHostProtocol,
            BatchHostProtocol,
            ChatHostProtocol,
            SessionSyncHostProtocol,
            DialogHostProtocol,
        ):
            self.assertIsInstance(interfaz, proto)

    def test_theme_controller_aislado_con_inyeccion(self):
        host = SimpleNamespace(
            modo_oscuro=True,
            fondo=None,
            superficie=None,
            texto=None,
            secundario=None,
            borde=None,
            fondo_acento=None,
            posicion_sidebar="izquierda",
        )
        rebuilds: list[bool] = []
        ctrl = ThemeController(
            host,
            on_rebuild=lambda: rebuilds.append(True),
            prefs_loader=lambda _u: {"posicion_sidebar": "derecha", "modo_oscuro": False},
        )
        ctrl.aplicar_paleta(modo_oscuro=True)
        self.assertEqual(host.fondo, ft.Colors.BLACK)

        ctrl.alternar_tema()
        self.assertFalse(host.modo_oscuro)
        self.assertEqual(host.fondo, ft.Colors.GREY_100)
        self.assertEqual(len(rebuilds), 1)

        ctrl.aplicar_preferencias_usuario(SimpleNamespace(username="op1"))
        self.assertEqual(host.posicion_sidebar, "derecha")
        self.assertTrue(host._prefs_cargadas_usuario)

    def test_auth_controller_aislado_sin_interfaz_flet(self):
        avisos: list[str] = []
        user = User(7, "op_di", "operador", True)
        order_store = MagicMock()
        user_store = MagicMock()
        user_store.get_user.return_value = user
        host = SimpleNamespace(
            usuario_actual=user,
            user_store=user_store,
            order_store=order_store,
            ultima_actividad=datetime.now() - timedelta(minutes=2),
            controles_tarea=[],
            conversacion=_DummyListView(),
            ventana_chat_flotante=None,
            btn_cierre_jornada=None,
            page=MagicMock(),
        )
        ctrl = AuthSessionController(
            host,
            inactivity_limit_fn=lambda: 1,
            notify_fn=avisos.append,
        )
        with patch("src.ui.controllers.auth_controller.mostrar_inicio_sesion") as mock_login:
            permitido = ctrl.exigir_roles("operador")
        self.assertFalse(permitido)
        self.assertIsNone(host.usuario_actual)
        mock_login.assert_called_once()
        order_store.registrar_auditoria.assert_called_once()

    def test_session_sync_service_usa_sessions_provider_inyectado(self):
        s1 = MagicMock(usuario_actual=User(1, "ana", "operador", True), modo_chat_activo="equipo", modo_oscuro=True)
        s2 = MagicMock(usuario_actual=None)
        host = SimpleNamespace(usuario_actual=User(2, "luis", "operador", True))
        svc = SessionSyncService(host, sessions_provider=lambda: [host, s1, s2])
        svc.sincronizar_sesiones(notificar_chat=("luis", "ana", "Hola Ana"))
        s1.actualizar_estado.assert_called_once()
        s1.actualizar_badge_chat.assert_called_once()
        s1.cargar_mensajes_equipo.assert_called_once()
        s1.page.show_dialog.assert_called_once()
        s2.actualizar_estado.assert_not_called()

    def test_batch_controller_aislado_usa_lock_inyectado_y_callbacks(self):
        estado_lock = {"activo": False}
        refrescos: list[str] = []
        host = SimpleNamespace(
            page=MagicMock(),
            menu=MagicMock(),
            order_store=MagicMock(),
            usuario_actual=User(1, "op", "operador", True),
            ocupado=False,
            modo_oscuro=True,
            texto=ft.Colors.WHITE,
            mayoristas=SimpleNamespace(value=True),
            canjes=SimpleNamespace(value=False),
            mercado_libre=SimpleNamespace(value=True),
            progreso_barra=_DummyProgress(),
            estado_tarea=_DummyText(),
            actividad=_DummyListView(),
            controles_tarea=[],
        )
        ctrl = BatchTaskController(
            host,
            get_global_lock_fn=lambda: estado_lock["activo"],
            set_global_lock_fn=lambda v: estado_lock.__setitem__("activo", v),
            check_roles_fn=lambda *_r: True,
            notify_fn=refrescos.append,
            refresh_dashboard_fn=lambda: refrescos.append("refresh"),
            sync_sessions_fn=lambda: refrescos.append("sync"),
        )
        self.assertEqual(ctrl.fuentes_seleccionadas(), (True, False, True))

        async def _inline_to_thread(func, /, *args, **kwargs):
            return func(*args, **kwargs)

        def _drive_sync(coro):
            try:
                while True:
                    coro.send(None)
            except StopIteration as exc:
                return exc.value

        with patch("src.ui.controllers.batch_controller.asyncio.to_thread", new=_inline_to_thread):
            ok = _drive_sync(ctrl.ejecutar_tarea("PruebaDI", lambda: print("ok_tarea")))

        self.assertTrue(ok)
        self.assertFalse(estado_lock["activo"])
        self.assertFalse(host.ocupado)
        self.assertIn("refresh", refrescos)
        self.assertIn("sync", refrescos)
        self.assertIn("finalizada", host.estado_tarea.value.lower())

    def test_document_viewer_service_y_shim_compatibilidad_sin_recursion(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pdf = root / "Documentacion" / "Manual_Operador.pdf"
            pdf.parent.mkdir(parents=True, exist_ok=True)
            pdf.write_bytes(b"%PDF-1.4 test")

            abiertas: list[str] = []
            host = SimpleNamespace(
                page=SimpleNamespace(web=True),
                usuario_actual=User(3, "op_web", "operador", True),
                informes=[],
                informe_seleccionado=None,
                abrir_url_en_navegador=abiertas.append,
            )
            svc = DocumentViewerService(host, app_root_fn=lambda: root)
            svc.mostrar_manual_usuario()
            self.assertEqual(len(abiertas), 1)
            self.assertIn("Manual_Operador.pdf", abiertas[0])

            # Sin abrir_url_en_navegador en el host, el servicio web abre vía page.launch_url
            # sin recursión ni puentes heredados en src/ui/mixins/.
            host_web = SimpleNamespace(
                page=SimpleNamespace(web=True, launch_url=MagicMock()),
                usuario_actual=User(4, "operador4", "operador", True),
                informes=[],
                informe_seleccionado=None,
                notificar=lambda _m: None,
            )

            with patch("src.ui.controllers.document_viewer_service.application_root", return_value=root):
                DocumentViewerService(host_web).mostrar_manual_usuario()
            host_web.page.launch_url.assert_called_once()
            self.assertFalse((Path(__file__).resolve().parent.parent / "src" / "ui" / "mixins").exists())

    def test_dialog_coordinator_aplica_precondiciones_en_un_punto(self):
        llamadas: list[str] = []
        host = SimpleNamespace(order_store=None, menu=None, usuario_actual=None)
        coord_denegado = DialogCoordinator(
            host,
            check_roles_fn=lambda *_r: False,
            close_drawer_fn=lambda: llamadas.append("drawer"),
            ensure_file_picker_fn=lambda: llamadas.append("picker"),
        )
        coord_denegado.mostrar_cierre_mercado()
        self.assertEqual(llamadas, [])

        coord_ok = DialogCoordinator(
            host,
            check_roles_fn=lambda *_r: True,
            close_drawer_fn=lambda: llamadas.append("drawer"),
            ensure_file_picker_fn=lambda: llamadas.append("picker"),
        )
        with patch("src.ui.controllers.dialog_coordinator.mostrar_dialogo_crear_pedido") as mock_dlg:
            coord_ok.mostrar_crear_pedido()
        mock_dlg.assert_called_once_with(host)
        self.assertEqual(llamadas, ["drawer", "picker"])

    def test_campana_audio_manager_wave_y_web_shared_prefs(self):
        self.assertIn("campana", TONOS_FRECUENCIAS)
        wav = _sintetizar_wav_tono("campana")
        self.assertTrue(wav.startswith(b"RIFF"))
        self.assertEqual(wav[8:12], b"WAVE")

        run_js_mock = MagicMock()
        host_js = SimpleNamespace(page=SimpleNamespace(run_js=run_js_mock))
        reproducir_sonido_web(host_js, "campana")
        run_js_mock.assert_called_once()
        self.assertIn("playTone(", run_js_mock.call_args[0][0])

        sp_fake = MagicMock()
        async def _fake_set(key, val):
            return True
        sp_fake.set = MagicMock(side_effect=_fake_set)
        dispatched = []

        def _fake_run_task(coro_fn):
            coro = coro_fn()
            try:
                coro.send(None)
            except StopIteration:
                pass
            dispatched.append(True)

        host_web = SimpleNamespace(
            shared_prefs=sp_fake,
            page=SimpleNamespace(web=True, services=[sp_fake], run_task=_fake_run_task, update=lambda: None),
        )
        reproducir_sonido_web(host_web, "campana")
        self.assertTrue(dispatched)
        sp_fake.set.assert_called_once()
        self.assertEqual(sp_fake.set.call_args[0][0], "__sa_audio_event")
        self.assertTrue(sp_fake.set.call_args[0][1].startswith("campana:"))

    def test_sync_service_toca_campana_si_habilitada_y_respeta_silencio(self):
        s_sonido = MagicMock(
            usuario_actual=User(1, "ana", "operador", True),
            modo_chat_activo="equipo",
            modo_oscuro=True,
            sonido_chat_activo=True,
        )
        s_muda = MagicMock(
            usuario_actual=User(2, "carlos", "operador", True),
            modo_chat_activo="equipo",
            modo_oscuro=True,
            sonido_chat_activo=False,
        )
        host = SimpleNamespace(usuario_actual=User(3, "luis", "operador", True))
        svc = SessionSyncService(host, sessions_provider=lambda: [host, s_sonido, s_muda])
        svc.sincronizar_sesiones(notificar_chat=("luis", "Todos", "Nuevo pedido listo"))

        s_sonido.reproducir_sonido.assert_called_once_with("campana")
        s_muda.reproducir_sonido.assert_not_called()

    def test_badge_puntos_y_titulo_se_actualizan_y_limpian_por_tab(self):
        counts = {"equipo": 2}
        order_store = MagicMock()
        order_store.contar_mensajes_no_leidos.side_effect = lambda _u: counts["equipo"]
        order_store.marcar_mensajes_leidos.side_effect = lambda _u: counts.__setitem__("equipo", 0)

        page_mock = MagicMock()
        page_mock.title = "StockAgent · Sistema Integral de Depósito"

        host = SimpleNamespace(
            usuario_actual=User(1, "ana", "operador", True),
            order_store=order_store,
            page=page_mock,
            sonido_chat_activo=True,
            modo_chat_activo="bot",
            _mensajes_bot_no_leidos=1,
            _ultimo_no_leidos_chat=1,
            badge_chat_container=SimpleNamespace(visible=False),
            texto_badge_chat=SimpleNamespace(value=""),
            texto_badge_tab=SimpleNamespace(value=""),
            punto_nuevo_chat=SimpleNamespace(visible=False),
            punto_nuevo_chat_movil=SimpleNamespace(visible=False),
            punto_nuevo_chat_movil_sel=SimpleNamespace(visible=False),
            punto_tab_equipo=SimpleNamespace(visible=False),
            punto_tab_bot=SimpleNamespace(visible=False),
            reproducir_sonido=MagicMock(),
            cargar_mensajes_equipo=MagicMock(),
            conversacion_equipo=SimpleNamespace(controls=[]),
            user_store=MagicMock(),
            selector_destinatario_equipo=SimpleNamespace(options=[], value="Todos"),
            entrada_chat_equipo=SimpleNamespace(value=""),
            texto=ft.Colors.WHITE,
            secundario=ft.Colors.GREY,
            borde=ft.Colors.GREY,
            modo_oscuro=True,
        )
        svc = SessionSyncService(host)
        svc.actualizar_badge_chat(sonar_si_aumenta=True)

        self.assertTrue(host.badge_chat_container.visible)
        self.assertEqual(host.texto_badge_chat.value, "3")
        self.assertEqual(host.texto_badge_tab.value, " (2)")
        self.assertTrue(host.punto_nuevo_chat.visible)
        self.assertTrue(host.punto_nuevo_chat_movil.visible)
        self.assertTrue(host.punto_nuevo_chat_movil_sel.visible)
        self.assertTrue(host.punto_tab_equipo.visible)
        self.assertTrue(host.punto_tab_bot.visible)
        self.assertTrue(page_mock.title.startswith("(3) "))
        host.reproducir_sonido.assert_called_once_with("campana")

        svc.marcar_mensajes_chat_leidos(solo_tab="equipo")
        self.assertEqual(host.texto_badge_chat.value, "1")
        self.assertFalse(host.punto_tab_equipo.visible)
        self.assertTrue(host.punto_tab_bot.visible)

        svc.marcar_mensajes_chat_leidos(solo_tab="bot")
        self.assertFalse(host.badge_chat_container.visible)
        self.assertFalse(host.punto_nuevo_chat.visible)
        self.assertFalse(host.punto_tab_bot.visible)
        self.assertFalse(page_mock.title.startswith("("))

    def test_chatbot_toca_campana_y_marca_punto_si_cerrado_o_en_otro_tab(self):
        def _drive_sync(coro):
            try:
                while True:
                    coro.send(None)
            except StopIteration as exc:
                return exc.value

        badges: list[int] = []
        host = SimpleNamespace(
            usuario_actual=User(1, "ana", "operador", True),
            chat_visible=False,
            modo_chat_activo="bot",
            sonido_chat_activo=True,
            _mensajes_bot_no_leidos=0,
            escribir_chat=MagicMock(),
            reproducir_sonido=MagicMock(),
            actualizar_badge_chat=lambda: badges.append(host._mensajes_bot_no_leidos),
            page=MagicMock(),
        )

        _drive_sync(procesar_mensaje_chat_agente(host, "Hola"))
        host.reproducir_sonido.assert_called_once_with("campana")
        self.assertEqual(host._mensajes_bot_no_leidos, 1)
        self.assertEqual(badges, [1])

        host.chat_visible = True
        host.reproducir_sonido.reset_mock()
        host._mensajes_bot_no_leidos = 0
        badges.clear()
        _drive_sync(procesar_mensaje_chat_agente(host, "Hola"))
        host.reproducir_sonido.assert_called_once_with("campana")
        self.assertEqual(host._mensajes_bot_no_leidos, 0)
        self.assertEqual(badges, [])

    def test_chat_controller_al_abrir_marca_leidos(self):
        host = SimpleNamespace(
            chat_visible=False,
            modo_chat_activo="equipo",
            ventana_chat_flotante=SimpleNamespace(visible=False),
            refrescar_usuarios_chat_equipo=MagicMock(),
            cargar_mensajes_equipo=MagicMock(),
            marcar_mensajes_chat_leidos=MagicMock(),
            page=MagicMock(),
        )
        ctrl = ChatAssistantController(host)
        ctrl.alternar_chat_flotante()
        self.assertTrue(host.chat_visible)
        self.assertTrue(host.ventana_chat_flotante.visible)
        host.marcar_mensajes_chat_leidos.assert_called_once_with(solo_tab="equipo")


if __name__ == "__main__":
    unittest.main()
