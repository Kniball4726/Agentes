import asyncio
import unittest
from types import SimpleNamespace
from typing import cast
from unittest.mock import patch

import flet as ft

from src.flet_gui import InterfazFlet


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

    def add(self, *controls):
        self.controls.extend(controls)

    def update(self):
        pass


class FletGuiTests(unittest.TestCase):
    def crear_interfaz(self):
        menu = FakeMenu()
        page = FakePage()
        with patch("src.flet_gui.MenuAgente", return_value=menu):
            interfaz = InterfazFlet(cast(ft.Page, page))
        return interfaz, menu, page

    def test_builds_dashboard_and_local_chat(self):
        interfaz, _, page = self.crear_interfaz()

        self.assertEqual(len(page.controls), 1)
        self.assertEqual(len(interfaz.controles_tarea), 8)
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

    def test_chat_uses_local_status_command(self):
        interfaz, _, _ = self.crear_interfaz()
        interfaz.entrada_chat.value = "/estado"

        asyncio.run(interfaz.enviar_chat())

        self.assertEqual(len(interfaz.conversacion.controls), 3)
        respuesta_control = cast(ft.Container, interfaz.conversacion.controls[-1])
        respuesta_columna = cast(ft.Column, respuesta_control.content)
        respuesta = cast(ft.Text, respuesta_columna.controls[1]).value
        self.assertIn("Pendientes:", respuesta)


if __name__ == "__main__":
    unittest.main()
