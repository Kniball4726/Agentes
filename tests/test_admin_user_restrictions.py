"""Pruebas unitarias para las restricciones de seguridad del rol Administrador en la gestión de usuarios:
1. No puede ver otros administradores.
2. No puede crear administradores.
3. No puede ver el usuario master.
"""

import tempfile
import unittest
from pathlib import Path
from typing import cast
from unittest.mock import MagicMock, patch

import flet as ft

from src.auth import UserStore, UserStoreError
from src.orders import OrderStore
from tests.test_flet_gui import FakeMenu, FakePage, InterfazFlet
from src.ui.dialogs.dlg_usuarios import mostrar_dialogo_gestion_usuarios


class TestAdminUserRestrictions(unittest.TestCase):
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

        # Crear usuarios para el escenario:
        # - Master (Desarrollo) ya existe por defecto en u_store
        # - Admin 1 (supervisor1)
        # - Admin 2 (supervisor2)
        # - Operador 1 (operario1)
        self.admin1 = self.u_store.create_user("supervisor1", "AdminPass1234!", "administrador", creator_role="master")
        self.admin2 = self.u_store.create_user("supervisor2", "AdminPass1234!", "administrador", creator_role="master")
        self.oper1 = self.u_store.create_user("operario1", "OperPass1234!", "operador", creator_role="master")
        self.master_user = self.u_store.get_user_by_username("Desarrollo")

    def tearDown(self):
        self.tmp.cleanup()

    def test_admin_list_users_excludes_master_and_other_admins(self):
        """Verifica que list_users filtre a master y a otros administradores cuando consulta un admin."""
        # 1. Master ve a todos
        todos = self.u_store.list_users(include_master=True)
        roles = [u.role for u in todos]
        self.assertIn("master", roles)
        self.assertEqual(roles.count("administrador"), 2)

        # 2. Administrador 1 no ve a master ni a Administrador 2
        filtrados_admin1 = self.u_store.list_users(
            include_master=False,
            exclude_other_admins=True,
            current_user_id=self.admin1.id,
        )
        nombres = [u.username for u in filtrados_admin1]
        self.assertNotIn("Desarrollo", nombres)  # No ve al master
        self.assertNotIn("supervisor2", nombres)  # No ve al otro administrador
        self.assertIn("supervisor1", nombres)  # Sí se ve a sí mismo
        self.assertIn("operario1", nombres)  # Sí ve al operador

    def test_admin_cannot_create_administrator_at_store_level(self):
        """El UserStore rechaza que un administrador cree otro administrador."""
        with self.assertRaises(UserStoreError) as ctx:
            self.u_store.create_user(
                "nuevo_admin",
                "ClaveSegura123!",
                "administrador",
                creator_role="administrador",
            )
        self.assertIn("Solo un usuario con rol master puede crear administradores", str(ctx.exception))

    def test_admin_ui_dialog_restrictions(self):
        """En el diálogo de gestión de usuarios, el administrador no ve a master ni a otros administradores, y no puede elegir rol admin."""
        self.interfaz.usuario_actual = self.admin1

        mostrar_dialogo_gestion_usuarios(self.interfaz)
        self.assertEqual(len(self.page.dialogos), 1)
        dlg = self.page.dialogos[0]

        # 1. El dropdown de creación de nuevo rol NO debe contener 'Administrador' ni 'Master'
        col_content = dlg.content.content
        fila_rol = col_content.controls[3]
        dropdown_rol = fila_rol.controls[0]
        roles_disponibles = [opt.key for opt in dropdown_rol.options]
        self.assertNotIn("administrador", roles_disponibles)
        self.assertNotIn("master", roles_disponibles)
        self.assertIn("operador", roles_disponibles)
        self.assertIn("picker", roles_disponibles)
        self.assertIn("consulta", roles_disponibles)

        # 2. La lista de usuarios existentes NO debe mostrar al master ni a supervisor2
        usuarios_col = col_content.controls[7]
        textos_visibles = []
        for fila in usuarios_col.controls:
            for c in fila.controls:
                if isinstance(c, ft.Column):
                    for t in c.controls:
                        if hasattr(t, "value") and t.value:
                            textos_visibles.append(t.value)

        texto_unido = " ".join(textos_visibles)
        self.assertNotIn(f"@{self.master_user.username}", texto_unido)
        self.assertNotIn("@supervisor2", texto_unido)  # El otro administrador no es visible
        self.assertIn("@supervisor1", texto_unido)     # Su propio usuario sí
        self.assertIn("@operario1", texto_unido)       # El operador subordinado sí

    def test_master_ui_dialog_shows_all_admins_and_allows_creating_admin(self):
        """El rol Master sí puede ver a todos los administradores y crear administradores."""
        self.interfaz.usuario_actual = self.master_user

        mostrar_dialogo_gestion_usuarios(self.interfaz)
        self.assertEqual(len(self.page.dialogos), 1)
        dlg = self.page.dialogos[0]

        col_content = dlg.content.content
        fila_rol = col_content.controls[3]
        dropdown_rol = fila_rol.controls[0]
        roles_disponibles = [opt.key for opt in dropdown_rol.options]
        self.assertIn("administrador", roles_disponibles)

        usuarios_col = col_content.controls[7]
        textos_visibles = []
        for fila in usuarios_col.controls:
            for c in fila.controls:
                if isinstance(c, ft.Column):
                    for t in c.controls:
                        if hasattr(t, "value") and t.value:
                            textos_visibles.append(t.value)

        texto_unido = " ".join(textos_visibles)
        self.assertIn(f"@{self.master_user.username}", texto_unido)
        self.assertIn("@supervisor1", texto_unido)
        self.assertIn("@supervisor2", texto_unido)
        self.assertIn("@operario1", texto_unido)

    def test_master_can_unlock_user_and_reset_password_without_name_error(self):
        """Verifica que el master pueda desbloquear usuarios y abrir el modal de reset de clave sin NameError."""
        # Bloquear a operario1
        for _ in range(5):
            self.u_store.authenticate("operario1", "clave_incorrecta_123")
        self.assertIn("operario1", self.u_store.list_locked_usernames())

        self.interfaz.usuario_actual = self.master_user
        mostrar_dialogo_gestion_usuarios(self.interfaz)
        dlg = self.page.dialogos[0]
        col_content = dlg.content.content
        usuarios_col = col_content.controls[7]

        # Buscar fila de operario1
        fila_operario = None
        for fila in usuarios_col.controls:
            for c in fila.controls:
                if isinstance(c, ft.Column):
                    for t in c.controls:
                        if hasattr(t, "value") and "@operario1" in str(t.value):
                            fila_operario = fila
                            break

        self.assertIsNotNone(fila_operario)
        boton_desbloquear = fila_operario.controls[2]
        boton_reset = fila_operario.controls[4]

        self.assertFalse(boton_desbloquear.disabled)
        # Ejecutar on_click de desbloquear
        boton_desbloquear.on_click(None)
        self.assertNotIn("operario1", self.u_store.list_locked_usernames())

        # Ejecutar on_click de reset de clave
        boton_reset.on_click(None)
        # Debe abrir el diálogo de reset sin NameError
        self.assertGreaterEqual(len(self.page.dialogos), 2)


if __name__ == "__main__":
    unittest.main()
