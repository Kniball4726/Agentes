"""Tests para el ambiente de pruebas (QA) y datos semilla."""

import os
import tempfile
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

from src.core.environment import (
    get_environment,
    set_environment,
    is_qa_environment,
    get_data_dir,
    get_descuentos_dir,
)
from src.qa.seeder import inicializar_ambiente_qa, PRODUCTOS_SEMILLA_QA, USUARIOS_SEMILLA_QA
from src.auth.store import UserStore
from src.products.store import ProductStore
from src.orders.store import OrderStore
from src.ui.components.header import _crear_badge_qa


class TestQAEnvironment(unittest.TestCase):
    def setUp(self):
        self.temp_root = tempfile.TemporaryDirectory()
        self.orig_env = os.environ.get("STOCKAGENT_ENV")

    def tearDown(self):
        if self.orig_env is not None:
            os.environ["STOCKAGENT_ENV"] = self.orig_env
        elif "STOCKAGENT_ENV" in os.environ:
            del os.environ["STOCKAGENT_ENV"]

        try:
            self.temp_root.cleanup()
        except Exception:
            pass

    def test_environment_variables_switch(self):
        set_environment("production")
        self.assertFalse(is_qa_environment())
        self.assertEqual(get_environment(), "production")

        set_environment("qa")
        self.assertTrue(is_qa_environment())
        self.assertEqual(get_environment(), "qa")

    def test_get_directories_isolation(self):
        set_environment("production")
        prod_data = get_data_dir()
        self.assertTrue(str(prod_data).endswith("data"))

        set_environment("qa")
        qa_data = get_data_dir()
        self.assertTrue(str(qa_data).endswith("data_qa"))
        self.assertNotEqual(prod_data, qa_data)

        prod_desc = get_descuentos_dir()
        set_environment("production")
        prod_desc = get_descuentos_dir()
        self.assertTrue(str(prod_desc).endswith("Descuentos"))

        set_environment("qa")
        qa_desc = get_descuentos_dir()
        self.assertTrue(str(qa_desc).endswith("Descuentos_QA"))
        self.assertNotEqual(prod_desc, qa_desc)

    def test_seeder_inicializa_datos_completos_qa(self):
        with patch("src.core.environment.application_root", return_value=Path(self.temp_root.name)):
            info = inicializar_ambiente_qa(forzar_reinicio=True)

            self.assertEqual(info["ambiente"], "qa")
            data_dir = Path(info["data_dir"])
            desc_dir = Path(info["descuentos_dir"])

            self.assertTrue(data_dir.exists())
            self.assertTrue(desc_dir.exists())

            # 1. Verificar usuarios
            u_store = UserStore(data_dir / "usuarios.sqlite3")
            for u_tuple in USUARIOS_SEMILLA_QA:
                u = u_store.get_user_by_username(u_tuple[0])
                self.assertIsNotNone(u)
                self.assertEqual(u.role, u_tuple[2])

            # 2. Verificar productos
            p_store = ProductStore(data_dir / "productos.sqlite3")
            catalogo = p_store.list_products()
            self.assertGreaterEqual(len(catalogo), len(PRODUCTOS_SEMILLA_QA))
            prod_101 = p_store.get_product("101")
            self.assertIsNotNone(prod_101)
            self.assertEqual(prod_101["name"], "Proteína Whey 1kg Vainilla")

            # 3. Verificar pedidos
            o_store = OrderStore(data_dir / "pedidos.sqlite3")
            pedidos = o_store.listar_pedidos()
            self.assertGreaterEqual(len(pedidos), 1)

            planes = o_store.listar_planes_mercado_full()
            self.assertGreaterEqual(len(planes), 1)

            # 4. Verificar archivos Excel
            self.assertTrue((desc_dir / "Productos.xlsx").exists())
            self.assertTrue((desc_dir / "MercadoFull" / "Planilla_Full_QA.xlsx").exists())

    def test_badge_qa_se_muestra_solo_en_ambiente_qa(self):
        set_environment("production")
        badge_prod = _crear_badge_qa("desktop")
        self.assertIsNone(badge_prod)

        set_environment("qa")
        badge_qa = _crear_badge_qa("desktop")
        self.assertIsNotNone(badge_qa)

    def test_persistencia_archivo_env_active(self):
        with patch("src.core.environment.application_root", return_value=Path(self.temp_root.name)):
            set_environment("qa", persistir=True)
            self.assertEqual(get_environment(), "qa")
            env_file = Path(self.temp_root.name) / ".env_active"
            self.assertTrue(env_file.exists())
            self.assertEqual(env_file.read_text(encoding="utf-8").strip(), "qa")

            set_environment("production", persistir=True)
            self.assertEqual(get_environment(), "production")
            self.assertEqual(env_file.read_text(encoding="utf-8").strip(), "production")

    def test_mostrar_gestion_ambientes_permisos_y_dialogo(self):
        from src.ui.dialogs.dlg_gestion_ambientes import mostrar_gestion_ambientes

        mock_interfaz = MagicMock()
        mock_interfaz.modo_oscuro = True
        mock_interfaz.secundario = "#888888"
        mock_interfaz.texto = "#ffffff"
        mock_interfaz.ancho_adaptable.return_value = 580

        # Caso 1: Usuario no master (ej. administrador o picker) es rechazado
        mock_interfaz.exigir_roles.return_value = False
        mostrar_gestion_ambientes(mock_interfaz)
        mock_interfaz.page.show_dialog.assert_not_called()

        # Caso 2: Usuario master es permitido y muestra el diálogo
        mock_interfaz.exigir_roles.return_value = True
        mostrar_gestion_ambientes(mock_interfaz)
        mock_interfaz.page.show_dialog.assert_called_once()
        dialogo = mock_interfaz.page.show_dialog.call_args[0][0]
        self.assertIsNotNone(dialogo)


if __name__ == "__main__":
    unittest.main()
