"""Pruebas unitarias de regresión para los parches de seguridad y UI de la Fase 1."""

from __future__ import annotations

import asyncio
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import flet as ft
import openpyxl

from src.auth import User, UserStore
from src.backup_manager import guardar_config_backup, restaurar_backup_sistema
from src.core.security_utils import (
    es_ruta_unc_o_sistema,
    es_url_navegable_segura,
    resolver_ruta_confinada,
    sanitizar_componente_archivo,
    validar_nombre_impresora_seguro,
)
from src.inventory import StockManager
from src.orders import OrderStore
from src.paths import application_root
from src.ui.components.network_heartbeat import (
    actualizar_estado_conexion_ui,
    detener_heartbeat_red,
)
from src.ui.components.print_labels import imprimir_directo_spooler
from src.ui.controllers.auth_controller import AuthSessionController
from src.ui.controllers.theme_controller import ThemeController
from src.ui.shell_builder import copiar_al_portapapeles_ui, fijar_estado_tarea_ui
from src.ui.theme import FONDO_OSCURO, SUPERFICIE_OSCURO, TEXTO_OSCURO


class TestFase1SecurityUtilsAndInjection(unittest.TestCase):
    """Valida utilidades de seguridad modular y prevención de inyección de comandos."""

    def test_security_utils_sanitizacion_y_confinamiento(self):
        self.assertEqual(sanitizar_componente_archivo("../../etc/passwd"), "passwd")
        self.assertEqual(sanitizar_componente_archivo("   "), "archivo")
        self.assertTrue(es_ruta_unc_o_sistema(r"\\192.168.1.10\share\bk"))
        self.assertTrue(es_ruta_unc_o_sistema("//attacker/share"))
        self.assertTrue(es_ruta_unc_o_sistema(r"C:\Windows\System32"))
        self.assertFalse(es_ruta_unc_o_sistema(r"D:\Backups_Deposito"))

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            ok_path = resolver_ruta_confinada(base, "informe.pdf")
            self.assertEqual(ok_path.parent, base.resolve())
            with self.assertRaises(ValueError):
                resolver_ruta_confinada(base, "../../escape.pdf")

    def test_validacion_impresora_y_url_segura(self):
        self.assertEqual(validar_nombre_impresora_seguro("Zebra ZD220 (USB001)"), "Zebra ZD220 (USB001)")
        for invalida in ("Zebra'; calc.exe #", "HP | whoami", ""):
            with self.assertRaises(ValueError):
                validar_nombre_impresora_seguro(invalida)

        self.assertTrue(es_url_navegable_segura("/documentos/informe.pdf?dt=abc"))
        self.assertTrue(es_url_navegable_segura("https://ejemplo.com/doc"))
        self.assertFalse(es_url_navegable_segura("javascript:alert(1)"))
        self.assertFalse(es_url_navegable_segura("file:///C:/Windows/win.ini"))
        self.assertFalse(es_url_navegable_segura("data:text/html,<script>1</script>"))

    def test_imprimir_directo_spooler_rechaza_inyeccion_y_usa_env_vars(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf = Path(tmp) / "etiqueta.pdf"
            pdf.write_bytes(b"%PDF-1.4")
            txt = Path(tmp) / "nota.txt"
            txt.write_text("no es pdf", encoding="utf-8")

            with patch("src.ui.components.print_labels.subprocess.run") as mock_run:
                self.assertFalse(imprimir_directo_spooler(pdf, "Zebra'; Start-Process calc #"))
                self.assertFalse(imprimir_directo_spooler(txt, "Zebra ZD220"))
                mock_run.assert_not_called()

            with patch("src.ui.components.print_labels.subprocess.run") as mock_run:
                mock_run.return_value = SimpleNamespace(returncode=0)
                ok = imprimir_directo_spooler(pdf, "Zebra ZD220")
                self.assertTrue(ok)
                mock_run.assert_called_once()
                kwargs = mock_run.call_args.kwargs
                cmd = mock_run.call_args.args[0]
                self.assertNotIn("Zebra ZD220", " ".join(cmd))
                self.assertEqual(kwargs["env"]["STOCKAGENT_PRINT_PRINTER"], "Zebra ZD220")
                self.assertEqual(kwargs["env"]["STOCKAGENT_PRINT_PDF"], str(pdf.resolve()))

    def test_scripts_windows_sin_interpolacion_insegura(self):
        root = application_root()
        fw = (root / "configurar_firewall_red.bat").read_text(encoding="utf-8", errors="ignore")
        self.assertIn("STOCKAGENT_FW_SCRIPT", fw)
        self.assertNotIn("FilePath '%~f0'", fw)

        autostart = (root / "configurar_inicio_automatico.bat").read_text(encoding="utf-8", errors="ignore")
        self.assertIn("STOCKAGENT_ACCESO_DIRECTO", autostart)
        self.assertIn("STOCKAGENT_SCRIPT_VBS", autostart)

        vbs = (root / "iniciar_en_segundo_plano.vbs").read_text(encoding="utf-8", errors="ignore")
        self.assertIn("STOCKAGENT_BAT_PATH", vbs)
        self.assertIn("RegExp", vbs)


class TestFase1IsolationBackupAndRBAC(unittest.TestCase):
    """Valida aislamiento QA/Producción, backup seguro, RBAC y autenticación fail-closed."""

    def test_stock_manager_qa_no_hace_fallback_a_produccion(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            qa_desc = root / "Descuentos_QA"
            qa_desc.mkdir(parents=True)
            excel_qa = qa_desc / "Productos.xlsx"
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Stock"
            ws.append(["CÓDIGO", "PRODUCTOS", "STOCK"])
            ws.append([])
            ws.append(["QA-1", "Item QA", 10])
            wb.save(excel_qa)
            wb.close()

            orig_env = os.environ.get("STOCKAGENT_ENV")
            try:
                os.environ["STOCKAGENT_ENV"] = "qa"
                sm = StockManager(excel_qa)
                self.assertIn("data_qa", str(sm.product_store.database_path))
                self.assertNotIn(str(root / "data" / "productos.sqlite3"), str(sm.product_store.database_path))
            finally:
                if orig_env is None:
                    os.environ.pop("STOCKAGENT_ENV", None)
                else:
                    os.environ["STOCKAGENT_ENV"] = orig_env

    def test_zapping_produccion_bloqueado_en_qa(self):
        from src.core.system_reset import ejecutar_zapping_produccion

        with patch("src.core.system_reset.is_qa_environment", return_value=True):
            with self.assertRaises(RuntimeError):
                ejecutar_zapping_produccion()

    def test_backup_rechaza_unc_y_zip_slip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch("src.backup_manager.application_root", return_value=root):
                with self.assertRaises(ValueError):
                    guardar_config_backup(r"\\10.0.0.5\share\backups")
                with self.assertRaises(ValueError):
                    guardar_config_backup(r"C:\Windows\Temp")

                evil_zip = root / "evil.zip"
                with zipfile.ZipFile(evil_zip, "w") as zf:
                    zf.writestr("../escape.sqlite3", b"bad")
                ok, msg, _ = restaurar_backup_sistema(evil_zip)
                self.assertFalse(ok)
                self.assertIn("rutas inválidas", msg)

    def test_token_documento_rechaza_recurso_vacio(self):
        from src.api.deps import crear_token_documento, validar_token_documento

        admin = User(1, "admin", "administrador", True)
        with self.assertRaises(ValueError):
            crear_token_documento(admin, recurso="")
        tok = crear_token_documento(admin, recurso="informe.pdf")
        self.assertIsNone(validar_token_documento(tok, recurso_solicitado=""))
        self.assertIsNotNone(validar_token_documento(tok, recurso_solicitado="informe.pdf"))

    def test_despacho_bloquea_retroceso_sin_permiso_explicito(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = OrderStore(Path(tmp) / "pedidos.sqlite3")
            store.registrar_pedido(
                nota_pedido="R-900",
                numero_pedido="900",
                cliente="Cliente Test",
                bultos=1,
                logistica="Domicilio",
                armador="op",
                tipo_archivo="pdf",
                nombre_archivo="r900.pdf",
                agregado=False,
                articulos_descontados=2,
                resumen_items="1 prod (2 un.)",
            )
            ok1, _, _ = store.avanzar_estado_por_codigo("R-900", usuario="op", nuevo_estado="DESPACHADO")
            self.assertTrue(ok1)

            ok_back_denied, msg_denied, _ = store.avanzar_estado_por_codigo(
                "R-900", usuario="op", nuevo_estado="ARMADO", permitir_retroceso=False
            )
            self.assertFalse(ok_back_denied)
            self.assertIn("administrador", msg_denied.lower())

            ok_back_admin, _, _ = store.avanzar_estado_por_codigo(
                "R-900", usuario="admin", nuevo_estado="ARMADO", permitir_retroceso=True
            )
            self.assertTrue(ok_back_admin)

    def test_auth_controller_fail_closed_y_limpieza_total(self):
        with tempfile.TemporaryDirectory() as tmp:
            u_store = UserStore(Path(tmp) / "usuarios.sqlite3")
            u_store.create_user("op_test", "ClaveSegura123!", role="operador")
            user = u_store.get_user_by_username("op_test")
            assert user is not None

            def _make_host(store_obj):
                return SimpleNamespace(
                    usuario_actual=user,
                    user_store=store_obj,
                    order_store=MagicMock(),
                    controles_tarea=["b1"],
                    botones_cierre_jornada=["b2"],
                    conversacion=SimpleNamespace(controls=["m1"]),
                    conversacion_equipo=SimpleNamespace(controls=["e1"]),
                    actividad=SimpleNamespace(controls=["a1"]),
                    lista_pedidos_preparados=SimpleNamespace(controls=["p1"]),
                    lista_informes=SimpleNamespace(controls=["i1"]),
                    informes=[Path("x.pdf")],
                    informe_seleccionado=Path("x.pdf"),
                    _prefs_cargadas_usuario=True,
                    _heartbeat_activo=True,
                    _heartbeat_iniciado=True,
                    page=SimpleNamespace(title="Test", navigation_bar="nav"),
                )

            # 1. Excepción en DB -> fail-closed
            broken_store = MagicMock()
            broken_store.get_user.side_effect = RuntimeError("DB locked")
            host1 = _make_host(broken_store)
            ctrl1 = AuthSessionController(host1, inactivity_limit_fn=lambda: 60)
            with patch("src.ui.controllers.auth_controller.mostrar_inicio_sesion") as mock_login:
                self.assertFalse(ctrl1.exigir_roles("operador"))
                mock_login.assert_called_once()
            self.assertIsNone(host1.usuario_actual)
            self.assertEqual(host1.conversacion.controls, [])
            self.assertEqual(host1.conversacion_equipo.controls, [])
            self.assertEqual(host1.informes, [])
            self.assertIsNone(host1.page.navigation_bar)
            self.assertFalse(host1._prefs_cargadas_usuario)

            # 2. Usuario inexistente (None) -> fail-closed
            missing_store = MagicMock()
            missing_store.get_user.return_value = None
            host2 = _make_host(missing_store)
            ctrl2 = AuthSessionController(host2, inactivity_limit_fn=lambda: 60)
            with patch("src.ui.controllers.auth_controller.mostrar_inicio_sesion") as mock_login:
                self.assertFalse(ctrl2.exigir_roles("operador"))
                mock_login.assert_called_once()
            self.assertIsNone(host2.usuario_actual)


class TestFase1UIRegressionsAndDialogs(unittest.TestCase):
    """Valida correcciones de Modo Oscuro, Flet 1.0.4, diálogos críticos y assets PWA."""

    def test_theme_controller_dark_mode_unificado_y_persistencia(self):
        guardadas: list[tuple[str, str, object]] = []
        host = SimpleNamespace(
            modo_oscuro=False,
            usuario_actual=SimpleNamespace(username="ana"),
            fondo=None,
            superficie=None,
            texto=None,
            secundario=None,
            borde=None,
            fondo_acento=None,
            posicion_sidebar="izquierda",
        )
        ctrl = ThemeController(
            host,
            on_rebuild=lambda: None,
            prefs_loader=lambda _u: {"modo_oscuro": True},
            prefs_saver=lambda u, k, v: guardadas.append((u, k, v)),
        )
        ctrl.aplicar_preferencias_usuario(host.usuario_actual)
        self.assertTrue(host.modo_oscuro)
        self.assertEqual(host.fondo, FONDO_OSCURO)
        self.assertEqual(host.superficie, SUPERFICIE_OSCURO)
        self.assertEqual(host.texto, TEXTO_OSCURO)
        self.assertEqual(host.fondo_acento, ft.Colors.BLUE_GREY_800)

        ctrl.alternar_tema()
        self.assertFalse(host.modo_oscuro)
        self.assertEqual(guardadas, [("ana", "modo_oscuro", False)])

    def test_fijar_estado_tarea_y_heartbeat_usan_icon_y_clipboard_reutilizable(self):
        icono = ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE_ROUNDED)
        sem_icon = ft.Icon(ft.Icons.CIRCLE)
        sem_txt = ft.Text("En línea")
        sem = ft.Container(content=ft.Row([sem_icon, sem_txt]))
        page = SimpleNamespace(services=[], overlay=[], update=MagicMock(), run_task=MagicMock())
        host = SimpleNamespace(
            estado_tarea=ft.Text(""),
            icono_estado_tarea=icono,
            secundario=ft.Colors.GREY,
            semaforo_conexion=sem,
            semaforo_conexion_movil=None,
            modo_oscuro=True,
            _estado_red_actual="online",
            _heartbeat_primer_ping=False,
            page=page,
        )

        fijar_estado_tarea_ui(host, "Fallo de prueba", estado="error")
        self.assertEqual(icono.icon, ft.Icons.ERROR_OUTLINE_ROUNDED)

        # En estado estable "online" repetido no debe disparar page.update() innecesario
        page.update.reset_mock()
        actualizar_estado_conexion_ui(host, "online", latencia_ms=15.0)
        page.update.assert_not_called()

        # Al cambiar de estado sí actualiza .icon y la página
        actualizar_estado_conexion_ui(host, "degraded", latencia_ms=1200.0)
        self.assertEqual(sem_icon.icon, ft.Icons.WARNING_AMBER_ROUNDED)
        page.update.assert_called_once()

        # Clipboard reutiliza un único servicio en page.services y nunca llena page.overlay
        copiar_al_portapapeles_ui(host, "uno")
        copiar_al_portapapeles_ui(host, "dos")
        self.assertEqual(len(page.services), 1)
        self.assertEqual(len(page.overlay), 0)
        self.assertEqual(page.run_task.call_count, 2)

        # Detener heartbeat despierta stop_event inmediatamente
        import threading

        ev = threading.Event()
        host._heartbeat_stop_event = ev
        host._heartbeat_activo = True
        host._heartbeat_iniciado = True
        detener_heartbeat_red(host)
        self.assertTrue(ev.is_set())
        self.assertFalse(host._heartbeat_activo)

    def test_idempotencia_crear_pedido_bloquea_doble_descuento_de_stock(self):
        from src.ui.dialogs.pedidos_crear_modales import ejecutar_descuento_y_registro_pedido

        stock_mgr = MagicMock()
        order_store = MagicMock()
        order_store.registrar_transaccion_idempotente.return_value = False
        interfaz = SimpleNamespace(
            order_store=order_store,
            menu=SimpleNamespace(ruta_excel_base=Path("dummy.xlsx"), carpeta_descuentos=Path(".")),
        )
        ejecutar_descuento_y_registro_pedido(
            interfaz=interfaz,
            remito="R-DUP-1",
            num_ped="100",
            cli="Cliente",
            bultos_val=1,
            log="Domicilio",
            f_retiro="2026-11-20",
            armador_nom="op",
            es_agregado=False,
            tipo_archivo="pdf",
            archivo_path=Path("r.pdf"),
            hash_comprobante="abcdef123456",
            cache_simulacion={"stock_mgr": stock_mgr, "reporte": MagicMock()},
        )
        stock_mgr.actualizar_stock_base.assert_not_called()
        order_store.registrar_pedido.assert_not_called()

    def test_inventario_vivo_finalizar_usa_tarea_sincrona_y_muestra_resumen(self):
        from src.ui.dialogs.dlg_inventario_vivo import mostrar_dialogo_inventario_vivo

        dialogos: list[ft.AlertDialog] = []
        page = SimpleNamespace(
            width=800,
            show_dialog=lambda d: dialogos.append(d),
            pop_dialog=lambda: dialogos.pop() if dialogos else None,
            update=lambda: None,
        )
        sm = MagicMock()
        sm.product_store.list_products.return_value = [
            {"code": "SKU1", "name": "Prod 1", "stock": 5, "cod_barras": "123"}
        ]
        sm.procesar_stock_fisico.return_value = (Path("inv.xlsx"), {"total": 1})

        async def _fake_ejecutar_tarea(_titulo, accion):
            self.assertFalse(asyncio.iscoroutinefunction(accion))
            accion()
            return True

        interfaz = SimpleNamespace(
            page=page,
            usuario_actual=User(1, "op1", "operador", True),
            menu=SimpleNamespace(ruta_excel_base=Path("dummy.xlsx")),
            exigir_roles=lambda *_r: True,
            modo_oscuro=True,
            texto=ft.Colors.WHITE,
            secundario=ft.Colors.GREY,
            borde=ft.Colors.GREY_700,
            superficie=ft.Colors.BLUE_GREY_900,
            boton_dialogo=lambda t, cb: ft.TextButton(t, on_click=cb),
            notificar=MagicMock(),
            ejecutar_tarea=_fake_ejecutar_tarea,
        )

        with patch("src.ui.dialogs.dlg_inventario_vivo._get_stock_manager", return_value=lambda _r: sm), patch(
            "src.ui.dialogs.dlg_inventario_vivo.mostrar_resumen_inventario_finalizado"
        ) as mock_resumen:
            mostrar_dialogo_inventario_vivo(interfaz)
            dlg = dialogos[0]
            col = dlg.content.content
            input_escaneo = col.controls[0].controls[0]
            btn_sumar = col.controls[1].controls[1]
            input_escaneo.value = "SKU1"
            btn_sumar.on_click(None)

            btn_finalizar = dlg.actions[1]
            asyncio.run(btn_finalizar.on_click(None))
            sm.procesar_stock_fisico.assert_called_once()
            mock_resumen.assert_called_once()

    def test_pwa_assets_hardening(self):
        assets = application_root() / "assets"
        sw = (assets / "sw.js").read_text(encoding="utf-8")
        self.assertIn("stockagent-pwa-v4", sw)
        self.assertIn("esRecursoEstaticoPermitido", sw)
        self.assertIn("'/api/'", sw)
        self.assertIn("'/documentos/'", sw)
        self.assertIn("no-store", sw)

        scanner = (assets / "js" / "scanner.js").read_text(encoding="utf-8")
        self.assertNotIn('postMessage(msg, "*")', scanner)
        self.assertNotIn('postMessage(postMsg, "*")', scanner)
        self.assertIn("window.location.origin", scanner)
        self.assertIn("cancelAnimationFrame", scanner)
        self.assertIn("stockagent_scanned_batch", scanner)

        index_html = (assets / "index.html").read_text(encoding="utf-8")
        self.assertIn("clearTimeout(offlineBannerTimer)", index_html)
        self.assertIn("banner.style.background = '#b91c1c'", index_html)

        offline_html = (assets / "offline.html").read_text(encoding="utf-8")
        self.assertNotIn("100.121.31.38", offline_html)
        self.assertIn("validarUrlServidor", offline_html)


if __name__ == "__main__":
    unittest.main()
