"""Pruebas unitarias para la tipografía Inter aplicada exclusivamente a los menús."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import patch

import flet as ft

from src.auth import UserStore
from src.flet_gui import InterfazFlet
from src.orders import OrderStore
from src.ui.components.header import construir_encabezado
from src.ui.components.sidebar import construir_sidebar_controls
from src.ui.components.sidebar_horizontal import construir_sidebar_horizontal_controls
from src.ui.components.window_manager import mostrar_menu_movil_fallback
from src.ui.dialogs.dlg_command_palette import mostrar_command_palette
from src.ui.theme import (
    FUENTE_MENU,
    FUENTE_MENU_BOLD,
    FUENTE_MENU_MEDIUM,
    FUENTE_MENU_SEMIBOLD,
    FUENTES_APP,
)
from tests.test_flet_gui import FakeMenu, FakePage

FAMILIAS_INTER = {FUENTE_MENU, FUENTE_MENU_MEDIUM, FUENTE_MENU_SEMIBOLD, FUENTE_MENU_BOLD}
ROLES_SISTEMA = ("operador", "administrador", "picker", "despachador", "master", "consulta")


def _recorrer_controles(raiz: Any) -> list[Any]:
    """Recorre recursivamente un árbol de controles Flet evitando ciclos."""
    salida: list[Any] = []
    visitados: set[int] = set()
    cola: list[Any] = [raiz] if not isinstance(raiz, (list, tuple)) else list(raiz)
    while cola:
        actual = cola.pop(0)
        if actual is None or isinstance(actual, str) or id(actual) in visitados:
            continue
        visitados.add(id(actual))
        salida.append(actual)
        for attr in ("content", "title", "leading", "trailing"):
            hijo = getattr(actual, attr, None)
            if hijo is not None and not isinstance(hijo, str):
                cola.append(hijo)
        for attr_lista in ("controls", "actions", "items"):
            hijos = getattr(actual, attr_lista, None)
            if isinstance(hijos, (list, tuple)):
                cola.extend(hijos)
    return salida


class TestMenuFonts(unittest.TestCase):
    """Verifica el registro de Inter y su aplicación en todos los menús de navegación."""

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
        self.interfaz.usuario_actual = self.u_store.get_user_by_username("Desarrollo")
        self.page.dialogos.clear()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_archivos_fuente_inter_existen_en_assets(self) -> None:
        """Todos los archivos TTF referenciados en FUENTES_APP existen en assets/."""
        assets_dir = Path(__file__).resolve().parent.parent / "assets"
        self.assertEqual(set(FUENTES_APP.keys()), FAMILIAS_INTER)
        for rel_path in FUENTES_APP.values():
            ruta = assets_dir / rel_path
            self.assertTrue(ruta.is_file(), f"Falta archivo de fuente: {ruta}")
            self.assertGreater(ruta.stat().st_size, 0)

    def test_tema_shell_registra_fuentes_solo_en_menus_y_no_global(self) -> None:
        """El tema registra Inter en page.fonts y subtemas de menú sin alterar font_family global."""
        self.assertEqual(self.page.fonts, FUENTES_APP)
        for tema in (self.page.theme, self.page.dark_theme):
            self.assertIsNone(tema.font_family)
            self.assertEqual(tema.popup_menu_theme.label_text_style.font_family, FUENTE_MENU)
            self.assertEqual(tema.navigation_bar_theme.label_text_style.font_family, FUENTE_MENU_MEDIUM)
            self.assertEqual(tema.navigation_drawer_theme.label_text_style.font_family, FUENTE_MENU_MEDIUM)

    def test_sidebar_vertical_aplica_inter_en_todos_los_textos_y_botones(self) -> None:
        """Todos los roles del sidebar vertical usan Inter en encabezados, ítems y accesos rápidos."""
        for rol in ROLES_SISTEMA:
            with self.subTest(rol=rol):
                self.interfaz.usuario_actual = SimpleNamespace(
                    username=f"usr_{rol}",
                    nombre_identificador=f"Usuario {rol}",
                    role=rol,
                )
                controles = construir_sidebar_controls(self.interfaz)
                nodos = _recorrer_controles(controles)
                textos = [n for n in nodos if isinstance(n, ft.Text)]
                self.assertGreater(len(textos), 0)
                for txt in textos:
                    self.assertIn(txt.font_family, FAMILIAS_INTER, f"Texto sin Inter en sidebar ({rol}): {txt.value!r}")

                botones = [n for n in nodos if isinstance(n, ft.Button)]
                self.assertGreater(len(botones), 0)
                for btn in botones:
                    self.assertIsNotNone(btn.style)
                    self.assertIn(btn.style.text_style.font_family, FAMILIAS_INTER)

    def test_barra_horizontal_aplica_inter_en_menubar_y_pildoras(self) -> None:
        """La barra horizontal aplica Inter en MenuBar, SubmenuButton, MenuItemButton y píldoras."""
        for rol in ROLES_SISTEMA:
            with self.subTest(rol=rol):
                self.interfaz.usuario_actual = SimpleNamespace(
                    username=f"usr_{rol}",
                    nombre_identificador=f"Usuario {rol}",
                    role=rol,
                )
                controles = construir_sidebar_horizontal_controls(self.interfaz)
                nodos = _recorrer_controles(controles)

                textos = [n for n in nodos if isinstance(n, ft.Text)]
                self.assertGreater(len(textos), 0)
                for txt in textos:
                    self.assertIn(txt.font_family, FAMILIAS_INTER, f"Texto sin Inter en barra horizontal ({rol}): {txt.value!r}")

                menu_items = [n for n in nodos if isinstance(n, ft.MenuItemButton)]
                self.assertGreater(len(menu_items), 0)
                for item in menu_items:
                    self.assertIn(item.style.text_style.font_family, FAMILIAS_INTER)

                submenus = [n for n in nodos if isinstance(n, ft.SubmenuButton)]
                self.assertGreater(len(submenus), 0)
                for sub in submenus:
                    self.assertIn(sub.style.text_style.font_family, FAMILIAS_INTER)

    def test_header_menus_usuario_y_dock_usan_inter_desktop_y_movil(self) -> None:
        """Los menús desplegables de usuario y posición de barra usan Inter en desktop y móvil."""
        for ancho in (1280, 390):
            with self.subTest(ancho=ancho):
                self.page.width = ancho
                enc = construir_encabezado(self.interfaz)
                popups = [n for n in _recorrer_controles(enc) if isinstance(n, ft.PopupMenuButton)]
                self.assertGreater(len(popups), 0)
                for popup in popups:
                    for item in popup.items:
                        if item.content is None and item.icon is None:
                            continue
                        self.assertIsNotNone(item.label_text_style)
                        self.assertIn(item.label_text_style.font_family, FAMILIAS_INTER)
                        if isinstance(item.content, ft.Text):
                            self.assertIn(item.content.font_family, FAMILIAS_INTER)
                    if popup.content is not None:
                        for txt in [n for n in _recorrer_controles(popup.content) if isinstance(n, ft.Text)]:
                            self.assertIn(txt.font_family, FAMILIAS_INTER)

    def test_menu_movil_fallback_usa_inter(self) -> None:
        """El menú modal alternativo en móvil aplica Inter tanto en botones como en cierre."""
        self.page.dialogos.clear()
        self.interfaz._mostrar_menu_movil_fallback()
        self.assertEqual(len(self.page.dialogos), 1)
        dlg_ctrl = self.page.dialogos[-1]
        btn_cerrar = dlg_ctrl.actions[0]
        self.assertEqual(btn_cerrar.style.text_style.font_family, FUENTE_MENU_MEDIUM)

        self.page.dialogos.clear()
        mostrar_menu_movil_fallback(self.interfaz)
        self.assertEqual(len(self.page.dialogos), 1)
        self.assertEqual(self.page.dialogos[-1].actions[0].style.text_style.font_family, FUENTE_MENU_MEDIUM)

    def test_command_palette_usa_inter_en_todo_el_menu_rapido(self) -> None:
        """La paleta F2 / Ctrl+K aplica Inter en buscador, resultados, encabezados y botón cerrar."""
        self.page.dialogos.clear()
        self.interfaz._command_palette_abierto = False
        mostrar_command_palette(self.interfaz)
        self.assertEqual(len(self.page.dialogos), 1)
        dlg = self.page.dialogos[-1]

        nodos = _recorrer_controles(dlg)
        textos = [n for n in nodos if isinstance(n, ft.Text)]
        self.assertGreater(len(textos), 0)
        for txt in textos:
            self.assertIn(txt.font_family, FAMILIAS_INTER, f"Texto sin Inter en paleta F2: {txt.value!r}")

        campos = [n for n in nodos if isinstance(n, ft.TextField)]
        self.assertEqual(len(campos), 1)
        self.assertEqual(campos[0].text_style.font_family, FUENTE_MENU)
        self.assertEqual(campos[0].hint_style.font_family, FUENTE_MENU)
        self.assertEqual(dlg.actions[0].style.text_style.font_family, FUENTE_MENU_MEDIUM)

        # Verificar también al filtrar resultados de búsqueda (coincidencias y sin coincidencias)
        for consulta in ("usuarios", "inexistente_xyz"):
            campos[0].value = consulta
            campos[0].on_submit(SimpleNamespace(control=SimpleNamespace(value=consulta)))
            nodos_filtrados = _recorrer_controles(dlg)
            for txt in [n for n in nodos_filtrados if isinstance(n, ft.Text)]:
                self.assertIn(txt.font_family, FAMILIAS_INTER, f"Resultado sin Inter en paleta F2 ({consulta}): {txt.value!r}")
