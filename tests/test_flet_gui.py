import asyncio
import unittest
from types import SimpleNamespace
from typing import cast
from unittest.mock import patch

import flet as ft

from src.flet_gui import InterfazFlet
from src.user_store import User, UserRole


class FakeMenu:
    ruta_excel_base = "Productos.xlsx"

    def __init__(self):
        self.procesamientos = []

    def _obtener_pendientes(self):
        return [], [], []

    def _obtener_archivados(self):
        return [], [], []

    def _obtener_generados(self):
        return []

    def procesar(self, **opciones):
        self.procesamientos.append(opciones)
        print("Simulación comprobada")


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
        self.assertEqual(len(interfaz.controles_tarea), 9)
        bienvenida = cast(ft.Container, interfaz.conversacion.controls[0])
        contenido = cast(ft.Column, bienvenida.content)
        self.assertEqual(cast(ft.Text, contenido.controls[0]).value, "Agente")
        self.assertEqual(interfaz.estado_tarea.value, "Listo")

    def test_simulation_calls_agent_in_read_only_mode(self):
        interfaz, menu, _ = self.crear_interfaz()

        asyncio.run(interfaz.procesar(simulacion=True))

        self.assertEqual(
            menu.procesamientos,
            [
                {
                    "incluir_mayoristas": True,
                    "incluir_canjes": True,
                    "incluir_mercado_libre": True,
                    "simulacion": True,
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

    def test_consultation_role_cannot_process_or_simulate(self):
        interfaz, menu, page = self.crear_interfaz(role="consulta")

        asyncio.run(interfaz.procesar(simulacion=True))

        self.assertEqual(menu.procesamientos, [])
        self.assertEqual(len(page.dialogos), 1)
        self.assertEqual(len(interfaz.controles_tarea), 4)


if __name__ == "__main__":
    unittest.main()
