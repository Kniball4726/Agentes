"""Tests unitarios para el rol Picker y su alcance restringido en la interfaz."""

import tempfile
import unittest
from pathlib import Path
from typing import cast
from unittest.mock import patch

import flet as ft

from src.orders_store import OrderStore
from src.user_store import USER_ROLES, UserStore
from src.ui.components.sidebar import obtener_secciones_rol
from tests.test_flet_gui import FakeMenu, FakePage, InterfazFlet


class TestPickerRole(unittest.TestCase):
    def setUp(self):
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

        self.picker_user = self.u_store.create_user(
            username="picker_test",
            password="PickerPassword123!",
            role="picker",
            nombre="Operador Picker",
        )
        self.interfaz.usuario_actual = self.picker_user

    def tearDown(self):
        self.tmp.cleanup()

    def test_picker_in_user_roles(self):
        """Verifica que el rol picker esté en la definición de USER_ROLES y UserStore."""
        self.assertIn("picker", USER_ROLES)
        usuario = self.u_store.get_user_by_username("picker_test")
        self.assertIsNotNone(usuario)
        self.assertEqual(usuario.role, "picker")

    def test_picker_sidebar_controls_only_allowed_sections(self):
        """Verifica que el rol Picker solo vea Despacho (ML/Full) y Movimientos (Ingreso/Egreso)."""
        secciones = obtener_secciones_rol(self.interfaz)
        titulos_secciones = [s.titulo for s in secciones]
        todos_los_items = []
        for s in secciones:
            for item in s.items:
                todos_los_items.append(item[0])

        # Secciones permitidas
        self.assertIn("DESPACHO", titulos_secciones)
        self.assertIn("MOVIMIENTOS DE STOCK", titulos_secciones)

        # Opciones permitidas
        self.assertIn("Descontar Mercado Libre", todos_los_items)
        self.assertIn("Descontar Mercado Full", todos_los_items)
        self.assertIn("Ingreso de Mercadería", todos_los_items)
        self.assertIn("Ingreso de Fábrica", todos_los_items)
        self.assertIn("Egreso de Mercadería", todos_los_items)

        # Opciones prohibidas
        self.assertNotIn("Cargar / Armar Pedido", todos_los_items)
        self.assertNotIn("Gestión de Clientes", todos_los_items)
        self.assertNotIn("Cierre de Jornada", todos_los_items)
        self.assertNotIn("Gestionar usuarios", todos_los_items)
        self.assertNotIn("Copia de Seguridad", todos_los_items)
        self.assertNotIn("Historial de Pedidos", todos_los_items)
        self.assertNotIn("Métricas y Rendimiento", todos_los_items)

    def test_picker_permisos_permitidos_y_bloqueados(self):
        """Verifica que picker pueda abrir sus operaciones asignadas y sea bloqueado en las demás."""
        # 1. Ingreso rápido y egreso rápido
        self.interfaz.mostrar_dialogo_ingreso_rapido()
        self.assertEqual(len(self.page.dialogos), 1)
        self.page.pop_dialog()

        self.interfaz.mostrar_dialogo_salida_rapida()
        self.assertEqual(len(self.page.dialogos), 1)
        self.page.pop_dialog()

        # 2. Operaciones bloqueadas
        self.interfaz.mostrar_gestion_usuarios()
        self.assertEqual(len(self.page.dialogos), 1)
        dlg = self.page.dialogos[0]
        texto_contenido = getattr(dlg.content, "value", "") if hasattr(dlg, "content") else ""
        self.assertIn("no tiene permiso", texto_contenido)
        self.page.pop_dialog()


    def test_panel_acceso_rapido_picker(self):
        """Verifica que el panel de acceso rápido para Picker tenga Ingreso, Egreso y Descontar ML."""
        ctrl = self.interfaz.panel_acceso_rapido()
        self.assertTrue(ctrl.visible if hasattr(ctrl, "visible") else True)

        def extraer_textos(control):
            txts = []
            if hasattr(control, "value") and control.value:
                txts.append(str(control.value))
            if hasattr(control, "content") and control.content:
                txts.extend(extraer_textos(control.content))
            if hasattr(control, "controls") and control.controls:
                for c in control.controls:
                    txts.extend(extraer_textos(c))
            return txts

        textos = extraer_textos(ctrl)
        self.assertIn("Ingreso de Stock", textos)
        self.assertIn("Egreso de Stock", textos)
        self.assertIn("Descontar Mercado Libre", textos)
        self.assertNotIn("Cargar / Armar Pedido", textos)

    def test_panel_acceso_rapido_administrador(self):
        """Verifica que el panel de acceso rápido para Administrador solo tenga Ingreso y Egreso."""
        admin_user = self.u_store.create_user("admin_test", "AdminPass1234!", "administrador")
        self.interfaz.usuario_actual = admin_user

        ctrl = self.interfaz.panel_acceso_rapido()
        self.assertTrue(ctrl.visible if hasattr(ctrl, "visible") else True)

        def extraer_textos(control):
            txts = []
            if hasattr(control, "value") and control.value:
                txts.append(str(control.value))
            if hasattr(control, "content") and control.content:
                txts.extend(extraer_textos(control.content))
            if hasattr(control, "controls") and control.controls:
                for c in control.controls:
                    txts.extend(extraer_textos(c))
            return txts

        textos = extraer_textos(ctrl)
        self.assertIn("Ingreso de Stock", textos)
        self.assertIn("Egreso de Stock", textos)
        self.assertNotIn("Descontar Mercado Libre", textos)
        self.assertNotIn("Cargar / Armar Pedido", textos)

    def test_sidebar_botonera_rapida_por_rol(self):
        """Verifica que la botonera de acceso rápido del menú lateral respete los roles solicitados."""
        def extraer_textos(control):
            txts = []
            if hasattr(control, "value") and control.value:
                txts.append(str(control.value))
            if hasattr(control, "content") and control.content:
                txts.extend(extraer_textos(control.content))
            if hasattr(control, "controls") and control.controls:
                for c in control.controls:
                    txts.extend(extraer_textos(c))
            return txts

        # 1. Picker: tiene Entrada, Salida y Descontar ML (no Cargar Pedido)
        self.interfaz.usuario_actual = self.picker_user
        sidebar_picker = self.interfaz._sidebar_controls()
        txts_picker = []
        for c in sidebar_picker:
            txts_picker.extend(extraer_textos(c))
        self.assertIn("Entrada", txts_picker)
        self.assertIn("Salida", txts_picker)
        self.assertIn("Descontar ML", txts_picker)
        self.assertNotIn("Cargar Pedido", txts_picker)

        # 2. Administrador: solo Entrada y Salida (ni Cargar Pedido ni Mercado Libre)
        admin_user = self.u_store.get_user_by_username("admin_test") or self.u_store.create_user("admin_test", "AdminPass1234!", "administrador")
        self.interfaz.usuario_actual = admin_user
        sidebar_admin = self.interfaz._sidebar_controls()
        txts_admin = []
        for c in sidebar_admin:
            txts_admin.extend(extraer_textos(c))
        self.assertIn("Entrada", txts_admin)
        self.assertIn("Salida", txts_admin)
        self.assertNotIn("Cargar Pedido", txts_admin)
        self.assertNotIn("Mercado Libre", txts_admin)
        self.assertNotIn("Descontar ML", txts_admin)

        # 3. Master: tiene botonera técnica con Usuarios y Auditoría (sin Entrada, Salida ni Mercado Libre)
        master_user = self.u_store.get_user_by_username("Desarrollo")
        self.interfaz.usuario_actual = master_user
        sidebar_master = self.interfaz._sidebar_controls()
        txts_master = []
        for c in sidebar_master:
            txts_master.extend(extraer_textos(c))
        self.assertIn("Usuarios", txts_master)
        self.assertIn("Auditoría", txts_master)
        self.assertNotIn("Entrada", txts_master)
        self.assertNotIn("Salida", txts_master)
        self.assertNotIn("Cargar Pedido", txts_master)
        self.assertNotIn("Mercado Libre", txts_master)
        self.assertNotIn("Descontar ML", txts_master)


if __name__ == "__main__":
    unittest.main()
