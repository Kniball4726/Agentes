"""Pruebas unitarias e integrales para la Fase 3: Sistema de Diseño Unificado, Contraste WCAG AA, Formularios Seguros y UX Responsiva."""

from __future__ import annotations

from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from typing import cast
from unittest.mock import patch

import flet as ft

from src.auth import UserStore
from src.flet_gui import InterfazFlet
from src.orders import OrderStore
from src.ui.components.mobile_nav import (
    construir_navigation_bar_movil,
    manejar_cambio_navegacion_movil,
)
from src.ui.components.sidebar_sections import _obtener_seccion_predeterminada
from src.ui.design import (
    MARCA_NEUTRO,
    MARCA_PELIGRO,
    MARCA_PRIMARIO,
    boton_dialogo_semantico,
    campo_secreto_seguro,
    colores_semanticos,
    confirmar_accion_destructiva,
    fijar_ocupado,
    marcar_error,
    resolver_secreto,
    tono_legible,
    validar_entero_no_negativo,
    validar_fecha_ddmmaaaa,
)
from src.ui.dialogs.api_panel_tabs import construir_tab_docs_estado
from src.ui.dialogs.dlg_command_palette import mostrar_command_palette
from src.ui.dialogs.dlg_mercadolibre import mostrar_dialogo_mercadolibre
from src.ui.dialogs.dlg_smtp import mostrar_dialogo_configuracion_smtp
from src.ui.dialogs.dlg_telegram import mostrar_dialogo_configuracion_telegram
from tests.test_flet_gui import FakeMenu, FakePage


def _extraer_textos(ctrl: object) -> list[str]:
    """Recorre recursivamente un árbol de controles Flet y extrae todos los textos."""
    out: list[str] = []
    visitados: set[int] = set()
    cola = [ctrl]
    while cola:
        actual = cola.pop(0)
        if actual is None or id(actual) in visitados:
            continue
        visitados.add(id(actual))
        for attr in ("value", "text", "label", "hint_text"):
            val = getattr(actual, attr, None)
            if isinstance(val, str) and val:
                out.append(val)
        content = getattr(actual, "content", None)
        if isinstance(content, str) and content:
            out.append(content)
        elif content is not None:
            cola.append(content)
        for list_attr in ("controls", "actions", "tabs"):
            hijos = getattr(actual, list_attr, None)
            if isinstance(hijos, (list, tuple)):
                cola.extend(hijos)
    return out


def _extraer_textfields(ctrl: object) -> list[ft.TextField]:
    """Devuelve todos los ft.TextField dentro de un árbol de controles."""
    campos: list[ft.TextField] = []
    visitados: set[int] = set()
    cola = [ctrl]
    while cola:
        actual = cola.pop(0)
        if actual is None or id(actual) in visitados:
            continue
        visitados.add(id(actual))
        if isinstance(actual, ft.TextField):
            campos.append(actual)
        content = getattr(actual, "content", None)
        if content is not None and not isinstance(content, str):
            cola.append(content)
        for list_attr in ("controls", "actions", "tabs"):
            hijos = getattr(actual, list_attr, None)
            if isinstance(hijos, (list, tuple)):
                cola.extend(hijos)
    return campos


class TestFase3DesignSystemUX(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "data").mkdir(parents=True, exist_ok=True)
        self.u_store = UserStore(self.root / "data" / "usuarios.sqlite3")
        self.o_store = OrderStore(self.root / "data" / "pedidos.sqlite3")
        self.page = FakePage()
        self.menu = FakeMenu()
        with patch("src.flet_gui.MenuAgente", return_value=self.menu), patch(
            "src.flet_gui.UserStore", return_value=self.u_store
        ), patch("src.flet_gui.OrderStore", return_value=self.o_store):
            self.interfaz = InterfazFlet(cast(ft.Page, self.page))
        self.master_user = self.u_store.get_user_by_username("Desarrollo")
        self.interfaz.usuario_actual = self.master_user
        self.page.dialogos.clear()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_jerarquia_semantica_botones_dialogo(self) -> None:
        """Verifica que Cancelar/Cerrar sean neutros, Eliminar/Revocar sean peligro y Guardar sea primario."""
        for lbl_neutro in ("Cancelar", "Cerrar", "Cerrar (Esc)", "Volver", "Cancelar y Revisar"):
            btn_n = self.interfaz.boton_dialogo(lbl_neutro, lambda _e: None)
            self.assertEqual(btn_n.data, MARCA_NEUTRO)
            self.assertEqual(btn_n.bgcolor, ft.Colors.TRANSPARENT)

        for lbl_peligro in ("Eliminar", "Sí, Revocar", "Anular pedido", "Restaurar"):
            btn_p = boton_dialogo_semantico(lbl_peligro, lambda _e: None)
            self.assertEqual(btn_p.data, MARCA_PELIGRO)
            self.assertEqual(btn_p.bgcolor, ft.Colors.RED_900)

        btn_prim = self.interfaz.boton_dialogo("Guardar cambios", lambda _e: None)
        self.assertEqual(btn_prim.data, MARCA_PRIMARIO)

    def test_tokens_contraste_wcag_claro_y_oscuro(self) -> None:
        """Verifica tonos legibles en modo claro (700/800/900) y oscuro (200/300)."""
        self.assertEqual(tono_legible("AMBER", False), ft.Colors.AMBER_900)
        self.assertEqual(tono_legible("AMBER", True), ft.Colors.AMBER_300)
        self.assertEqual(tono_legible("GREEN", False), ft.Colors.GREEN_800)
        self.assertEqual(tono_legible("CYAN", False), ft.Colors.CYAN_800)

        pal_clara = colores_semanticos(False)
        pal_oscura = colores_semanticos(True)
        self.assertEqual(pal_oscura.etiqueta_emisor, ft.Colors.RED_200)
        self.assertEqual(pal_clara.etiqueta_emisor, ft.Colors.RED_800)
        self.assertNotEqual(pal_clara.superficie, pal_oscura.superficie)

    def test_endpoints_reales_en_api_panel_tabs(self) -> None:
        """Verifica que la pestaña de documentación liste endpoints reales de /api/v1/* y no ficticios."""
        col_docs = construir_tab_docs_estado(self.interfaz, ft.Colors.WHITE)
        texto_completo = "\n".join(_extraer_textos(col_docs))

        # Endpoints reales existentes en src/api/v1/
        self.assertIn("/api/v1/sistema/ping", texto_completo)
        self.assertIn("/api/v1/sistema/estado", texto_completo)
        self.assertIn("/api/v1/auth/login", texto_completo)
        self.assertIn("/api/v1/productos/buscar", texto_completo)
        self.assertIn("/api/v1/productos/{codigo}/stock", texto_completo)
        self.assertIn("/api/v1/inventario/finalizar", texto_completo)
        self.assertIn("/api/v1/despacho/escanear", texto_completo)

        # Endpoints ficticios eliminados
        self.assertNotIn("/api/v1/sistema/health", texto_completo)
        self.assertNotIn("/api/v1/inventario/stock", texto_completo)
        self.assertNotIn("POST /api/v1/despacho/pedidos", texto_completo)

    def test_enmascaramiento_secretos_smtp_telegram_mercadolibre(self) -> None:
        """Verifica que los secretos guardados nunca se precarguen en los TextFields y se conserven al dejar vacío."""
        campo = campo_secreto_seguro("Clave API", "secreto_super_privado_123")
        self.assertEqual(campo.value, "")
        self.assertTrue(campo.password)
        self.assertIn("••••••••", campo.hint_text or "")
        self.assertEqual(resolver_secreto(campo, "secreto_super_privado_123"), "secreto_super_privado_123")
        campo.value = "nuevo_secreto_456"
        self.assertEqual(resolver_secreto(campo, "secreto_super_privado_123"), "nuevo_secreto_456")

        # 1. Diálogo SMTP no expone smtp_password
        with patch(
            "src.ui.dialogs.dlg_smtp.obtener_config_email",
            return_value={"smtp_servidor": "smtp.test.com", "smtp_puerto": 587, "smtp_password": "CLAVE_SECRETA_SMTP"},
        ):
            mostrar_dialogo_configuracion_smtp(self.interfaz)
            dlg_smtp = self.page.dialogos[-1]
            valores_smtp = [c.value for c in _extraer_textfields(dlg_smtp)]
            self.assertNotIn("CLAVE_SECRETA_SMTP", valores_smtp)
            self.page.pop_dialog()

        # 2. Diálogo Telegram no expone bot_token
        with patch(
            "src.ui.dialogs.dlg_telegram.cargar_config_telegram",
            return_value={"bot_token": "999999:TOKEN_SECRETO_TELEGRAM", "chat_id": "12345"},
        ):
            mostrar_dialogo_configuracion_telegram(self.interfaz)
            dlg_tg = self.page.dialogos[-1]
            valores_tg = [c.value for c in _extraer_textfields(dlg_tg)]
            self.assertNotIn("999999:TOKEN_SECRETO_TELEGRAM", valores_tg)
            self.page.pop_dialog()

        # 3. Diálogo Mercado Libre no expone client_secret, access_token ni refresh_token
        with patch(
            "src.ui.dialogs.dlg_mercadolibre.cargar_config_mercadolibre",
            return_value={
                "app_id": "111",
                "client_secret": "ML_SECRET_PRIVADO",
                "access_token": "APP_USR_TOKEN_PRIVADO",
                "refresh_token": "TG_REFRESH_PRIVADO",
                "activo": False,
            },
        ):
            mostrar_dialogo_mercadolibre(self.interfaz)
            dlg_ml = self.page.dialogos[-1]
            valores_ml = [c.value for c in _extraer_textfields(dlg_ml)]
            self.assertNotIn("ML_SECRET_PRIVADO", valores_ml)
            self.assertNotIn("APP_USR_TOKEN_PRIVADO", valores_ml)
            self.assertNotIn("TG_REFRESH_PRIVADO", valores_ml)
            self.page.pop_dialog()

    def test_confirmar_accion_destructiva_rbac_y_auditoria(self) -> None:
        """Verifica que confirmar_accion_destructiva valide rol fail-closed, ejecute la acción y registre auditoría."""
        ejecutado = [False]

        # 1. Rol sin permiso -> bloqueado
        oper = self.u_store.create_user("oper_f3", "ClaveSegura123!", "operador")
        self.interfaz.usuario_actual = oper
        confirmar_accion_destructiva(
            self.interfaz,
            "Acción Master",
            "¿Confirmar?",
            lambda: ejecutado.__setitem__(0, True),
            roles_permitidos=("master",),
        )
        self.assertFalse(ejecutado[0])
        self.page.dialogos.clear()

        # 2. Rol Master -> abre modal, ejecuta al confirmar y registra auditoría
        self.interfaz.usuario_actual = self.master_user
        confirmar_accion_destructiva(
            self.interfaz,
            "Purgar Datos",
            "¿Estás seguro?",
            lambda: ejecutado.__setitem__(0, True),
            texto_confirmar="Sí, Purgar",
            roles_permitidos=("master",),
            auditoria=("PURGAR_TEST", "Ejecución de prueba Fase 3"),
        )
        self.assertEqual(len(self.page.dialogos), 1)
        dlg = self.page.dialogos[-1]
        self.assertTrue(dlg.modal)
        # El botón de confirmación está a la derecha dentro de actions[1]
        acc_der = dlg.actions[1]
        btn_confirmar = acc_der.controls[1] if isinstance(acc_der, ft.Row) else acc_der
        btn_confirmar.on_click(None)
        self.assertTrue(ejecutado[0])
        eventos = self.o_store.listar_auditoria(limit=10, filtro="PURGAR_TEST")
        self.assertEqual(len(eventos), 1)

    def test_validacion_inline_y_estado_ocupado(self) -> None:
        """Verifica marcar_error (.error en Flet 1.0), validación numérica/fecha y fijar_ocupado."""
        campo_num = ft.TextField(label="Stock", value="-5")
        self.assertIsNone(validar_entero_no_negativo(campo_num, "El stock", minimo=0))
        self.assertIn("menor a 0", campo_num.error or "")

        campo_num.value = "42"
        self.assertEqual(validar_entero_no_negativo(campo_num, "El stock", minimo=0), 42)
        self.assertIsNone(campo_num.error)

        campo_fecha = ft.TextField(label="Fecha", value="2026-11-20")
        self.assertIsNone(validar_fecha_ddmmaaaa(campo_fecha, permitir_vacio=False))
        self.assertIn("DD/MM/AAAA", campo_fecha.error or "")

        campo_fecha.value = "20/11/2026"
        fecha_ok = validar_fecha_ddmmaaaa(campo_fecha, permitir_vacio=False)
        self.assertIsNotNone(fecha_ok)
        self.assertIsNone(campo_fecha.error)

        marcar_error(campo_num, "Error de prueba")
        self.assertEqual(campo_num.error, "Error de prueba")
        marcar_error(campo_num, None)
        self.assertIsNone(campo_num.error)

        btn = ft.Button("Guardar", icon=ft.Icons.SAVE)
        fijar_ocupado(btn, True, "Guardando...")
        self.assertTrue(btn.disabled)
        self.assertEqual(btn.content, "Guardando...")
        fijar_ocupado(btn, False)
        self.assertFalse(btn.disabled)
        self.assertEqual(btn.content, "Guardar")

    def test_responsividad_tablet_navegacion_movil_por_rol_y_command_palette(self) -> None:
        """Verifica que iPad/tablets no trunquen diálogos a 336px, que mobile_nav se adapte al rol y Command Palette tenga guardia."""
        # 1. Tablet iPad (1024px) no trunca diálogos a 336px
        self.page.width = 1024
        self.page.client_user_agent = "Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) AppleWebKit/605.1.15"
        self.assertFalse(self.interfaz.es_pantalla_movil)
        self.assertEqual(self.interfaz.ancho_adaptable(720), 720)
        self.page.client_user_agent = ""

        # 2. Barra de navegación móvil adaptada a cada rol
        esperados_por_rol = {
            "despachador": ["Despacho", "Chat"],
            "picker": ["Ola Picking", "Escanear ML", "Full", "Fábrica", "Chat"],
            "administrador": ["Pedidos", "Stock", "Cierres", "Reportes", "Chat"],
            "master": ["Usuarios", "Auditoría", "API REST", "Backup", "Chat"],
            "consulta": ["Stock", "Reportes", "Informes", "Chat"],
            "operador": ["Pedidos", "Escanear ML", "Fábrica", "Cierre", "Chat"],
        }
        for rol, labels_esperados in esperados_por_rol.items():
            self.interfaz.usuario_actual = SimpleNamespace(role=rol, username=f"u_{rol}")
            nav = construir_navigation_bar_movil(self.interfaz)
            self.assertEqual([d.label for d in nav.destinations], labels_esperados)

        # Verificar enrutamiento de picker en mobile_nav
        self.interfaz.usuario_actual = SimpleNamespace(role="picker", username="pick1")
        with patch.object(self.interfaz, "mostrar_picking_guiado_full") as mock_full:
            manejar_cambio_navegacion_movil(
                self.interfaz, SimpleNamespace(control=SimpleNamespace(selected_index=2))
            )
            mock_full.assert_called_once()

        # 3. Sección predeterminada para picker
        self.assertEqual(_obtener_seccion_predeterminada("picker"), "DESPACHO")

        # 4. Command Palette: guardia contra doble apertura y cierre limpio
        self.interfaz.usuario_actual = self.master_user
        self.page.dialogos.clear()
        mostrar_command_palette(self.interfaz)
        self.assertEqual(len(self.page.dialogos), 1)
        # Segundo llamado mientras está abierto no apila otro diálogo
        mostrar_command_palette(self.interfaz)
        self.assertEqual(len(self.page.dialogos), 1)
        # Cerrar con botón Cerrar (Esc) libera la guardia
        dlg_cmd = self.page.dialogos[-1]
        dlg_cmd.actions[0].on_click(None)
        self.assertFalse(getattr(self.interfaz, "_command_palette_abierto", False))

    def test_accesibilidad_html_y_touch_targets_css(self) -> None:
        """Verifica que index.html y scanner.html permitan zoom, declaren lang='es' y scanner.css tenga >= 44px."""
        root_dir = Path(__file__).resolve().parent.parent
        index_html = (root_dir / "assets" / "index.html").read_text(encoding="utf-8")
        scanner_html = (root_dir / "assets" / "scanner.html").read_text(encoding="utf-8")
        scanner_css = (root_dir / "assets" / "css" / "scanner.css").read_text(encoding="utf-8")

        self.assertIn('<html lang="es">', index_html)
        self.assertNotIn("user-scalable=no", index_html)
        self.assertIn("aria-live", index_html)

        self.assertIn('<html lang="es">', scanner_html)
        self.assertNotIn("user-scalable=no", scanner_html)
        self.assertIn("aria-live=\"polite\"", scanner_html)
        self.assertIn("aria-label=", scanner_html)

        self.assertIn("min-height: 44px;", scanner_css)


if __name__ == "__main__":
    unittest.main()
