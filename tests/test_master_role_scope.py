"""Tests unitarios para la verificación del alcance restringido y seguro del Rol Master (SoD / IAM / Auditoría)."""

import asyncio
import tempfile
import unittest
from pathlib import Path
from typing import cast
from unittest.mock import patch

import flet as ft

from src.orders_store import OrderStore
from src.user_store import UserStore
from tests.test_flet_gui import FakeMenu, FakePage, InterfazFlet


class TestMasterRoleScope(unittest.TestCase):
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

    def test_master_sidebar_only_contains_technical_management(self):
        """Verifica que el panel lateral de Master solo tenga opciones técnicas y de auditoría."""
        items = self.interfaz._sidebar_controls()
        textos = []
        for it in items:
            if isinstance(it, ft.Text) and it.value:
                textos.append(it.value)
            elif isinstance(it, ft.Button) and hasattr(it, "content") and isinstance(it.content, str):
                textos.append(it.content)

        # Debe incluir secciones técnicas
        self.assertIn("SEGURIDAD Y ACCESOS", textos)
        self.assertIn("AUDITORÍA Y TRAZABILIDAD", textos)
        self.assertIn("RESGUARDO Y CONTINUIDAD", textos)
        self.assertIn("SISTEMA", textos)

        # NO debe incluir opciones de negocio
        self.assertNotIn("PEDIDOS EN TIEMPO REAL", textos)
        self.assertNotIn("INFORMES", textos)
        self.assertNotIn("Gestionar productos", textos)
        self.assertNotIn("Ajustar stock / Fábrica", textos)
        self.assertNotIn("Descontar Mercado Libre", textos)
        self.assertNotIn("Cierre de Jornada", textos)

    def test_master_permisos_permitidos(self):
        """El rol Master puede abrir Gestión de Usuarios, Auditoría, Backups y SMTP."""
        # 1. Gestionar usuarios
        self.interfaz.mostrar_gestion_usuarios()
        self.assertEqual(len(self.page.dialogos), 1)
        self.page.pop_dialog()

        # 2. Registro de auditoría
        self.interfaz.mostrar_registro_auditoria()
        self.assertEqual(len(self.page.dialogos), 1)
        self.page.pop_dialog()

        # 3. Copia de seguridad
        self.interfaz.mostrar_dialogo_backup()
        self.assertEqual(len(self.page.dialogos), 1)
        self.page.pop_dialog()

        # 4. Configuración SMTP
        self.interfaz.mostrar_configuracion_smtp()
        self.assertEqual(len(self.page.dialogos), 1)
        self.page.pop_dialog()

    def test_master_permisos_restringidos_de_negocio(self):
        """El rol Master NO puede realizar tareas de inventario, stock ni remitos."""
        # Intento de simular
        asyncio.run(self.interfaz.simular(None))
        self.assertEqual(self.menu.procesamientos, [])
        self.assertEqual(len(self.page.dialogos), 1)
        self.page.pop_dialog()

        # Intento de procesar
        asyncio.run(self.interfaz.procesar(simulacion=False))
        self.assertEqual(self.menu.procesamientos, [])
        self.assertEqual(len(self.page.dialogos), 1)
        self.page.pop_dialog()

        # Intento de entrar a gestión de productos
        self.interfaz.mostrar_gestion_productos()
        self.assertEqual(len(self.page.dialogos), 1)
        dlg = self.page.dialogos[0]
        texto_contenido = getattr(dlg.content, "value", "") if hasattr(dlg, "content") else ""
        self.assertIn("no tiene permiso", texto_contenido)
        self.page.pop_dialog()

        # Intento de cierre de jornada
        self.interfaz.mostrar_cierre_jornada()
        self.assertEqual(len(self.page.dialogos), 1)
        dlg = self.page.dialogos[0]
        texto_contenido = getattr(dlg.content, "value", "") if hasattr(dlg, "content") else ""
        self.assertIn("exclusiva", texto_contenido.lower())
        self.page.pop_dialog()

    def test_master_chat_restringe_comandos_de_stock(self):
        """El asistente en el chat responde con aviso de alcance cuando Master consulta comandos de stock."""
        self.interfaz.entrada_chat.value = "/stock 100"
        asyncio.run(self.interfaz.enviar_chat(None))

        mensajes_chat = [
            c.content.controls[1].value
            for c in self.interfaz.conversacion.controls
            if hasattr(c, "content") and hasattr(c.content, "controls") and len(c.content.controls) > 1
        ]
        self.assertTrue(any("Master está dedicado exclusivamente a Seguridad" in m for m in mensajes_chat))

    def test_admin_cannot_access_audit_logs_but_has_shared_iam(self):
        """El rol Administrador NO puede ver auditoría, pero conserva gestión compartida de usuarios."""
        admin_user = self.u_store.create_user("supervisor1", "PasswordSeguro2026!", "administrador")
        self.interfaz.usuario_actual = admin_user

        # 1. Sidebar de administrador no contiene Auditoría
        items = self.interfaz._sidebar_controls()
        textos = []
        for it in items:
            if isinstance(it, ft.Text) and it.value:
                textos.append(it.value)
            elif isinstance(it, ft.Button) and hasattr(it, "content") and isinstance(it.content, str):
                textos.append(it.content)

        self.assertNotIn("Registro de Auditoría", textos)
        self.assertIn("Gestionar usuarios", textos)
        self.assertIn("Copia de Seguridad", textos)

        # 2. Intento de abrir registro de auditoría directo
        self.interfaz.mostrar_registro_auditoria()
        self.assertEqual(len(self.page.dialogos), 1)
        dlg = self.page.dialogos[0]
        texto_contenido = getattr(dlg.content, "value", "") if hasattr(dlg, "content") else ""
        self.assertIn("no tiene permiso", texto_contenido)
        self.page.pop_dialog()

        # 3. Chat: intento de consultar /auditoria
        self.interfaz.entrada_chat.value = "/auditoria"
        asyncio.run(self.interfaz.enviar_chat(None))
        mensajes_chat = [
            c.content.controls[1].value
            for c in self.interfaz.conversacion.controls
            if hasattr(c, "content") and hasattr(c.content, "controls") and len(c.content.controls) > 1
        ]
        self.assertTrue(any("reservado exclusivamente para el rol Master" in m for m in mensajes_chat))

        # 4. Gestión compartida de usuarios sigue disponible para administrador
        self.interfaz.mostrar_gestion_usuarios()
        self.assertEqual(len(self.page.dialogos), 1)
        dlg_usr = self.page.dialogos[0]
        self.page.pop_dialog()


if __name__ == "__main__":
    unittest.main()
