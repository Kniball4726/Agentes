"""Tests unitarios para la sección de API REST y Claves de Integración del usuario Master."""

import tempfile
import unittest
from pathlib import Path
from typing import cast
from unittest.mock import patch

import flet as ft

from src.orders_store import OrderStore
from src.user_store import UserStore
from src.ui.dialogs.dlg_api import (
    mostrar_dialogo_api_master,
    mostrar_gestion_api_keys,
    mostrar_estado_api,
    mostrar_sesiones_api,
)
from tests.test_flet_gui import FakeMenu, FakePage, InterfazFlet


class TestApiMasterDialog(unittest.TestCase):
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

        self.master_user = self.u_store.get_user_by_username("Desarrollo")
        self.interfaz.usuario_actual = self.master_user

    def tearDown(self):
        self.tmp.cleanup()

    def test_user_store_api_methods(self):
        """Verifica las operaciones CRUD de claves y sesiones en UserStore."""
        # 1. Crear clave API
        raw_key, key_hash = self.u_store.create_api_key("ERP Central", role="operador")
        self.assertTrue(raw_key.startswith("sk_live_"))
        self.assertEqual(len(key_hash), 64)

        # 2. Listar claves
        keys = self.u_store.list_api_keys()
        self.assertEqual(len(keys), 1)
        self.assertEqual(keys[0]["client_name"], "ERP Central")
        self.assertEqual(keys[0]["active"], 1)

        # 3. Revocar clave
        self.assertTrue(self.u_store.revoke_api_key(key_hash))
        keys_after = self.u_store.list_api_keys()
        self.assertEqual(keys_after[0]["active"], 0)

        # 4. Eliminar clave
        self.assertTrue(self.u_store.delete_api_key(key_hash))
        self.assertEqual(len(self.u_store.list_api_keys()), 0)

        # 5. Sesiones API
        self.u_store.create_api_session(
            token_hash="hash_token_123",
            user_id=1,
            username="master_user",
            role="master",
            nombre="Master Admin",
            email="master@deposito.com",
        )
        sesiones = self.u_store.list_api_sessions()
        self.assertEqual(len(sesiones), 1)
        self.assertEqual(sesiones[0]["username"], "master_user")

        # 6. Revocar todas las sesiones
        total_revocadas = self.u_store.revoke_all_sessions()
        self.assertEqual(total_revocadas, 1)
        self.assertEqual(len(self.u_store.list_api_sessions()), 0)

    def test_mostrar_dialogos_api_roles_permitidos(self):
        """El rol Master puede abrir todas las vistas de la sección API."""
        # Pestaña 0: Claves
        mostrar_gestion_api_keys(self.interfaz)
        self.assertEqual(len(self.page.dialogos), 1)
        dlg0 = self.page.dialogos[-1]
        self.assertIn("API REST", dlg0.title.controls[1].value)
        self.page.pop_dialog()

        # Pestaña 1: Estado y docs
        mostrar_estado_api(self.interfaz)
        self.assertEqual(len(self.page.dialogos), 1)
        self.page.pop_dialog()

        # Pestaña 2: Sesiones
        mostrar_sesiones_api(self.interfaz)
        self.assertEqual(len(self.page.dialogos), 1)
        self.page.pop_dialog()

        # A través de InterfazFlet
        self.interfaz.mostrar_gestion_api_keys()
        self.assertEqual(len(self.page.dialogos), 1)
        self.page.pop_dialog()

    def test_rol_no_master_bloqueado(self):
        """Usuarios con rol operador o consulta no pueden abrir la sección API."""
        oper_user = self.u_store.create_user("operario1", "OperPass1234!", "operador")
        self.interfaz.usuario_actual = oper_user

        mostrar_dialogo_api_master(self.interfaz)
        # Se notifica la restricción de permiso y no se abre el diálogo de API
        self.assertEqual(len(self.page.dialogos), 1)
        dlg = self.page.dialogos[0]
        texto_contenido = getattr(dlg.content, "value", "") if hasattr(dlg, "content") else ""
        self.assertIn("no tiene permiso", texto_contenido)


if __name__ == "__main__":
    unittest.main()
